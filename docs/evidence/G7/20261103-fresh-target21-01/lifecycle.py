"""Fresh ordinary metadata registration/enable and native reference connector."""
import argparse,copy,json,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from target import ROOT,OUT,LOCAL,f,NEW
from worker import IMAGE,PRIVATE as WORKER_PRIVATE
from modular import configuration
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator,operator_observer
from modular_platform.catalog import Catalog
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
from modular_platform.profile_channel import publish_profile
from modular_platform.plans import data_digest
PRIVATE=LOCAL/'reference-lifecycle';PUBLIC=OUT/'reference-lifecycle';f.OUTPUT=PUBLIC
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
def context(action):
 state=f.load(LOCAL/'state.json');f.guard(state);kind=NativeExecutor if action=='connector' else ReferenceMetadataExecutor
 return state,kind(OperatorStore(LOCAL/'operator/control'),LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'))
def prefix():return [sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'operator/trust.json')]
def options(native):return ['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def validation(native):return ['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def path(action):return PRIVATE/(action+'.json')
def phase(r,state,action):r['state']=state;f.write(path(action),r)
def snapshot(state,label):
 query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)+');ROLLBACK;'
 return json.loads(f.sql(state,label,query))
def worker(native,label):
 op=WorkerOperator(native.store,native.target_path,LOCAL/'operator/worker-target.json');entry=op.publisher._document()['endpoints'][0]
 a=op.observer(entry['descriptor'],op.publisher._key_digest(entry['descriptor']),entry['key_id']);row=json.loads(f.command(label,['docker','inspect',a['container_id']]))[0]
 return dict(id=row['Id'],image=row['Image'],started=row['State']['StartedAt'],restarts=row['RestartCount'],mounts=row['Mounts'],networks=row['NetworkSettings']['Networks'],publication=data_digest(op.publisher._document()))
