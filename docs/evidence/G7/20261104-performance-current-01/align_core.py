"""Explicit current-schema initialization of the recorded unmanaged read fixture."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();PRIVATE=ROOT/'.local/g7-performance-current-01';OUT=Path(__file__).parent
def load(p):return json.loads(p.read_bytes())
record=load(PRIVATE/'record-before.json');state=load(PRIVATE/'alignment.json');assert state['phase']=='checkpointed_existing_unmanaged_fixture'
assert record['project']=='mp-g7-perf-6fafdba2c44c' and record['database']=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c'
for key,name in [('database','database.dump'),('private_combined_volume','volume.tar.gz')]:assert hashlib.sha256((PRIVATE/'checkpoints'/name).read_bytes()).hexdigest()==state['checkpoints'][key]['sha256']
def command(label,args,*,data=None,timeout=120,output_path=None):
 path=output_path or PRIVATE/'logs'/(label+'.stdout')
 with path.open('xb') as out,(PRIVATE/'logs'/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=data,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect existing child/native DB/phase; never replay initialization'
 return path.read_bytes()
rows=json.loads(command('pre-alignment-stopped-containers',['docker','inspect',record['app_id'],record['edge_id']]))
assert all(not r['State']['Running'] and r['Config']['Labels']['com.modular.disposable']==record['project'] for r in rows)
name=record['project']+'-core23-fixture-alignment';assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0
native_guard="""import configparser,hashlib,json,os,pathlib,psycopg2,sys
database,inventory=sys.argv[1:]
assert database=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c'
assert 'sha256:'+hashlib.sha256(pathlib.Path('/opt/modular/distribution-inventory.json').read_bytes()).hexdigest()==inventory
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
assert options['db_name']==database and options['dbfilter']=='^'+database+'$' and options['max_cron_threads']=='0'
assert options['db_host']=='db' and options['addons_path']=='/opt/modular/addons' and options['server_wide_modules']=='base,web'
assert not pathlib.Path('/run/worker-authority').exists() and not pathlib.Path('/var/run/docker.sock').exists()
connection=psycopg2.connect(host=options['db_host'],port=options['db_port'],user=options['db_user'],password=options['db_password'],dbname=database)
connection.set_session(readonly=True,autocommit=True)
with connection.cursor() as cursor:
 cursor.execute('SELECT current_database()');assert cursor.fetchone()==(database,)
 cursor.execute("SELECT latest_version,state FROM ir_module_module WHERE name='mp_core'");assert cursor.fetchone()==('19.0.0.1.20','installed')
 cursor.execute('SELECT count(*) FROM mp_example_note');assert cursor.fetchone()==(10006,)
 cursor.execute("SELECT count(*) FROM mp_service_credential WHERE state='active'");assert cursor.fetchone()==(0,)
 cursor.execute("SELECT count(*) FROM mp_dispatch_control WHERE state<>'paused'");assert cursor.fetchone()==(0,)
connection.close()
os.execv('/venv/bin/python',['/venv/bin/python','odoo-bin','-c','/run/secrets/odoo_config','-d',database,'--no-http','--workers=0','--max-cron-threads=0','--stop-after-init','--without-demo','-u','mp_core'])
"""
state['phase']='initializing_current_core_in_checkpointed_unmanaged_fixture';state['native_child_name']=name;(PRIVATE/'alignment.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
command('initialize-current-core',['docker','run','--name',name,'--label','com.modular.disposable='+record['project'],'--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1536m','--cpus','2','--pids-limit','256','--tmpfs','/tmp','--network',record['source_runtime_network'],
 '--mount','type=volume,source='+record['volume']+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+record['volume']+',target=/var/lib/modular,volume-subpath=data','--entrypoint','/venv/bin/python',state['target_image'],'-c',native_guard,record['database'],state['target_inventory']],timeout=300)
before=load(PRIVATE/'benchmark-tables-before.json');original=load(PRIVATE/'original-tables-before.json')
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
def sql(label,db,query,*,output_path=None):return json.loads(command(label,['docker','exec',record['source_pg_container'],'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',db,'-c',query],output_path=output_path))
after=sql('benchmark-after-core',record['database'],query,output_path=PRIVATE/'benchmark-tables-after-core.json');source=load(ROOT/'.local/g6-events/state.json');source_after=sql('original-after-core',source['active_db'],query,output_path=PRIVATE/'original-tables-after-core.json')
assert after==before and source_after==original,'Inspect extra business/authority/queue changes; do not publish or restart'
version=sql('native-core-version',record['database'],"SELECT jsonb_build_object('version',latest_version,'state',state) FROM ir_module_module WHERE name='mp_core';");assert version==dict(version='19.0.0.1.23',state='installed')
state['phase']='current_core_initialized_tables_exact_needs_publication';(PRIVATE/'alignment.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
report=dict(result='current_unmanaged_fixture_core_initialized_with_exact17table_preservation',utc=datetime.now(timezone.utc).isoformat(),project=record['project'],database=record['database'],image=state['target_image'],inventory=state['target_inventory'],native_version=version,benchmark17tables_exact=True,original17tables_exact=True,notes=10006,workspace_target_notes=10000,issuer_not_mounted=True,dispatch_and_credentials_unchanged=True,native_child=name,limits=['Benchmark test-fixture initialization under ADR0054, not an independent product lifecycle upgrade/recovery qualification.','Fixture remains stopped; guarded current app/client-release publication and actual measurements remain required.'])
with (OUT/'core-alignment.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],native_version=version,benchmark17tables_exact=True,original17tables_exact=True)))
