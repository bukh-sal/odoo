"""Actual late continuation flow, with only Docker/SQL/ACL boundaries faked.

The original dump/extraction/authority activities must never execute twice.
These tests are host-flow evidence, not installed database qualification.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(ROOT)]
import test_completed_checkpoint_flow as fixture
from test_completed_checkpoint_flow import RECOVERY, SOURCE, IMAGE
from modular_platform import completed_checkpoint as module
from modular_platform.dispatch_operator import BOOTSTRAP, DispatchMaintenance
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.restore_executor import restored_fence_correlation


class LateContinuation(unittest.TestCase):
    def setUp(self):
        self.b=fixture.CompletedCheckpointFlow('test_actual_execute_shared_completion_and_original_history_unchanged')
        self.b.setUp();self.addCleanup(self.b.doCleanups)

    def partial(self):
        b=self.b;r=b.recovery
        # A real archive, immutable manifest and actual seven-step journal.
        b.manifest['dispatch_profile']['control']['state']='paused'
        with tarfile.open(b.checkpoint/'filestore.tar.gz','w:gz') as archive:
            entry=tarfile.TarInfo('filestore/'+b.config['sites'][0]['database']+'/aa/blob')
            entry.size=4;archive.addfile(entry,io.BytesIO(b'body'))
        b.manifest['files']['filestore.tar.gz']=hashlib.sha256((b.checkpoint/'filestore.tar.gz').read_bytes()).hexdigest()
        (b.checkpoint/'manifest.json').write_text(json.dumps(b.manifest))
        b.prepare_shared_completion()
        real_child=b.native._child.side_effect
        b.native._child.side_effect=lambda op,label,**kw: (['docker','run',label],b.config['project']+'-op-'+op+'-'+label)
        b.native._private_command.side_effect=lambda args,path,**kw:(Path(path).write_text('{"filestore_restored":true}'),
            Path(str(path)+'.stderr.log').write_bytes(b''),b.timeline.append('filestore-load'))[-1]
        self.source_child=None;self.decision=None;self.fail_restored=True
        module.DispatchMaintenance._suffix.side_effect=DispatchMaintenance._suffix
        def dispatch(action,op,directory,**kw):
            directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
            restored=bool(kw.get('configuration'));config=kw.get('configuration') or b.config
            request=dict(action=action,database=config['sites'][0]['database'],site_id=config['sites'][0]['site_id'],
                release_digest=kw['release_digest'],control_release=kw.get('control_release'),operation_id=op,
                expected_digest=None,image_id=config['image_id'],helper_sha256='h'*64,authority_sha256='a'*64,script_sha256='s'*64)
            (directory/(action+'-request.json')).write_text(json.dumps(request))
            if restored and self.fail_restored:
                self.fail_restored=False
                (directory/'fence.stdout').write_bytes(b'')
                (directory/'fence.stdout.stderr.log').write_text('docker: Error response from daemon: Conflict. The container name "/'+self.source_child['Name'][1:]+'" is already in use by container "'+self.source_child['Id']+'". You have to remove (or rename) that container to be able to reuse that name.\n\nRun \'docker run --help\' for more information\n')
                raise OperatorError('Observed source/target name conflict')
            result=b.dispatch(action,op,directory,**kw)
            name=b.native._child(op,DispatchMaintenance._suffix(action,kw.get('review_id')))[1]
            (directory/(action+'.stdout')).write_text(json.dumps(dict(action=action,result=result)))
            (directory/(action+'.stdout.stderr.log')).write_bytes(b'')
            (directory/(action+'.json')).write_text(json.dumps(dict(child=name,action=action,result=result)))
            if not restored and action=='fence':
                project=b.config['project']
                self.source_child=dict(Id='f'*64,Name='/'+name,Image=IMAGE,State=dict(Running=False,ExitCode=0),
                    Config=dict(Entrypoint=['/venv/bin/python'],Cmd=['-c',BOOTSTRAP],User='10001:10001',
                        Labels={'com.modular.operation':RECOVERY,'com.modular.deployment':b.config['deployment_id']}),
                    HostConfig=dict(ReadonlyRootfs=True,Privileged=False,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],NetworkMode=project+'_runtime'),
                    NetworkSettings=dict(Networks={project+'_runtime':{}}),
                    Mounts=[dict(Type='volume',Name=project+'_appconfig',Destination='/run/secrets',RW=False),
                            dict(Type='volume',Name=project+'_filestore',Destination='/var/lib/modular',RW=False)])
            return result
        b.helper.run.side_effect=dispatch
        inspect=b.native._inspect.side_effect
        b.native._inspect.side_effect=lambda name:copy.deepcopy(self.source_child) if self.source_child and name==self.source_child['Name'][1:] else inspect(name)
        self.decision=b.decide()
        with self.assertRaisesRegex(OperatorError,'name conflict'):b.execute(self.decision)
        self.old_journal={p.name:p.read_bytes() for p in (r._journal.root/'journal').iterdir()}
        self.old_diagnostics=r._fence_diagnostics()
        self.old_intent=(r._journal.root/'activities'/self.decision['review']['review_id']/'restored-dispatch-fence.intent.json').read_bytes()
        b.helper.inspect_current.side_effect=lambda **kw:copy.deepcopy(b.manifest['dispatch_profile']|dict(release_digest=data_digest(self.decision['restored_release_lock']))) if kw.get('configuration') else copy.deepcopy(b.profile)
        b.stack.enter_context(patch.object(r,'_inspection',return_value=json.dumps({'aa/blob':hashlib.sha256(b'body').hexdigest()}).encode()))
        command=b.command
        def run(args,**kw):
            if 'pg_dump' in args:return b'-- arbitrary comment\nCREATE TABLE example();\n'
            return command(args,**kw)
        b.stack.enter_context(patch('modular_platform.completed_checkpoint._run',side_effect=run))
        b.stack.enter_context(patch('modular_platform.completed_checkpoint.subprocess.Popen',side_effect=lambda *a,**kw:DumpProcess()))
        b.source_hashes['reviewed.py']='2'*64
        return r

    def test_real_late_state_continue_shared_complete_no_dump_or_auth_replay(self):
        r=self.partial();b=self.b
        continued=r.prepare_continue(RECOVERY)
        self.assertEqual(continued['continuation']['reason'],'retained_source_fence_name_collision')
        self.assertNotEqual(continued['review']['review_id'],self.decision['review']['review_id'])
        before=list(b.timeline)
        result=r.continue_restore(continued,exact_hash=data_digest(continued),noninteractive=True)
        self.assertEqual(result['state'],'restored_verified')
        for command in ('createdb','pg_restore','filestore-load','authority-overlay'):
            self.assertEqual(b.timeline.count(command),before.count(command),command)
        for name,raw in self.old_journal.items():self.assertEqual((r._journal.root/'journal'/name).read_bytes(),raw)
        self.assertEqual(r._fence_diagnostics(),self.old_diagnostics)
        self.assertEqual((r._journal.root/'activities'/self.decision['review']['review_id']/'restored-dispatch-fence.intent.json').read_bytes(),self.old_intent)
        status=r._journal.status();self.assertEqual(status['phase'],'restore_verified');self.assertIsNone(status['pending'])
        self.assertIn('pending_adoption_digest',status['completed'][7]['completion']['details'])
        self.assertTrue(r._require_complete_activities())
        self.assertEqual(b.original,(b.store.source,b.store.source_status))
        # Later revocation cannot erase immutable completion evidence.
        RecoveryReviews(b.store).revoke(continued,exact_hash=data_digest(continued))
        self.assertEqual(r._journal.status()['phase'],'restore_verified')

    def test_actual_physical_diagnostic_and_activity_counterexamples_refuse(self):
        r=self.partial();root=r._journal.root
        cases=[(root/'dispatch-fence/fence.stdout',b'{"uncertain":true}'),
               (root/'dispatch-fence/fence.json',b'{}'),
               (root/'dispatch-fence/fence.stdout.stderr.log',b'permission denied'),
               (root/'previous-odoo.conf',b'unexpected later publication'),
               (root/'source-dispatch-fence/fence.stdout',b'{}')]
        for path,raw in cases:
            with self.subTest(path=path.name):
                old=path.read_bytes() if path.exists() else None;path.write_bytes(raw)
                with self.assertRaises(OperatorError):r.prepare_continue(RECOVERY)
                if old is None:path.unlink()
                else:path.write_bytes(old)
        self.source_child['State']['Running']=True
        with self.assertRaisesRegex(OperatorError,'source fence child'):r.prepare_continue(RECOVERY)
        self.source_child['State']['Running']=False
        self.b.drift_effect=True
        with self.assertRaisesRegex(OperatorError,'semantic effects differ'):r.prepare_continue(RECOVERY)
        self.assertEqual(self.b.timeline.count('createdb'),1)

    def test_rehashed_db_or_source_drift_invalidates_fresh_review_before_adoption(self):
        r=self.partial();decision=r.prepare_continue(RECOVERY)
        self.b.source_hashes['reviewed.py']='3'*64
        before=list(self.b.timeline)
        with self.assertRaisesRegex(OperatorError,'actual state changed'):
            r.continue_restore(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.b.timeline,before)
        self.assertFalse((r._journal.root/'adoptions').exists())
        self.assertFalse((r._journal.root/'continuations').exists())

    def test_unknown_journal_boundary_and_activity_never_adopted(self):
        r=self.partial();root=r._journal.root
        extra=root/'activities'/self.decision['review']['review_id']/'unknown.intent.json';extra.write_text('{}')
        with self.assertRaises(OperatorError):r.prepare_continue(RECOVERY)
        extra.unlink()
        original=r._journal.status
        wrong=dict(original(),pending=dict(step='checkpoint_loaded',intent={}))
        with self.assertRaises(OperatorError):r._unstarted_restored_fence_state(wrong)

    def test_current_authority_filestore_dispatch_and_database_drift_refuse(self):
        r=self.partial();b=self.b
        decision=r.prepare_continue(RECOVERY)
        authority=r._authority.side_effect
        def changed(db):
            value,private=authority(db);value['memberships']=[{'unexpected':'drift'}];return value,private
        with patch.object(r,'_authority',side_effect=changed):
            with self.assertRaisesRegex(OperatorError,'source authority'):r.prepare_continue(RECOVERY)
        with patch.object(r,'_inspection',return_value=b'{"aa/blob":"wrong"}'):
            with self.assertRaisesRegex(OperatorError,'filestore differs'):r.prepare_continue(RECOVERY)
        with patch('modular_platform.completed_checkpoint.subprocess.Popen',return_value=DumpProcess(b'CREATE TABLE changed();')):
            with self.assertRaisesRegex(OperatorError,'actual state changed'):
                r.continue_restore(decision,exact_hash=data_digest(decision),noninteractive=True)
        inspected=b.helper.inspect_current.side_effect
        def dispatch(**kw):
            value=inspected(**kw)
            if kw.get('configuration'):value['control']['state']='enabled'
            return value
        with patch.object(b.helper,'inspect_current',side_effect=dispatch):
            with self.assertRaisesRegex(OperatorError,'untouched checkpoint'):r.prepare_continue(RECOVERY)
        self.assertFalse((r._journal.root/'adoptions').exists())

    def test_resolution_and_adoption_are_bound_to_exact_fresh_review(self):
        r=self.partial();b=self.b;decision=r.prepare_continue(RECOVERY)
        r.continue_restore(decision,exact_hash=data_digest(decision),noninteractive=True)
        review=decision['review']['review_id']
        paths=[r._journal.root/'adoptions'/(review+'.json'),
            r._journal.root/'activities'/self.decision['review']['review_id']/'restored-dispatch-fence.resolution.json']
        for path in paths:
            old=path.read_bytes();value=json.loads(old);value['review_id']=RECOVERY;path.write_text(json.dumps(value))
            with self.subTest(path=path.name):
                with self.assertRaises((OperatorError,FileNotFoundError)):
                    r._journal.status() if path.parent.name=='adoptions' else r._require_complete_activities()
            path.write_bytes(old)
        self.assertEqual(b.original,(b.store.source,b.store.source_status))

    def test_streamed_dump_matches_canonical_and_checks_failure_and_size(self):
        from modular_platform.restore_continuation import canonical_dump_digest
        r=self.b.recovery
        raw=b'-- comment\n\\restrict random\nCREATE TABLE example();\n'+b'x'*(17*1024*1024)+b'\n\\unrestrict random\n'
        with patch('modular_platform.completed_checkpoint.subprocess.Popen',return_value=DumpProcess(raw)) as child:
            self.assertEqual(r._restored_database_digest('db',r._fresh_database()),canonical_dump_digest(raw))
            self.assertEqual(child.call_args.args[0][:4],['docker','exec','db','pg_dump'])
        failed=DumpProcess(b'partial',code=1)
        with patch('modular_platform.completed_checkpoint.subprocess.Popen',return_value=failed):
            with self.assertRaisesRegex(OperatorError,'failed or exceeded'):r._restored_database_digest('db',r._fresh_database())
        huge=DumpProcess();huge.stdout=OversizedLine()
        with patch('modular_platform.completed_checkpoint.subprocess.Popen',return_value=huge):
            with self.assertRaisesRegex(OperatorError,'128MiB'):r._restored_database_digest('db',r._fresh_database())
        self.assertTrue(huge.killed)

    def test_role_specific_correlation_keeps_parent_and_source_names(self):
        review='767902d7-6437-4444-8278-a6854744a373';database='mp_disposable_checkpoint'
        child=restored_fence_correlation(review,database)
        self.assertEqual(child,restored_fence_correlation(review,database))
        self.assertNotEqual(DispatchMaintenance._suffix('fence',review),DispatchMaintenance._suffix('fence',child))
        self.assertNotEqual(child,restored_fence_correlation(review,database+'other'))
        for invalid in ('../path','not-a-review',None):
            with self.assertRaises((OperatorError,ValueError,TypeError,AttributeError)):
                restored_fence_correlation(invalid,database)


class DumpProcess:
    def __init__(self,raw=b'-- arbitrary comment\nCREATE TABLE example();\n',code=0):
        self.stdout=io.BytesIO(raw);self.code=code;self.killed=False
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def kill(self):self.killed=True
    def wait(self):return self.code


class OversizedLine:
    def readline(self,size):return b'x'*size


if __name__=='__main__':unittest.main()
