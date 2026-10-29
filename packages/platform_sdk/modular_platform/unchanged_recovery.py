"""Host-only reviewed resume of an unmutated failed deployment's exact base."""
from pathlib import Path

from .catalog import Catalog
from .contracts import load_json
from .deployment import _run
from .operator_os import OperatorError, OperationLocks, protect_directory
from .operator_store import _write_new
from .plans import check_bundle, data_digest
from .recovery_reviews import RecoveryReviews
from .workers import snapshots, wait_ready


PHASES = ('reserved','staged','maintenance','drained','checkpointed',
          'unchanged_resume_started','unchanged_release_ready','unchanged_traffic_resumed')
DISPATCH_CHECK = """BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5s';
SELECT jsonb_build_object('dispatch',to_regclass('mp_job') IS NOT NULL OR to_regclass('mp_outbox') IS NOT NULL);
ROLLBACK;"""


def validate_failed_base(status):
    if (status['state']!='failed_before_mutation' or status['mutation_started'] or status['phase'] not in PHASES
            or status['traffic_resumed'] and not status['phase'].startswith('unchanged_')):
        raise OperatorError('Only an independently verified failure before mutation can resume unchanged code')


def validate_base_worker(info,config,inventory):
    project=config['project']
    expected={'/run/secrets':('volume',project+'_appconfig',False),
              '/var/lib/modular':('volume',project+'_filestore',True)}
    mounts={m['Destination']:(m['Type'],m.get('Name'),m['RW']) for m in info['Mounts']}
    cmd=['-c',Path(__file__).with_name('worker_start.py').read_text(encoding='utf8'),config['sites'][0]['database'],inventory]
    if (info['Id']!=config.get('worker_id') or info['Image']!=config['image_id'] or mounts!=expected
            or info['Config']['User']!='10001:10001' or info['Config']['Entrypoint']!=['/venv/bin/python']
            or info['Config']['Cmd']!=cmd or not info['HostConfig']['ReadonlyRootfs']
            or info['HostConfig']['CapDrop']!=['ALL'] or 'no-new-privileges' not in (info['HostConfig']['SecurityOpt'] or [])
            or set(info['NetworkSettings']['Networks'])!={project+'_runtime'}):
        raise OperatorError('Unchanged recovery requires the exact existing guarded worker topology and pins')


