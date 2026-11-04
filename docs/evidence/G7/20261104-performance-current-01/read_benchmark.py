"""Current14de read measurements on the retained exact10k dataset/ordinary HTTP."""
import concurrent.futures,hashlib,json,math,platform,statistics,subprocess,sys,threading,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-performance-current-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import r1_probe
def load(p):return json.loads(p.read_bytes())
def write(p,v):
 with p.open('x',encoding='utf8') as stream:json.dump(v,stream,indent=2);stream.write('\n')
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
record=load(ROOT/'.local/g7-performance-10k-01/state.json');state=load(PRIVATE/'alignment.json');assert state['phase']=='current_guarded_fixture_ready_needs_authenticated_validation' and record['state']=='current_image_fixture_ready_needs_read_qualification'
progress=PRIVATE/'read-progress.json';assert not progress.exists()
def mark(value):progress.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
mark(dict(phase='observing_before_measurement',cases={}))
source=load(ROOT/'.local/g6-events/state.json');before=load(PRIVATE/'benchmark-tables-before.json');original=load(PRIVATE/'original-tables-before.json')
def sql(database,query):
 assert database in [record['database'],source['active_db']]
 return json.loads(call(['docker','exec',record['source_pg_container'],'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',database,'-c',query]))
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
assert sql(record['database'],query)==before and sql(source['active_db'],query)==original
fixture=load(ROOT/'.local/g6-events/fixtures.json');r1_probe.r1.r0.LOCAL=ROOT/'.local/g6-events'
notes=before['mp_example_note'];owned=[n for n in notes if n['workspace_id']==fixture['workspaces']['A']['id']];assert len(owned)==10000 and len(notes)==10006
note=next(n for n in owned if n['title']=='G7 benchmark note 00100');assert len(note['body'].encode())==9600
owned_ids={n['id'] for n in owned};public_ids={n['public_id'] for n in owned}
fences=sql(record['database'],"SELECT jsonb_build_object('control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c),'credentials_active',(SELECT count(*) FROM mp_service_credential WHERE state='active'),'digest',(SELECT encode(sha256(convert_to(jsonb_agg(to_jsonb(n) ORDER BY id)::text,'UTF8')),'hex') FROM mp_example_note n));")
assert fences['credentials_active']==0 and all(r['state']=='paused' for r in fences['control']) and fences['digest']==record['dataset']['dataset_sha256']
write(PRIVATE/'benchmark-fences-before-load.json',fences)
protected=load(PRIVATE/'protected-runtime-before.json')[2:];protected_current=json.loads(call(['docker','inspect',*[r['Id'] for r in protected]]))
def identity(r):return {k:r[k] for k in ['Id','Image','RestartCount','Mounts']}|dict(started=r['State']['StartedAt'],networks=r['NetworkSettings']['Networks'])
assert [identity(r) for r in protected_current]==[identity(r) for r in protected]
info=json.loads(call(['docker','info','--format','{{json .}}']));runtimes=json.loads(call(['docker','inspect',record['app_id'],record['source_pg_container'],record['edge_id'],protected[-1]['Id']]))
assert runtimes[0]['Image']==state['target_image'] and runtimes[2]['Image']==record['edge_image']
assert runtimes[0]['HostConfig']['Memory']==1610612736 and runtimes[0]['HostConfig']['NanoCpus']==2000000000
config_code="import configparser,json;p=configparser.ConfigParser();p.read('/run/secrets/odoo_config');print(json.dumps({k:p['options'].get(k) for k in ['workers','db_maxconn','max_cron_threads','limit_memory_soft','limit_memory_hard','dev_mode']}))"
settings=json.loads(call(['docker','exec',record['app_id'],'/venv/bin/python','-c',config_code]));assert settings['workers']=='2' and settings['max_cron_threads']=='0'
resources=dict(docker={k:info.get(k) for k in ['ServerVersion','KernelVersion','OperatingSystem','Architecture','NCPU','MemTotal','Driver','DriverStatus']},host_OS=platform.platform(),host_operator_Python=platform.python_version(),clocks={k:dict(implementation=time.get_clock_info(k).implementation,resolution=time.get_clock_info(k).resolution) for k in ['monotonic','perf_counter']},
 runtimes=[dict(role=role,container_id=r['Id'],image=r['Image'],user=r['Config']['User'],memory_limit_bytes=r['HostConfig']['Memory'],nano_cpus=r['HostConfig']['NanoCpus'],readonly_root=r['HostConfig']['ReadonlyRootfs']) for role,r in zip(['benchmark_app','shared_database','benchmark_edge','preserved_original_worker'],runtimes)],actual_app_settings=settings,global_running_container_count=len(call(['docker','ps','-q']).splitlines()),limits=['Recorded actual engine/container allocation and shared background workload, not dedicated4CPU/8GiB equivalence.','Same benchmark app2CPU/1536MiB/twoworkers, sharedPG1CPU/512MiB and unmodified proxy admission; no limit increase for a passing result.'])
