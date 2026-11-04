"""Ordinary current-reference core24 preparation/approval/apply, never a replay."""
import argparse,hashlib,json,os,sqlite3,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;REFERENCE=ROOT/'.local/release-kit-rehearsal/private/reference';PRIVATE=ROOT/'.local/g7-core24-accessibility-01/maintenance'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular import configuration
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.catalog import Catalog
from modular_platform.worker_operator import WorkerPlanningReader
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular_platform.plans import data_digest

def load(p):return json.loads(p.read_bytes())
def create(p,value):
 with p.open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.write('\n')
def phase(state,value):
 state['phase']=value;state['updated_at']=datetime.now(timezone.utc).isoformat();temporary=PRIVATE/'state.tmp';create(temporary,state);os.replace(temporary,PRIVATE/'state.json')
def call(label,args,*,input=None,timeout=90):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:
  result=subprocess.run(args,input=input,stdout=out,stderr=err,timeout=timeout)
 if result.returncode:raise RuntimeError('Command '+label+' failed; inspect protected streams, no automatic replay')
 return (PRIVATE/(label+'.stdout')).read_bytes()
def context():
 operator=REFERENCE/'operator';catalog=ROOT/'.local/release-kit-rehearsal/private/catalog';assert catalog.is_dir();return StagedNativeExecutor(OperatorStore(operator/'control'),operator/'target.json',catalog,configuration(operator/'trust.json'))
