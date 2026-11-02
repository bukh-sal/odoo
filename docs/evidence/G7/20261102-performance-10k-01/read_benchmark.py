"""Actual10k workspace Notes,20concurrent ordinary authenticated read benchmark."""
import concurrent.futures,configparser,importlib.util,json,math,platform,statistics,subprocess,sys,threading,time
from pathlib import Path
from uuid import uuid4
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('performance10k_current',OUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
import r1_probe
from modular_platform.operator_os import protect_directory
f=m.f;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=m.j.LOCAL
PRIVATE=ROOT/'.local/g7-performance-10k-load-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=45)
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
source_state,native=m.context();assert native.config['generation']==29
record=f.load(ROOT/'.local/g7-performance-10k-01/state.json');assert record['state']=='prepared_needs_HTTP_dataset_validation' and f.load(OUT/'fixture.json')['source17tables_worker_exact']
assert record['image_id']==source_state['image_id'] and record['inventory_digest']==source_state['inventory_digest']
state={**source_state,'active_db':record['database'],'port':record['port']}
before=m.snapshot(source_state,'perf10k-load-source-before');worker=m.worker(native,'perf10k-load-worker-before');fixture=f.load(m.j.LOCAL/'fixtures.json')
metadata=json.loads(f.sql(source_state,'perf10k-load-dataset-before',"BEGIN READ ONLY; SELECT jsonb_build_object('notes',(SELECT jsonb_agg(jsonb_build_object('id',id,'public_id',public_id,'workspace_id',workspace_id,'title',title,'body_bytes',octet_length(body)) ORDER BY id) FROM mp_example_note),'dataset_sha256',(SELECT encode(sha256(convert_to(jsonb_agg(to_jsonb(n) ORDER BY id)::text,'UTF8')),'hex') FROM mp_example_note n),'dispatch',(SELECT jsonb_agg(state) FROM mp_dispatch_control),'credentials_active',(SELECT count(*) FROM mp_service_credential WHERE state='active')); ROLLBACK;",database=record['database']))
assert metadata['dataset_sha256']==record['dataset']['dataset_sha256'] and metadata['dispatch']==['paused'] and metadata['credentials_active']==0
owned=[r for r in metadata['notes'] if r['workspace_id']==fixture['workspaces']['A']['id']];assert len(owned)==10000 and len(metadata['notes'])==10006
owned_ids={r['id'] for r in owned};owned_public_ids={r['public_id'] for r in owned}
note=next(r for r in owned if r['title']=='G7 benchmark note 00100');assert note['body_bytes']==9600
save(PRIVATE/'source-data-before.json',before);save(PRIVATE/'dataset-metadata.json',metadata)
info=json.loads(call(['docker','info','--format','{{json .}}']));save(PRIVATE/'docker-info.json',info)
ids=[record['app_id'],record['source_pg_container'],record['edge_id'],worker['container_id']]
inspections=json.loads(call(['docker','inspect',*ids]));save(PRIVATE/'runtime-inspections.json',inspections)
resource=dict(docker={k:info.get(k) for k in ['ServerVersion','KernelVersion','OperatingSystem','Architecture','NCPU','MemTotal','Driver','DriverStatus']},host_OS=platform.platform(),host_python=sys.version,clocks={k:dict(implementation=time.get_clock_info(k).implementation,resolution=time.get_clock_info(k).resolution) for k in ['monotonic','perf_counter']},
 runtimes=[dict(role=role,image=v['Image'],user=v['Config']['User'],memory_limit_bytes=v['HostConfig']['Memory'],nano_cpus=v['HostConfig']['NanoCpus'],cpu_period=v['HostConfig']['CpuPeriod'],cpu_quota=v['HostConfig']['CpuQuota'],readonly_root=v['HostConfig']['ReadonlyRootfs']) for role,v in zip(['benchmark_app','shared_database','benchmark_edge','preserved_original_external_worker'],inspections)],global_running_containers=int(call(['docker','ps','--format','{{.ID}}']).decode().count('\n')),
 reference='Spec provisional4CPU/8GiB for app/database; actual engine and per-container caps are recorded, no equivalence assumed.',storage='Docker managed Linux volumes; actual storage driver/backing metadata above. Physical Windows disk model not yet bound.',target_dataset_notes=10000,actual_total_notes=len(metadata['notes']),actual_workspace_notes=len(owned),concurrent_requests=20)
cfg_code="import configparser,json;p=configparser.ConfigParser();p.read('/run/secrets/odoo_config');print(json.dumps({k:p['options'].get(k) for k in ['workers','db_maxconn','max_cron_threads','limit_memory_soft','limit_memory_hard','dev_mode']}))"
resource['actual_app_settings']=json.loads(call(['docker','exec',record['app_id'],'/venv/bin/python','-c',cfg_code]));save(OUT/'resources.json',resource)
clients=[]
for index in range(20):
 clients.append(r1_probe.Client(state,fixture))
 if (index+1)%10==0:print(json.dumps(dict(authenticated_independent_sessions=index+1)),flush=True)
binding=next(r['descriptor'] for r in before['mp_service_binding'] if r['public_id']==fixture['bindings']['A']['binding_id'])
def native_payload(method,args=None,kwargs=None):return dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method=method,args=args or [],kwargs=kwargs or {}))
def request(client,case):
 if case=='native_list80':
  status,response=client.request('/web/dataset/call_kw/mp.example.note.web_search_read',native_payload('web_search_read',kwargs=dict(domain=[],limit=80,offset=0,specification={k:{} for k in ['title','revision','write_date','x_notes_labels']})),'A')
  result=response.get('result',{});ok=status==200 and len(result.get('records',[]))==min(80,len(owned)) and all(r['id'] in owned_ids for r in result.get('records',[]))
 elif case=='native_detail':
  status,response=client.request('/web/dataset/call_kw/mp.example.note.web_read',native_payload('web_read',[[note['id']]],dict(specification={k:{} for k in ['title','body','revision','x_notes_labels']})),'A')
  result=response.get('result');ok=status==200 and isinstance(result,list) and len(result)==1 and result[0]['id']==note['id'] and len(result[0]['body'].encode())==9600
 else:
  method='list' if case=='gateway_list25' else 'get';values=dict(limit=25) if method=='list' else dict(note_id=note['public_id'])
  status,response=client.request('/api/v1/services/org.example.notes.documents/'+method,dict(api_version=binding['api_version'],request_id='perf-'+uuid4().hex,input=values),'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
  result=response.get('data');ok=status==200 and isinstance(result,dict) and (len(result.get('items',[]))==25 and all(r['id'] in owned_public_ids for r in result['items']) and bool(result.get('next_cursor')) if method=='list' else result.get('id')==note['public_id'] and len(result.get('body','').encode())==9600)
 error=response.get('error',{});return dict(ok=ok,status=status,error=error.get('code'),native_error=error.get('data',{}).get('name'))
# Validate actual authenticated dataset routing and bounded server filters/pages.
client=clients[0]
status,count=client.request('/web/dataset/call_kw/mp.example.note.search_count',native_payload('search_count',[[]]),'A');assert status==200 and count.get('result')==10000
prefix='G7 benchmark note 001'
status,filtered=client.request('/web/dataset/call_kw/mp.example.note.web_search_read',native_payload('web_search_read',kwargs=dict(domain=[['title','ilike',prefix]],limit=80,offset=0,order='title,id',specification={'title':{}})),'A')
assert status==200 and len(filtered['result']['records'])==80 and all(prefix in r['title'] for r in filtered['result']['records'])
def gateway_page(cursor=None):
 values=dict(limit=25,query=prefix,order='title_asc')
 if cursor:values['cursor']=cursor
 status,response=client.request('/api/v1/services/org.example.notes.documents/list',dict(api_version=binding['api_version'],request_id='perf-validation-'+uuid4().hex,input=values),'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
 assert status==200 and len(response['data']['items'])==25 and all(prefix in r['title'] for r in response['data']['items']) and response['data']['next_cursor']
 return response['data']
page1=gateway_page();page2=gateway_page(page1['next_cursor']);assert not {r['id'] for r in page1['items']} & {r['id'] for r in page2['items']}
save(OUT/'authenticated-dataset-validation.json',dict(result='passed_actual_authenticated_10k_and_bounded_filters_pagination',workspace_count=10000,native_filtered_rows=80,gateway_page_sizes=[25,25],gateway_pages_disjoint=True,detail_body_bytes=9600,dispatch_paused=True,copied_technical_credentials_revoked=True,source_workspace_notes=24,benchmark_database=record['database']))
def describe(values):return dict(samples=len(values),median_ms=round(statistics.median(values),3),p95_ms=round(sorted(values)[math.ceil(.95*len(values))-1],3),max_ms=round(max(values),3))
control=[]
for _ in range(2):assert clients[0].request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',id=1,params={}))[1]['result']['uid']
for _ in range(20):
 started=time.monotonic();status,response=clients[0].request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',id=1,params={}));elapsed=(time.monotonic()-started)*1000
 assert status==200 and response.get('result',{}).get('uid');control.append(elapsed)
results={};save(PRIVATE/'progress.json',dict(state='measuring',cases=results))
for case in ['native_list80','native_detail','gateway_list25','gateway_detail']:
 for _ in range(3):assert request(clients[0],case)['ok'],'Inspect original warmup; no dataset mutation or fake target pass'
 samples=[]
 for round_index in range(10):
  barrier=threading.Barrier(21)
  def one(index):
   barrier.wait(timeout=20);started=time.perf_counter();result=request(clients[index],case);return dict(result,latency_ms=(time.perf_counter()-started)*1000)
  with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
   pending=[pool.submit(one,index) for index in range(20)];barrier.wait(timeout=20);samples.extend(future.result(timeout=45) for future in pending)
  time.sleep(1.15)  # 20/s service admission remains enabled; no unbounded overload.
 result=dict(timing=describe([v['latency_ms'] for v in samples]),errors=[v for v in samples if not v['ok']],concurrency=20,independent_sessions=20,rounds=10,batch_pacing_seconds=1.15,all_requests=samples)
 results[case]=result;save(PRIVATE/'progress.json',dict(state='measuring',cases=results));print(json.dumps(dict(case=case,timing=result['timing'],errors=len(result['errors']))),flush=True)
assert m.snapshot(source_state,'perf10k-load-data-after')==before and m.worker(native,'perf10k-load-worker-after')==worker
after_digest=f.sql(source_state,'perf10k-load-dataset-after',"BEGIN READ ONLY; SELECT encode(sha256(convert_to(jsonb_agg(to_jsonb(n) ORDER BY id)::text,'UTF8')),'hex') FROM mp_example_note n; ROLLBACK;",database=record['database']).decode().strip();assert after_digest==metadata['dataset_sha256']
save(OUT/'read-benchmark.json',dict(result='actual_10k_20concurrent_read_benchmark',image=state['image_id'],configuration_generation=29,total_notes=len(metadata['notes']),workspace_notes=len(owned),target10000_dataset_met=True,quality_target_passed=all(not v['errors'] and v['timing']['p95_ms']<500 for v in results.values()),cases=results,warm_sequential_session_control=dict(timing=describe(control),samples_ms=control,R0_control_p95_ms=31.0,limits='G0 used admin/different old environment and coarse monotonic clock; this is an upstream session control, not a Notes benchmark.'),all17tables_worker_exact=True,no_product_source_or_limits_changed=True,limits=['Required read benchmark only; shell/mount cycles/R0/heartbeat/revocation and other G7 work remain.','Public proxy admission and ordinary authorization remain active; batches paced rather than disabling controls.','No body payloads or session credentials in public timing evidence. The original PostgreSQL process/hardware/network are shared and recorded; logical fixture only.']))
save(PRIVATE/'progress.json',dict(state='completed',cases=results));print('Required10k read measurements complete; inspect actual p95/errors/preservation before qualification, fullG7 remains')
