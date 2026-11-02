"""Actual approved worker duplicate and signed-scope tests; no business mutation."""
import copy,hashlib,json,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-notes-stats-install-01'))
from install import context,base,f,j
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerPlanningReader
from modular_platform.worker_authority import PublishedWorkerAuthority
from modular_platform.tokens import ISSUER,AUDIENCE
from modular_platform.contracts import validate
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'worker-scope-01';MARKER=PRIVATE/'qualification.json'

# No signing key or database access enters this short-lived probe. Only scoped
# invocation tokens cross stdin into the already-running app network client.
PROBE='''import http.client,json,sys
from concurrent.futures import ThreadPoolExecutor
p=json.load(sys.stdin)
def call(case):
 c=http.client.HTTPConnection(p['address'],p['port'],timeout=5)
 try:
  c.request('POST','/analyze',json.dumps(case['request']).encode(),{'Host':p['host'],'Content-Type':'application/json','Authorization':'Bearer '+case['token']})
  r=c.getresponse();body=json.loads(r.read(65537));return {'name':case['name'],'status':r.status,'body':body}
 finally:c.close()
results=[call(case) for case in p['sequential']]
with ThreadPoolExecutor(max_workers=8) as pool:results+=list(pool.map(call,p['concurrent']))
print(json.dumps(results))
'''

