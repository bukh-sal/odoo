"""Normal reviewed core23 maintenance on the existing fresh qualification site."""
import argparse,json,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker,LOCAL,prefix,options,validation
from modular_platform.operator_os import protect_directory
from modular_platform.catalog import Catalog
from modular_platform.restore_continuation import FILE_OBSERVATION
PRIVATE=LOCAL/'core23-maintenance';f.OUTPUT=OUT

def prepare():
 state,native=context('connector');assert native.config['generation']==5 and native.config['image_id']==state['image_id']
 assert not PRIVATE.exists();protect_directory(PRIVATE)
 admission=f.load(ROOT/'docs/evidence/G7/20261104-core23-uninstall-image-03/candidate-admission.json');assert admission['result']=='passed_static_candidate_admission'
 r=dict(state='observing',image_id=admission['image_id'],inventory_digest=admission['inventory_digest'],base_generation=5);f.write(PRIVATE/'state.json',r)
 catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot();before=native.observer.state(native.observer.read(),catalog)['state'];f.save('state-before.json',before)
 data=snapshot(state,'core23-data-before');assert len(data['mp_job'])==1 and all(j['state']=='completed' for j in data['mp_job']) and not any(e['state']=='leased' for e in data['mp_event_delivery']);f.write(PRIVATE/'data-before.json',data);f.write(PRIVATE/'worker-before.json',worker(native,'core23-worker-before'))
 f.write(PRIVATE/'modules-before.json',json.loads(f.sql(state,'core23-modules-before',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;")))
 f.write(PRIVATE/'files-before.json',json.loads(f.command('core23-files-before',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']])))
 staged=json.loads(f.command('core23-stage',prefix()+['plugin','stage-image','--image-id',r['image_id']]+options(native)));f.save('staged-image.json',staged);assert staged['base_image_id']==state['image_id'] and staged['target_image_id']==r['image_id']
 plugins={p['plugin_id'] for p in before['release_lock']['plugins'] if p['runtime']=='native'};targets=[{k:i[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='deploy') for i in before['installations'] if i['state']=='installed' and i['plugin_id'] in plugins];assert len(targets)==8
 f.save('nomination.json',dict(operation_type='core_upgrade',targets=targets));bundle=json.loads(f.command('core23-plan',prefix()+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options(native)));f.save('bundle.json',bundle)
 assert bundle['operation_lock']['native_core_changes']==admission['native_changes'] and bundle['operation_lock'].get('python_dependency_changes') is None and admission['python_dependency_changes'] is None
 assert not bundle['plan']['permission_changes'] and bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and bundle['operation_lock']['bindings']==before['bindings'] and bundle['operation_lock']['endpoints']==before['endpoints']
 r.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(PRIVATE/'state.json',r)
 ops=prefix()+['operations','--store',str(native.store.root)];f.command('core23-register',ops+['register','--bundle',str(OUT/'bundle.json')]+validation(native));f.save('independent-review.json',native.store.review(r['operation_id'],native._validate()))
 f.command('core23-approve',ops+['approve',r['operation_id'],'--plan-hash',r['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation(native));r['state']='approved';f.write(PRIVATE/'state.json',r);f.guard(state)
 print(json.dumps(dict(result='core23_exact_independent_review_approved',operation_id=r['operation_id'],plan_hash=r['plan_hash'],native_scopes=8)))

def apply():
 state,native=context('connector');r=f.load(PRIVATE/'state.json');assert r['state']=='approved' and native.config['generation']==5
 r['state']='applying';f.write(PRIVATE/'state.json',r)
 value=json.loads(f.command('core23-apply',prefix()+['plugin','apply',r['operation_id']]+options(native),timeout=600));f.save('completed.json',value);assert value['state']=='completed' and value['traffic_resumed']
 config=f.load(native.target_path);assert config['generation']==6 and config['image_id']==r['image_id'];state.update(image_id=r['image_id'],inventory_digest=r['inventory_digest']);f.phase(state,'core23_completed_needs_verification');r['state']='completed_needs_verification';f.write(PRIVATE/'state.json',r);f.guard(state)
 print('Actual reviewed core23 maintenance completed; installed/native/HTTP/preservation checks pending')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','apply']);a=p.parse_args();globals()[a.action]()