def prepare(action):
 state,native=context(action);assert native.config['generation']==(2 if action=='register' else 3)
 if not PRIVATE.exists():assert action=='register';protect_directory(PRIVATE);PUBLIC.mkdir()
 assert not path(action).exists() and f.load(WORKER_PRIVATE/'state.json')['state']=='published_healthy'
 if action=='enable':assert f.load(path('register'))['state']=='verified'
 if action=='connector':assert f.load(path('enable'))['state']=='verified'
 scope=f.load(WORKER_PRIVATE/'state.json')['scope'];before=snapshot(state,'fresh-'+action+'-before');assert before['mp_job']==[] and before['mp_example_note']==[]
 f.write(PRIVATE/(action+'-before.json'),before);f.write(PRIVATE/(action+'-worker-before.json'),worker(native,'fresh-'+action+'-worker-before'))
 modules=json.loads(f.sql(state,'fresh-'+action+'-modules-before',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"));f.write(PRIVATE/(action+'-modules-before.json'),modules)
 f.save(action+'-profile.json',publish_profile(operator_observer(native.store,native.target_path),Catalog(native.catalog_root,native.validator,readonly=True)))
 r=dict(scope=scope,base_generation=native.config['generation']);phase(r,'preparing',action)
 catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot()
 if action=='connector':
  observer=operator_observer(native.store,native.target_path);obs=observer.read();document=observer.state(obs,catalog);fixture=f.load(LOCAL/'fixtures.json')
  targets=[dict(installation_id=installation_id(obs['sites'][0],'org.example.notes_stats'),site_id=state['site_id'],workspace_id=w['public_id'],plugin_id='org.example.notes_stats',action='install') for w in fixture['workspaces'].values()]
  bundle=prepare_current_install_targets(document,obs['sites'],catalog,activation_targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
 else:
  nomination=dict(operation_type='install' if action=='register' else 'enable',targets=[dict(**scope,plugin_id='org.example.document_stats',action='install' if action=='register' else 'enable')])
  if action=='register':
   chosen=[c for c in catalog if c['plugin_id']=='org.example.document_stats' and c['version']=='0.1.3'];assert len(chosen)==1
   nomination.update(selections=[dict(plugin_id='org.example.document_stats',version='0.1.3',digest=chosen[0]['digest'])],feature_states=[dict(**scope,availability='suspended')])
  f.save(action+'-nomination.json',nomination);bundle=json.loads(f.command('fresh-'+action+'-plan',prefix()+['plugin','plan-external','--input',str(PUBLIC/(action+'-nomination.json'))]+options(native)))
 f.save(action+'-bundle.json',bundle);r.update(operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);phase(r,'prepared',action)
 ops=prefix()+['operations','--store',str(native.store.root)]
 f.command('fresh-'+action+'-register',ops+['register','--bundle',str(PUBLIC/(action+'-bundle.json'))]+validation(native))
 review=native.store.review(r['operation_id'],native._validate());assert review['plan_hash']==r['plan_hash'];f.save(action+'-review.json',review)
 f.command('fresh-'+action+'-approve',ops+['approve',r['operation_id'],'--plan-hash',r['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+validation(native))
 phase(r,'approved',action);print(action+': ordinary exact independently reconstructed/reviewed/approved',flush=True)
def apply(action):
 state,native=context(action);r=f.load(path(action));assert r['state']=='approved';phase(r,'applying',action)
 result=json.loads(f.command('fresh-'+action+'-apply',prefix()+['plugin','apply',r['operation_id']]+options(native),timeout=600));f.save(action+'-completed.json',result)
 assert result['state']=='completed' and result['traffic_resumed'];phase(r,'completed_needs_verification',action);print(action+': ordinary executor completed; verify next',flush=True)
def verify(action):
 state,native=context(action);r=f.load(path(action));assert r['state']=='completed_needs_verification'
 before=f.load(PRIVATE/(action+'-before.json'));after=snapshot(state,'fresh-'+action+'-after')
 unchanged=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_service_credential','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
 assert all(after[t]==before[t] for t in unchanged)
 assert worker(native,'fresh-'+action+'-worker-after')==f.load(PRIVATE/(action+'-worker-before.json'))
 modules=json.loads(f.sql(state,'fresh-'+action+'-modules-after',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"));old=f.load(PRIVATE/(action+'-modules-before.json'))
 if action=='connector':
  previous=next(x for x in old if x['name']=='mp_example_notes_stats');current=next(x for x in modules if x['name']==previous['name']);assert previous['state']=='uninstalled' and current['state']=='installed' and current['version']=='19.0.0.1.1';previous.update(current)
 assert modules==old
 before_inst=len(before['mp_plugin_installation']);assert len(after['mp_plugin_installation'])==before_inst+(0 if action=='enable' else 1)
 plugin='org.example.notes_stats' if action=='connector' else 'org.example.document_stats';inst=next(x for x in after['mp_plugin_installation'] if x['plugin_id']==plugin)
 assert inst['state']=='installed' and inst['version']==('0.1.1' if action=='connector' else '0.1.3')
 features=[x for x in after['mp_workspace_plugin'] if x['installation_id']==inst['id']];assert len(features)==(2 if action=='connector' else 1) and all(x['availability']==('suspended' if action=='register' else 'enabled') for x in features)
 assert native.config['generation']==(4 if action=='connector' else 3)
 f.save(action+'-preservation.json',dict(result='passed_fresh_reference_'+action,operation_id=r['operation_id'],configuration_generation=native.config['generation'],all12_business_actor_event_job_tables_exact=True,independent_worker_image_process_key_mounts_network_publication_exact=True,only_expected_native_module_installed=action=='connector',other_native_modules_versions_exact=True,plugin=plugin,version=inst['version'],features=len(features),availability=features[0]['availability'],counts={t:len(rows) for t,rows in after.items()},metadata_controls_no_runtime=True))
 phase(r,'verified',action);f.phase(state,'fresh_target21_'+action+'_verified');print(action+': expected fresh registration/features/modules and exact worker/data verified',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['register','enable','connector']);p.add_argument('step',choices=['prepare','apply','verify']);a=p.parse_args();globals()[a.step](a.action)
