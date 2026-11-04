"""Observe the retained unmanaged read fixture before any current-image alignment."""
import hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-performance-current-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
def load(p):return json.loads(p.read_bytes())
def write(p,v):
 with p.open('x',encoding='utf8') as stream:json.dump(v,stream,indent=2);stream.write('\n')
assert not PRIVATE.exists();protect_directory(PRIVATE);OUT.mkdir(exist_ok=True)
record=load(ROOT/'.local/g7-performance-10k-01/state.json');assert record['project']=='mp-g7-perf-6fafdba2c44c' and record['database']=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c'
assert record['experimental_fixture_not_approved_deployment'] and record['shared_PostgreSQL_process']
source=load(ROOT/'.local/g6-events/state.json');assert source['project']==record['source_project'] and source['active_db']!=record['database']
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=90)
def sql(database,query):
 assert database in [record['database'],source['active_db']]
 return json.loads(call(['docker','exec',record['source_pg_container'],'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',database,'-c',query]))
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)+');ROLLBACK;'
before=sql(record['database'],query);original=sql(source['active_db'],query);write(PRIVATE/'benchmark-tables-before.json',before);write(PRIVATE/'original-tables-before.json',original)
assert len(before['mp_example_note'])==10006 and len([n for n in before['mp_example_note'] if n['title'].startswith('G7 benchmark note ')])==9976
assert not any(r['state']=='active' for r in before['mp_service_credential'])
fences=sql(record['database'],"SELECT jsonb_build_object('control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c),'params',(SELECT jsonb_object_agg(key,value) FROM ir_config_parameter WHERE key IN ('mp.site_id','mp.deployment_id','mp.release_generation','mp.release_digest','mp.active_inventory_digest')),'profile',(SELECT payload FROM mp_operation_profile LIMIT1));".replace('LIMIT1','LIMIT 1'))
assert all(c['state']=='paused' for c in fences['control']);write(PRIVATE/'benchmark-publication-before.json',fences)
old=inspect_image(record['image_id']);new_id=load(ROOT/'docs/evidence/G7/20261104-core23-repro-01/qualification.json')['reference_image'];new=inspect_image(new_id)
write(PRIVATE/'old-runtime.json',old);write(PRIVATE/'new-runtime.json',new)
modules=sql(record['database'],"SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module WHERE state IN ('installed','to install','to upgrade','to remove');")
assert all(row['state']=='installed' for row in modules);changes=[]
for row in modules:
 name=row['name'];assert name in new['native_manifests'];wanted=new['native_manifests'][name].get('version','1.0');wanted=wanted if wanted.startswith('19.0.') else '19.0.'+wanted
 if row['version']!=wanted:changes.append(dict(addon=name,before=row['version'],after=wanted))
assert changes==[dict(addon='mp_core',before='19.0.0.1.20',after='19.0.0.1.23')],changes
ids=[record['app_id'],record['edge_id'],record['source_pg_container']]
worker=load(ROOT/'.local/g6-events/operator/worker-target.json');worker_project=worker['runtime']['project']
ids+=call(['docker','ps','--no-trunc','-q','--filter','label=com.docker.compose.project='+worker_project]).decode().split();assert len(ids)==4
rows=json.loads(call(['docker','inspect',*ids]));write(PRIVATE/'protected-runtime-before.json',rows)
assert all(row['State']['Running'] for row in rows)
for row in rows[:2]:assert row['Config']['Labels'].get('com.modular.disposable')==record['project']
assert rows[0]['Image']==record['image_id'] and all(m['Destination'] not in ['/run/worker-authority','/var/run/docker.sock'] for m in rows[0]['Mounts'])
assert rows[0]['Config']['Cmd'][-2:]==[record['database'],record['inventory_digest']]
assert 'app' not in (rows[0]['NetworkSettings']['Networks'][record['source_runtime_network']].get('Aliases') or [])
for name in ['volume','edge_network']:
 kind='volume' if name=='volume' else 'network';data=json.loads(call(['docker',kind,'inspect',record[name]]))[0];assert data['Labels'].get('com.modular.disposable')==record['project']
write(PRIVATE/'record-before.json',record)
result=dict(result='read_only_retained_benchmark_preflight_passed',utc=datetime.now(timezone.utc).isoformat(),project=record['project'],database=record['database'],old_image=record['image_id'],new_image=new_id,new_inventory=new['inventory_digest'],native_version_changes=changes,notes=10006,synthetic_notes=9976,source_notes=len(original['mp_example_note']),dispatch_paused=True,copied_technical_credentials_revoked=True,app_issuer_absent=True,shared_PostgreSQL_explicit=True,original_runtime_alias_app_not_used_by_benchmark=True,
 actual_app_limits=dict(memory=rows[0]['HostConfig']['Memory'],nano_cpus=rows[0]['HostConfig']['NanoCpus']),private_snapshot_sha256={name:hashlib.sha256((PRIVATE/name).read_bytes()).hexdigest() for name in ['benchmark-tables-before.json','original-tables-before.json','benchmark-publication-before.json','old-runtime.json','new-runtime.json','protected-runtime-before.json','record-before.json']},limits=['Observation only, no schema/configuration/container/approval changes.','Next controlled benchmark-only fixture alignment needs checkpoint and exact isolated target guards; no product lifecycle approval/recovery claim.'])
write(OUT/'preflight.json',result);print(json.dumps(dict(result=result['result'],changes=changes,notes=10006,new_image=new_id)))
