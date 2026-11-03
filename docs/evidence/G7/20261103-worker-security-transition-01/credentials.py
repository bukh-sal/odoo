"""Real RS256 current/stale/audience/scope/key checks against dependency worker87."""
import copy,json,sys,time
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
import jwt
sys.path.insert(0,str(Path(__file__).parent))
from runtime import s,op,base,f,j,PRIVATE
from modular_platform.worker_authority import PublishedWorkerAuthority,AuthorityUnavailable
from modular_platform.tokens import ISSUER,AUDIENCE
from modular_platform.contracts import validate

def credentials():
    state,native=s.context();assert native.config['generation']==31 and f.load(PRIVATE/'enable.json')['state']=='verified'
    before=base.snapshot(state,'worker-security-credentials-before');assert len(before['mp_job'])==37
    worker=base.worker(native,'worker-security-credentials-worker-before');operator=op(native);document=operator.publisher._document();assert document['generation']==13
    scope=f.load(PRIVATE/'runtime.json')['scope'];endpoint=next(e['descriptor'] for e in document['endpoints'] if all(e['descriptor'][k]==scope[k] for k in ['installation_id','site_id','workspace_id']))
    assert endpoint['generation']==11 and endpoint['state']=='enabled'
    authority=PublishedWorkerAuthority(operator.publisher.projection,deployment_id=native.config['deployment_id'],site_id=scope['site_id'])
    snapshot=authority.select(**{k:endpoint[k] for k in ['installation_id','workspace_id','endpoint_config']})
    try:authority.issuer(snapshot,'provider13_issuer')
    except AuthorityUnavailable:pass
    else:raise AssertionError('Retired issuer ref accepted')
    kid,key=authority.issuer(snapshot,endpoint['issuer_key_ref']);assert kid=='recovery19-key'
    retired=(operator.publisher.keys/'provider13_issuer.pem').read_bytes();now=int(time.time())
    body=dict(api_version='1.0',request_id=str(uuid4()),operation_id=str(uuid4()),method='analyze',endpoint_generation=11,
        input=dict(text='Current image approval verification',note_id=str(uuid4()),expected_revision=1),**scope)
    claims=dict(iss=ISSUER,aud=AUDIENCE,sub=scope['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+120,methods=['analyze'],endpoint_generation=11,**scope)
    validate('worker-request',body);validate('worker-claims',claims)
    cases=[]
    for name,expected in [('current',200),('old_endpoint9',403),('wrong_audience',401),('foreign_workspace',403),('payload_workspace',403),('payload_site',403),('retired_key_current_kid',401)]:
        request=copy.deepcopy(body);request.update(request_id=str(uuid4()),operation_id=str(uuid4()))
        payload=dict(claims,jti=str(uuid4()));signing=key
        if name=='old_endpoint9':request['endpoint_generation']=payload['endpoint_generation']=9
        elif name=='wrong_audience':payload['aud']='foreign-host-audience'
        elif name=='foreign_workspace':request['workspace_id']=payload['workspace_id']=str(uuid4())
        elif name=='payload_workspace':request['workspace_id']=str(uuid4())
        elif name=='payload_site':request['site_id']=str(uuid4())
        elif name=='retired_key_current_kid':signing=retired
        cases.append(dict(name=name,request=request,token=jwt.encode(payload,signing,algorithm='RS256',headers={'kid':kid}),expected=expected))
    destination=urlsplit(endpoint['destination']);packet=dict(address=snapshot.egress[endpoint['endpoint_config']]['addresses'][0],port=destination.port,host=destination.netloc,cases=cases)
    code="""import http.client,json,sys
p=json.load(sys.stdin);results=[]
for case in p['cases']:
 c=http.client.HTTPConnection(p['address'],p['port'],timeout=5)
 try:
  c.request('POST','/analyze',json.dumps(case['request']).encode(),{'Host':p['host'],'Content-Type':'application/json','Authorization':'Bearer '+case['token']})
  r=c.getresponse();results.append(dict(name=case['name'],status=r.status,body=json.loads(r.read(65537))))
 finally:c.close()
print(json.dumps(results))
"""
    f.write(PRIVATE/'credentials-marker.json',dict(state='sending_current_authority_cases'))
    responses=json.loads(f.command('worker-security-current-credentials',['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','-c',code],input=json.dumps(packet).encode()))
    assert len(responses)==len(cases)
    for case,response in zip(cases,responses):
        assert response['name']==case['name'] and response['status']==case['expected'],(response['name'],response['status'])
        if response['status']==200:
            validate('worker-response',response['body']);text=body['input']['text'];assert response['body']['data']==dict(characters=len(text),words=len(text.split()),lines=len(text.splitlines()))
        else:assert response['body']==dict(error=dict(code='UNAUTHENTICATED' if response['status']==401 else 'FORBIDDEN'))
    assert base.snapshot(state,'worker-security-credentials-after')==before and operator.publisher._document()==document and authority._current(snapshot)==snapshot
    assert base.worker(native,'worker-security-credentials-worker-after')==worker
    f.save('current-credentials.json',dict(result='passed_actual_new_image_current_generation_audience_scope_key_checks',publication_generation=13,endpoint_generation=11,
        cases=[dict(name=r['name'],status=r['status']) for r in responses],retired_issuer_ref_refused=True,
        all37jobs_other17tables_and_current_worker_exact=True,private_signing_material_only_in_operator_OS=True,
        limits='Direct operator-signed worker verification; ordinary host actor authorization is tested by the separate real job.'))
    f.write(PRIVATE/'credentials-marker.json',dict(state='verified'));print('Actual dependency image current11 accepted; old9/foreign audience/workspace/retired key refused; host data and worker unchanged',flush=True)

if __name__=="__main__":credentials()
