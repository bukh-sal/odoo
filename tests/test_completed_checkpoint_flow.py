"""Actual recovery/journal/shared host flow; Docker/SQL/ACL boundaries are fake.

Real OS ownership/SQLite and actual semantic SQL have separate qualification.
These tests do not claim an installed restore or Docker command execution.
"""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT/'packages/platform_sdk'),str(ROOT)]
from modular_platform.completed_checkpoint import CompletedCheckpointRecovery
from modular_platform.checkpoint_recovery_journal import CheckpointRecoveryJournal
from modular_platform.dispatch_lifecycle import PHYSICAL_SCHEMA
from modular_platform.native_auth_recovery import public_binding
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.restore_executor import canonical_authority, EFFECTS_SELECT


def identity(number):return f'00000000-0000-4000-8000-{number:012d}'
SOURCE,RECOVERY,SITE,DEPLOY=map(identity,(400,500,20,10))
IMAGE='sha256:'+'a'*64
INVENTORY='sha256:'+'b'*64
STAMP='2026-11-13T10:00:00Z'


def protect(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=True);return path


class HeldLocks:
    def __init__(self,root,deployment,sites):
        self.locks=[SimpleNamespace(directory=root,name=name) for name in
            ['deployment-'+deployment]+['site-'+value for value in sorted(sites)]]
        self.owner=uuid4().hex;self.held=False
    def __enter__(self):self.held=True;return self
    def __exit__(self,*args):self.held=False
    def check(self):
        if not self.held:raise OperatorError('Test lock is not held')
        return [self.owner]


class Store:
    _authorize_plan=OperatorStore._authorize_plan
    _require_no_checkpoint_recovery=OperatorStore._require_no_checkpoint_recovery
    _lock_identity=OperatorStore._lock_identity
    def __init__(self,root,bundle):
        self.root=protect(root);self.source=copy.deepcopy(bundle)
        self.source_status=dict(state='completed',phase='completed',backup_id=SOURCE,traffic_resumed=True)
        self.policy=dict(allow_noninteractive=True,deployments={DEPLOY:[SITE]},policy_version=1,
            authorization_generation=1,maximum_start_lifetime=900)
    def _policy(self):return self.policy
    def _regular(self,path):
        if path.is_symlink() or not path.is_file():raise OperatorError('Regular private file required')
    def bundle(self,op):
        if op!=SOURCE:raise OperatorError('Original operation only; recovery is not an operation row')
        self._authorize_plan(self.source['plan'],generation=False)
        return copy.deepcopy(self.source)
    def status(self,op):
        self.bundle(op);return copy.deepcopy(self.source_status)


