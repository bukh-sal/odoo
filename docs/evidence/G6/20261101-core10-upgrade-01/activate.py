"""Normal exact independently staged core upgrade on the retained populated DB."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'core10-upgrade-01.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state);record=f.load(MARKER)
    native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,record,native

def prepare():
    state,record,native=context();assert state['phase']=='core10_candidate_validated' and record['state']=='candidate_validated_not_staged' and native.config['generation']==5
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==7
    f.save('state-before-plan.json',before)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')];options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    record['state']='staging';f.write(MARKER,record);f.phase(state,'core10_staging')
    staged=json.loads(f.command('core10-stage-01',prefix+['plugin','stage-image','--image-id',record['image_id']]+options));f.save('staged-image.json',staged)
    nomination=dict(operation_type='core_upgrade',targets=[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='deploy') for row in before['installations']]);f.save('nomination.json',nomination)
    bundle=json.loads(f.command('core10-plan-01',prefix+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options));f.save('bundle.json',bundle)
    assert bundle['operation_lock']['native_core_changes']==f.load(OUT/'candidate-validation.json')['native_core_changes']
    assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
    assert len(bundle['operation_lock']['targets'])==7 and bundle['operation_lock']['staged_image']['target_image_id']==record['image_id']
    operation=bundle['plan']['operation_id'];record.update(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('core10-register-01',ops+['register','--bundle',str(OUT/'bundle.json')]+validation)
    f.save('independent-review.json',native.store.review(operation,native._validate()))
    f.command('core10-approve-01',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation)
    record['state']='approved_needs_seed';f.write(MARKER,record);f.phase(state,'core10_approved_needs_seed');f.guard(state)
    print('Exact core-only plan registered/reviewed/approved; seed original-user work next, then normal apply.')

def seed():
    state,record,native=context();assert state['phase']=='core10_approved_needs_seed' and record['state']=='approved_needs_seed' and native.config['generation']==5
    private=j.LOCAL/'core10-seed-01.json';assert not private.exists()
    record['state']='seeding_owned_claim';f.write(MARKER,record)
    code='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\nPRIOR_NOTE='+repr(f.load(j.LOCAL/'native-recovery-seed-01.json')['note_id'])+'\n'+(OUT/'seed_native.py').read_text()
    raw=f.native(state,'core10-seed-01',[],code);rows=[json.loads(l.split('MP_CORE10_SEED=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE10_SEED=')];assert len(rows)==1
    f.write(private,rows[0]);f.save('seed.json',dict(result='seeded_original_user_claim_before_core_upgrade',job_id=rows[0]['job_id'],note_id=rows[0]['note_id'],attempts=1,fixture_timeout_seconds=3600,production_timeout_seconds=120,original_input_key_trace_claim_receipt_and_history_retained_privately=True,created_after_approval_before_drain=True))
    record['state']='seeded_ready_to_apply';f.write(MARKER,record);f.phase(state,'core10_seeded_ready_to_apply');f.guard(state)

def apply():
    state,record,native=context();assert state['phase']=='core10_seeded_ready_to_apply' and record['state']=='seeded_ready_to_apply' and native.config['generation']==5
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    record['state']='applying';f.write(MARKER,record);f.phase(state,'core10_applying')
    result=json.loads(f.command('core10-apply-01',prefix+['plugin','apply',record['operation_id'],'--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)],timeout=600));assert result['state']=='completed' and result['traffic_resumed']
    current=f.load(native.target_path);assert current['image_id']==record['image_id'] and current['generation']==6 and current['sites'][0]['database']==state['active_db']
    reader=DockerObserver(current);catalog=Catalog(native.catalog_root,native.validator,readonly=True);after=reader.state(reader.read(),catalog.snapshot())['state'];before=f.load(OUT/'state-before-plan.json')
    assert after['installations']==before['installations'] and after['bindings']==before['bindings']
    f.save('completed.json',result);f.save('state-after.json',after)
    fixture=f.load(j.LOCAL/'fixtures.json')
    for key,space in fixture['workspaces'].items():
        fixture['bindings'][key]=next(b for b in after['bindings'] if b['workspace_id']==space['public_id'] and b['alias']=='documents' and b['consumer_installation_id']==next(i['installation_id'] for i in after['installations'] if i['workspace_id']==space['public_id'] and i['plugin_id']=='org.example.notes'))
    f.write(j.LOCAL/'fixtures.json',fixture)
    state.update(image_id=current['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'core10_completed_needs_verification');f.guard(state)
    print('Normal exact core-only upgrade completed on same populated DB, generation6; original installations/bindings retained.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','seed','apply']);args=parser.parse_args();globals()[args.action]()
