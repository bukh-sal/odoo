"""Actual post-metadata-commit fault and separately reviewed fresh reference restore."""
import argparse,copy,hashlib,json,sys,tarfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-connector-lifecycle-01'))
from lifecycle import base,f,j,positive
from modular import configuration
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.contracts import validate_operations_view
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.restore_continuation import FILE_OBSERVATION
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'reference-restore-01';MARKER=PRIVATE/'recovery.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,native
def phase(record,value):record['state']=value;f.write(MARKER,record)

def baseline():
    state,native=context();assert native.config['generation']==18 and not PRIVATE.exists();protect_directory(PRIVATE)
    data=base.snapshot(state,'reference-restore-before');assert len(data['mp_job'])==28 and all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
    f.write(PRIVATE/'data-before.json',data);f.write(PRIVATE/'worker-before.json',base.worker(native,'reference-restore-worker-before'))
    f.write(PRIVATE/'schema-before.json',dict(digest=base.schema(state,'reference-restore-schema-before')))
    modules=json.loads(f.sql(state,'reference-restore-modules-before','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'));f.write(PRIVATE/'modules-before.json',modules)
    record=dict(original_database=state['active_db'],scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope'])
    phase(record,'baseline_captured');print('Fresh28-terminal-job/full native metadata/worker baseline captured; no mutation',flush=True)

def prepare():
    state,native=context();record=f.load(MARKER);assert record['state']=='baseline_captured'
    c=positive.r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),'operator');scope=record['scope'];phase(record,'requesting')
    body=dict(schema_version=1,operation='prepare',operation_type='suspend',plugin_id='org.example.document_stats',site_id=scope['site_id'],workspace_ids=[scope['workspace_id']],cascade=False)
    status,response=c.request('/api/v1/operations/prepare',body,headers={'X-CSRFToken':c.csrf});assert status==200
    preview=validate_operations_view(response['data']);assert preview['targets']==[dict(**scope,plugin_id='org.example.document_stats',action='suspend')]
    record.update(operation_id=preview['operation_id'],plan_hash=preview['plan_hash']);phase(record,'prepared');f.save('preview.json',preview)
    status,response=c.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=record['operation_id'],plan_hash=record['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':c.csrf});assert status==200
    status,response=c.request('/api/v1/operations/bundle/'+record['operation_id']);assert status==200;bundle=response['data'];assert bundle['plan_hash']==record['plan_hash'];f.save('bundle.json',bundle)
    assert base.snapshot(state,'reference-restore-after-request')==f.load(PRIVATE/'data-before.json')
    phase(record,'manager_requested');print('New actual normal manager metadata nomination captured; no independent approval yet',flush=True)

