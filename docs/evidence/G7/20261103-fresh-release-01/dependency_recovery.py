"""Actual dependency-changing native fault in the one owned qualification realm."""
import argparse,hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
from fixture import ROOT,OUT,LOCAL,f,OLD,NEW
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.restore_continuation import FILE_OBSERVATION
PUBLIC=OUT/'dependency-recovery';PRIVATE=LOCAL/'dependency-recovery';MARKER=PRIVATE/'state.json';f.OUTPUT=PUBLIC
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
def context():
 state=f.load(LOCAL/'state.json');f.guard(state)
 return state,StagedNativeExecutor(OperatorStore(LOCAL/'operator/control'),LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'))
def prefix():return [sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'operator/trust.json')]
def options(native):return ['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def validation(native):return ['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def snapshot(state,label):
 presence=json.loads(f.sql(state,label+'-presence',"BEGIN READ ONLY;SELECT jsonb_object_agg(n,to_regclass(n) IS NOT NULL) FROM unnest(ARRAY["+','.join("'"+t+"'" for t in TABLES)+"]) n;ROLLBACK;"))
 present=[t for t in TABLES if presence[t]]
 query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in present)+');ROLLBACK;'
 rows=json.loads(f.sql(state,label,query));return {t:rows.get(t) for t in TABLES}
def schema(state,label):
 query="BEGIN READ ONLY;SELECT encode(sha256(convert_to(jsonb_agg(v ORDER BY v::text)::text,'UTF8')),'hex') FROM (SELECT jsonb_build_array(c.relname,c.relkind,a.attname,a.atttypid::regtype::text,a.attnotnull) v FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE n.nspname='public' AND c.relkind IN ('r','p','S')) s;ROLLBACK;"
 return f.sql(state,label,query).decode().strip()
def seed():
 state,native=context();assert state['phase']=='references_installed' and native.config['generation']==2 and state['image_id']==OLD
 assert not PRIVATE.exists() and not PUBLIC.exists();protect_directory(PRIVATE);PUBLIC.mkdir()
 f.write(MARKER,dict(state='seeding',baseline_image=OLD,target_image=NEW,original_database=state['active_db']))
 code='FIXTURE='+repr(f.load(LOCAL/'fixtures.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'+(OUT/'seed_native.py').read_text()
 raw=f.native(state,'g7-recovery-seed01',[],code)
 rows=[json.loads(line.split('MP_G7_RECOVERY_SEED=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_G7_RECOVERY_SEED=')];assert len(rows)==1
 f.write(PRIVATE/'seed.json',rows[0]);f.save('seed.json',dict(result='seeded_actual_native_reference_history',**rows[0]))
 before=snapshot(state,'g7-recovery-seed-data');assert len(before['mp_example_note'])==4 and len(before['mp_example_canvas_board'])==1 and len(before['mp_job'])==1 and before['mp_job'][0]['state']=='completed'
 f.write(PRIVATE/'before.json',before);f.write(PRIVATE/'schema.json',dict(sha256=schema(state,'g7-recovery-seed-schema')))
 modules=json.loads(f.sql(state,'g7-recovery-seed-modules',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"));f.write(PRIVATE/'modules.json',modules)
 files=json.loads(f.command('g7-recovery-seed-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]));assert files and rows[0]['attachment_store_fname'] in files
 f.write(PRIVATE/'files.json',files);r=f.load(MARKER);r['state']='seeded';f.write(MARKER,r);f.phase(state,'g7_recovery_seeded');print('Real4Notes/1minimalCanvas/attachment/original-actor completed job and exact baseline captured',flush=True)
def prepare():
 state,native=context();r=f.load(MARKER);assert r['state']=='seeded' and native.config['generation']==2 and native.config['image_id']==OLD
 staged=json.loads(f.command('g7-recovery-stage',prefix()+['plugin','stage-image','--image-id',NEW]+options(native)));f.save('staged-image.json',staged)
 catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot();observation=native.observer.read();before=native.observer.state(observation,catalog)['state'];f.save('state-before.json',before)
 plugins={p['plugin_id'] for p in before['release_lock']['plugins'] if p['runtime']=='native'}
 targets=[{k:row[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='deploy') for row in before['installations'] if row['state']=='installed' and row['plugin_id'] in plugins];assert len(targets)==6
 f.save('nomination.json',dict(operation_type='core_upgrade',targets=targets))
 bundle=json.loads(f.command('g7-recovery-plan',prefix()+['plugin','plan-staged','--input',str(PUBLIC/'nomination.json')]+options(native)));f.save('bundle.json',bundle)
 changes=bundle['operation_lock']['python_dependency_changes'];assert changes and changes==f.load(ROOT/'docs/evidence/G7/20261103-core21-dependencies-image-01/candidate-admission.json')['python_dependency_changes']
 assert bundle['plan']['destructive'] and bundle['plan']['backup']['required']
 r.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(MARKER,r)
 ops=prefix()+['operations','--store',str(native.store.root)]
 f.command('g7-recovery-register',ops+['register','--bundle',str(PUBLIC/'bundle.json')]+validation(native))
 review=native.store.review(r['operation_id'],native._validate());assert review['plan_hash']==r['plan_hash'];f.save('independent-review.json',review)
 f.command('g7-recovery-approve',ops+['approve',r['operation_id'],'--plan-hash',r['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation(native))
 r['state']='approved';f.write(MARKER,r);f.phase(state,'g7_dependency_fault_approved');print('Exact real old31→new570 dependency plan independently reviewed/approved',flush=True)
class InjectedDependencyCommitFault(RuntimeError):pass
def fault():
 state,native=context();r=f.load(MARKER);assert r['state']=='approved' and native.config['image_id']==OLD
 original=native._private_command
 def command(arguments,path,**kwargs):
  result=original(arguments,path,**kwargs)
  if Path(path).name=='native.log':
   f.write(PRIVATE/'fault-boundary.json',dict(state='real_new570_native_child_exit0_before_metadata',operation_id=r['operation_id']))
   raise InjectedDependencyCommitFault('Owned dependency-changing post-native-commit fault')
  return result
 r['state']='applying';f.write(MARKER,r);f.phase(state,'g7_dependency_fault_applying')
 with patch.object(native,'_private_command',side_effect=command):
  try:native.apply(r['operation_id'])
  except InjectedDependencyCommitFault:pass
  else:raise AssertionError('Real post-native-commit fault boundary not reached')
 status=native.store.status(r['operation_id']);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
 stage=native.store.root/'stages'/r['operation_id'];manifest=f.load(native.store.root/'checkpoints'/r['operation_id']/'manifest.json');fence=f.load(stage/'dispatch-fence/fence.json')['result']
 assert manifest['dispatch_profile']==fence['after'] and fence['after']['control']['state']=='paused'
 r['state']='recovery_required';f.write(MARKER,r);f.phase(state,'g7_dependency_requires_fresh_restore')
 f.save('fault.json',dict(result='actual_dependency_changing_native_postcommit_fault',operation_id=r['operation_id'],status=status,checkpoint_dispatch_profile=manifest['dispatch_profile'],native_child_exit0=True,baseline_image=OLD,target_image=NEW,traffic_closed=True,original_working_deployment_untouched=True))
 print('Actual dependency-native child committed; recovery_required with traffic/dispatch closed',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seed','prepare','fault']);a=p.parse_args();globals()[a.action]()
