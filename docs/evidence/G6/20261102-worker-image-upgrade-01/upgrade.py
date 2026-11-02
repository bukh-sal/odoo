"""Normal changed-image manager upgrade, private native proof, post-commit fault."""
import argparse,copy,json,sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import suspend as s
from runtime import ROOT,OUT,PRIVATE,RUNTIME,op,f,j,base
from modular import configuration
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.contracts import validate_operations_view
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
MARKER=PRIVATE/'metadata.json'
def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    return state,ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
def phase(record,value):record['state']=value;f.write(MARKER,record)
def prepare():
    state,native=context();record=f.load(MARKER);assert record['state']=='curated_unapproved_image_refused' and native.config['generation']==20
    assert f.load(RUNTIME)['state']=='new_image_published9' and op(native).publisher._document()['generation']==9
    before=base.snapshot(state,'image-upgrade-data-before');assert len(before['mp_job'])==29
    f.write(PRIVATE/'upgrade-data-before.json',before);f.write(PRIVATE/'upgrade-worker-before.json',base.worker(native,'image-upgrade-worker-before'))
    f.write(PRIVATE/'upgrade-schema-before.json',dict(digest=base.schema(state,'image-upgrade-schema-before')))
    f.write(PRIVATE/'upgrade-modules-before.json',json.loads(f.sql(state,'image-upgrade-modules-before','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;')))
    client=s.client(state);scope=record['scope'];phase(record,'requesting')
    nomination=dict(schema_version=1,operation='prepare',operation_type='upgrade',plugin_id='org.example.document_stats',site_id=scope['site_id'],
        workspace_ids=[scope['workspace_id']],cascade=False,artifact_version=record['version'],artifact_digest=record['digest'])
    code,response=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});assert code==200,(code,response)
    view=validate_operations_view(response['data']);assert view['targets']==[dict(**scope,plugin_id='org.example.document_stats',action='upgrade')]
    assert view['restart_required'] and not view['native_trusted_code']
    record.update(operation_id=view['operation_id'],plan_hash=view['plan_hash']);phase(record,'prepared');f.save('upgrade-preview.json',view)
    code,response=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=record['operation_id'],plan_hash=record['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200
    code,response=client.request('/api/v1/operations/bundle/'+record['operation_id']);assert code==200;bundle=response['data'];f.save('upgrade-bundle.json',bundle)
    assert bundle['plan_hash']==record['plan_hash'] and bundle['plan']['operation_type']=='upgrade'
    assert bundle['operation_lock']['release']['generation']==21 and bundle['operation_lock']['endpoints']==op(native).planning_state()['endpoints'][-1:]
    assert base.snapshot(state,'image-upgrade-after-request')==before
    phase(record,'manager_requested');print('Actual manager changed-image0.1.1->0.1.2 request captures current approved endpoint7/newimage; all host data unchanged',flush=True)

def approve():
    state,native=context();record=f.load(MARKER);assert record['state']=='manager_requested' and native.config['generation']==20
    ops=base.prefix()+['operations','--store',str(native.store.root)];phase(record,'importing_and_reviewing')
    f.save('upgrade-import.json',json.loads(f.command('image-upgrade-import',ops+['import-request',record['operation_id']]+base.validation(native))))
    review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];f.save('upgrade-review.json',review)
    native._runtime_preflight(native.store.bundle(record['operation_id']))
    f.command('image-upgrade-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+base.validation(native))
    phase(record,'approved');print('Same changed-image HTTP request independently reconstructed/reviewed/exact approved; no remote runtime control',flush=True)

def observe():
    state,native=context();record=f.load(MARKER);assert record['state']=='approved'
    helper=ReferenceDispatchMaintenance(native,operation=record['operation_id']);snapshot=helper.inspect()
    helper.require_profile(snapshot);policy=helper.policy_for(snapshot)
    assert policy['profile']=='r1-reference-stateless-transition-v1' and policy['worker_transition']['operation_id']==record['operation_id']
    assert policy['runtime_image']==record['image'] and policy['registrations'][0]['version']=='0.1.1'
    assert snapshot['external_installations']==1 and snapshot['job_states']==dict(completed=11,dead_letter=16,cancelled=2)
    assert all(f['feature_state']=='suspended' for r in policy['registrations'] for f in r['features'])
    assert base.snapshot(state,'image-upgrade-after-reviewed-native-observation')==f.load(PRIVATE/'upgrade-data-before.json')
    f.save('reviewed-transition-native.json',dict(result='passed_actual_installed_native_private_transition_observation',snapshot=snapshot,policy=policy,
        all29jobs_and_other17tables_exact=True,default_profile_refusal_separately_observed=True,no_mutation=True))
    phase(record,'reviewed_native_transition_verified');print('Actual installed native DB checker accepts ONLY stored approved oldmetadata/newimage suspended transition; no data mutation',flush=True)

class InjectedMetadataCommitFault(RuntimeError):pass
def fault():
    state,native=context();record=f.load(MARKER);assert record['state']=='reviewed_native_transition_verified'
    original=native._private_command
    def command(arguments,path,**kwargs):
        result=original(arguments,path,**kwargs)
        if Path(path).name=='metadata.log':
            f.write(PRIVATE/'upgrade-fault-boundary.json',dict(state='new_metadata_child_exit0_before_ready',operation_id=record['operation_id']))
            raise InjectedMetadataCommitFault('Disposable changed-image post-metadata-commit fault')
        return result
    phase(record,'applying_with_post_commit_fault');f.phase(state,'image_upgrade_postcommit_fault_applying')
    with patch.object(native,'_private_command',side_effect=command):
        try:native.apply(record['operation_id'])
        except InjectedMetadataCommitFault:pass
        else:raise AssertionError('Actual changed-image post-commit fault did not fire')
    status=native.store.status(record['operation_id']);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
    assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
    before=f.load(PRIVATE/'upgrade-data-before.json');after=base.snapshot(state,'image-upgrade-after-postcommit-fault')
    inst=next(r for r in before['mp_plugin_installation'] if r['public_id']==record['scope']['installation_id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==record['scope']['workspace_id'])
    for table,rows in before.items():
        expected=copy.deepcopy(rows)
        if table=='mp_plugin_installation':
            row=next(r for r in expected if r['id']==inst['id']);current=next(r for r in after[table] if r['id']==row['id'])
            assert {k for k in row if row[k]!=current[k]}=={'version','artifact_digest','manifest'}
            assert current['version']=='0.1.2' and current['artifact_digest']==record['digest'] and current['manifest']['external_service']['expected_image']==record['image']
            row.update(**{k:current[k] for k in ['version','artifact_digest','manifest']})
        elif table=='mp_workspace_plugin':
            row=next(r for r in expected if r['installation_id']==inst['id'] and r['workspace_id']==workspace['id']);current=next(r for r in after[table] if r['id']==row['id'])
            assert row['availability']==current['availability']=='suspended';row['write_date']=current['write_date']
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        assert expected==after[table],table+' outside actual metadata commit footprint'
    assert base.worker(native,'image-upgrade-worker-after-fault')==f.load(PRIVATE/'upgrade-worker-before.json')
    f.save('upgrade-fault.json',dict(result='passed_actual_changed_image_metadata_commit_fault_fenced',operation_id=record['operation_id'],plan_hash=record['plan_hash'],
        real_new_metadata_0_1_2_committed=True,actual_metadata_child_exit0=True,host_fault_after_commit_before_ready=True,state=status['state'],traffic_resumed=False,
        old29job_outcomes_and_all_other_data_exact=True,provider_all_scopes_still_suspended=True,new_worker_and_approval9_unchanged=True,
        limits='Injected host-side exception after real child exit0; not a second process-kill test. Recovery is required next; no success/rollback claim yet.'))
    phase(record,'recovery_required');f.phase(state,'image_upgrade_recovery_required');print('Real newimage metadata commit then host failure: recovery_required/edge closed; old29jobs/native data exact, newworker/pub9 unchanged',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','approve','observe','fault']);a=p.parse_args();globals()[a.action]()