def run():
    state,native=context();assert native.config['generation']==18
    continuation=PRIVATE.exists()
    if continuation:
        # The first attempt failed local schema validation before signing/IO.
        # Preserve that baseline; refuse any uncertain already-dispatched run.
        assert not MARKER.exists()
        before=f.load(PRIVATE/'data-before.json');worker=f.load(PRIVATE/'worker-before.json')
        assert base.snapshot(state,'worker-scope-continuation2-before')==before
        assert base.worker(native,'worker-scope-continuation2-worker-before')==worker
    else:
        protect_directory(PRIVATE)
        before=base.snapshot(state,'worker-scope-before')
        worker=base.worker(native,'worker-scope-worker-before');f.write(PRIVATE/'data-before.json',before);f.write(PRIVATE/'worker-before.json',worker)
    assert len(before['mp_job'])==22 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    op=WorkerPlanningReader(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')
    document=op.publisher._document();scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope']
    descriptor=next(e['descriptor'] for e in document['endpoints'] if e['descriptor']['installation_id']==scope['installation_id'])
    authority=PublishedWorkerAuthority(op.publisher.projection,deployment_id=native.config['deployment_id'],site_id=scope['site_id'])
    snapshot=authority.select(**{k:descriptor[k] for k in ('installation_id','workspace_id','endpoint_config')});assert snapshot.publication_generation==5 and descriptor['generation']==3
    kid,key=authority.issuer(snapshot,descriptor['issuer_key_ref']);now=int(time.time())
    inputs=copy.deepcopy(f.load(ROOT/'packages/contracts/examples/v1/worker-request.json')['input'])
    inputs.update(text='Scoped canonical worker\nreference check',note_id=str(uuid4()))
    request=dict(api_version='1.0',request_id=str(uuid4()),operation_id=str(uuid4()),method='analyze',input=inputs,endpoint_generation=3,**scope)
    validate('worker-request',request)
    claims=dict(iss=ISSUER,aud=AUDIENCE,sub=scope['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+120,methods=['analyze'],endpoint_generation=3,**scope)
    validate('worker-claims',claims)
    cases=[];expected={}
    def case(name,body=None,changes=None,status=200,code=None,signing_key=key,signing_kid=kid,algorithm='RS256'):
        current={**claims,'jti':str(uuid4()),**(changes or {})}
        token=jwt.encode(current,signing_key,algorithm=algorithm,headers={'kid':signing_kid})
        value=copy.deepcopy(body or request);validate('worker-request',value)
        cases.append(dict(name=name,request=value,token=token));expected[name]=dict(status=status,code=code,request_id=value['request_id'],operation_id=value['operation_id'])
    case('first')
    repeated={**request,'request_id':str(uuid4())};case('duplicate_new_transport_id',repeated)
    changed={**request,'input':{**inputs,'text':'Changed input'}};case('same_operation_changed_input',changed,status=409,code='CONFLICT')
    case('original_after_conflict')
    for field in ('site_id','workspace_id','installation_id','endpoint_generation'):
        wrong=4 if field=='endpoint_generation' else str(uuid4())
        altered={**request,field:wrong}
        case('payload_only_'+field,altered,status=401,code='UNAUTHENTICATED')
        changes={field:wrong}
        if field=='installation_id':changes['sub']=wrong
        case('signed_matching_foreign_'+field,altered,changes,status=403,code='FORBIDDEN')
    for name,changes in [
        ('expired_retry',dict(iat=now-120,nbf=now-120,exp=now-1)),
        ('future_not_before',dict(iat=now+60,nbf=now+60,exp=now+120)),
        ('wrong_audience',dict(aud='another-worker')),
        ('wrong_issuer',dict(iss='another-host')),
        ('wrong_subject',dict(sub=str(uuid4()))),
        ('wrong_method',dict(methods=['unsupported'])),
        ('excessive_lifetime',dict(exp=now+600)),
    ]:case(name,changes=changes,status=401,code='UNAUTHENTICATED')
    case('wrong_key_id',status=401,code='UNAUTHENTICATED',signing_kid='unapproved-key')
    case('wrong_signature',status=401,code='UNAUTHENTICATED',signing_key=rsa.generate_private_key(public_exponent=65537,key_size=2048))
    case('wrong_algorithm',status=401,code='UNAUTHENTICATED',signing_key=b'not-a-trusted-signing-key',algorithm='HS256')
    concurrent=[];operation=str(uuid4())
    for index in range(8):
        case('concurrent_duplicate_'+str(index),{**request,'operation_id':operation,'request_id':str(uuid4())})
        concurrent.append(cases.pop())
    from urllib.parse import urlsplit
    destination=urlsplit(descriptor['destination']);egress=snapshot.egress[descriptor['endpoint_config']]
    packet=dict(address=egress['addresses'][0],port=destination.port,host=destination.netloc,sequential=cases,concurrent=concurrent)
    # The operator reselects its immutable scoped publication before dispatch.
    assert authority._current(snapshot)==snapshot and op.publisher._document()==document
    f.write(MARKER,dict(state='sending_actual_worker_requests',cases=len(expected),publication_generation=5,endpoint_generation=3))
    responses=json.loads(f.command('worker-scope-actual-http',['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','-c',PROBE],input=json.dumps(packet).encode(),timeout=90))
    f.write(MARKER,dict(state='responses_received_needs_verification',cases=len(expected)))
    stats=dict(characters=len(request['input']['text']),words=len(request['input']['text'].split()),lines=len(request['input']['text'].splitlines()))
    results=[]
    assert len(responses)==len(expected) and len({r['name'] for r in responses})==len(expected)
    for response in responses:
        name=response['name'];want=expected[name];assert response['status']==want['status'],(name,response['status'])
        if want['code']:assert response['body']==dict(error=dict(code=want['code'])),name
        else:
            validate('worker-response',response['body'])
            assert response['body']['data']==stats and response['body']['request_id']==want['request_id'] and response['body']['operation_id']==want['operation_id'],name
        results.append(dict(name=name,status=response['status'],error_code=want['code']))
    assert base.snapshot(state,'worker-scope-after')==before
    assert base.worker(native,'worker-scope-worker-after')==worker
    assert op.publisher._document()==document and authority._current(snapshot)==snapshot
    report=dict(result='passed_actual_canonical_worker_duplicates_and_scoped_tokens',cases=results,configuration_generation=18,dispatch_generation=88,
        same_running_worker_image_key_config3_publication5=True,all17tables_and22terminal_jobs_exact=True,
        private_key_remains_operator_only=True,short_lived_tokens_stdin_only_not_logged=True,
        positive_duplicate_responses_and_changed_input_conflict=True,concurrent_duplicate_requests=8,
        source_commit='be3910ee',source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['services/document_stats/engine.py','services/document_stats/server.py','packages/platform_sdk/modular_platform/tokens.py']},
        limits=['Direct real worker verifier qualification; no host gateway bypass or original-actor finalization claim. Installed gateway/bridge positive and outage evidence is separate. No private cache instrumentation or single-computation-count assertion. In-flight revocation, external recovery and changed-image qualification remain.'])
    f.save('qualification.json',report);f.write(MARKER,dict(state='verified',cases=len(results)));f.phase(state,'worker_scope_verified');f.guard(state)
    print('Actual canonical worker: %d duplicate/scope/token cases pass;17 tables/22 terminal jobs and running worker/authority exact'%len(results),flush=True)

if __name__=='__main__':run()