write(OUT/'resources.json',resources)
clients=[]
for i in range(20):
 clients.append(r1_probe.Client(dict(active_db=record['database'],port=record['port']),fixture))
 if (i+1)%10==0:print(json.dumps(dict(authenticated_independent_sessions=i+1)),flush=True)
binding=next(r['descriptor'] for r in before['mp_service_binding'] if r['public_id']==fixture['bindings']['A']['binding_id'])
def native_payload(method,args=None,kwargs=None):return dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method=method,args=args or [],kwargs=kwargs or {}))
def request(client,case):
 if case=='native_list80':
  status,response=client.request('/web/dataset/call_kw/mp.example.note.web_search_read',native_payload('web_search_read',kwargs=dict(domain=[],limit=80,offset=0,specification={k:{} for k in ['title','revision','write_date','x_notes_labels']})),'A')
  result=response.get('result',{});ok=status==200 and len(result.get('records',[]))==80 and all(r['id'] in owned_ids for r in result.get('records',[]))
 elif case=='native_detail':
  status,response=client.request('/web/dataset/call_kw/mp.example.note.web_read',native_payload('web_read',[[note['id']]],dict(specification={k:{} for k in ['title','body','revision','x_notes_labels']})),'A')
  result=response.get('result');ok=status==200 and isinstance(result,list) and len(result)==1 and result[0]['id']==note['id'] and len(result[0]['body'].encode())==9600
 else:
  method='list' if case=='gateway_list25' else 'get';values=dict(limit=25) if method=='list' else dict(note_id=note['public_id'])
  status,response=client.request('/api/v1/services/org.example.notes.documents/'+method,dict(api_version=binding['api_version'],request_id='perf-'+uuid4().hex,input=values),'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
  result=response.get('data');ok=status==200 and isinstance(result,dict) and (len(result.get('items',[]))==25 and all(r['id'] in public_ids for r in result['items']) and bool(result.get('next_cursor')) if method=='list' else result.get('id')==note['public_id'] and len(result.get('body','').encode())==9600)
 error=response.get('error',{});return dict(ok=ok,status=status,error=error.get('code'),native_error=error.get('data',{}).get('name'))
client=clients[0];status,value=client.request('/web/dataset/call_kw/mp.example.note.search_count',native_payload('search_count',[[]]),'A');assert status==200 and value.get('result')==10000
prefix='G7 benchmark note 001'
status,value=client.request('/web/dataset/call_kw/mp.example.note.web_search_read',native_payload('web_search_read',kwargs=dict(domain=[['title','ilike',prefix]],limit=80,offset=0,order='title,id',specification={'title':{}})),'A');assert status==200 and len(value['result']['records'])==80 and all(prefix in r['title'] for r in value['result']['records'])
def page(cursor=None):
 values=dict(limit=25,query=prefix,order='title_asc')
 if cursor:values['cursor']=cursor
 status,value=client.request('/api/v1/services/org.example.notes.documents/list',dict(api_version=binding['api_version'],request_id='perf-page-'+uuid4().hex,input=values),'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
 assert status==200 and len(value['data']['items'])==25 and all(prefix in r['title'] for r in value['data']['items']) and value['data']['next_cursor'];return value['data']
first=page();second=page(first['next_cursor']);assert not {n['id'] for n in first['items']}&{n['id'] for n in second['items']}
write(OUT/'authenticated-dataset-validation.json',dict(result='passed_current_authenticated_10k_server_filters_disjoint_pagination',workspace_count=10000,total_notes=10006,native_filtered_rows=80,gateway_page_sizes=[25,25],detail_bytes=9600,image=record['image_id']))
def describe(values):return dict(samples=len(values),median_ms=round(statistics.median(values),3),p95_ms=round(sorted(values)[math.ceil(.95*len(values))-1],3),max_ms=round(max(values),3),requests_over_500ms=sum(v>=500 for v in values))
control=[]
for _ in range(2):assert client.request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',id=1,params={}))[1]['result']['uid']
for _ in range(20):
 start=time.perf_counter();status,value=client.request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',id=1,params={}));control.append((time.perf_counter()-start)*1000);assert status==200 and value['result']['uid']
results={};mark(dict(phase='measuring',cases=results))
for case in ['native_list80','native_detail','gateway_list25','gateway_detail']:
 for _ in range(3):assert request(client,case)['ok'],'Inspect warmup; do not change data/security/limits to manufacture a pass'
 samples=[]
 for round_index in range(10):
  barrier=threading.Barrier(21)
  def one(index):
   barrier.wait(timeout=20);start=time.perf_counter();value=request(clients[index],case);return dict(value,latency_ms=(time.perf_counter()-start)*1000)
  with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
   pending=[pool.submit(one,i) for i in range(20)];barrier.wait(timeout=20);samples.extend(p.result(timeout=45) for p in pending)
  time.sleep(1.15)
 results[case]=dict(timing=describe([s['latency_ms'] for s in samples]),errors=[s for s in samples if not s['ok']],concurrency=20,independent_sessions=20,rounds=10,batch_pacing_seconds=1.15,all_requests=samples)
 mark(dict(phase='measuring',cases=results));print(json.dumps(dict(case=case,timing=results[case]['timing'],errors=len(results[case]['errors']))),flush=True)
assert sql(record['database'],query)==before and sql(source['active_db'],query)==original
after_fences=sql(record['database'],"SELECT jsonb_build_object('control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c),'credentials_active',(SELECT count(*) FROM mp_service_credential WHERE state='active'),'digest',(SELECT encode(sha256(convert_to(jsonb_agg(to_jsonb(n) ORDER BY id)::text,'UTF8')),'hex') FROM mp_example_note n));");assert after_fences==fences
after_protected=json.loads(call(['docker','inspect',*[r['Id'] for r in protected]]));assert [identity(r) for r in after_protected]==[identity(r) for r in protected]
report=dict(result='actual_current_10k_20session_native_gateway_read_measurements',utc=datetime.now(timezone.utc).isoformat(),image=record['image_id'],inventory=record['inventory_digest'],generation=state['generation'],workspace_notes=10000,total_notes=10006,dataset_sha256=fences['digest'],cases=results,requests=800,total_errors=sum(len(r['errors']) for r in results.values()),quality_target_passed=all(not r['errors'] and r['timing']['p95_ms']<500 for r in results.values()),warm_sequential_upstream_session_control=describe(control),R0_session_control_p95_ms=31.0,
 benchmark17tables_and_fences_exact=True,original17tables_and_PG_worker_identity_exact=True,ordinary_auth_CSRF_binding_release_proxy_admission_retained=True,source_and_limits_unchanged_during_measurement=True,
 limits=['Read portion only; shell/mount/disposal/upstream comparison/heartbeat/revocation and full performance/G7 remain.','Shared PostgreSQL process/hardware/network/background work explicitly recorded; R0 used different actor/environment/coarse clock, so31ms is contextual rather than a controlled Notes comparison.','Warmup3/case,20independent sessions,10paced batches/case,200samples/case; all latency tails/errors retained, no uniform latency guarantee.'])
write(OUT/'read-benchmark.json',report);mark(dict(phase='completed',cases=results,quality_target_passed=report['quality_target_passed']));print(json.dumps(dict(result=report['result'],target_passed=report['quality_target_passed'],requests=800,errors=report['total_errors'])))
