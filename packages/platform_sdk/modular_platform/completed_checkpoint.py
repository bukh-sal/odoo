"""Reviewed completed-uninstall checkpoint clone with independent recovery identity.

Only the exact current completed native uninstall is eligible initially. Original
operation authority/history is never rewritten. External side effects are not
undone; trusted native source must be reviewed for this bounded effect model.
"""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from threading import Timer
from uuid import uuid4

from .catalog import Catalog
from .checkpoint_effects import require_same_effects, validate_footprint
from .checkpoint_recovery_journal import CheckpointRecoveryJournal, canonical_id
from .contracts import load_json
from .deployment import inspect_image, _run
from .dispatch_operator import BOOTSTRAP, DispatchMaintenance
from .integration_grant_recovery import PROOF_NAME, grant_proof, reconciled_authority
from .native_auth_recovery import overlay_sql
from .operator_os import OperatorError, OperationLocks, current_identity, protect_directory, verify_private_directory
from .operator_store import _write_new
from .plans import data_digest
from .projection import runtime_inputs
from .recovery_reviews import RecoveryReviews
from .restore_executor import RestoreExecutor, recovery_configuration, authority_sql, restored_release_sql, EXTRACT_FILESTORE
from .restore_continuation import FILE_OBSERVATION
from .workers import snapshots


EFFECT_READER = """import configparser,json,psycopg2,sys,types
sources=json.loads(sys.stdin.buffer.read())
for name in ('dispatch_lifecycle','checkpoint_effects'):
 module=types.ModuleType('modular_platform.'+name)
 module.__package__='modular_platform'
 sys.modules[module.__name__]=module
 exec(compile(sources[name],'<reviewed-'+name+'>','exec'),module.__dict__)
from modular_platform.dispatch_lifecycle import LifecycleScope
from modular_platform.checkpoint_effects import observe_effects
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port',5432),user=options['db_user'],password=options['db_password'],dbname=sys.argv[1],connect_timeout=5)
try:
 connection.set_session(readonly=True,isolation_level='REPEATABLE READ')
 with connection.cursor() as cr:
  cr.execute("SET LOCAL statement_timeout='30000ms'")
  value=observe_effects(cr,LifecycleScope(sys.argv[2],sys.argv[3],sys.argv[4]))
  print(json.dumps(value,sort_keys=True))
finally:
 connection.rollback();connection.close()
"""