def approve():
    state,native=context();record=f.load(MARKER);assert record['state']=='manager_requested';phase(record,'importing_and_reviewing')
    ops=base.prefix()+['operations','--store',str(native.store.root)];validation=base.validation(native)
    f.save('import.json',json.loads(f.command('reference-restore-import',ops+['import-request',record['operation_id']]+validation)))
    review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];f.save('review.json',review)
    native._runtime_preflight(native.store.bundle(record['operation_id']))
    f.command('reference-restore-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+validation)
    phase(record,'approved');print('Same request independently reconstructed/reviewed/exact approved; fault apply next',flush=True)

class InjectedMetadataCommitFault(RuntimeError):pass

def fault():
    state,native=context();record=f.load(MARKER);assert record['state']=='approved';original=native._private_command
    def command(arguments,path,**kwargs):
        result=original(arguments,path,**kwargs)
        if Path(path).name=='metadata.log':
            f.write(PRIVATE/'fault-boundary.json',dict(state='metadata_child_exit0_before_ready',operation_id=record['operation_id']))
            raise InjectedMetadataCommitFault('Disposable post-metadata-commit fault')
        return result
    phase(record,'applying_with_post_commit_fault');f.phase(state,'reference_restore_fault_applying')
    with patch.object(native,'_private_command',side_effect=command):
        try:native.apply(record['operation_id'])
        except InjectedMetadataCommitFault:pass
        else:raise AssertionError('Actual post-metadata-commit fault did not fire')
    status=native.store.status(record['operation_id']);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
    assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
    assert f.load(PRIVATE/'fault-boundary.json')['state']=='metadata_child_exit0_before_ready'
    after=base.snapshot(state,'reference-restore-after-fault');before=f.load(PRIVATE/'data-before.json')
    installation=next(r for r in before['mp_plugin_installation'] if r['public_id']==record['scope']['installation_id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==record['scope']['workspace_id'])
    for table,rows in before.items():
        expected=copy.deepcopy(rows)
        if table=='mp_workspace_plugin':
            row=next(r for r in expected if r['installation_id']==installation['id'] and r['workspace_id']==workspace['id']);actual=next(r for r in after[table] if r['id']==row['id'])
            assert row['availability']=='enabled' and actual['availability']=='suspended';row.update(availability='suspended',write_date=actual['write_date'])
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        assert expected==after[table],table+' beyond committed feature/policy footprint'
    assert base.worker(native,'reference-restore-worker-after-fault')==f.load(PRIVATE/'worker-before.json')
    phase(record,'recovery_required');f.phase(state,'reference_restore_required')
    f.save('fault.json',dict(result='verified_actual_post_metadata_commit_fault',operation_id=record['operation_id'],plan_hash=record['plan_hash'],state=status['state'],mutation_started=True,traffic_resumed=False,
        actual_metadata_child_exit0=True,only_provider_feature_and_policy_committed=True,all28job_outcomes_and_other_data_exact=True,same_worker_and_current_publication=True))
    print('Real metadata commit verified; recovery_required/traffic closed, old data/jobs/worker exact',flush=True)

def recover(action):
    state,native=context();record=f.load(MARKER)
    phases={'prepare-restore':('recovery_required','restore_reviewed'),'restore':('restore_reviewed','restored_closed'),'prepare-resume':('restored_verified','resume_reviewed'),'prepare-resume-current':('restored_verified','resume_reviewed'),'resume':('resume_reviewed','resumed')}
    expected,finished=phases[action];assert record['state']==expected
    filename='restore-decision.json' if 'restore' in action else 'resume-current-decision.json' if action=='prepare-resume-current' else record.get('resume_decision_file','resume-decision.json')
    path=PRIVATE/filename
    args=base.prefix()+['plugin','recover','prepare-resume' if action=='prepare-resume-current' else action,record['operation_id']]+base.options(native)
    if not action.startswith('prepare-'):
        seal=f.load(path.with_suffix('.hash.json'));args+=['--decision',str(path),'--decision-hash',seal['decision_hash'],'--noninteractive']
    phase(record,'running_'+action);f.phase(state,'reference_recovery_'+action)
    result=json.loads(f.command('reference-restore-'+action,args,timeout=600))
    if action.startswith('prepare-'):
        f.write(path,result['decision']);f.write(path.with_suffix('.hash.json'),dict(decision_hash=result['decision_hash']))
        f.save(action+'.json',dict(result='exact_private_recovery_review',decision_hash=result['decision_hash'],review=result['decision']['review'],action=result['decision']['action']))
        if action=='prepare-resume-current':record['resume_decision_file']=filename
    else:
        assert result['state']==('restored_verified' if action=='restore' else 'restored_traffic_resumed');f.save(action+'.json',result)
        target=f.load(native.target_path);state['active_db']=target['sites'][0]['database'];state['databases']=sorted(set(state['databases']+[state['active_db']]))
        fixture=f.load(j.LOCAL/'fixtures.json');fixture['database']=state['active_db'];f.write(j.LOCAL/'fixtures.json',fixture)
    phase(record,finished);f.phase(state,'reference_'+finished);f.guard(state);print('Actual reviewed recovery action completed: '+action,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','prepare','approve','fault','prepare-restore','restore','prepare-resume','prepare-resume-current','resume']);a=p.parse_args()
    if a.action in ('baseline','prepare','approve','fault'):globals()[a.action]()
    else:recover(a.action)
