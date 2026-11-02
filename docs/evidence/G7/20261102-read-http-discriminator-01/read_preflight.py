"""Informational current-data read timings; not the required10k benchmark."""
import concurrent.futures,configparser,importlib.util,json,math,platform,statistics,subprocess,sys,threading,time
from pathlib import Path
from uuid import uuid4
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('performance_current',OUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
import r1_probe
from modular_platform.operator_os import protect_directory
f=m.f;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=m.j.LOCAL
PRIVATE=ROOT/'.local/g7-read-http-discriminator-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=45)
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
state,native=m.context();assert native.config['generation']==29 and f.load(m.MARKER)['state']=='qualified'
before=m.snapshot(state,'read-http-discriminator-data-before');worker=m.worker(native,'read-http-discriminator-worker-before');fixture=f.load(m.j.LOCAL/'fixtures.json')
owned=[r for r in before['mp_example_note'] if r['workspace_id']==fixture['workspaces']['A']['id']];note=owned[0]
save(PRIVATE/'data-before.json',before)
info=json.loads(call(['docker','info','--format','{{json .}}']));save(PRIVATE/'docker-info.json',info)
ids=[native.config['worker_id'],state['project']+'-db-1',state['project']+'-edge-1',worker['container_id']]
inspections=json.loads(call(['docker','inspect',*ids]));save(PRIVATE/'runtime-inspections.json',inspections)
resource=dict(docker={k:info.get(k) for k in ['ServerVersion','KernelVersion','OperatingSystem','Architecture','NCPU','MemTotal','Driver','DriverStatus']},host_OS=platform.platform(),host_python=sys.version,clocks={k:dict(implementation=time.get_clock_info(k).implementation,resolution=time.get_clock_info(k).resolution) for k in ['monotonic','perf_counter']},
 runtimes=[dict(role=role,image=v['Image'],user=v['Config']['User'],memory_limit_bytes=v['HostConfig']['Memory'],nano_cpus=v['HostConfig']['NanoCpus'],cpu_period=v['HostConfig']['CpuPeriod'],cpu_quota=v['HostConfig']['CpuQuota'],readonly_root=v['HostConfig']['ReadonlyRootfs']) for role,v in zip(['app','database','edge','external_worker'],inspections)],global_running_containers=int(call(['docker','ps','--format','{{.ID}}']).decode().count('\n')),
 reference='Spec provisional4CPU/8GiB for app/database; actual engine and per-container caps are recorded, no equivalence assumed.',storage='Docker managed Linux volumes; actual storage driver/backing metadata above. Physical Windows disk model not yet bound.',target_dataset_notes=10000,actual_total_notes=len(before['mp_example_note']),actual_workspace_notes=len(owned),concurrent_requests=20)
cfg_code="import configparser,json;p=configparser.ConfigParser();p.read('/run/secrets/odoo_config');print(json.dumps({k:p['options'].get(k) for k in ['workers','db_maxconn','max_cron_threads','limit_memory_soft','limit_memory_hard','dev_mode']}))"
resource['actual_app_settings']=json.loads(call(['docker','exec',native.config['worker_id'],'/venv/bin/python','-c',cfg_code]));save(OUT/'resources.json',resource)
clients=[]
for index in range(20):
 clients.append(r1_probe.Client(state,fixture))
 if (index+1)%10==0:print(json.dumps(dict(authenticated_independent_sessions=index+1)),flush=True)
binding=next(r['descriptor'] for r in before['mp_service_binding'] if r['public_id']==fixture['bindings']['A']['binding_id'])
def native_payload(method,args=None,kwargs=None):return dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method=method,args=args or [],kwargs=kwargs or {}))
def request(client,case):
 if case=='native_list80':
  status,response=client.request('/web/dataset/call_kw/mp.example.note.web_search_read',native_payload('web_search_read',kwargs=dict(domain=[],limit=80,offset=0,specification={k:{} for k in ['title','revision','write_date','x_notes_labels']})),'A')
  result=response.get('result',{});ok=status==200 and len(result.get('records',[]))==min(80,len(owned)) and all(r['id'] in {n['id'] for n in owned} for r in result.get('records',[]))
 elif case=='native_detail':
  status,response=client.request('/web/dataset/call_kw/mp.example.note.web_read',native_payload('web_read',[[note['id']]],dict(specification={k:{} for k in ['title','body','revision','x_notes_labels']})),'A')
  result=response.get('result');ok=status==200 and isinstance(result,list) and len(result)==1 and result[0]['id']==note['id']
 else:
  method='list' if case=='gateway_list25' else 'get';values=dict(limit=25) if method=='list' else dict(note_id=note['public_id'])
  status,response=client.request('/api/v1/services/org.example.notes.documents/'+method,dict(api_version=binding['api_version'],request_id='perf-'+uuid4().hex,input=values),'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
  result=response.get('data');ok=status==200 and isinstance(result,dict) and (len(result.get('items',[]))==min(25,len(owned)) if method=='list' else result.get('id')==note['public_id'])
 error=response.get('error',{});return dict(ok=ok,status=status,error=error.get('code'),native_error=error.get('data',{}).get('name'))
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
 for round_index in range(2):
  barrier=threading.Barrier(21)
  def one(index):
   barrier.wait(timeout=20);started=time.perf_counter();result=request(clients[index],case);return dict(result,latency_ms=(time.perf_counter()-started)*1000)
  with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
   pending=[pool.submit(one,index) for index in range(20)];barrier.wait(timeout=20);samples.extend(future.result(timeout=45) for future in pending)
  time.sleep(1.15)  # 20/s service admission remains enabled; no unbounded overload.
 result=dict(timing=describe([v['latency_ms'] for v in samples]),errors=[v for v in samples if not v['ok']],concurrency=20,independent_sessions=20,rounds=2,batch_pacing_seconds=1.15,all_requests=samples)
 results[case]=result;save(PRIVATE/'progress.json',dict(state='measuring',cases=results));print(json.dumps(dict(case=case,timing=result['timing'],errors=len(result['errors']))),flush=True)
assert m.snapshot(state,'read-http-discriminator-data-after')==before and m.worker(native,'read-http-discriminator-worker-after')==worker
save(OUT/'read-preflight.json',dict(result='informational_existing_dataset_read_preflight',image=state['image_id'],configuration_generation=29,total_notes=len(before['mp_example_note']),workspace_notes=len(owned),target10000_dataset_met=False,quality_target_passed=False,cases=results,warm_sequential_session_control=dict(timing=describe(control),samples_ms=control,R0_control_p95_ms=31.0,limits='G0 used admin/different old environment and coarse monotonic clock; this is an upstream session control, not a Notes benchmark.'),all17tables_worker_exact=True,no_product_source_or_limits_changed=True,limits=['Read-only existing30Note preflight only; required10kNotes target and full G7 still pending.','Public proxy admission and ordinary authorization remain active; batches paced rather than disabling controls.','No body payloads or session credentials in public timing evidence.']))
save(PRIVATE/'progress.json',dict(state='completed',cases=results));print('Read-only preflight complete;10k/performance/G7 not qualified from this dataset')
