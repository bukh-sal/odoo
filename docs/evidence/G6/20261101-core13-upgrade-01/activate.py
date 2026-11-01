"""Once-only reviewed core13 upgrade, preserving current native plugin inputs."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.release_staging import validate_core_upgrade
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'core13-upgrade-01.json'
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation',
    'mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership',
    'mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,native

def data_snapshot(state,label):
    query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='10s'; SELECT jsonb_build_object("
    query+=','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)
    query+='); ROLLBACK;'
    return json.loads(f.sql(state,label,query))

def candidate():
    state,native=context();assert native.config['generation']==10 and not MARKER.exists()
    build=f.load(ROOT/'docs/evidence/G6/20261101-core13-candidate-01/candidate-build.json')
    assert build['state']=='built' and not build['deployment_changed']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
    old=inspect_image(state['image_id']);new=inspect_image(build['image_id'])
    assert old['platform_version']=='0.1.12' and new['platform_version']=='0.1.13'
    assert old['inventory']['artifacts']==new['inventory']['artifacts']==build['artifacts']
    assert old['inventory']['policy']==new['inventory']['policy']
    assert all(old[k]==new[k] for k in ['python_metadata','python_lock_digest'])
    diff,changes=validate_core_upgrade(old,new,dict(base_image_id=state['image_id'],target_image_id=build['image_id']))
    assert changes==[dict(addon='mp_core',previous_version='19.0.0.1.12',target_version='19.0.0.1.13',migrations=[])]
    assert all(old['native_manifests'][n]==new['native_manifests'][n] for n in old['native_manifests'] if n!='mp_core')
    assert 'mp_example_notes_stats' not in new['native_manifests']
    required=['native_feature_executor','coordinated_feature_metadata','reference_recovery','metadata_executor','external_metadata']
    assert all('packages/platform_sdk/modular_platform/'+n+'.py' in new['inventory']['files'] for n in required)
    f.save('candidate-validation.json',dict(result='passed_exact_core13_candidate',image_id=build['image_id'],inventory_digest=new['inventory_digest'],
        native_core_changes=changes,source_diff=diff,native_plugin_artifacts_and_manifests_exact=True,Python_and_policy_exact=True,
        connector_not_in_image=True,metadata_lifecycle_recovery_and_feature_readers_inventoried=True,deployment_changed=False))
    f.write(MARKER,dict(state='candidate_validated',image_id=build['image_id'],inventory_digest=new['inventory_digest']))
    f.phase(state,'core13_candidate_validated');print('Core13 candidate admitted; native packages/Python/policy exact')

def prepare():
    state,native=context();record=f.load(MARKER);assert record['state']=='candidate_validated' and native.config['generation']==10
    catalog=Catalog(native.catalog_root,native.validator,readonly=True)
    before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==7
    f.save('state-before.json',before)
    data=data_snapshot(state,'core13-preservation-before');f.write(j.LOCAL/'core13-preservation-before.json',data)
    assert len(data['mp_job'])==18 and all(row['state'] in ['completed','dead_letter','cancelled'] for row in data['mp_job'])
    assert not any(row['state']=='leased' for row in data['mp_event_delivery'])
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    record['state']='staging';f.write(MARKER,record);f.phase(state,'core13_staging')
    staged=json.loads(f.command('core13-stage-01',prefix+['plugin','stage-image','--image-id',record['image_id']]+options));f.save('staged-image.json',staged)
    nomination=dict(operation_type='core_upgrade',targets=[{k:r[k] for k in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='deploy') for r in before['installations'] if r['state']=='installed'])
    f.save('nomination.json',nomination)
    bundle=json.loads(f.command('core13-plan-01',prefix+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options));f.save('bundle.json',bundle)
    assert bundle['operation_lock']['native_core_changes']==f.load(OUT/'candidate-validation.json')['native_core_changes']
    assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
    operation=bundle['plan']['operation_id'];record.update(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('core13-register-01',ops+['register','--bundle',str(OUT/'bundle.json')]+validation)
    f.save('independent-review.json',native.store.review(operation,native._validate()))
    f.command('core13-approve-01',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation)
    record['state']='approved';f.write(MARKER,record);f.phase(state,'core13_approved');f.guard(state)
    print('Core13 exact immutable operation independently reconstructed and approved; no mutation yet')

def apply():
    state,native=context();record=f.load(MARKER);assert record['state']=='approved' and native.config['generation']==10
    record['state']='applying';f.write(MARKER,record);f.phase(state,'core13_applying')
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    result=json.loads(f.command('core13-apply-01',prefix+['plugin','apply',record['operation_id'],'--store',str(native.store.root),
        '--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)],timeout=600))
    assert result['state']=='completed' and result['traffic_resumed']
    config=f.load(native.target_path)
    assert config['generation']==11 and config['image_id']==record['image_id'] and config['sites'][0]['database']==state['active_db']
    from modular_platform.deployment import DockerObserver
    reader=DockerObserver(config);after=reader.state(reader.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
    before=f.load(OUT/'state-before.json');assert before['installations']==after['installations'] and before['bindings']==after['bindings']
    f.save('completed.json',result);f.save('state-after.json',after)
    state.update(image_id=config['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_qualification';f.write(MARKER,record)
    f.phase(state,'core13_completed_needs_qualification');f.guard(state)
    print('Reviewed core13 upgrade completed config11; detailed data/queue/file qualification follows')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['candidate','prepare','apply']);args=parser.parse_args();globals()[args.action]()
