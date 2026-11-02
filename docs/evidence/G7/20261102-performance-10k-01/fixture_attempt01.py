"""Once-only owned logical read fixture; no mutation of the source database."""
import configparser,hashlib,importlib.util,json,re,socket,sys,time,urllib.request
from pathlib import Path
from uuid import uuid4
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('perf10k_source',OUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest
f=m.f;f.OUTPUT=OUT;PRIVATE=ROOT/'.local/g7-performance-10k-01'

VOLUME_SEED=r'''import configparser,hashlib,json,os,pathlib,re,shutil,sys
d=json.load(sys.stdin);root=pathlib.Path('/probe');assert not list(root.iterdir())
p=configparser.ConfigParser();p.read('/source-config/odoo_config');assert p['options']['db_name']==d['source_database']
p['options'].update(db_name=d['database'],dbfilter='^'+d['database']+'$',workers='2',max_cron_threads='0')
for name in ['config','data','edge']:(root/name).mkdir()
with (root/'config/odoo_config').open('x') as stream:p.write(stream)
(root/'config/odoo_config').chmod(0o444)
source=pathlib.Path('/source-data/filestore')/d['source_database'];assert source.is_dir()
assert not any(p.is_symlink() for p in source.rglob('*'))
destination=root/'data/filestore'/d['database'];shutil.copytree(source,destination)
for path in [root/'data',*(root/'data').rglob('*')]:os.chown(path,10001,10001)
proxy=pathlib.Path('/source-proxy/default.conf').read_text();assert 'app:8069' in proxy
proxy=re.sub(r'app:(8069|8072)',lambda v:d['app']+':'+v.group(1),proxy)
assert 'app:8069' not in proxy
(root/'edge/default.conf').write_text(proxy);(root/'edge/default.conf').chmod(0o444)
print(json.dumps(dict(files={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.rglob('*') if p.is_file()},proxy_sha256=hashlib.sha256(proxy.encode()).hexdigest(),workers=p['options']['workers'])))
'''

def prepare():
 assert not PRIVATE.exists();protect_directory(PRIVATE)
 state,native=m.context();assert native.config['generation']==29 and f.load(m.MARKER)['state']=='qualified'
 fixture=f.load(m.j.LOCAL/'fixtures.json');token=uuid4().hex[:12];project='mp-g7-perf-'+token;database='mp_disposable_r0_r1_g7_perf_'+token
 assert re.fullmatch(r'mp_disposable_r0_r1_g7_perf_[0-9a-f]{12}',database)
 port=18089
 with socket.socket() as probe:probe.bind(('127.0.0.1',port))
 image=state['image_id'];assert image==native.config['image_id']
 record=dict(state='recorded_before_creation',project=project,database=database,app=project+'-app',edge=project+'-edge',volume=project+'-data-config',edge_network=project+'-edge',port=port,image_id=image,inventory_digest=state['inventory_digest'],source_project=state['project'],source_database=state['active_db'],source_configuration_generation=29,source_runtime_network=state['project']+'_runtime',source_pg_container=state['project']+'-db-1',experimental_fixture_not_approved_deployment=True,shared_PostgreSQL_process=True)
 _write_new(PRIVATE/'state.json',record)
 def phase(value):record['state']=value;f.write(PRIVATE/'state.json',record);print(json.dumps(dict(phase=value,project=project)),flush=True)
 def command(label,args,**kwargs):return f.command('perf10k-'+label,args,**kwargs)
 def sql(label,query):return f.sql(state,'perf10k-'+label,query,database=database)
 before=m.snapshot(state,'perf10k-source-before');worker=m.worker(native,'perf10k-source-worker-before')
 f.write(PRIVATE/'source-data-before.json',before);f.write(PRIVATE/'source-worker-before.json',worker)
 owner=f.sql(state,'perf10k-source-owner','SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database();').decode().strip();assert re.fullmatch('[a-z_][a-z0-9_]*',owner)
 assert f.sql(state,'perf10k-db-absence',"SELECT count(*) FROM pg_database WHERE datname='"+database+"';",database='postgres').strip()==b'0'
 phase('dumping_owned_source')
 archive=command('source-dump',['docker','exec',record['source_pg_container'],'pg_dump','-U','postgres','-Fc',state['active_db']])
 (PRIVATE/'source.dump').write_bytes(archive);record['source_dump_sha256']=hashlib.sha256(archive).hexdigest()
 phase('creating_distinct_database')
 command('create-db',['docker','exec',record['source_pg_container'],'createdb','-U','postgres','-T','template0','-O',owner,database])
 command('restore-db',['docker','exec','-i',record['source_pg_container'],'pg_restore','-U','postgres','--exit-on-error','--no-owner','--role',owner,'-d',database],input=archive)
 query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in m.base.TABLES)+'); ROLLBACK;'
 assert json.loads(sql('copied-tables',query))==before
 phase('creating_private_volume')
 command('create-volume',['docker','volume','create','--label','com.modular.disposable='+project,record['volume']])
 seeded=command('seed-volume',['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+state['project']+'_appconfig,target=/source-config,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/source-data,readonly','--mount','type=volume,source='+state['project']+'_proxyconfig,target=/source-proxy,readonly','--mount','type=volume,source='+record['volume']+',target=/probe','--entrypoint','/venv/bin/python',image,'-c',VOLUME_SEED],input=json.dumps(record).encode())
 f.write(PRIVATE/'volume-seed.json',json.loads(seeded))
 workspace=fixture['workspaces']['A']['id'];user=fixture['users']['alice']['id'];principal=next(p['id'] for p in before['mp_principal'] if p['user_id']==user)
 assert len([n for n in before['mp_example_note'] if n['workspace_id']==workspace])==24
 phase('seeding_bounded_read_dataset')
 seed=f'''BEGIN;
UPDATE mp_dispatch_control SET state='paused',generation=generation+1;
UPDATE mp_service_credential SET state='revoked';
UPDATE mp_workspace_plugin SET availability='suspended' WHERE plugin_id='org.example.document_stats';
INSERT INTO mp_example_note(public_id,title,body,author_id,revision,workspace_id,create_uid,write_uid,create_date,write_date)
 SELECT gen_random_uuid()::text,'G7 benchmark note '||lpad(g::text,5,'0'),
 repeat('Bounded benchmark text. ',CASE WHEN g%100=0 THEN 400 WHEN g%5=0 THEN 120 ELSE 40 END),
 {principal},1,{workspace},{user},{user},timestamp '2026-11-02 00:00:00'+g*interval '1second',timestamp '2026-11-02 00:00:00'+g*interval '1second'
 FROM generate_series(1,9976) g;
COMMIT;
ANALYZE mp_example_note;
BEGIN READ ONLY; SELECT jsonb_build_object('total',(SELECT count(*) FROM mp_example_note),'workspace',(SELECT count(*) FROM mp_example_note WHERE workspace_id={workspace}),
 'synthetic',(SELECT count(*) FROM mp_example_note WHERE title LIKE 'G7 benchmark note %'),'dispatch',(SELECT jsonb_agg(state) FROM mp_dispatch_control),
 'credentials_active',(SELECT count(*) FROM mp_service_credential WHERE state='active'),
 'body_max',(SELECT max(length(body)) FROM mp_example_note WHERE title LIKE 'G7 benchmark note %'),
 'dataset_sha256',(SELECT encode(sha256(convert_to(jsonb_agg(to_jsonb(n) ORDER BY id)::text,'UTF8')),'hex') FROM mp_example_note n)); ROLLBACK;'''
 summary=json.loads(sql('seed-read-dataset',seed));assert summary['total']==10006 and summary['workspace']==10000 and summary['synthetic']==9976 and summary['credentials_active']==0 and summary['dispatch']==['paused'] and summary['body_max']<=10000
 f.write(PRIVATE/'dataset.json',summary);record['dataset']=summary
 phase('starting_guarded_app')
 runtime_code=(ROOT/'packages/platform_sdk/modular_platform/worker_start.py').read_text()
 app_id=command('create-app',['docker','create','--name',record['app'],'--label','com.modular.disposable='+project,'--label','com.docker.compose.project='+project,'--label','com.docker.compose.service=app','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--memory','1536m','--cpus','2','--tmpfs','/tmp','--network',record['source_runtime_network'],'--mount','type=volume,source='+record['volume']+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+record['volume']+',target=/var/lib/modular,volume-subpath=data','--entrypoint','/venv/bin/python',image,'-c',runtime_code,database,record['inventory_digest']]).decode().strip();record['app_id']=app_id;f.write(PRIVATE/'state.json',record)
 command('start-app',['docker','start',app_id])
 phase('starting_independent_edge')
 command('create-edge-network',['docker','network','create','--label','com.modular.disposable='+project,record['edge_network']])
 edge_info=json.loads(command('source-edge-inspect',['docker','inspect',state['project']+'-edge-1']))[0];record['edge_image']=edge_info['Image']
 edge_id=command('create-edge',['docker','create','--name',record['edge'],'--label','com.modular.disposable='+project,'--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m','--cpus','0.5','--network',record['edge_network'],'--publish','127.0.0.1:'+str(port)+':8069','--tmpfs','/tmp','--tmpfs','/var/cache/nginx:uid=101,gid=101,mode=0755','--tmpfs','/var/run:uid=101,gid=101,mode=0755','--mount','type=volume,source='+record['volume']+',target=/etc/nginx/conf.d,volume-subpath=edge,readonly','--entrypoint','nginx',record['edge_image'],'-g','daemon off;']).decode().strip();record['edge_id']=edge_id;f.write(PRIVATE/'state.json',record)
 command('edge-connect',['docker','network','connect',record['source_runtime_network'],edge_id]);command('start-edge',['docker','start',edge_id])
 http=urllib.request.build_opener(urllib.request.ProxyHandler({}));deadline=time.monotonic()+75
 while True:
  try:
   with http.open('http://127.0.0.1:'+str(port)+'/web/login',timeout=3) as response:assert response.status==200
   break
  except Exception:
   if time.monotonic()>deadline:raise RuntimeError('Inspect exact owned benchmark target; do not rebuild/recreate')
   time.sleep(1)
 assert m.snapshot(state,'perf10k-source-after')==before and m.worker(native,'perf10k-source-worker-after')==worker
 phase('prepared_needs_HTTP_dataset_validation')
 f.save('fixture.json',dict(result='prepared_owned_logical_read_benchmark',project=project,database=database,image=image,inventory=record['inventory_digest'],port=port,dataset=summary,source17tables_worker_exact=True,guarded_exact_image_start=True,app_CPUs=2,app_memory_bytes=1610612736,shared_PG_CPUs=1,shared_PG_memory_bytes=536870912,workers=2,issuer_not_mounted=True,dispatch_paused_credentials_revoked_in_copy=True,experimental_not_approved_deployment=True,limits=['Distinct logical database/filestore/app/proxy; shared original PostgreSQL process/hardware/network explicitly retained.','No benchmark target pass yet; ordinary authenticated HTTP validation and actual warm measurements remain.','Source runtime unchanged. One new volume/two containers/one network and one known new database; no new image.']))
 print('Owned10k fixture prepared; original runtime preserved, authenticated validation and benchmark remain')

if __name__=='__main__':prepare()
