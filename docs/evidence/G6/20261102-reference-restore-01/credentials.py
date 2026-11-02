"""Real rotated worker key verification; signing material stays in operator OS."""
import copy,json,sys,time
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from recovery import context,base,f,j,OUT,PRIVATE
from authority import op,AUTH
from modular_platform.worker_authority import PublishedWorkerAuthority,AuthorityUnavailable
from modular_platform.tokens import ISSUER,AUDIENCE
from modular_platform.contracts import validate
import jwt
from urllib.parse import urlsplit

state,native=context();record=f.load(AUTH);assert record['state']=='current_key_published7'
assert not (OUT/'current-credentials.json').exists()
before=base.snapshot(state,'reference-credentials-before');operator=op(native);operator.publisher._authorize()
document=operator.publisher._document();assert document['generation']==7
entry=next(e for e in document['endpoints'] if e['descriptor']['installation_id']==record['scope']['installation_id']);endpoint=entry['descriptor']
authority=PublishedWorkerAuthority(operator.publisher.projection,deployment_id=native.config['deployment_id'],site_id=record['scope']['site_id'])
snapshot=authority.select(**{k:endpoint[k] for k in ('installation_id','workspace_id','endpoint_config')});assert snapshot.publication_generation==7 and endpoint['generation']==5
try:authority.issuer(snapshot,'provider13_issuer')
except AuthorityUnavailable:pass
else:raise AssertionError('Retired issuer reference was accepted for current approval')
kid,current=authority.issuer(snapshot,endpoint['issuer_key_ref']);assert kid=='recovery19-key'
old=(operator.publisher.keys/'provider13_issuer.pem').read_bytes();now=int(time.time())
body=dict(api_version='1.0',request_id=str(uuid4()),operation_id=str(uuid4()),method='analyze',endpoint_generation=5,
    input=dict(text='Recovery key rotation check',note_id=str(uuid4()),expected_revision=1),**record['scope'])
claims=dict(iss=ISSUER,aud=AUDIENCE,sub=record['scope']['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+120,methods=['analyze'],endpoint_generation=5,**record['scope'])
validate('worker-request',body);validate('worker-claims',claims)
cases=[]
for name,key,key_id,generation,expected in [('current_key',current,kid,5,200),('retired_key_current_kid',old,kid,5,401),('retired_key_and_kid',old,'provider13-key',5,401),('new_key_old_endpoint',current,kid,3,403)]:
    request=copy.deepcopy(body);request.update(endpoint_generation=generation,request_id=str(uuid4()))
    payload=dict(claims,jti=str(uuid4()),endpoint_generation=generation)
    cases.append(dict(name=name,request=request,token=jwt.encode(payload,key,algorithm='RS256',headers={'kid':key_id}),expected=expected))
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
f.write(PRIVATE/'credentials-marker.json',dict(state='sending_rotated_key_test_requests'))
responses=json.loads(f.command('reference-current-key-http',['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','-c',code],input=json.dumps(packet).encode()))
assert len(responses)==4
for case,response in zip(cases,responses):
    assert response['name']==case['name'] and response['status']==case['expected'],(response['name'],response['status'])
    if response['status']!=200:assert response['body']==dict(error=dict(code='UNAUTHENTICATED' if response['status']==401 else 'FORBIDDEN'))
    else:
        validate('worker-response',response['body']);text=body['input']['text']
        assert response['body']['data']==dict(characters=len(text),words=len(text.split()),lines=len(text.splitlines()))
assert base.snapshot(state,'reference-credentials-after')==before
assert operator.publisher._document()==document and authority._current(snapshot)==snapshot
assert base.worker(native,'reference-credentials-current-worker')==f.load(PRIVATE/'worker-current.json')
f.save('current-credentials.json',dict(result='passed_actual_rotated_worker_key_and_retired_credential_refusal',publication_generation=7,endpoint_generation=5,key_id=kid,
    retired_issuer_ref_denied_for_current_snapshot=True,cases=[dict(name=r['name'],status=r['status']) for r in responses],all17tables_and28jobs_exact=True,
    same_current_worker_publication=True,private_signing_material_stays_operator_only=True,short_tokens_stdin_only=True,
    limits=['Direct worker verifier/issuer checks, not a host gateway bypass or arbitrary external-effect recovery claim. Ordinary recovered job remains the separate final integration check.']))
f.write(PRIVATE/'credentials-marker.json',dict(state='verified'))
print('Actual rotated key accepted; old signing key/kid and old endpoint generation rejected; current issuer denies retired reference, host data exact',flush=True)
