"""Reviewed immutable core-only upgrade; native plugin bytes stay unchanged."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.release_staging import validate_core_upgrade
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'core11-upgrade-01.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,native

def candidate():
    state,native=context();assert native.config['generation']==8
    if MARKER.exists():assert f.load(MARKER)['state']=='candidate_rejected_platform_mismatch'
    build=f.load(ROOT/'docs/evidence/G6/20261101-core11-candidate-02/candidate-build.json');assert build['state']=='built' and not build['deployment_changed']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in build['source_sha256'].items())
    f.write(MARKER,dict(state='validating',image_id=build['image_id']))
    old=inspect_image(state['image_id']);new=inspect_image(build['image_id'])
    assert old['platform_version']=='0.1.10' and new['platform_version']=='0.1.11'
    assert old['inventory']['artifacts']==new['inventory']['artifacts']==build['artifacts']
    for key in ['python_metadata','python_lock_digest']:assert old[key]==new[key]
    assert old['inventory']['policy']==new['inventory']['policy']
    diff,changes=validate_core_upgrade(old,new,dict(base_image_id=state['image_id'],target_image_id=build['image_id']))
    assert changes==[dict(addon='mp_core',previous_version='19.0.0.1.10',target_version='19.0.0.1.11',migrations=[])]
    assert all(old['native_manifests'][n]==new['native_manifests'][n] for n in old['native_manifests'] if n!='mp_core')
    proof=dict(result='passed_exact_core11_candidate',image_id=build['image_id'],inventory_digest=new['inventory_digest'],native_core_changes=changes,source_diff=diff,all_plugin_artifacts_manifests_exact=True,Python_and_distribution_policy_exact=True,notes_stats_not_in_base_image=True,build_record='docs/evidence/G6/20261101-core11-candidate-02/candidate-build.json',deployment_changed=False)
    assert 'mp_example_notes_stats' not in new['native_manifests']
    f.save('candidate-validation.json',proof);f.write(MARKER,dict(state='candidate_validated',image_id=build['image_id'],inventory_digest=new['inventory_digest']))
    f.phase(state,'core11_candidate_validated');f.guard(state);print('Core1.11 candidate exact; all current native plugin bytes/manifests preserved')

def prepare():
    state,native=context();record=f.load(MARKER);assert record['state']=='candidate_validated' and native.config['generation']==8
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==7
    f.save('state-before.json',before)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    record['state']='staging';f.write(MARKER,record);f.phase(state,'core11_staging')
    staged=json.loads(f.command('core11-stage-01',prefix+['plugin','stage-image','--image-id',record['image_id']]+options));f.save('staged-image.json',staged)
    nomination=dict(operation_type='core_upgrade',targets=[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='deploy') for row in before['installations']]);f.save('nomination.json',nomination)
    bundle=json.loads(f.command('core11-plan-01',prefix+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options));f.save('bundle.json',bundle)
    assert bundle['operation_lock']['native_core_changes']==f.load(OUT/'candidate-validation.json')['native_core_changes']
    assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes'] and len(bundle['operation_lock']['targets'])==7
    operation=bundle['plan']['operation_id'];record.update(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('core11-register-01',ops+['register','--bundle',str(OUT/'bundle.json')]+validation)
    f.save('independent-review.json',native.store.review(operation,native._validate()))
    f.command('core11-approve-01',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation)
    record['state']='approved';f.write(MARKER,record);f.phase(state,'core11_approved');f.guard(state);print('Exact core-only upgrade reviewed/approved with coordinated checkpoint; no plugin/grant change')

def apply():
    state,native=context();record=f.load(MARKER);assert record['state']=='approved' and native.config['generation']==8
    record['state']='applying';f.write(MARKER,record);f.phase(state,'core11_applying')
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    result=json.loads(f.command('core11-apply-01',prefix+['plugin','apply',record['operation_id'],'--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)],timeout=600))
    assert result['state']=='completed' and result['traffic_resumed'];config=f.load(native.target_path)
    assert config['generation']==9 and config['image_id']==record['image_id'] and config['sites'][0]['database']==state['active_db']
    reader=DockerObserver(config);catalog=Catalog(native.catalog_root,native.validator,readonly=True);after=reader.state(reader.read(),catalog.snapshot())['state'];before=f.load(OUT/'state-before.json')
    assert before['installations']==after['installations'] and before['bindings']==after['bindings']
    f.save('completed.json',result);f.save('state-after.json',after)
    state.update(image_id=config['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_qualification';f.write(MARKER,record);f.phase(state,'core11_completed_needs_qualification');f.guard(state)
    print('Normal approved immutable core1.11 upgrade completed config9; original plugin scopes/bindings retained')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['candidate','prepare','apply']);args=parser.parse_args();globals()[args.action]()