class UnchangedReleaseRecovery:
    def __init__(self,native):
        self.native=native;self.store=native.store;self.config=native.config;self.observer=native.observer

    def _state(self,operation):
        status=self.store.status(operation);validate_failed_base(status)
        bundle=self.store.bundle(operation);self.store._authorize_plan(bundle['plan'])
        if (bundle['plan']['operation_type'] in ('suspend','enable') or len(self.config['sites'])!=1
                or load_json(self.native.target_path.read_bytes())!=self.config):
            raise OperatorError('Unchanged recovery requires the exact independent single-site native base configuration')
        stage=self.store.root/'stages'/operation
        if (stage/'worker-replacement.json').exists():
            raise OperatorError('A replacement was attempted; reconcile possible mutation before recovery')
        if (stage/'configuration.json').exists():
            self.store._regular(stage/'configuration.json')
            if load_json((stage/'configuration.json').read_bytes())!=self.config:
                raise OperatorError('Failed base configuration changed; unchanged resume denied')
        running=_run(['docker','ps','-q','--filter','label=com.modular.operation='+operation]).decode().strip()
        if running:raise OperatorError('A maintenance child is still running; reconcile before resume')
        workers=snapshots(self.config)
        if any(w['running'] and w['container_id']!=self.config.get('worker_id') for w in workers):
            raise OperatorError('Unexpected running worker prevents unchanged resume')
        app=self.observer._container('app',stopped=True);info=self.native._inspect(app)
        observation=self.observer.read(quiesced=not info['State']['Running'])
        catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
        state=self.observer.state(observation,catalog)['state'];check_bundle(bundle,state)
        if any(i['runtime']!='native' for s in observation['sites'] for i in s['installations']):
            raise OperatorError('External runtimes require dispatch reconciliation')
        validate_base_worker(info,self.config,observation['runtime']['inventory_digest'])
        raw=_run(['docker','exec','-i',self.observer._container('db'),'psql','-X','-qAt','-U','postgres',
                  '-d',self.config['sites'][0]['database'],'-v','ON_ERROR_STOP=1'],input=DISPATCH_CHECK.encode())
        if load_json(raw)['dispatch']:raise OperatorError('Jobs/outbox require the later dispatch reconciliation profile')
        edge=self.native._inspect(self.observer._container('edge',stopped=True))
        return {'schema_version':1,'action':'resume_unchanged_release','operation_id':operation,
                'plan_hash':bundle['plan_hash'],'configuration':self.config,'base_state_digest':data_digest(state),
                'observation_digest':data_digest(observation),'managed_workers':workers,
                'worker_id':info['Id'],'worker_running':info['State']['Running'],
                'edge':{'id':edge['Id'],'image_id':edge['Image'],'running':edge['State']['Running']},
                'journal_phase':status['phase'],'last_event_sequence':status['history'][-1]['sequence'],
                'traffic_may_have_opened':status['traffic_resumed'],'database_restore':False}

    def prepare(self,operation):
        bundle=self.store.bundle(operation)
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']):
            return RecoveryReviews(self.store).issue(self._state(operation))

    def resume(self,decision,*,exact_hash,noninteractive=False):
        operation=decision['operation_id'];bundle=self.store.bundle(operation);reviews=RecoveryReviews(self.store)
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']) as locks:
            reviews.verify(decision,exact_hash=exact_hash,current_payload=self._state(operation))
            if noninteractive and not self.store._policy()['allow_noninteractive']:
                raise OperatorError('Noninteractive recovery is not enabled')
            parent=protect_directory(self.store.root/'unchanged-resumes'/operation)
            directory=parent/decision['review']['review_id']
            if directory.exists():raise OperatorError('Interrupted unchanged resume requires a fresh review of actual state')
            directory=protect_directory(directory);_write_new(directory/'decision.json',decision)
            self.store.record_unchanged_resume(operation,locks,decision_hash=exact_hash,phase='unchanged_resume_started')
            if not decision['worker_running']:_run(['docker','start',decision['worker_id']])
            wait_ready(decision['worker_id'])
            current=self._state(operation)
            if current['edge']['id']!=decision['edge']['id'] or current['edge']['image_id']!=decision['edge']['image_id']:
                raise OperatorError('Ingress changed after review; traffic remains fenced')
            locks.check();reviews.check_reserved(decision,exact_hash=exact_hash)
            self.store.record_unchanged_resume(operation,locks,decision_hash=exact_hash,phase='unchanged_release_ready')
            _write_new(directory/'ready.json',{'observation_digest':current['observation_digest'],'base_state_digest':current['base_state_digest']})
            locks.check();reviews.check_reserved(decision,exact_hash=exact_hash)
            # Conservative external-effect fence precedes reopening; this action
            # never authorizes DB/filestore rollback, including after a crash.
            self.store.record_unchanged_resume(operation,locks,decision_hash=exact_hash,phase='unchanged_traffic_resumed')
            if not current['edge']['running']:_run(['docker','start',current['edge']['id']])
            if not self.native._inspect(current['edge']['id'])['State']['Running']:
                raise OperatorError('Ingress did not resume; prepare a fresh unchanged-release review')
            result={'state':'unchanged_release_resumed','operation_id':operation,'original_plan_state':'failed_before_mutation',
                    'generation':self.config['generation'],'database_restore':False,'worker_replaced':False,'traffic_resumed':True}
            _write_new(directory/'result.json',result);reviews.revoke(decision,exact_hash=exact_hash)
            self.native.mirror_progress(operation)
            return result
