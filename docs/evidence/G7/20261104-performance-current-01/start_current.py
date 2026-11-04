"""Replace only the stopped owned benchmark app/proxy; retain old IDs/checkpoint."""
import hashlib,json,re,subprocess,sys,tarfile,urllib.request
from pathlib import Path
ROOT=Path.cwd();PRIVATE=ROOT/'.local/g7-performance-current-01';OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));from modular_platform.workers import wait_ready
def load(p):return json.loads(p.read_bytes())
record=load(PRIVATE/'record-before.json');state=load(PRIVATE/'alignment.json');assert state['phase']=='current_fixture_published_needs_guarded_app'
assert record['project']=='mp-g7-perf-6fafdba2c44c' and record['database']=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c'
def command(label,args,*,data=None,timeout=120):
 with (PRIVATE/'logs'/(label+'.stdout')).open('xb') as out,(PRIVATE/'logs'/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=data,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect current IDs/phase and native readiness; never recreate blindly'
 return (PRIVATE/'logs'/(label+'.stdout')).read_bytes()
def phase(name):state['phase']=name;(PRIVATE/'alignment.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(phase=name)),flush=True)
old=json.loads(command('recheck-old-benchmark-stopped',['docker','inspect',record['app_id'],record['edge_id']]))
assert all(not r['State']['Running'] and r['Config']['Labels']['com.modular.disposable']==record['project'] for r in old)
proxy=load(ROOT/'.local/releases/r1-0.1.23/images.json')['images']['proxy']['image_id'];assert json.loads(command('selected-benchmark-proxy-image',['docker','image','inspect',proxy]))[0]['Id']==proxy
with tarfile.open(PRIVATE/'checkpoints/volume.tar.gz') as archive:old_proxy=archive.extractfile('volume/edge/default.conf').read()
current_proxy=(ROOT/'deploy/nginx-r0.conf').read_text();current_proxy=re.sub(r'\bapp:(8069|8072)\b',lambda m:record['app']+':'+m.group(1),current_proxy)
assert not re.search(r'(?<![A-Za-z0-9_.-])app:(8069|8072)\b',current_proxy)
phase('replacing_only_benchmark_proxy_configuration')
script="import hashlib,json,os,pathlib,sys;data=json.load(sys.stdin);path=pathlib.Path('/proxy/default.conf');assert hashlib.sha256(path.read_bytes()).hexdigest()==data['expected'];path.chmod(0o644)\nwith path.open('w') as stream:stream.write(data['content']);stream.flush();os.fsync(stream.fileno())\npath.chmod(0o444);print(hashlib.sha256(path.read_bytes()).hexdigest())"
proxy_sha=hashlib.sha256(current_proxy.encode()).hexdigest();assert command('write-current-benchmark-proxy',['docker','run','--rm','-i','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+record['volume']+',target=/proxy,volume-subpath=edge','--entrypoint','/venv/bin/python',state['target_image'],'-c',script],data=json.dumps(dict(expected=hashlib.sha256(old_proxy).hexdigest(),content=current_proxy)).encode()).decode().strip()==proxy_sha
phase('retaining_stopped_old_fixture_containers')
for role,suffix in [('app','old31'),('edge','old479')]:
 ident=record[role+'_id'];name=record[role]+'-'+suffix;assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0
 command('rename-old-'+role,['docker','rename',ident,name])
 command('disconnect-old-'+role,['docker','network','disconnect',record['source_runtime_network'],ident])
runtime_code=(ROOT/'packages/platform_sdk/modular_platform/worker_start.py').read_text();runtime=load(PRIVATE/'new-runtime.json');assert hashlib.sha256(runtime_code.encode()).hexdigest()==runtime['inventory']['files']['packages/platform_sdk/modular_platform/worker_start.py']
phase('creating_guarded_current_benchmark_app')
app=command('create-current-benchmark-app',['docker','create','--name',record['app'],'--label','com.modular.disposable='+record['project'],'--label','com.docker.compose.project='+record['project'],'--label','com.docker.compose.service=app','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--memory','1536m','--cpus','2','--tmpfs','/tmp','--network',record['source_runtime_network'],
 '--mount','type=volume,source='+record['volume']+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+record['volume']+',target=/var/lib/modular,volume-subpath=data','--entrypoint','/venv/bin/python',state['target_image'],'-c',runtime_code,record['database'],state['target_inventory']]).decode().strip();state['new_app_id']=app;phase('starting_guarded_current_benchmark_app')
command('start-current-benchmark-app',['docker','start',app]);wait_ready(app)
app_info=json.loads(command('inspect-current-benchmark-app',['docker','inspect',app]))[0];assert 'app' not in (app_info['NetworkSettings']['Networks'][record['source_runtime_network']].get('Aliases') or [])
phase('creating_current_benchmark_edge')
edge=command('create-current-benchmark-edge',['docker','create','--name',record['edge'],'--label','com.modular.disposable='+record['project'],'--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m','--cpus','0.5','--network',record['edge_network'],'--publish','127.0.0.1:'+str(record['port'])+':8069','--tmpfs','/tmp','--tmpfs','/var/cache/nginx:uid=101,gid=101,mode=0755','--tmpfs','/var/run:uid=101,gid=101,mode=0755',
 '--mount','type=volume,source='+record['volume']+',target=/etc/nginx/conf.d,volume-subpath=edge,readonly','--entrypoint','nginx',proxy,'-g','daemon off;']).decode().strip();state['new_edge_id']=edge;phase('starting_current_benchmark_edge')
command('connect-current-benchmark-edge',['docker','network','connect',record['source_runtime_network'],edge]);command('start-current-benchmark-edge',['docker','start',edge])
http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with http.open('http://127.0.0.1:'+str(record['port'])+'/web/login',timeout=30) as response:assert response.status==200;response.read()
record.update(state='current_image_fixture_ready_needs_read_qualification',image_id=state['target_image'],inventory_digest=state['target_inventory'],app_id=app,edge_id=edge,edge_image=proxy,fixture_generation=state['generation'],fixture_release_digest=state['release_digest'])
(ROOT/'.local/g7-performance-10k-01/state.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');phase('current_guarded_fixture_ready_needs_authenticated_validation')
report=dict(result='current_guarded_unmanaged_benchmark_app_proxy_ready',image=record['image_id'],inventory=record['inventory_digest'],generation=state['generation'],new_app=app,new_edge=edge,proxy_image=proxy,proxy_template_sha256=proxy_sha,port=record['port'],app_limits=dict(CPUs=2,memory=1610612736,workers=2),retained_old_containers=[r['Id'] for r in old],existing_volume_networks_database_reused=True,new_images_volumes_networks_databases=0,no_original_app_alias_or_compose_project_claim=True,limits=['Read fixture setup only; actual authenticated dataset/ordinary20session benchmark/preservation checks required.','Old containers/checkpoints retained until verification; original app/worker/PG remain separate, shared physical/network resources explicitly reported.'])
with (OUT/'current-ready.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],image=record['image_id'],generation=state['generation'],port=record['port'])))
