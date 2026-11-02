"""One new owned empty database/config/data volume for actual core bootstrap.

Shared existing disposable PostgreSQL/network are explicit; never restore or
reset an existing database. Original data/worker fingerprints must stay exact.
"""
import hashlib,json,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PRIVATE=ROOT/'.local/g7-core21-fresh-registry-01';assert PRIVATE.is_dir()
source=json.loads((ROOT/'.local/g6-events/state.json').read_text())
admission=json.loads((OUT/'candidate-admission.json').read_text());assert admission['result']=='passed_static_candidate_admission'
record=json.loads((PRIVATE/'state.json').read_text());assert record['state']=='creating_owned_config_data' and record['image_id']==admission['image_id']
def phase(value):record['state']=value;(PRIVATE/'state.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(phase=value,project=project)),flush=True)
def command(label,args,raw=None,timeout=180):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=raw,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect exact '+label+' and state; never recreate/retry mutation'
 return (PRIVATE/(label+'.stdout')).read_bytes()
def sql(label,query,db=None):return command(label,['docker','exec','-i',record['shared_pg'],'psql','-X','-qAt','-U','postgres','-d',db or record['source_database'],'-v','ON_ERROR_STOP=1'],query.encode())
tables=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
fingerprint="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT encode(sha256(convert_to(jsonb_build_object("+','.join("'"+name+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+name+" t),'[]'::jsonb)" for name in tables)+")::text,'UTF8')),'hex'); ROLLBACK;"
worker='6e786efe43b7bf5716fd82e276ba7fd95133492dc872b91d6a4ce2807ab8a93d'
def worker_status(label):
 info=json.loads(command(label,['docker','inspect','--type','container',worker]))[0]
 assert info['State']['Running'] and info['Image']=='sha256:5482020e027debc8a7b3d0a413e36417717b60642ea5b38e168aed328af5bbe0'
 return {key:info[key] for key in ['Id','Image','RestartCount']}|dict(started=info['State']['StartedAt'])
before=(PRIVATE/'source-before.stdout').read_text().strip()
i=json.loads((PRIVATE/'worker-before.stdout').read_text())[0]
before_worker={key:i[key] for key in ['Id','Image','RestartCount']}|dict(started=i['State']['StartedAt'])
assert sql('source-before-continuation',fingerprint).strip().decode()==before
assert sql('empty-database-continuation',"SELECT count(*) FROM pg_class WHERE relname='ir_module_module';",record['database']).strip()==b'0'
v=json.loads(command('owned-volume-inspection',['docker','volume','inspect',record['volume']]))[0]
assert v['Labels']['com.modular.disposable']==record['project']
phase('repairing_only_recorded_seed_permissions')
fix="""import configparser,json,os,pathlib,stat,sys
+d=json.load(sys.stdin);root=pathlib.Path('/probe');file=root/'config/odoo_config';data=root/'data'
+p=configparser.ConfigParser();p.read(file);assert p['options']['db_name']==d['database']
+assert file.stat().st_uid==10001 and stat.S_IMODE(file.stat().st_mode)==0o644 and not list(data.iterdir())
+os.chown(file,0,0);file.chmod(0o400);os.chown(file,10001,10001)
+assert data.stat().st_uid==0;data.chmod(0o700);os.chown(data,10001,10001)
+print('Recorded own config/data permissions corrected, no bytes regenerated')
+""".replace('\n+','\n')
command('seed-permissions-continuation',['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+record['volume']+',target=/probe','--entrypoint','/venv/bin/python',record['image_id'],'-B','-c',fix],json.dumps(record).encode())
phase('initializing_fresh_core_registry')
command('initialize-core',['docker','run','--name',record['init_container'],'--label','com.modular.disposable='+project,'--log-driver','none','--network',record['network'],'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1536m','--cpus','2','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+record['volume']+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+record['volume']+',target=/var/lib/modular,volume-subpath=data','--entrypoint','/venv/bin/python',record['image_id'],'odoo-bin','-c','/run/secrets/odoo_config','-d',database,'--no-http','--workers=0','--max-cron-threads=0','-i','mp_shell,auth_password_policy','--stop-after-init','--without-demo'],timeout=300)
modules=json.loads(sql('fresh-modules',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'version',latest_version,'state',state) ORDER BY name) FROM ir_module_module WHERE state!='uninstalled'; ROLLBACK;",database))
assert next(m for m in modules if m['name']=='mp_core')['version']=='19.0.0.1.21'
allowed=set(json.loads((ROOT/'.local/g7-core21-dependencies-image-01/candidate-runtime.json').read_text())['inventory']['native_addons'])
assert all(m['name'] in allowed and m['state']=='installed' for m in modules)
assert sql('source-after',fingerprint).strip().decode()==before and worker_status('worker-after')==before_worker
phase('fresh_core_registry_passed_retained_for_http_and_release_rehearsal')
report=dict(result='passed_empty_database_native_core_initialization',**record,modules=modules,source_17table_sha256=before,source_17tables_worker_exact=True,
 limits=['No HTTP/login/plugin-install/current acceptance pass yet; bootstrap-only registry probe, not approved live deployment.',
 'One new owned database and config/data volume retained for required HTTP/fresh-release follow-up, one terminal init helper needs retirement.',
 'Uses shared PostgreSQL16 process/network and the same trusted DB role; not hostile-native isolation.'])
with (OUT/'fresh-registry.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],database=database,modules=len(modules),original_preserved=True)))