class CompletedCheckpointRecovery(RestoreExecutor):
    def __init__(self, native):
        super().__init__(native)
        self._source_operation = None
        self._journal = None
        self._active_decision = None
        self._active_hash = None
        self._active_locks = None

    def _bind(self, recovery, source):
        recovery, source = canonical_id(recovery), canonical_id(source)
        if recovery == source:
            raise OperatorError('A new checkpoint recovery identity is required')
        self._operation, self._source_operation = recovery, source
        self._journal = CheckpointRecoveryJournal(self.store, recovery)

    def _load(self, recovery):
        journal = CheckpointRecoveryJournal(self.store, recovery)
        state = journal.status()
        self._bind(recovery, state['checkpoint_operation_id'])
        return state

    def _bundle(self, operation):
        if operation != self._operation or self._source_operation is None:
            raise OperatorError('An exact completed-checkpoint source binding is required')
        return self.store.bundle(self._source_operation)

    def _checkpoint_directory(self, operation):
        self._bundle(operation)
        return self.store.root/'checkpoints'/self._source_operation

    def _recovery_directory(self, operation):
        if self._journal is None or operation != self._operation:
            raise OperatorError('Recovery identity is not bound')
        return self._journal.root

    def _operation_status(self, operation):
        if operation != self._operation:
            raise OperatorError('Recovery identity mismatch')
        state = self._journal.status()
        return dict(state='checkpoint_recovery',phase=state['phase'],pending=state['pending'],
                    original_operation_state='completed',traffic_resumed=state['phase']=='resumed')

    def _authorize_recovery_plan(self, plan):
        # Historical approval is not reused. Current review/policy generations
        # and current OS allowlist independently authorize this new action.
        self.store._authorize_plan(plan, generation=False)

    def _ready_to_resume(self, status):
        return status['state']=='checkpoint_recovery' and status['phase']=='restore_verified' and status['pending'] is None

    def _original_plan_state(self):
        return 'completed'

    def _supported_profiles(self):
        return {'r1-native-dispatch-v1'}

    def _source_hashes(self):
        package = Path(__file__).parent
        result = {}
        for path in sorted(package.glob('*.py')):
            if path.is_symlink() or not path.is_file():
                raise OperatorError('Regular reviewed host recovery source required')
            result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        cli = package.parents[2]/'tools/modular.py'
        result['tools/modular.py'] = hashlib.sha256(cli.read_bytes()).hexdigest()
        return result

    def _source_binding(self):
        bundle, status = self._journal._source(self._source_operation)
        return dict(checkpoint_operation_id=self._source_operation,plan_hash=bundle['plan_hash'],
                    source_bundle_digest=data_digest(bundle),source_operation_digest=data_digest(status))

    def _fresh_database(self):
        return 'mp_disposable_r0_r1_checkpoint_'+self._operation.replace('-','')

    def _checkpoint(self):
        bundle, status = self._journal._source(self._source_operation)
        if (bundle['plan']['operation_type'] != 'uninstall' or not bundle['plan']['destructive']
                or any(a['runtime']!='native' for a in bundle['plan']['artifacts'])
                or any(p['runtime']!='native' for p in bundle['operation_lock']['release']['plugins'])):
            raise OperatorError('Completed checkpoint profile currently requires an exact native destructive uninstall')
        checkpoint = self._checkpoint_directory(self._operation)
        verify_private_directory(checkpoint)
        self.store._regular(checkpoint/'manifest.json')
        manifest = load_json((checkpoint/'manifest.json').read_bytes())
        if (manifest['operation_id'] != self._source_operation or manifest['plan_hash'] != bundle['plan_hash']
                or data_digest(manifest['previous_release']['release_lock']) != bundle['plan']['base_release_digest']
                or (manifest.get('dispatch_profile') or {}).get('profile') != 'r1-native-dispatch-v1'
                or manifest.get('reference_policy') is not None or manifest.get('recurrence_policy') is not None):
            raise OperatorError('Exact coordinated native checkpoint and supported effect profile required')
        names = {'database.dump','database.dump.stderr.log','filestore.tar.gz','filestore.tar.gz.stderr.log'}
        if set(manifest['files']) != names:
            raise OperatorError('Exact coordinated checkpoint members are required')
        for name, digest in manifest['files'].items():
            self.store._regular(checkpoint/name)
            if hashlib.sha256((checkpoint/name).read_bytes()).hexdigest() != digest:
                raise OperatorError('Coordinated checkpoint hash mismatch')
        return bundle, status, manifest

    def _effects(self, configuration):
        if (configuration['project'] != self.config['project'] or configuration['deployment_id'] != self.config['deployment_id']
                or len(configuration['sites']) != 1 or configuration['sites'][0]['site_id'] != self.config['sites'][0]['site_id']
                or configuration['sites'][0]['database'] not in {self.config['sites'][0]['database'], self._fresh_database()}):
            raise OperatorError('Exact independently bound source or fresh recovery database required')
        runtime = inspect_image(configuration['image_id'])
        package = Path(__file__).parent
        # Runtime imports are fixed infrastructure, not restored addon imports.
        for name in ('durable.py','plans.py','dispatch_operator.py','operator_os.py','contracts.py'):
            path = 'packages/platform_sdk/modular_platform/'+name
            if runtime['inventory']['files'].get(path) != hashlib.sha256((package/name).read_bytes()).hexdigest():
                raise OperatorError('Retained effect-reader infrastructure differs from reviewed host source')
        helper = DispatchMaintenance(self.native)
        observed = helper.require_profile(helper.inspect_current(configuration=configuration))
        sources = {name:(package/(name+'.py')).read_text(encoding='utf8') for name in ('dispatch_lifecycle','checkpoint_effects')}
        value = load_json(self._inspection('effects',configuration,EFFECT_READER,
            [configuration['sites'][0]['database'],configuration['sites'][0]['site_id'],observed['release_digest'],observed['control']['release_digest']],
            input=json.dumps(sources).encode()))
        validate_footprint(value)
        return value

    def _fresh_absent(self):
        database = self.observer._container('db')
        fresh = self._fresh_database()
        raw = _run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],
            input=("SELECT count(*) FROM pg_database WHERE datname='"+fresh+"';").encode())
        if raw.strip() != b'0':
            raise OperatorError('Fresh checkpoint database already exists; inspect without replay')
        code="from pathlib import Path;import sys;p=Path('/var/lib/modular/filestore')/sys.argv[1];assert not p.exists() and not p.is_symlink(),'Fresh filestore already exists'"
        self._inspection('absence',self.config,code,[fresh],network=False)

    def _inspection(self,label,configuration,script,arguments,*,input=None,network=True):
        root=protect_directory(self.store.root/'checkpoint-inspections')
        root=protect_directory(root/self._operation)
        directory=protect_directory(root/uuid4().hex)
        args,child=self.native._child(self._operation,'checkpoint-'+label+'-'+directory.name,
            network=network,image_id=configuration['image_id'])
        if input is not None:args.insert(2,'-i')
        _write_new(directory/'request.json',dict(child=child,configuration_digest=data_digest(configuration),
            image_id=configuration['image_id'],script_sha256=hashlib.sha256(script.encode()).hexdigest(),
            arguments=arguments,input_sha256=hashlib.sha256(input or b'').hexdigest(),read_only=True))
        self.native._private_command(args+['-c',script,*arguments],directory/'inspect.stdout',input=input,timeout=60)
        value=(directory/'inspect.stdout').read_bytes()
        _write_new(directory/'complete.json',dict(child=child,stdout_sha256=hashlib.sha256(value).hexdigest()))
        return value

    def _current_configuration(self):
        self.store._regular(self.native.target_path)
        verify_private_directory(self.native.target_path.parent)
        if load_json(self.native.target_path.read_bytes()) != self.config:
            raise OperatorError('Protected current target changed')

    def _restore_state(self, operation):
        if operation != self._operation:
            raise OperatorError('Recovery identity mismatch')
        self._current_configuration()
        self.native._require_jobs_drained()
        bundle, status, manifest = self._checkpoint()
        self._authorize_recovery_plan(bundle['plan'])
        if len(self.config['sites']) != 1 or any(p['runtime']!='native' for p in self.config.get('published_release',{}).get('plugins',[])):
            raise OperatorError('One current native deployment is required')
        replacement = self.store.root/'stages'/self._source_operation/'worker-replacement.json'
        self.store._regular(replacement)
        recorded = load_json(replacement.read_bytes())
        target, lock = recovery_configuration(self.config,manifest,bundle,recorded)
        if self.config != recorded['configuration'] or data_digest(self.config['published_release']) != bundle['plan']['target_release_digest']:
            raise OperatorError('Completed checkpoint must match the exact current replacement; later operations require separate reconciliation')
        result = self.store.root/'stages'/self._source_operation/'result.json'
        self.store._regular(result)
        completed = load_json(result.read_bytes())
        if completed.get('state') != 'completed' or completed.get('release_digest') != bundle['plan']['target_release_digest']:
            raise OperatorError('Completed native result does not match the original plan')
        observation = self.observer.read()
        catalog = Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
        state = self.observer.state(observation,catalog)['state']
        if state['release_digest'] != bundle['plan']['target_release_digest']:
            raise OperatorError('Current published release differs from completed operation')
        retained = inspect_image(manifest['configuration']['image_id'])
        runtime_inputs(retained,catalog)
        if retained['inventory_digest'] != lock['core_inventory_digest']:
            raise OperatorError('Retained code differs from coordinated checkpoint')
        authority, _ = self._authority(self.config['sites'][0]['database'])
        if authority['api_key_count']:
            raise OperatorError('API key reconciliation is outside this completed-checkpoint profile')
        profile = DispatchMaintenance(self.native).require_profile(DispatchMaintenance(self.native).inspect_current())
        if profile['active_credentials'] or profile['external_installations'] or profile['uncertain_jobs']:
            raise OperatorError('Unreviewed active credentials or effects prevent completed checkpoint recovery')
        effects = self._effects(self.config)
        edge = self.observer._container('edge')
        workers = snapshots(self.config)
        if (not self.native._inspect(edge)['State']['Running']
                or {w['container_id'] for w in workers if w['running']} != {self.config['worker_id']}):
            raise OperatorError('Initial review requires the exact live completed target; partial recovery has a separate continuation')
        self._fresh_absent()
        return dict(schema_version=1,action='restore_completed_checkpoint',operation_id=operation,**self._source_binding(),
            checkpoint_digest=data_digest(manifest),source_state_digest=data_digest(observation),configuration=self.config,
            base_configuration=manifest['configuration'],restore_configuration=target,restored_release_lock=lock,
            managed_workers=workers,fresh_database=self._fresh_database(),authority=authority,source_dispatch=profile,source_effects=effects,
            operator_source_sha256=self._source_hashes(),keep_traffic_closed=True,current_database_retained=True,
            point_in_time_business_data=True,operator_authorization_generation=self.store.policy['authorization_generation'])

    def prepare(self, source_operation):
        self._bind(str(uuid4()),canonical_id(source_operation))
        self.store._require_no_checkpoint_recovery(self._bundle(self._operation)['plan'])
        return RecoveryReviews(self.store).issue(self._restore_state(self._operation))

    def _activate(self,decision,exact_hash,locks):
        self._active_decision,self._active_hash,self._active_locks=decision,exact_hash,locks
        self._check_active()

    def _check_active(self):
        if self._active_decision is None:
            raise OperatorError('An independently reviewed active recovery context is required')
        RecoveryReviews(self.store).check_reserved(self._active_decision,exact_hash=self._active_hash)
        self.store._lock_identity(self._bundle(self._operation)['plan'],self._active_locks)
        if self._active_decision['operator_source_sha256'] != self._source_hashes():
            raise OperatorError('Host recovery source changed during execution; keep traffic closed')

    def _restore_activity(self,operation,label,details,action):
        if operation != self._operation or not re.fullmatch('[a-z][a-z0-9-]{1,100}',label):
            raise OperatorError('Fixed recovery activity identity required')
        self._check_active()
        root=protect_directory(self._journal.root/'activities')
        root=protect_directory(root/self._active_decision['review']['review_id'])
        intent=root/(label+'.intent.json');completion=root/(label+'.complete.json')
        _write_new(intent,dict(label=label,details=details,review_hash=self._active_hash,
            operator_source_digest=data_digest(self._source_hashes())))
        result=action()
        self._check_active()
        digest=hashlib.sha256(result).hexdigest() if isinstance(result,bytes) else data_digest(result)
        _write_new(completion,dict(intent_sha256=hashlib.sha256(intent.read_bytes()).hexdigest(),result_digest=digest))
        return result

    def _require_complete_activities(self, *, unstarted_review=None):
        root=self._journal.root/'activities'
        if not root.exists():return {}
        verify_private_directory(root)
        hashes={}
        for directory in root.iterdir():
            canonical_id(directory.name);verify_private_directory(directory)
            files={p.name for p in directory.iterdir()}
            for path in directory.iterdir():self.store._regular(path)
            intents={name.removesuffix('.intent.json') for name in files if name.endswith('.intent.json')}
            completions={name.removesuffix('.complete.json') for name in files if name.endswith('.complete.json')}
            resolutions={name.removesuffix('.resolution.json') for name in files if name.endswith('.resolution.json')}
            pending = {'restored-dispatch-fence'} if directory.name == unstarted_review else set()
            if (intents != completions | resolutions | pending or completions & resolutions
                    or resolutions - {'restored-dispatch-fence'}
                    or len(files) != 2*len(intents)-len(pending)):
                raise OperatorError('A recovery activity is uncertain; inspect without repeating it')
            for name in intents:
                original=directory/(name+'.intent.json')
                intent=load_json(original.read_bytes())
                if (set(intent)!={'label','details','review_hash','operator_source_digest'} or intent['label']!=name
                        or not re.fullmatch('[a-z][a-z0-9-]{1,100}',name) or not isinstance(intent['details'],dict)):
                    raise OperatorError('Recovery activity evidence changed')
                if name in resolutions:
                    self._activity_resolution(directory, original)
                elif name not in pending:
                    done=load_json((directory/(name+'.complete.json')).read_bytes())
                    if (set(done)!={'intent_sha256','result_digest'}
                            or done['intent_sha256']!=hashlib.sha256(original.read_bytes()).hexdigest()):
                        raise OperatorError('Recovery activity evidence changed')
            for name in sorted(files):
                hashes[directory.name+'/'+name]=hashlib.sha256((directory/name).read_bytes()).hexdigest()
        return hashes

    def _activity_resolution(self, directory, intent_path):
        """Historical refusal is resolved, never represented as child success."""
        resolution=self._journal._read(directory/'restored-dispatch-fence.resolution.json')
        review_id=canonical_id(resolution.get('review_id'))
        decision=self._journal._read(self._journal.root/'continuations'/review_id/'decision.json')
        RecoveryReviews(self.store)._record(decision,data_digest(decision))
        continuation=decision.get('continuation',{});failed=continuation.get('failed_activity',{})
        records=self._fence_diagnostics()
        expected=dict(schema_version=1,kind='unstarted_restored_fence',
            intent_sha256=hashlib.sha256(intent_path.read_bytes()).hexdigest(),
            diagnostics_digest=data_digest(records),continuation_decision_digest=data_digest(decision),review_id=review_id)
        if (resolution!=expected or decision.get('action')!='continue_completed_checkpoint'
                or decision.get('operation_id')!=self._operation
                or decision.get('checkpoint_operation_id')!=self._source_operation
                or continuation.get('phase')!='restored_before_first_dispatch_fence'
                or continuation.get('reason')!='retained_source_fence_name_collision'
                or failed.get('review_id')!=directory.name
                or failed.get('intent_sha256')!=expected['intent_sha256']
                or failed.get('diagnostics')!=records):
            raise OperatorError('Exact reviewed unstarted-fence activity resolution required')

    def _fence_diagnostics(self):
        root=self._journal.root
        records={}
        for folder,names in (
                ('dispatch-fence',{'fence-request.json','fence.stdout','fence.stdout.stderr.log'}),
                ('source-dispatch-fence',{'fence-request.json','fence.json','fence.stdout','fence.stdout.stderr.log'})):
            directory=root/folder;verify_private_directory(directory)
            if {p.name for p in directory.iterdir()}!=names:
                raise OperatorError('Restored fence may have run; exact unstarted diagnostics required')
            for name in sorted(names):
                path=directory/name;self.store._regular(path)
                records[folder+'/'+name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for name in (PROOF_NAME,'filestore.log','filestore.log.stderr.log','restored-effect-proof.json'):
            path=root/name;self.store._regular(path);records[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        if (root/'dispatch-fence/fence.stdout').stat().st_size:
            raise OperatorError('Restored child output is uncertain; continuation denied')
        return records

    def _begin(self,step,details):
        self._check_active()
        self._journal.begin(step,details,decision=self._active_decision,exact_hash=self._active_hash,locks=self._active_locks)

    def _finish(self,step,details):
        self._check_active()
        self._journal.finish(step,details,decision=self._active_decision,exact_hash=self._active_hash,locks=self._active_locks)

    def _no_clients(self):
        database=self.observer._container('db');source=self.config['sites'][0]['database']
        value=_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],
            input=("SELECT count(*) FROM pg_stat_activity WHERE datname='"+source+"';").encode())
        if value.strip()!=b'0':raise OperatorError('Unexpected source database clients prevent closed recovery')

    def _no_live_children(self):
        for operation in (self._source_operation,self._operation):
            if _run(['docker','ps','-q','--filter','label=com.modular.operation='+operation]).strip():
                raise OperatorError('A maintenance child is still running; reconcile before recovery')

    def _quiesce(self,decision):
        operation=self._operation;edge=self.observer._container('edge')
        self._begin('traffic_closed',{'container_id':edge})
        self._restore_activity(operation,'stop-current-edge',{'container_id':edge},lambda:_run(['docker','stop','--time','20',edge]))
        if self.native._inspect(edge)['State']['Running']:raise OperatorError('Traffic did not close')
        self._finish('traffic_closed',{'container_id':edge})
        helper=DispatchMaintenance(self.native)
        self._begin('dispatch_fenced',{'reviewed_digest':decision['source_dispatch']['state_digest']})
        fence=self._restore_activity(operation,'fence-current-dispatch',{'release_digest':decision['source_dispatch']['release_digest']},
            lambda:helper.run('fence',operation,self._journal.root/'source-dispatch-fence',
                release_digest=decision['source_dispatch']['release_digest'],review_id=decision['review']['review_id']))
        if fence['before'] != decision['source_dispatch']:
            raise OperatorError('Source effects changed after review; source remains closed for reconciliation')
        helper.require_profile(fence['after'],closed=True)
        self._finish('dispatch_fenced',fence)
        self._begin('workers_drained',{'workers':decision['managed_workers']})
        for worker in decision['managed_workers']:
            if worker['running']:
                if worker['container_id']!=self.config['worker_id'] or worker['image_id']!=self.config['image_id']:
                    raise OperatorError('Only the exact pinned current worker may drain')
                self._restore_activity(operation,'stop-current-worker',{'container_id':worker['container_id']},
                    lambda:_run(['docker','stop','--time','30',worker['container_id']]))
                info=self.native._inspect(worker['container_id'])
                if info['State']['Running'] or info['State']['ExitCode']!=0:
                    raise OperatorError('Current worker did not drain cleanly')
        self._no_clients();self._no_live_children()
        self._finish('workers_drained',{'workers':snapshots(self.config)})
        self._begin('source_verified',{})
        authority,_=self._authority(self.config['sites'][0]['database'])
        if authority != decision['authority']:raise OperatorError('Source authority changed during drain')
        profile=helper.require_profile(helper.inspect_current(),closed=True)
        if profile != fence['after']:raise OperatorError('Source dispatch changed after its exact fence')
        effects=self._effects(self.config)
        self._fresh_absent()
        self._finish('source_verified',{'authority':authority,'dispatch':profile,'effects':effects,'workers':snapshots(self.config)})

    def execute(self,decision,*,exact_hash,noninteractive=False):
        if not isinstance(decision,dict) or decision.get('action')!='restore_completed_checkpoint':
            raise OperatorError('Exact completed-checkpoint restore decision required')
        self._bind(decision['operation_id'],decision['checkpoint_operation_id'])
        bundle=self._bundle(self._operation)
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']) as locks:
            self.store._require_no_checkpoint_recovery(bundle['plan'])
            RecoveryReviews(self.store).verify(decision,exact_hash=exact_hash,current_payload=self._restore_state(self._operation))
            if noninteractive and not self.store.policy['allow_noninteractive']:
                raise OperatorError('Noninteractive recovery is not enabled')
            self._no_live_children()
            self._journal.create(decision,exact_hash=exact_hash,locks=locks)
            _write_new(self._journal.root/'decision.json',dict(decision=decision,hash=exact_hash,operator_id=current_identity()))
            self._activate(decision,exact_hash,locks)
            self._quiesce(decision)
            return self._restore_from_quiesced(decision)

    def _restore_from_quiesced(self,decision):
        self._check_active();state=self._journal.status()
        if state['phase']!='source_verified' or state['pending'] is not None:
            raise OperatorError('Exact completed quiesce boundary is required before creation')
        bundle,_,manifest=self._checkpoint();checkpoint=self._checkpoint_directory(self._operation)
        database=self.observer._container('db');fresh=decision['fresh_database']
        self._fresh_absent();self._no_clients();self._no_live_children()
        current,private=self._authority(self.config['sites'][0]['database'])
        quiesced=state['completed'][3]['completion']['details']
        if current!=decision['authority'] or current!=quiesced['authority']:
            raise OperatorError('Current authority changed before fresh target creation')
        helper=DispatchMaintenance(self.native)
        if helper.require_profile(helper.inspect_current(),closed=True)!=quiesced['dispatch']:
            raise OperatorError('Source dispatch changed before fresh target creation')
        require_same_effects(self._effects(self.config),quiesced['effects'])
        self._begin('target_created',{'database':fresh})
        self._restore_activity(self._operation,'create-fresh-database',{'database':fresh},
            lambda:_run(['docker','exec',database,'createdb','-U','postgres','-O','modular',fresh]))
        self._finish('target_created',{'database':fresh})
        self._begin('checkpoint_loaded',{'checkpoint_digest':decision['checkpoint_digest']})
        self._restore_activity(self._operation,'load-checkpoint-database',{'database':fresh,'checkpoint_digest':decision['checkpoint_digest']},
            lambda:_run(['docker','exec','-i',database,'pg_restore','-U','postgres','--no-owner','--role=modular','--exit-on-error','-d',fresh],input=(checkpoint/'database.dump').read_bytes()))
        args,_=self.native._child(self._operation,'restore-filestore',writable=True,network=False);args.insert(2,'-i')
        self._restore_activity(self._operation,'load-checkpoint-filestore',{'database':fresh,'checkpoint_digest':decision['checkpoint_digest']},
            lambda:self.native._private_command(args+['-c',EXTRACT_FILESTORE,self.config['sites'][0]['database'],fresh],
                self._journal.root/'filestore.log',input=(checkpoint/'filestore.tar.gz').read_bytes()))
        self._finish('checkpoint_loaded',{'database':fresh})
        self._begin('authority_applied',{'source_authority_digest':data_digest(current)})
        old_authority,_=self._authority(fresh)
        _write_new(self._journal.root/PROOF_NAME,grant_proof(decision,old_authority['integration_grants']))
        overlay=(authority_sql(decision['authority'])+overlay_sql(private)+restored_release_sql(decision['restore_configuration'],decision['restored_release_lock'],self._operation)).encode()
        self._restore_activity(self._operation,'overlay-current-authority',{'input_sha256':hashlib.sha256(overlay).hexdigest()},
            lambda:_run(['docker','exec','-i',database,'psql','-X','-q','-U','postgres','-d',fresh,'-v','ON_ERROR_STOP=1','--single-transaction'],input=overlay))
        self._finish('authority_applied',{'database':fresh})
        self._begin('restore_verified',{'database':fresh})
        self._complete_restore(decision,exact_hash=self._active_hash,locks=self._active_locks,directory=self._journal.root,
            checkpoint=checkpoint,manifest=manifest,fresh=fresh,private_native_auth=private)
        return dict(state='restored_verified',operation_id=self._operation,checkpoint_operation_id=self._source_operation,
            original_operation_state='completed',fresh_database=fresh,current_database_retained=True,keep_traffic_closed=True)

    def _before_registry_restore(self,decision,configuration):
        state=self._journal.status();quiesced=state['completed'][3]['completion']['details']
        checkpoint=self._effects(configuration)
        require_same_effects(checkpoint,quiesced['effects'])
        proof=dict(checkpoint=checkpoint,current=quiesced['effects'],proof_before_registry_start=True)
        if decision.get('continuation',{}).get('reason')=='retained_source_fence_name_collision':
            if self._journal._read(self._journal.root/'restored-effect-proof.json')!=proof:
                raise OperatorError('Preserved pre-registry effect proof changed')
            attempt=self._journal.root/'continuations'/decision['review']['review_id']
            _write_new(attempt/'restored-effect-reobservation.json',proof)
        else:
            _write_new(self._journal.root/'restored-effect-proof.json',proof)

    def _commit_verified_result(self,operation,locks,details,directory,result):
        self._check_active()
        result=result|dict(checkpoint_operation_id=self._source_operation,original_operation_state='completed')
        _write_new(directory/'result.json',result)
        self._finish('restore_verified',dict(result_digest=data_digest(result),current_database_retained=True,keep_traffic_closed=True))

    def _continuation_state(self,recovery):
        state=self._load(recovery)
        self._current_configuration()
        if state['phase']=='authority_applied' and state['pending'] is not None:
            return self._unstarted_restored_fence_state(state)
        if state['phase']!='source_verified' or state['pending'] is not None:
            raise OperatorError('Only the proven precreation boundary supports continuation; inspect other partial states')
        activities=self._require_complete_activities()
        original=load_json((self._journal.root/'decision.json').read_bytes())
        RecoveryReviews(self.store).check_reserved(original['decision'],exact_hash=original['hash'])
        decision=copy.deepcopy(original['decision']);decision.pop('review')
        if decision['configuration']!=self.config:
            raise OperatorError('Original source configuration changed before continuation')
        bundle,_,manifest=self._checkpoint()
        if decision['checkpoint_digest']!=data_digest(manifest) or self._source_binding()!={key:decision[key] for key in self._source_binding()}:
            raise OperatorError('Original checkpoint or completed source changed')
        self.native._require_jobs_drained();self._no_clients();self._no_live_children();self._fresh_absent()
        edge=self.observer._container('edge',stopped=True)
        if self.native._inspect(edge)['State']['Running']:
            raise OperatorError('Quiesced traffic was reopened; continuation is unavailable')
        quiesced=state['completed'][3]['completion']['details']
        authority,_=self._authority(self.config['sites'][0]['database'])
        workers=snapshots(self.config)
        if authority!=decision['authority'] or authority!=quiesced['authority'] or workers!=quiesced['workers'] or any(w['running'] for w in workers):
            raise OperatorError('Source authority or workers changed after quiesce')
        helper=DispatchMaintenance(self.native)
        if helper.require_profile(helper.inspect_current(),closed=True)!=quiesced['dispatch']:
            raise OperatorError('Quiesced source dispatch changed')
        require_same_effects(self._effects(self.config),quiesced['effects'])
        decision.update(action='continue_completed_checkpoint',operator_source_sha256=self._source_hashes(),
            quiesced_journal_digest=state['chain_digest'],original_decision_hash=original['hash'],
            activity_digest=data_digest(activities))
        return decision

    def _unstarted_fence_child(self, original, target, manifest, activity):
        """Prove the exact daemon create refusal against a retained source child.

        The child uses Docker's no-log driver. Its protected stdout/result and
        activity digest, rather than unavailable daemon logs, bind success.
        """
        root=self._journal.root;decision=original['decision']
        source=self._journal._read(root/'source-dispatch-fence/fence.json')
        stdout=self._journal._read(root/'source-dispatch-fence/fence.stdout')
        request=self._journal._read(root/'dispatch-fence/fence-request.json')
        before=self._journal._read(root/'source-dispatch-fence/fence-request.json')
        suffix=DispatchMaintenance._suffix('fence',decision['review']['review_id'])
        _,name=self.native._child(self._operation,suffix,image_id=self.config['image_id'])
        child=self.native._inspect(name)
        cid=child.get('Id','');config=child.get('Config',{});host=child.get('HostConfig',{})
        actual_mounts={(m.get('Type'),m.get('Name'),m.get('Destination'),m.get('RW')) for m in child.get('Mounts',[])}
        expected_mounts={('volume',self.config['project']+'_appconfig','/run/secrets',False),
                         ('volume',self.config['project']+'_filestore','/var/lib/modular',False)}
        if (not re.fullmatch('[0-9a-f]{64}',cid) or child.get('Name')!='/'+name
                or child.get('Image')!=self.config['image_id']
                or child.get('State',{}).get('Running') is not False or child['State'].get('ExitCode')!=0
                or config.get('Entrypoint')!=['/venv/bin/python'] or config.get('Cmd')!=['-c',BOOTSTRAP]
                or config.get('User')!='10001:10001'
                or config.get('Labels')!={'com.modular.operation':self._operation,'com.modular.deployment':self.config['deployment_id']}
                or host.get('ReadonlyRootfs') is not True or host.get('Privileged') is not False
                or host.get('CapDrop')!=['ALL'] or host.get('SecurityOpt')!=['no-new-privileges']
                or host.get('NetworkMode')!=self.config['project']+'_runtime'
                or set(child.get('NetworkSettings',{}).get('Networks',{}))!={self.config['project']+'_runtime'}
                or actual_mounts!=expected_mounts or len(child.get('Mounts',[]))!=2
                or source.get('child')!=name or stdout!={k:source[k] for k in ('action','result')}
                or source.get('action')!='fence'
                or source.get('result')!=activity['completed'][1]['completion']['details']):
            raise OperatorError('Retained source fence child or protected result differs')
        expected='docker: Error response from daemon: Conflict. The container name "/'+name+'" is already in use by container "'+cid+'". You have to remove (or rename) that container to be able to reuse that name.'
        error=(root/'dispatch-fence/fence.stdout.stderr.log').read_text(encoding='utf8').strip().splitlines()
        if error!=[expected,'',"Run 'docker run --help' for more information"]:
            raise OperatorError('Only the exact retained-source container-name conflict supports continuation')
        activity_root=root/'activities'/decision['review']['review_id']
        done=self._journal._read(activity_root/'fence-current-dispatch.complete.json')
        if done['result_digest']!=data_digest(source['result']):
            raise OperatorError('Source fence result differs from its completed activity')
        common=('action','site_id','operation_id','image_id','helper_sha256','authority_sha256','script_sha256','expected_digest')
        if (any(request.get(k)!=before.get(k) for k in common)
                or request['action']!='fence' or request['operation_id']!=self._operation
                or request['site_id']!=self.config['sites'][0]['site_id'] or request['image_id']!=target['image_id']
                or request['database']!=decision['fresh_database']
                or request['release_digest']!=data_digest(decision['restored_release_lock'])
                or request['control_release']!=manifest['dispatch_profile']['control']['release_digest']
                or before['database']!=self.config['sites'][0]['database']
                or before['release_digest']!=decision['source_dispatch']['release_digest']):
            raise OperatorError('Exact source and unstarted restored-fence request required')
        return dict(source_child_id=cid,source_child_name=name,source_child_digest=data_digest(child))

    def _unstarted_restored_fence_state(self,state):
        root=self._journal.root
        if (len(state['completed'])!=7 or state['pending']['step']!='restore_verified'
                or state['pending']['intent']['review_hash']!=state['binding']['decision_hash']):
            raise OperatorError('Unsupported pending completed-checkpoint verification')
        expected={'activities','binding.json','decision.json','dispatch-fence','filestore.log',
                  'filestore.log.stderr.log',PROOF_NAME,'journal','restored-effect-proof.json','source-dispatch-fence'}
        if {p.name for p in root.iterdir()}!=expected:
            raise OperatorError('Partial recovery has later or unknown activity; inspect without replay')
        original=self._journal._read(root/'decision.json');old=original['decision']
        if original['hash']!=state['binding']['decision_hash'] or old!=state['binding']['decision']:
            raise OperatorError('Original reserved restore decision changed')
        RecoveryReviews(self.store).check_reserved(old,exact_hash=original['hash'])
        review=canonical_id(old['review']['review_id'])
        if {p.name for p in (root/'activities').iterdir()}!={review}:
            raise OperatorError('Only the original unstarted restored-fence activity may continue')
        activities=self._require_complete_activities(unstarted_review=review)
        labels={name.split('/')[-1].removesuffix('.intent.json') for name in activities if name.endswith('.intent.json')}
        if labels!={'stop-current-edge','fence-current-dispatch','stop-current-worker','create-fresh-database',
                    'load-checkpoint-database','load-checkpoint-filestore','overlay-current-authority','restored-dispatch-fence'}:
            raise OperatorError('Exact original restore activity sequence required')
        decision=copy.deepcopy(old);decision.pop('review')
        _,_,manifest=self._checkpoint()
        if (decision['configuration']!=self.config or decision['fresh_database']!=self._fresh_database()
                or decision['checkpoint_digest']!=data_digest(manifest)
                or self._source_binding()!={key:decision[key] for key in self._source_binding()}):
            raise OperatorError('Original source configuration, checkpoint or history changed')
        target=copy.deepcopy(decision['restore_configuration']);target['sites'][0]['database']=decision['fresh_database']
        intent_path=root/'activities'/review/'restored-dispatch-fence.intent.json'
        intent=self._journal._read(intent_path)
        if (intent['details']!={'configuration_digest':data_digest(target)}
                or intent['review_hash']!=original['hash']
                or intent['operator_source_digest']!=data_digest(decision['operator_source_sha256'])):
            raise OperatorError('Exact original restored-fence activity intent required')
        diagnostics=self._fence_diagnostics()
        child=self._unstarted_fence_child(original,target,manifest,state)
        self.native._require_jobs_drained();self._no_clients();self._no_live_children()
        database=self.observer._container('db');fresh=decision['fresh_database']
        clients=_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],
            input=("SELECT count(*) FROM pg_stat_activity WHERE datname='"+fresh+"';").encode())
        if clients.strip()!=b'0' or self.native._inspect(self.observer._container('edge',stopped=True))['State']['Running']:
            raise OperatorError('Fresh clients or reopened traffic prevent continuation')
        quiesced=state['completed'][3]['completion']['details'];workers=snapshots(self.config)
        current,private=self._authority(self.config['sites'][0]['database'])
        if (current!=decision['authority'] or current!=quiesced['authority'] or workers!=quiesced['workers']
                or any(w['running'] for w in workers)):
            raise OperatorError('Quiesced source authority or managed workers changed')
        helper=DispatchMaintenance(self.native)
        if helper.require_profile(helper.inspect_current(),closed=True)!=quiesced['dispatch']:
            raise OperatorError('Quiesced source dispatch changed')
        require_same_effects(self._effects(self.config),quiesced['effects'])
        observed=helper.require_profile(helper.inspect_current(configuration=target),closed=True)
        ignored={'release_digest','state_digest'}
        if {k:v for k,v in observed.items() if k not in ignored}!={k:v for k,v in manifest['dispatch_profile'].items() if k not in ignored}:
            raise OperatorError('Restored dispatch differs from untouched checkpoint')
        proof=self._grant_proof(root,decision);authority,fresh_private=self._authority(fresh)
        if authority!=reconciled_authority(decision,proof) or fresh_private!=private:
            raise OperatorError('Fresh current-authority overlay or private credentials changed')
        reader=self._recovery_observer(target,manifest=manifest)
        catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
        restored=reader.state(reader.read(quiesced=True,missing_worker=True),catalog)['state']
        if (restored['release_lock']!=decision['restored_release_lock']
                or any(restored[k]!=manifest['previous_release'][k] for k in ('installations','bindings'))):
            raise OperatorError('Restored release or metadata differs from reviewed checkpoint')
        files=load_json(self._inspection('continuation-files',target,FILE_OBSERVATION,[fresh],network=False))
        expected={};prefix='filestore/'+self.config['sites'][0]['database']+'/'
        with tarfile.open(self._checkpoint_directory(self._operation)/'filestore.tar.gz','r:gz') as archive:
            for member in archive:
                if member.isfile() and member.name.startswith(prefix):
                    name=member.name[len(prefix):]
                    if name in expected:raise OperatorError('Duplicate checkpoint filestore member')
                    expected[name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        if files!=expected or self._journal._read(root/'filestore.log').get('filestore_restored') is not True:
            raise OperatorError('Fresh filestore differs from coordinated checkpoint')
        effects=self._effects(target);require_same_effects(effects,quiesced['effects'])
        if self._journal._read(root/'restored-effect-proof.json')!=dict(checkpoint=effects,current=quiesced['effects'],proof_before_registry_start=True):
            raise OperatorError('Original restored-effect proof differs from fresh observation')
        database_digest=self._restored_database_digest(database,fresh)
        decision.update(action='continue_completed_checkpoint',operator_source_sha256=self._source_hashes(),managed_workers=workers,
            continuation=dict(phase='restored_before_first_dispatch_fence',reason='retained_source_fence_name_collision',
                original_decision_digest=data_digest(original),pending_intent_digest=data_digest(state['pending']['intent']),
                journal_digest=data_digest(state),activity_digest=data_digest(activities),
                failed_activity=dict(review_id=review,intent_sha256=hashlib.sha256(intent_path.read_bytes()).hexdigest(),
                    diagnostics=diagnostics,diagnostics_digest=data_digest(diagnostics),**child),
                restored_database_digest=database_digest,restored_state_digest=data_digest(restored),
                dispatch=observed,filestore_digest=data_digest(files),filestore_files=len(files),source_sha256=self._source_hashes(),
                replay_database_dump=False,reextract_filestore=False,reapply_native_auth=False))
        return decision

    def _restored_database_digest(self, container, database):
        """Hash a bounded plain dump without treating its contents as metadata.

        Keep the existing canonical dump convention (comments/random psql guard
        lines excluded). Neither dump bytes nor stderr enter files or replies.
        The independent metadata runner's 16MiB ceiling remains unchanged.
        """
        if database!=self._fresh_database():raise OperatorError('Exact fresh database digest target required')
        maximum=128*1024*1024
        with subprocess.Popen(['docker','exec',container,'pg_dump','-U','postgres','--no-owner','--no-privileges',database],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as process:
            timer=Timer(60,process.kill);timer.daemon=True;timer.start()
            digest=hashlib.sha256();total=0;first=True
            try:
                while True:
                    line=process.stdout.readline(maximum+1)
                    if not line:break
                    total+=len(line)
                    if total>maximum:
                        process.kill();raise OperatorError('Fresh database digest exceeds the 128MiB qualification bound')
                    line=line.rstrip(b'\r\n')
                    if line.startswith((b'--',b'\\restrict ',b'\\unrestrict ')):continue
                    if not first:digest.update(b'\n')
                    digest.update(line);first=False
                if process.wait()!=0:raise OperatorError('Fresh database digest failed or exceeded its 60s deadline')
            finally:
                timer.cancel()
        return 'sha256:'+digest.hexdigest()

    def prepare_continue(self,recovery):
        return RecoveryReviews(self.store).issue(self._continuation_state(recovery))

    def continue_restore(self,decision,*,exact_hash,noninteractive=False):
        if not isinstance(decision,dict) or decision.get('action')!='continue_completed_checkpoint':
            raise OperatorError('Exact reviewed completed-checkpoint continuation required')
        state=self._load(decision['operation_id']);bundle=self._bundle(self._operation)
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']) as locks:
            RecoveryReviews(self.store).verify(decision,exact_hash=exact_hash,current_payload=self._continuation_state(self._operation))
            if noninteractive and not self.store.policy['allow_noninteractive']:
                raise OperatorError('Noninteractive continuation is not enabled')
            self._activate(decision,exact_hash,locks)
            if decision.get('continuation',{}).get('reason')=='retained_source_fence_name_collision':
                root=self._journal.root
                attempt=protect_directory(root/'continuations')/decision['review']['review_id']
                if attempt.exists() or attempt.is_symlink():raise OperatorError('Continuation already attempted; inspect without replay')
                attempt=protect_directory(attempt);_write_new(attempt/'decision.json',decision)
                failed=decision['continuation']['failed_activity']
                _write_new(root/'activities'/failed['review_id']/'restored-dispatch-fence.resolution.json',
                    dict(schema_version=1,kind='unstarted_restored_fence',intent_sha256=failed['intent_sha256'],
                        diagnostics_digest=failed['diagnostics_digest'],continuation_decision_digest=exact_hash,review_id=decision['review']['review_id']))
                self._journal.adopt_unstarted_restored_fence(decision=decision,exact_hash=exact_hash,locks=locks)
                current,private=self._authority(self.config['sites'][0]['database'])
                if current!=decision['authority']:raise OperatorError('Source authority changed before continuation')
                _,_,manifest=self._checkpoint()
                return self._complete_restore(decision,exact_hash=exact_hash,locks=locks,directory=root,
                    checkpoint=self._checkpoint_directory(self._operation),manifest=manifest,fresh=decision['fresh_database'],
                    private_native_auth=private,dispatch_directory=attempt)
            return self._restore_from_quiesced(decision)

    def _resume_state(self,operation):
        state=self._load(operation);activities=self._require_complete_activities()
        self._current_configuration()
        path=self._journal.root/'result.json';self.store._regular(path)
        if (len(state['completed'])<8 or data_digest(load_json(path.read_bytes()))
                !=state['completed'][7]['completion']['details']['result_digest']):
            raise OperatorError('Verified checkpoint result differs from its immutable completion')
        payload=super()._resume_state(operation)
        # Bind all earlier commands. The current resume's readiness probe is
        # newly journalled after review and is rechecked by the shared final
        # closed-state observation; it cannot change the reviewed prior history.
        if self._active_decision and self._active_decision.get('action')=='resume_completed_checkpoint':
            prefix=self._active_decision['review']['review_id']+'/'
            activities={key:value for key,value in activities.items() if not key.startswith(prefix)}
        payload.update(action='resume_completed_checkpoint',**self._source_binding(),operator_source_sha256=self._source_hashes(),
            activity_digest=data_digest(activities),verified_journal_digest=state['chain_digest'])
        return payload

    def prepare_resume(self,recovery):
        return RecoveryReviews(self.store).issue(self._resume_state(recovery))

    def _record_restore_resume(self,operation,locks,*,decision_hash):
        self._begin('resume_started',{'decision_hash':decision_hash})
        self._finish('resume_started',{'traffic_may_resume':True})
        self._begin('resumed',{'decision_hash':decision_hash})

    def _finish_resume(self,operation,decision,exact_hash,locks):
        self._check_active()
        edge=self.observer._container('edge')
        if not self.native._inspect(edge)['State']['Running']:
            raise OperatorError('Traffic start was not observed; inspect without repeating resume')
        current=DispatchMaintenance(self.native).require_profile(DispatchMaintenance(self.native).inspect_current())
        if current['control']['state']!='enabled':
            raise OperatorError('Dispatch enable was not observed; inspect without repeating resume')
        self._finish('resumed',{'edge':edge,'dispatch_digest':current['state_digest']})

    def resume(self,decision,*,exact_hash,noninteractive=False):
        if not isinstance(decision,dict) or decision.get('action')!='resume_completed_checkpoint':
            raise OperatorError('Exact completed-checkpoint resume review required')
        self._load(decision['operation_id'])
        return super().resume(decision,exact_hash=exact_hash,noninteractive=noninteractive)

    @contextmanager
    def _resume_locks(self,decision,exact_hash,plan):
        with OperationLocks(self.store.root/'locks',plan['deployment_id'],plan['site_ids']) as locks:
            self._activate(decision,exact_hash,locks)
            yield locks

    def revoke_review(self,decision,*,exact_hash):
        self._bind(decision['operation_id'],decision['checkpoint_operation_id'])
        return super().revoke_review(decision,exact_hash=exact_hash)

    def status(self,recovery):
        state=self._load(recovery)
        return dict(recovery_id=recovery,checkpoint_operation_id=self._source_operation,phase=state['phase'],
            pending=state['pending'],original_operation_state='completed',
            requires_independent_resume=state['phase']=='restore_verified',
            activity_reconciliation_required=self._has_pending_activity())

    def _has_pending_activity(self):
        try:self._require_complete_activities()
        except OperatorError:return True
        return False