class CompletedCheckpointFlow(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.timeline=[];self.fail_command=None;self.drift_effect=False
        for module in ('completed_checkpoint','checkpoint_recovery_journal','recovery_reviews','operator_store'):
            self.stack.enter_context(patch('modular_platform.'+module+'.verify_private_directory',side_effect=lambda p:None))
        for module in ('completed_checkpoint','checkpoint_recovery_journal','recovery_reviews'):
            self.stack.enter_context(patch('modular_platform.'+module+'.protect_directory',side_effect=protect))
        for module in ('completed_checkpoint','checkpoint_recovery_journal','recovery_reviews'):
            self.stack.enter_context(patch('modular_platform.'+module+'.current_identity',return_value='fake-owned-OS-boundary'))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.OperationLocks',HeldLocks))
        self.stack.enter_context(patch('modular_platform.restore_executor.OperationLocks',HeldLocks))
        self.release1=dict(generation=1,created_at=STAMP,plugins=[],core_inventory_digest=INVENTORY)
        self.release2=self.release1|dict(generation=2)
        self.base=dict(project='mp-disposable-checkpoint-test',deployment_id=DEPLOY,image_id=IMAGE,generation=1,
            release_created_at=STAMP,sites=[dict(site_id=SITE,database='mp_disposable_r0_r1_current')],published_release=self.release1)
        self.config=self.base|dict(generation=2,worker_id='c'*64,published_release=self.release2)
        plan=dict(operation_id=SOURCE,operation_type='uninstall',deployment_id=DEPLOY,site_ids=[SITE],
            policy_version=1,operator_authorization_generation=1,destructive=True,artifacts=[dict(runtime='native')],
            created_at=STAMP,backup=dict(required=True),base_release_digest=data_digest(self.release1),target_release_digest=data_digest(self.release2))
        bundle=dict(plan=plan,plan_hash='sha256:'+'d'*64,operation_lock=dict(release=self.release2))
        self.store=Store(self.root/'control',bundle)
        self.state_by_id={'edge':True,'c'*64:True,'restored-app':False}
        self.profile=dict(profile='r1-native-dispatch-v1',external_installations=0,active_credentials=0,api_keys=0,
            uncertain_jobs=0,control=dict(state='enabled',release_digest=data_digest(self.release2)),
            release_digest=data_digest(self.release2),state_digest='before',schema_digest='schema')
        self.native=Mock();self.native.store=self.store;self.native.config=self.config
        self.native.target_path=self.root/'target.json';self.native.target_path.write_text(json.dumps(self.config))
        self.native.catalog_root=self.root/'catalog';self.native.validator=Mock()
        self.native._inspect.side_effect=lambda container:dict(State=dict(Running=self.state_by_id[container],ExitCode=0))
        self.native._child.side_effect=lambda op,label,**kw:(['docker','run',label],label)
        self.native._private_command.side_effect=self.private_command
        observer=self.native.observer
        observer._container.side_effect=lambda service,**kw:self.native.config['worker_id'] if service=='app' else service
        observer.read.return_value=dict(runtime=dict(published_release_protocol=1))
        observer.state.return_value=dict(state=dict(release_digest=data_digest(self.release2)))
        self.recovery=CompletedCheckpointRecovery(self.native);self.recovery._bind(RECOVERY,SOURCE)
        self.source_hashes={'reviewed.py':'1'*64}
        self.stack.enter_context(patch.object(self.recovery,'_source_hashes',side_effect=lambda:dict(self.source_hashes)))
        self.private_auth=dict(users=[dict(id=1,login='owner',active=True,password=None,totp_secret=None,totp_last_counter=0,groups=[])],passkeys=[])
        self.authority=canonical_authority(dict(principals=[],memberships=[],operators=[],integration_grants=[],api_key_count=0,has_dispatch_tables=True))|public_binding(self.private_auth)
        self.stack.enter_context(patch.object(self.recovery,'_authority',side_effect=lambda db:(copy.deepcopy(self.authority),self.private_auth)))
        body=dict(policy='native-checkpoint-effects-v1',site_id=SITE,
            schema_digest=data_digest({k:PHYSICAL_SCHEMA[k] for k in ('mp_dispatch_control','mp_job','mp_outbox')}),
            tables={k:dict(rows=1,sha256='e'*64) for k in ('mp_job','mp_outbox')})
        self.effects=body|dict(digest=data_digest(body))
        def effects(config):
            result=copy.deepcopy(self.effects)
            if self.drift_effect and config['sites'][0]['database']!=self.config['sites'][0]['database']:
                result['tables']['mp_job']['sha256']='f'*64
                result['digest']=data_digest({k:v for k,v in result.items() if k!='digest'})
            return result
        self.stack.enter_context(patch.object(self.recovery,'_effects',side_effect=effects))
        self.helper=Mock();self.helper.require_profile.side_effect=lambda value,**kw:copy.deepcopy(value)
        self.helper.inspect_current.side_effect=lambda **kw:copy.deepcopy(self.profile)
        self.helper.inspect.side_effect=lambda **kw:copy.deepcopy(self.profile)
        self.helper.run.side_effect=self.dispatch
        self.helper.reconcile_jobs.side_effect=lambda *args,**kw:dict(resume_allowed=True)
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.DispatchMaintenance',return_value=self.helper))
        self.stack.enter_context(patch.object(self.recovery,'_dispatch_helper',return_value=self.helper))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.snapshots',side_effect=self.snapshots))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint._run',side_effect=self.command))
        self.stack.enter_context(patch('modular_platform.restore_executor._run',side_effect=self.command))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.Catalog',return_value=Mock(snapshot=lambda:{})))
        self.stack.enter_context(patch('modular_platform.restore_executor.Catalog',return_value=Mock(snapshot=lambda:{})))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.inspect_image',return_value=dict(inventory_digest=INVENTORY)))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.runtime_inputs'))
        self.stack.enter_context(patch.object(self.recovery,'_fresh_absent',side_effect=lambda:self.timeline.append('fresh-absent')))
        self.checkpoint=protect(self.store.root/'checkpoints'/SOURCE)
        files={}
        for name in ('database.dump','database.dump.stderr.log','filestore.tar.gz','filestore.tar.gz.stderr.log'):
            raw=name.encode();(self.checkpoint/name).write_bytes(raw);files[name]=hashlib.sha256(raw).hexdigest()
        self.manifest=dict(operation_id=SOURCE,plan_hash=bundle['plan_hash'],configuration=self.base,
            previous_release=dict(release_lock=self.release1,installations=[],bindings=[]),dispatch_profile=copy.deepcopy(self.profile),files=files)
        (self.checkpoint/'manifest.json').write_text(json.dumps(self.manifest))
        stage=protect(self.store.root/'stages'/SOURCE)
        (stage/'worker-replacement.json').write_text(json.dumps(dict(container_id='c'*64,configuration=self.config,previous_image_id=IMAGE)))
        (stage/'result.json').write_text(json.dumps(dict(state='completed',release_digest=data_digest(self.release2))))
        self.original=copy.deepcopy((self.store.source,self.store.source_status))

    def snapshots(self,config):
        return [dict(container_id='c'*64,image_id=IMAGE,running=self.state_by_id['c'*64])]

    def dispatch(self,action,operation,directory,**kw):
        self.timeline.append('dispatch-'+action)
        before=copy.deepcopy(self.profile)
        self.profile['control']['state']='enabled' if action=='enable' else 'paused'
        if kw.get('configuration'):
            self.profile['release_digest']=data_digest(kw['configuration']['published_release'])
            self.profile['control']['release_digest']=self.profile['release_digest']
        self.profile['state_digest']=action+'-'+str(len(self.timeline))
        return dict(before=before,after=copy.deepcopy(self.profile))

    def command(self,args,*,input=None,**kw):
        if args[:3]==['docker','ps','-q']:return b''
        if 'psql' in args:
            if input and input.startswith(b'SELECT count(*)'):return b'0\n'
            if input==EFFECTS_SELECT.encode():
                return json.dumps(dict(job_table=True,outbox_table=True,api_key_count=0,active_technical_credentials=0,external_installations=0)).encode()
            self.timeline.append('authority-overlay');return b''
        if args[:2]==['docker','stop']:
            self.timeline.append('stop-'+args[-1]);self.state_by_id[args[-1]]=False;return b''
        if args[:2]==['docker','start']:
            self.timeline.append('start-'+args[-1]);self.state_by_id[args[-1]]=True;return b''
        if 'createdb' in args or 'pg_restore' in args:
            action='createdb' if 'createdb' in args else 'pg_restore';self.timeline.append(action)
            if self.fail_command==action:raise OperatorError('Lost command response')
            return b''
        if args[:2]==['docker','run']:
            if 'read-config' in str(args):
                return ('[options]\ndb_name='+self.config['sites'][0]['database']+'\nmax_cron_threads=0\n').encode()
            self.timeline.append('config-write');return b''
        if args[:3]==['docker','exec','restored-app']:
            self.timeline.append('readiness');return b''
        raise AssertionError('Unrecognized fake Docker boundary: '+str(args[:5]))

    def private_command(self,args,path,**kw):
        self.timeline.append('filestore-load')
        Path(path).write_bytes(b'')

    def decide(self):
        return RecoveryReviews(self.store).issue(self.recovery._restore_state(RECOVERY))

    def execute(self,decision=None):
        decision=decision or self.decide()
        return self.recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True)

    def prepare_shared_completion(self):
        def observer(configuration,**kw):
            result=Mock();result.read.return_value=dict(runtime=dict(published_release_protocol=1))
            result.state.return_value=dict(state=dict(release_lock=configuration['published_release'],installations=[],bindings=[]))
            return result
        self.stack.enter_context(patch.object(self.recovery,'_recovery_observer',side_effect=observer))
        self.stack.enter_context(patch('modular_platform.restore_executor.ensure',side_effect=lambda *a,**kw:self.timeline.append('create-worker') or 'restored-app'))
        self.stack.enter_context(patch('modular_platform.restore_executor.wait_ready',side_effect=lambda *a:self.timeline.append('wait-ready')))
        self.stack.enter_context(patch('modular_platform.profile_channel.publish_profile',return_value=dict(state='published')))
        self.native._prepare_assets.return_value=None

    def test_actual_execute_shared_completion_and_original_history_unchanged(self):
        self.prepare_shared_completion();result=self.execute()
        self.assertEqual(result['state'],'restored_verified')
        state=self.recovery._journal.status();self.assertEqual(state['phase'],'restore_verified');self.assertIsNone(state['pending'])
        for first,second in [('stop-edge','dispatch-fence'),('dispatch-fence','stop-'+'c'*64),('stop-'+'c'*64,'createdb'),
                ('createdb','pg_restore'),('pg_restore','filestore-load'),('filestore-load','authority-overlay'),('authority-overlay','create-worker'),('create-worker','start-restored-app')]:
            self.assertLess(self.timeline.index(first),self.timeline.index(second))
        self.assertEqual(self.original,(self.store.source,self.store.source_status))
        self.assertFalse(self.state_by_id['edge']);self.assertTrue(self.state_by_id['restored-app'])
        self.assertTrue((state['binding']['decision']['fresh_database']).endswith(RECOVERY.replace('-','')))
        self.assertTrue((self.recovery._journal.root/'restored-effect-proof.json').is_file())
        self.assertEqual(json.loads(self.native.target_path.read_text())['worker_id'],'restored-app')
        with self.assertRaisesRegex(OperatorError,'active or uncertain'):
            self.store._authorize_plan(self.store.source['plan'])

    def test_effect_drift_refuses_before_registry_config_or_worker(self):
        self.prepare_shared_completion();self.drift_effect=True
        with self.assertRaisesRegex(OperatorError,'semantic effects differ'):self.execute()
        self.assertIn('authority-overlay',self.timeline);self.assertNotIn('create-worker',self.timeline)
        self.assertNotIn('config-write',self.timeline);self.assertNotIn('start-restored-app',self.timeline)
        self.assertEqual(self.recovery._journal.status()['pending']['step'],'restore_verified')

    def test_lost_createdb_response_is_pending_and_never_replayed(self):
        self.fail_command='createdb'
        with self.assertRaisesRegex(OperatorError,'Lost command'):self.execute()
        self.assertEqual(self.recovery._journal.status()['pending']['step'],'target_created')
        self.assertTrue(self.recovery.status(RECOVERY)['activity_reconciliation_required'])
        before=list(self.timeline)
        with self.assertRaisesRegex(OperatorError,'precreation boundary'):self.recovery.prepare_continue(RECOVERY)
        self.assertEqual(self.timeline,before);self.assertEqual(self.timeline.count('createdb'),1)

    def test_precreation_stop_fresh_continue_no_refence_or_redrain(self):
        decision=self.decide()
        with patch.object(self.recovery,'_restore_from_quiesced',side_effect=OperatorError('Controlled precreation stop')):
            with self.assertRaisesRegex(OperatorError,'precreation stop'):self.execute(decision)
        self.assertEqual(self.recovery._journal.status()['phase'],'source_verified')
        self.assertNotIn('createdb',self.timeline)
        # A fresh review explicitly binds changed reviewed host source and old receipts.
        self.source_hashes['reviewed.py']='2'*64
        continued=self.recovery.prepare_continue(RECOVERY)
        self.assertNotEqual(continued['review']['review_id'],decision['review']['review_id'])
        self.prepare_shared_completion()
        result=self.recovery.continue_restore(continued,exact_hash=data_digest(continued),noninteractive=True)
        self.assertEqual(result['state'],'restored_verified')
        self.assertEqual(self.timeline.count('stop-edge'),1);self.assertEqual(self.timeline.count('dispatch-fence'),2)
        self.assertEqual(self.timeline.count('createdb'),1);self.assertEqual(self.timeline.count('pg_restore'),1)

    def test_revoked_review_and_changed_current_payload_refuse_before_journal(self):
        decision=self.decide();RecoveryReviews(self.store).revoke(decision,exact_hash=data_digest(decision))
        with self.assertRaisesRegex(OperatorError,'revoked'):self.execute(decision)
        self.assertFalse(self.recovery._journal.root.exists())
        decision=self.decide();self.authority['api_key_count']=1
        with self.assertRaisesRegex(OperatorError,'API key'):self.execute(decision)
        self.assertFalse(self.recovery._journal.root.exists());self.assertNotIn('stop-edge',self.timeline)

    def test_initial_source_drift_refuses_before_mutation(self):
        decision=self.decide();self.source_hashes['reviewed.py']='3'*64
        with self.assertRaisesRegex(OperatorError,'actual state changed'):self.execute(decision)
        self.assertFalse(self.recovery._journal.root.exists());self.assertNotIn('stop-edge',self.timeline)

    def test_existing_unfinished_recovery_blocks_even_a_new_prepare(self):
        with patch.object(self.recovery,'_restore_from_quiesced',side_effect=OperatorError('Stopped')):
            with self.assertRaises(OperatorError):self.execute()
        with self.assertRaisesRegex(OperatorError,'active or uncertain'):self.recovery.prepare(SOURCE)

    def restored(self):
        self.prepare_shared_completion();self.execute()
        self.native.config=json.loads(self.native.target_path.read_text())
        self.recovery.config=self.native.config
        return self.recovery.prepare_resume(RECOVERY)

    def test_actual_shared_resume_activates_inside_locks_and_preserves_completed_source(self):
        decision=self.restored();digest=data_digest(decision)
        self.assertFalse(self.state_by_id['edge'])
        result=self.recovery.resume(decision,exact_hash=digest,noninteractive=True)
        self.assertEqual(result['original_plan_state'],'completed')
        self.assertEqual(self.recovery._journal.status()['phase'],'resumed')
        self.assertLess(self.timeline.index('readiness'),self.timeline.index('dispatch-enable'))
        self.assertLess(self.timeline.index('dispatch-enable'),self.timeline.index('start-edge'))
        self.assertEqual(self.original,(self.store.source,self.store.source_status))
        self.store._authorize_plan(self.store.source['plan'])
        before=list(self.timeline)
        with self.assertRaises(OperatorError):self.recovery.resume(decision,exact_hash=digest,noninteractive=True)
        self.assertEqual(self.timeline,before)

    def test_readiness_authority_drift_refuses_before_resume_fence_enable_or_traffic(self):
        decision=self.restored();original=self.command
        def change(args,**kw):
            result=original(args,**kw)
            if args[:3]==['docker','exec','restored-app']:self.authority['api_key_count']=1
            return result
        with patch('modular_platform.restore_executor._run',side_effect=change):
            with self.assertRaisesRegex(OperatorError,'changed before traffic resume'):
                self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertNotIn('dispatch-enable',self.timeline);self.assertNotIn('start-edge',self.timeline)
        self.assertEqual(self.recovery._journal.status()['phase'],'restore_verified')

    def test_lost_enable_response_stays_uncertain_and_blocks_forward_or_second_resume(self):
        decision=self.restored();original=self.dispatch
        def enable(*args,**kw):
            result=original(*args,**kw)
            if args[0]=='enable':raise OperatorError('Lost enable response')
            return result
        self.helper.run.side_effect=enable
        with self.assertRaisesRegex(OperatorError,'Lost enable'):
            self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        state=self.recovery._journal.status()
        self.assertEqual(state['phase'],'resume_started');self.assertEqual(state['pending']['step'],'resumed')
        self.assertTrue(self.recovery.status(RECOVERY)['activity_reconciliation_required'])
        self.assertNotIn('start-edge',self.timeline)
        with self.assertRaisesRegex(OperatorError,'active or uncertain'):self.store._authorize_plan(self.store.source['plan'])
        before=list(self.timeline)
        with self.assertRaises(OperatorError):self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.timeline,before)

    def test_verified_result_tamper_refuses_resume_review(self):
        self.restored();path=self.recovery._journal.root/'result.json'
        result=json.loads(path.read_text());result['state']='fabricated';path.write_text(json.dumps(result))
        with self.assertRaisesRegex(OperatorError,'immutable completion'):self.recovery.prepare_resume(RECOVERY)

    def test_pending_or_missing_binding_fences_forward_without_rewriting_source(self):
        root=protect(self.store.root/'checkpoint-restores'/RECOVERY)
        protect(root/'journal')
        with self.assertRaises(OperatorError):self.store._authorize_plan(self.store.source['plan'])
        self.assertEqual(self.original,(self.store.source,self.store.source_status))

    def test_foreign_deployment_is_not_blocked_by_a_valid_unrelated_journal(self):
        with patch.object(self.recovery,'_restore_from_quiesced',side_effect=OperatorError('Stopped')):
            with self.assertRaises(OperatorError):self.execute()
        unrelated=self.store.source['plan']|dict(deployment_id=identity(11),site_ids=[identity(21)])
        self.store.policy['deployments'][identity(11)]=[identity(21)]
        self.store._authorize_plan(unrelated)

    def test_coherently_rehashed_activity_drift_invalidates_continuation_review(self):
        with patch.object(self.recovery,'_restore_from_quiesced',side_effect=OperatorError('Stopped')):
            with self.assertRaises(OperatorError):self.execute()
        decision=self.recovery.prepare_continue(RECOVERY)
        activity=next((self.recovery._journal.root/'activities').glob('*/*.intent.json'))
        value=json.loads(activity.read_text());value['details']['unreviewed']='changed'
        activity.write_text(json.dumps(value))
        completion=activity.with_name(activity.name.replace('.intent.json','.complete.json'))
        result=json.loads(completion.read_text());result['intent_sha256']=hashlib.sha256(activity.read_bytes()).hexdigest()
        completion.write_text(json.dumps(result))
        with self.assertRaisesRegex(OperatorError,'actual state changed'):
            self.recovery.continue_restore(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertNotIn('createdb',self.timeline)

    def test_noninteractive_policy_refuses_before_journal_or_stop(self):
        decision=self.decide();self.store.policy['allow_noninteractive']=False
        with self.assertRaisesRegex(OperatorError,'Noninteractive recovery'):self.execute(decision)
        self.assertNotIn('stop-edge',self.timeline);self.assertFalse(self.recovery._journal.root.exists())

    def test_checkpoint_and_current_replacement_drift_refuse_without_new_review(self):
        decision=self.decide();(self.checkpoint/'database.dump').write_bytes(b'changed')
        with self.assertRaisesRegex(OperatorError,'hash mismatch'):self.execute(decision)
        self.assertNotIn('stop-edge',self.timeline)

    def test_original_completed_state_changed_cannot_be_hidden_by_recovery_journal(self):
        with patch.object(self.recovery,'_restore_from_quiesced',side_effect=OperatorError('Stopped')):
            with self.assertRaises(OperatorError):self.execute()
        self.store.source_status['traffic_resumed']=False
        with self.assertRaisesRegex(OperatorError,'immutable completed'):self.recovery.status(RECOVERY)

    def test_source_revocation_after_command_leaves_activity_uncertain(self):
        decision=self.decide();original=self.command
        def revoke(args,**kwargs):
            result=original(args,**kwargs)
            if args[:2]==['docker','stop']:
                RecoveryReviews(self.store).revoke(decision,exact_hash=data_digest(decision))
            return result
        with patch('modular_platform.completed_checkpoint._run',side_effect=revoke):
            with self.assertRaisesRegex(OperatorError,'revoked'):self.execute(decision)
        self.assertFalse(self.state_by_id['edge']);self.assertNotIn('dispatch-fence',self.timeline)
        self.assertEqual(self.recovery._journal.status()['pending']['step'],'traffic_closed')
        self.assertTrue(self.recovery.status(RECOVERY)['activity_reconciliation_required'])

    def test_protected_target_change_after_resume_review_refuses_before_readiness(self):
        decision=self.restored();target=json.loads(self.native.target_path.read_text())
        target['generation']+=1;self.native.target_path.write_text(json.dumps(target))
        with self.assertRaisesRegex(OperatorError,'current target changed'):
            self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertNotIn('readiness',self.timeline);self.assertNotIn('dispatch-enable',self.timeline)


if __name__=='__main__':unittest.main()
