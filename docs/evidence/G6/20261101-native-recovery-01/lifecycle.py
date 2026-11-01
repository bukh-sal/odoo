"""Once-only owned populated native fault and ordinary reviewed recovery."""
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.restore_executor import RestoreExecutor
f=j.f;f.OUTPUT=OUT
MARKER=j.LOCAL/'native-recovery-01.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    target=j.LOCAL/'operator/target.json';config=f.load(target)
    native=NativeExecutor(OperatorStore(j.LOCAL/'operator/control'),target,j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,config,native

def seed():
    state,config,native=context();assert state['phase']=='carryforward_scoped_install_qualified' and config['generation']==3 and not MARKER.exists()
    f.write(MARKER,dict(state='seeding_owned_claim'))
    code='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'+(OUT/'seed_native.py').read_text()
    raw=f.native(state,'native-recovery-seed-01',[],code)
    rows=[json.loads(l.split('MP_NATIVE_RECOVERY_SEED=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_NATIVE_RECOVERY_SEED=')];assert len(rows)==1
    f.write(j.LOCAL/'native-recovery-seed-01.json',rows[0])
    f.write(MARKER,dict(state='seeded',original_database=state['active_db'],job_id=rows[0]['job_id'],note_id=rows[0]['note_id']))
    f.save('seed.json',dict(result='seeded_original_actor_native_job_and_event_lease',job_id=rows[0]['job_id'],note_id=rows[0]['note_id'],attempts=1,max_attempts=5,fixture_timeout_seconds=3600,production_timeout_seconds=120,policy='Trusted once-only native test enqueue scheduling policy; actual registered handler/schema/effect/permissions unchanged; stored deadline will never be extended.',private_claim_receipt_and_trace_retained=True))
    f.phase(state,'native_recovery_seeded');f.guard(state)

def prepare():
    state,config,native=context();record=f.load(MARKER);assert state['phase']=='native_recovery_seeded' and record['state']=='seeded' and config['generation']==3
    reader=DockerObserver(config);catalog=Catalog(j.LOCAL/'operator/catalog',native.validator,readonly=True);snapshot=catalog.snapshot();obs=reader.read();document=reader.state(obs,snapshot)
    f.save('before.json',document['state']);operation=str(uuid4());fixture=f.load(j.LOCAL/'fixtures.json')
    targets=[dict(installation_id=installation_id(obs['sites'][0],'org.example.notes_labels'),site_id=state['site_id'],workspace_id=fixture['workspaces']['C']['public_id'],plugin_id='org.example.notes_labels',action='install')]
    bundle=prepare_current_install_targets(document,obs['sites'],snapshot,activation_targets=targets,operation_id=operation,created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    f.save('bundle.json',bundle);record.update(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'operations','--store',str(native.store.root)]
    options=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('native-recovery-register-01',prefix+['register','--bundle',str(OUT/'bundle.json')]+options)
    f.command('native-recovery-approve-01',prefix+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+options)
    record['state']='approved';f.write(MARKER,record);f.phase(state,'native_recovery_fault_approved')
    print('New exact independently approved Labels-C installation; existing Notes-C operation untouched.')

class InjectedNativeCommitFault(RuntimeError):pass

def apply():
    state,config,native=context();record=f.load(MARKER);assert state['phase']=='native_recovery_fault_approved' and record['state']=='approved' and config['generation']==3
    operation=record['operation_id'];original=native._private_command
    def private(arguments,path,**kwargs):
        result=original(arguments,path,**kwargs)
        if Path(path).name=='native.log':
            # The real blocking native child returned exit0. Its normal durable
            # journal mutation fence is already set; no test hook enters runtime.
            f.write(j.LOCAL/'native-recovery-injected-fault-01.json',dict(state='native_child_exit0_before_metadata',operation_id=operation))
            raise InjectedNativeCommitFault('Owned post-native-commit fault before metadata/traffic')
        return result
    record['state']='applying';f.write(MARKER,record);f.phase(state,'native_recovery_fault_applying')
    with patch.object(native,'_private_command',side_effect=private):
        try:native.apply(operation)
        except InjectedNativeCommitFault:pass
        else:raise AssertionError('Expected post-native-commit fault did not occur')
    status=native.store.status(operation);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
    assert f.load(j.LOCAL/'native-recovery-injected-fault-01.json')['state']=='native_child_exit0_before_metadata'
    stage=native.store.root/'stages'/operation;manifest=f.load(native.store.root/'checkpoints'/operation/'manifest.json');fence=f.load(stage/'dispatch-fence/fence.json')['result']
    assert manifest['dispatch_profile']==fence['after'] and fence['after']['control']['state']=='paused'
    record['state']='recovery_required';f.write(MARKER,record);f.phase(state,'native_recovery_requires_restore')
    f.save('fault.json',dict(result='expected_post_native_commit_fault',operation_id=operation,status=status,checkpoint_dispatch_profile=manifest['dispatch_profile'],native_child_returned_exit0=True,traffic_closed=True,original_image_and_database_retained=True))
    f.guard(state);print('Native child committed; expected recovery_required with ingress/dispatch fenced.')

def recover(action):
    state,config,native=context();record=f.load(MARKER)
    mapping={'prepare-restore':('native_recovery_requires_restore','native_restore_reviewed','native-restore-decision-01.json'),'restore':('native_restore_reviewed','native_restored_closed','native-restore-decision-01.json'),'prepare-continuation':('native_recovery_running_restore','native_continuation_reviewed','native-continuation-decision-01.json'),'continue-restore':('native_continuation_reviewed','native_restored_closed','native-continuation-decision-01.json'),'prepare-resume':('native_restored_closed_verified','native_resume_reviewed','native-resume-decision-01.json'),'resume':('native_resume_reviewed','native_restored_resumed','native-resume-decision-01.json')}
    expected,finished,filename=mapping[action];assert state['phase']==expected and record['state']=='recovery_required'
    cli_action={'prepare-continuation':'prepare-restore','continue-restore':'restore'}.get(action,action)
    args=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'plugin','recover',cli_action,record['operation_id'],'--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    if not action.startswith('prepare-'):
        sealed=f.load(j.LOCAL/(filename+'.hash'));args+=['--decision',str(j.LOCAL/filename),'--decision-hash',sealed['decision_hash'],'--noninteractive']
    f.phase(state,'native_recovery_running_'+action)
    result=json.loads(f.command('native-recovery-'+action+'-01',args,timeout=600))
    if action.startswith('prepare-'):
        private=result['decision'];f.write(j.LOCAL/filename,private);f.write(j.LOCAL/(filename+'.hash'),dict(decision_hash=result['decision_hash']))
        f.save(action+'.json',dict(result='exact_private_review_prepared',operation_id=record['operation_id'],decision_hash=result['decision_hash'],review=private['review'],action=private['action'],keep_traffic_closed=True))
    else:
        assert result['state']==('restored_verified' if action in {'restore','continue-restore'} else 'restored_traffic_resumed')
        f.save(action+'.json',result)
        current=f.load(native.target_path);state['active_db']=current['sites'][0]['database'];state['databases']=sorted(set(state['databases']+[state['active_db']]))
        fixture=f.load(j.LOCAL/'fixtures.json');fixture['database']=state['active_db'];f.write(j.LOCAL/'fixtures.json',fixture)
    f.phase(state,finished);f.guard(state);print('Exact CLI recovery step completed: '+action)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['seed','prepare','apply','prepare-restore','restore','prepare-continuation','continue-restore','prepare-resume','resume']);args=parser.parse_args()
    if args.action in ['seed','prepare','apply']:globals()[args.action]()
    else:recover(args.action)