def cli():return [sys.executable,'-X','utf8',str(ROOT/'tools/modular.py'),'--config',str(REFERENCE/'operator/trust.json')]
def options(native):return ['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def validation(native):return ['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def snapshot(label,native):
 tables=list(load(ROOT/'.local/g7-ui-qualification-01/tables-before.json'))
 query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in tables)+');ROLLBACK;'
 return json.loads(call(label,['docker','exec',native.config['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',native.config['sites'][0]['database'],'-c',query]))
def worker(native):
 reader=WorkerPlanningReader(native.store,native.target_path,native.target_path.with_name('worker-target.json'));document=reader.publisher._document();entry=document['endpoints'][0];observed=reader.observer(entry['descriptor'],reader.publisher._key_digest(entry['descriptor']),entry['key_id']);row=json.loads(subprocess.check_output(['docker','inspect',observed['container_id']],stderr=subprocess.PIPE,timeout=30))[0]
 return dict(id=row['Id'],image=row['Image'],started=row['State']['StartedAt'],restarts=row['RestartCount'],mounts=row['Mounts'],networks=row['NetworkSettings']['Networks'],publication=data_digest(document))
def prepare(resume=False):
 if resume:
  assert load(PRIVATE/'state.json')['phase']=='observing' and {p.name for p in PRIVATE.iterdir()}=={'state.json'}
 else:
  assert not PRIVATE.exists();protect_directory(PRIVATE)
 OUT.mkdir(exist_ok=True)
 native=context();admission=load(OUT.parent/'20261104-core24-accessibility-image-01/candidate-admission.json');assert native.config['generation']==4 and native.config['image_id']==admission['base_image_id']
 with sqlite3.connect('file:'+native.store.database.as_posix()+'?mode=ro',uri=True) as db:assert not db.execute("SELECT operation_id FROM operations WHERE state IN ('running','approved','recovery_required')").fetchall()
 state=dict(phase='observing',base_generation=4,base_image=native.config['image_id'],image_id=admission['image_id'],inventory_digest=admission['inventory_digest'])
 if resume:assert load(PRIVATE/'state.json')==state
 else:create(PRIVATE/'state.json',state)
 catalog=Catalog(native.catalog_root,native.validator,readonly=True);observation=native.observer.read();before=native.observer.state(observation,catalog.snapshot())['state'];create(PRIVATE/'state-before.json',before)
 data=snapshot('data-before',native);assert len(data['mp_job'])==1 and data['mp_job'][0]['state']=='completed';assert data==load(ROOT/'.local/g7-ui-qualification-01/tables-before.json');create(PRIVATE/'data-before.json',data);create(PRIVATE/'worker-before.json',worker(native));create(PRIVATE/'target-before.json',native.config);create(PRIVATE/'worker-target-before.json',load(native.target_path.with_name('worker-target.json')))
 modules=json.loads(call('modules-before',['docker','exec',native.config['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',native.config['sites'][0]['database'],'-c',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"]));create(PRIVATE/'modules-before.json',modules)
 files=json.loads(call('files-before',['docker','exec',native.config['worker_id'],'/venv/bin/python','-c',FILE_OBSERVATION,native.config['sites'][0]['database']]));create(PRIVATE/'files-before.json',files)
 phase(state,'staging_image');staged=json.loads(call('stage',cli()+['plugin','stage-image','--image-id',state['image_id']]+options(native)));create(OUT/'staged-image.json',staged);assert staged['base_image_id']==state['base_image'] and staged['target_image_id']==state['image_id'];phase(state,'image_staged')
 native_plugins={p['plugin_id'] for p in before['release_lock']['plugins'] if p['runtime']=='native'}
 targets=[{key:i[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='deploy') for i in before['installations'] if i['state']=='installed' and i['plugin_id'] in native_plugins]
 assert len(native_plugins)==4 and len(targets)==7,(len(native_plugins),len(targets))
 create(OUT/'nomination.json',dict(operation_type='core_upgrade',targets=targets));phase(state,'preparing_plan');bundle=json.loads(call('plan',cli()+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options(native)));create(OUT/'bundle.json',bundle)
 assert bundle['operation_lock']['native_core_changes']==admission['native_changes'] and bundle['operation_lock'].get('python_dependency_changes') is None
 assert not bundle['plan']['permission_changes'] and bundle['plan']['destructive'] and bundle['plan']['backup']['required']
 assert bundle['operation_lock']['bindings']==before['bindings'] and bundle['operation_lock']['endpoints']==before['endpoints']
 state.update(operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],native_scopes=len(targets));phase(state,'plan_prepared')
 call('register',cli()+['operations','--store',str(native.store.root),'register','--bundle',str(OUT/'bundle.json')]+validation(native));phase(state,'registered')
 review=native.store.review(state['operation_id'],native._validate());create(OUT/'independent-review.json',review);phase(state,'independently_reviewed_not_approved')
 assert snapshot('data-after-review',native)==data and worker(native)==load(PRIVATE/'worker-before.json')
 create(OUT/'preparation.json',dict(result='core24_seven_native_scopes_staged_registered_independently_reviewed_not_approved',operation_id=state['operation_id'],plan_hash=state['plan_hash'],native_plugins=sorted(native_plugins),native_scopes=7,native_changes=admission['native_changes'],all17_tables_exact=True,independent_worker_exact=True,external_provider_unchanged=True,no_permission_binding_endpoint_change=True,backup_required=True,destructive_review_required=True,limits=['No approval/apply yet. Native core maintenance marked destructive conservatively; schema migrations empty. No destructive uninstall or packaged plugin change.']))
 print(json.dumps(dict(result='independently_reviewed_not_approved',operation_id=state['operation_id'],plan_hash=state['plan_hash'],native_scopes=7)))
def resume_prepare():prepare(resume=True)
def approve():
 native=context();state=load(PRIVATE/'state.json');assert state['phase']=='independently_reviewed_not_approved' and native.config['generation']==4
 phase(state,'approving');result=json.loads(call('approve',cli()+['operations','--store',str(native.store.root),'approve',state['operation_id'],'--plan-hash',state['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation(native)));assert result['state']=='approved';create(OUT/'approval-status.json',result);phase(state,'approved');print(json.dumps(dict(result='exact_independent_core24_approval_recorded',operation_id=state['operation_id'])))
def apply():
 native=context();state=load(PRIVATE/'state.json');assert state['phase']=='approved' and native.config['generation']==4
 phase(state,'applying');result=json.loads(call('apply',cli()+['plugin','apply',state['operation_id']]+options(native),timeout=600));create(OUT/'completed.json',result);assert result['state']=='completed' and result['traffic_resumed']
 target=load(native.target_path);assert target['generation']==5 and target['image_id']==state['image_id'];phase(state,'completed_needs_installed_verification');print(json.dumps(dict(result='core24_actual_maintenance_completed_needs_verification',operation_id=state['operation_id'],generation=5,image=state['image_id'])))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','resume-prepare','approve','apply']);args=parser.parse_args();globals()[args.action.replace('-','_')]()
