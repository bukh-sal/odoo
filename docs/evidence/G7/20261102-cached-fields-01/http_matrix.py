"""Current native RPC scope matrix; no successful business mutations."""
import hashlib,importlib.util,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent/'post-http';OUT.mkdir(exist_ok=False)
sp=importlib.util.spec_from_file_location('current_native',ROOT/'docs/evidence/G6/20261102-notes-stats-ui-source-01/upgrade.py')
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.operator_os import protect_directory
import r1_probe
base,f,j=m.base,m.f,m.j;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=j.LOCAL
PRIVATE=j.LOCAL/'g7-cache-http-01'
state,native=m.context();assert native.config['generation']==26 and not PRIVATE.exists();protect_directory(PRIVATE)
before=base.snapshot(state,'g7-cache-http-before');worker=base.worker(native,'g7-cache-http-worker-before')
f.write(PRIVATE/'data-before.json',before);f.write(PRIVATE/'worker-before.json',worker)
fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture,'alice')
notes={w:next(r for r in before['mp_example_note'] if r['workspace_id']==fixture['workspaces'][w]['id']) for w in ['A','B']}
ids=[notes[w]['id'] for w in ['A','B']];domain=[['id','in',ids]];results=[];raw=[]
def call(name,method,args=None,kwargs=None,workspace='A',check=None,deny=False):
    body=dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method=method,args=args or [],kwargs=kwargs or {}))
    code,response=client.request('/web/dataset/call_kw/mp.example.note.'+method,body,workspace)
    raw.append(dict(name=name,status=code,response=response))
    error=response.get('error',{}).get('data',{}).get('name')
    passed=code==200 and ((error in ('odoo.exceptions.AccessError','odoo.exceptions.UserError') if method=='export_data' else error=='odoo.exceptions.AccessError') if deny else ('result' in response and check(response['result'])))
    results.append(dict(name=name,method=method,workspace=workspace or 'missing',expected=('native_export_permission_denial; authorized export scoped separately in native suite' if method=='export_data' else 'AccessError') if deny else 'scoped_success',
        passed=passed,error_type=error,result_count=len(response.get('result',[])) if isinstance(response.get('result'),(list,dict)) else None))
    f.write(PRIVATE/'http-raw.json',raw)
    f.save('http-progress.json',dict(result='running',checks=results)) if len(results)==1 else f.write(OUT/'http-progress.json',dict(result='running',checks=results))
for w in ['A','B']:
    own=notes[w]['id'];foreign=notes['B' if w=='A' else 'A']['id']
    call(w+' search_read','search_read',kwargs=dict(domain=domain,fields=['id','title','public_id']),workspace=w,check=lambda v,own=own:[r['id'] for r in v]==[own])
    call(w+' search_count','search_count',args=[domain],workspace=w,check=lambda v:v==1)
    call(w+' autocomplete','name_search',kwargs=dict(name='',domain=domain),workspace=w,check=lambda v,own=own:[r[0] for r in v]==[own])
    call(w+' aggregate','read_group',kwargs=dict(domain=domain,fields=['revision:sum'],groupby=[]),workspace=w,check=lambda v:v[0]['__count']==1)
    call(w+' web_search_read','web_search_read',kwargs=dict(domain=domain,specification={'id':{},'title':{}}),workspace=w,check=lambda v,own=own:[r['id'] for r in v['records']]==[own])
    call(w+' own web_read','web_read',args=[[own]],kwargs=dict(specification={'id':{},'title':{}}),workspace=w,check=lambda v,own=own:[r['id'] for r in v]==[own])
    call(w+' foreign read','read',args=[[foreign],['title']],workspace=w,deny=True)
    call(w+' mixed read','read',args=[ids,['title']],workspace=w,deny=True)
    call(w+' foreign web_read fields','web_read',args=[[foreign]],kwargs=dict(specification={'title':{}}),workspace=w,deny=True)
    call(w+' foreign web_read id-only','web_read',args=[[foreign]],kwargs=dict(specification={'id':{}}),workspace=w,deny=True)
    call(w+' mixed web_read empty spec','web_read',args=[ids],kwargs=dict(specification={}),workspace=w,deny=True)
    call(w+' foreign export','export_data',args=[[foreign],['title']],workspace=w,deny=True)
call('missing workspace search','search_read',kwargs=dict(domain=domain,fields=['title']),workspace=None,deny=True)
call('missing workspace id-only web_read','web_read',args=[[ids[0]]],kwargs=dict(specification={'id':{}}),workspace=None,deny=True)
call('forged native context','read',args=[[ids[0]],['title']],kwargs={'context':{'mp_workspace_id':fixture['workspaces']['B']['id']}},deny=True)
call('viewer native batch write','write',args=[[ids[1]],{'title':'Denied ID03 write'}],workspace='B',deny=True)
call('mixed native batch write','write',args=[ids,{'title':'Denied mixed write'}],workspace='A',deny=True)
assert base.snapshot(state,'g7-cache-http-after')==before and base.worker(native,'g7-cache-http-worker-after')==worker
f.write(OUT/'http-progress.json',dict(result='completed',checks=results))
f.save('http-matrix.json',dict(result='passed' if all(r['passed'] for r in results) else 'counterexamples_confirmed',checks=results,
    native_generation=26,image=state['image_id'],all36jobs_other16tables_and_worker_exact=True,
    source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['platform_addons/mp_identity/models/scoped.py','platform_addons/mp_identity/models/ir_http.py','addons/web/models/models.py']},
    failed=[r['name'] for r in results if not r['passed']],acceptance_ID03_passed=False))
print(json.dumps(dict(checks=len(results),passed=sum(r['passed'] for r in results),failed=[r['name'] for r in results if not r['passed']])) )
