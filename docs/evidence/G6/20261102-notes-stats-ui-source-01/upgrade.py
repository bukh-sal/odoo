"""Ordinary native NotesStats UI successor; retain existing backend/worker authority."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core15-upgrade-01'))
import activate as base
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.operator_store import OperatorStore
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.profile_channel import publish_profile
from modular_platform.release_staging import StageStore
from modular_platform.plans import data_digest
from modular_platform.contracts import validate_operations_view
j=base.j;f=base.f;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'notes-stats-ui-01';MARKER=PRIVATE/'upgrade.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    return state,StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))

def prepare():
    state,native=context();setup=f.load(PRIVATE/'setup.json');assert setup['state']=='candidate_validated' and not MARKER.exists() and native.config['generation']==23
    before=base.snapshot(state,'notes-ui-install-before');assert len(before['mp_job'])==30 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    f.write(PRIVATE/'data-before-install.json',before);f.write(PRIVATE/'worker-before-install.json',base.worker(native,'notes-ui-install-worker-before'))
    f.write(PRIVATE/'schema-before-install.json',dict(digest=base.schema(state,'notes-ui-install-schema-before')))
    modules=json.loads(f.sql(state,'notes-ui-install-modules-before','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'));f.write(PRIVATE/'modules-before-install.json',modules)
    requests=json.loads(f.sql(state,'notes-ui-install-request-ids-before',"BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(public_id ORDER BY public_id),'[]'::jsonb) FROM mp_operation_request; ROLLBACK;"))
    f.write(MARKER,dict(state='staging',before_request_ids=requests,image_id=setup['candidate_image'],inventory_digest=setup['candidate_inventory']))
    staged=json.loads(f.command('notes-ui-stage',base.prefix()+['plugin','stage-image','--image-id',setup['candidate_image']]+base.options(native)));f.save('staged-image.json',staged)
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);stages=StageStore(native.store,native.config,catalog)
    f.save('staged-profile-publication.json',publish_profile(native.observer,catalog,staged=stages.load()))
    assert base.snapshot(state,'notes-ui-after-stage-data')==before and base.worker(native,'notes-ui-after-stage-worker')==f.load(PRIVATE/'worker-before-install.json')
    record=f.load(MARKER);record['state']='awaiting_manager_request';f.write(MARKER,record)
    f.phase(state,'notes_stats_staged_manager_ready');print('UI successor candidate staged and sanitized profile published; data/worker unchanged')

def nominate():
    import r1_probe
    from uuid import uuid4
    r1_probe.r1.r0.LOCAL=j.LOCAL
    state,native=context();record=f.load(MARKER);assert record['state']=='awaiting_manager_request'
    fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture,'operator');setup=f.load(PRIVATE/'setup.json')
    nomination=dict(schema_version=1,operation='prepare',operation_type='upgrade',plugin_id='org.example.notes_stats',site_id=native.config['sites'][0]['site_id'],workspace_ids=[fixture['workspaces']['C']['public_id']],cascade=False,artifact_version='0.1.1',artifact_digest=setup['artifact_digest'])
    status,response=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});assert status==200,dict(status=status,error=response.get('error',{}).get('code'))
    preview=validate_operations_view(response['data']);assert preview['native_trusted_code'] and preview['restart_required'];f.save('http-preview.json',preview)
    record.update(state='http_prepared',operation_id=preview['operation_id'],plan_hash=preview['plan_hash']);f.write(MARKER,record)
    status,response=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=record['operation_id'],plan_hash=record['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert status==200
    result=validate_operations_view(response['data']);assert result['state']=='awaiting_operator_approval' and result['source']=='application_request';f.save('http-request.json',result)
    record['state']='http_requested';f.write(MARKER,record);print('Actual installed manager requests NotesStats UI upgrade C; independent authority still required')

def capture():
    state,native=context();record=f.load(MARKER);assert record['state']=='http_requested'
    rows=json.loads(f.sql(state,'notes-ui-app-request-capture',"BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(jsonb_build_object('operation_id',public_id,'plan_hash',plan_hash,'requested',requested,'bundle',bundle) ORDER BY id),'[]'::jsonb) FROM mp_operation_request; ROLLBACK;"))
    new=[r for r in rows if r['operation_id'] not in record['before_request_ids']];assert len(new)==1 and new[0]['requested'] and new[0]['operation_id']==record['operation_id']
    bundle=new[0]['bundle'];assert bundle['plan_hash']==record['plan_hash'] and bundle['plan']['operation_type']=='upgrade'
    assert len(bundle['operation_lock']['targets'])==1 and bundle['operation_lock']['targets'][0]['plugin_id']=='org.example.notes_stats'
    assert bundle['plan']['permission_changes']==[]
    assert bundle['operation_lock']['release']['generation']==24
    assert bundle['operation_lock']['staged_image']['target_image_id']==record['image_id'] and not bundle['plan']['destructive']
    assert base.snapshot(state,'notes-ui-request-data-after')==f.load(PRIVATE/'data-before-install.json')
    assert base.worker(native,'notes-ui-request-worker-after')==f.load(PRIVATE/'worker-before-install.json')
    f.save('manager-bundle.json',bundle);record['state']='manager_requested';f.write(MARKER,record);print('Exact native C request captured;no new grants; no data/worker mutation before independent approval')

def approve():
    state,native=context();record=f.load(MARKER);assert record['state']=='manager_requested';ops=base.prefix()+['operations','--store',str(native.store.root)]
    f.save('import.json',json.loads(f.command('notes-ui-import',ops+['import-request',record['operation_id']]+base.validation(native))))
    status=native.store.status(record['operation_id']);assert status['state']=='awaiting_operator_approval' and not status['mutation_started']
    f.save('independent-review.json',native.store.review(record['operation_id'],native._validate()));native._runtime_preflight(native.store.bundle(record['operation_id']))
    f.command('notes-ui-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+base.validation(native))
    record['state']='approved';f.write(MARKER,record);f.phase(state,'notes_stats_install_approved');print('NotesStats UI successor independently reconstructed/reviewed/exact approved with explicit trust+permission acknowledgements')

def apply():
    state,native=context();record=f.load(MARKER);assert record['state']=='approved';record['state']='applying';f.write(MARKER,record);f.phase(state,'notes_stats_install_applying')
    result=json.loads(f.command('notes-ui-install-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600));assert result['state']=='completed' and result['traffic_resumed'];f.save('completed.json',result)
    target=f.load(native.target_path);assert target['generation']==24 and target['image_id']==record['image_id']
    state.update(image_id=record['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'notes_stats_installed_needs_verification');print('NotesStats UI successor upgraded via same approved executor; exact preservation/integration verification required next')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','nominate','capture','approve','apply']);a=p.parse_args();globals()[a.action]()
