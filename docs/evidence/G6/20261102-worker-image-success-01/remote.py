"""Actual current worker credentials and ordinary original-actor remote job."""
import argparse,copy,json,sys,time
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
import jwt
sys.path.insert(0,str(Path(__file__).parent))
from approve_runtime import ROOT,OUT,PRIVATE,context,op,base,f,j,previous
from modular_platform.worker_authority import PublishedWorkerAuthority,AuthorityUnavailable
from modular_platform.tokens import ISSUER,AUDIENCE
from modular_platform.contracts import validate
s=previous.s;positive=s.positive

def credentials():
    state,native=context();assert native.config['generation']==23 and f.load(PRIVATE/'enable.json')['state']=='verified'
    before=base.snapshot(state,'image-success-credentials-before');assert len(before['mp_job'])==29
    worker=base.worker(native,'image-success-credentials-worker-before');operator=op(native);document=operator.publisher._document();assert document['generation']==11
    scope=f.load(PRIVATE/'runtime.json')['scope'];endpoint=next(e['descriptor'] for e in document['endpoints'] if all(e['descriptor'][k]==scope[k] for k in ['installation_id','site_id','workspace_id']))
    assert endpoint['generation']==9 and endpoint['state']=='enabled'
    authority=PublishedWorkerAuthority(operator.publisher.projection,deployment_id=native.config['deployment_id'],site_id=scope['site_id'])
    snapshot=authority.select(**{k:endpoint[k] for k in ['installation_id','workspace_id','endpoint_config']})
    try:authority.issuer(snapshot,'provider13_issuer')
    except AuthorityUnavailable:pass
    else:raise AssertionError('Retired issuer ref accepted')
    kid,key=authority.issuer(snapshot,endpoint['issuer_key_ref']);assert kid=='recovery19-key'
    retired=(operator.publisher.keys/'provider13_issuer.pem').read_bytes();now=int(time.time())
    body=dict(api_version='1.0',request_id=str(uuid4()),operation_id=str(uuid4()),method='analyze',endpoint_generation=9,
        input=dict(text='Current image approval verification',note_id=str(uuid4()),expected_revision=1),**scope)
    claims=dict(iss=ISSUER,aud=AUDIENCE,sub=scope['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+120,methods=['analyze'],endpoint_generation=9,**scope)
    validate('worker-request',body);validate('worker-claims',claims)
    cases=[]
    for name,expected in [('current',200),('old_endpoint7',403),('wrong_audience',401),('foreign_workspace',403),('retired_key_current_kid',401)]:
        request=copy.deepcopy(body);request.update(request_id=str(uuid4()),operation_id=str(uuid4()))
        payload=dict(claims,jti=str(uuid4()));signing=key
        if name=='old_endpoint7':request['endpoint_generation']=payload['endpoint_generation']=7
        elif name=='wrong_audience':payload['aud']='foreign-host-audience'
        elif name=='foreign_workspace':request['workspace_id']=payload['workspace_id']=str(uuid4())
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
    responses=json.loads(f.command('image-success-current-credentials',['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','-c',code],input=json.dumps(packet).encode()))
    assert len(responses)==len(cases)
    for case,response in zip(cases,responses):
        assert response['name']==case['name'] and response['status']==case['expected'],(response['name'],response['status'])
        if response['status']==200:
            validate('worker-response',response['body']);text=body['input']['text'];assert response['body']['data']==dict(characters=len(text),words=len(text.split()),lines=len(text.splitlines()))
        else:assert response['body']==dict(error=dict(code='UNAUTHENTICATED' if response['status']==401 else 'FORBIDDEN'))
    assert base.snapshot(state,'image-success-credentials-after')==before and operator.publisher._document()==document and authority._current(snapshot)==snapshot
    assert base.worker(native,'image-success-credentials-worker-after')==worker
    f.save('current-credentials.json',dict(result='passed_actual_new_image_current_generation_audience_scope_key_checks',publication_generation=11,endpoint_generation=9,
        cases=[dict(name=r['name'],status=r['status']) for r in responses],retired_issuer_ref_refused=True,
        all29jobs_other17tables_and_current_worker_exact=True,private_signing_material_only_in_operator_OS=True,
        limits='Direct operator-signed worker verification; ordinary host actor authorization is tested by the separate real job.'))
    f.write(PRIVATE/'credentials-marker.json',dict(state='verified'));print('Actual newimage current9 accepted; old7/foreign audience/workspace/retired key refused; host data and worker unchanged',flush=True)

def job():
    state,native=context();assert native.config['generation']==23 and f.load(PRIVATE/'credentials-marker.json')['state']=='verified'
    marker=PRIVATE/'remote-job.json';assert not marker.exists()
    before=base.snapshot(state,'image-success-job-before');assert len(before['mp_job'])==29
    worker=base.worker(native,'image-success-job-worker-before');client=s.client(state,'alice');saved=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
    for workspace in ['A','B','C']:
        views=client.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace);assert set(views['views'])=={'list','form'}
    record=dict(state='requesting',key='changed-image-success-'+uuid4().hex);f.write(marker,record)
    response=positive.call(client,saved,'analyze',dict(note_id=saved['note_id'],expected_revision=saved['revision']),record['key']);assert response['job']['state']=='pending'
    record.update(state='enqueued',job_id=response['job']['id']);f.write(marker,record)
    args=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    record['state']='running';f.write(marker,record);runner=json.loads(f.command('image-success-ordinary-runner',args,timeout=180));f.save('ordinary-runner.json',runner)
    record['state']='runner_terminal_needs_verification';f.write(marker,record)
    actual=positive.call(client,saved,'status',dict(note_id=saved['note_id']))['job']
    assert actual['id']==record['job_id'] and actual['state']=='completed' and actual['attempts']==1 and actual['error_code'] is None
    assert actual['result']==dict(note_id=saved['note_id'],revision=saved['revision'],statistics=saved['expected_statistics'])
    after=base.snapshot(state,'image-success-job-after')
    for table,rows in before.items():
        current=[r for r in after[table] if r['public_id']!=record['job_id']] if table=='mp_job' else after[table]
        assert current==rows,table
    assert base.worker(native,'image-success-job-worker-after')==worker
    code,response=s.client(state).request('/api/v1/operations/installed');assert code==200;validate('manager-view',response['data'])
    provider=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
    assert provider['health']['state']=='healthy' and provider['features'][0]['availability']=='enabled'
    for action in ['upgrade','enable']:
        cycle=f.load(PRIVATE/(action+'.json'))
        mirror=json.loads(f.command('image-success-'+action+'-mirror',base.prefix()+['operations','--store',str(native.store.root),'mirror-status',cycle['operation_id']]+base.validation(native)))
        f.save(action+'-completed-mirror.json',mirror)
        code,response=s.client(state).request('/api/v1/operations/status/'+cycle['operation_id']);assert code==200
        view=validate_operations_view(response['data']);assert view['state']=='completed' and view['source']=='operator_journal_mirror'
    f.save('ordinary-remote-job.json',dict(result='passed_actual_original_actor_remote_job_after_changed_image_upgrade_and_recovery',generation=23,job=actual,
        ordinary_independent_CLI=True,current_worker_image548202_publication11_endpoint9=True,native_A_B_C_views_retained=True,
        old29job_outcomes_and_other17tables_exact=True,manager_healthy_provider_enabled=True,new_upgrade_enable_completed_HTTP_mirrors=True,browser_rendering_tested=False))
    record['state']='verified';f.write(marker,record);f.phase(state,'changed_image_upgrade_enabled_remote_verified');f.guard(state)
    print('Actual ordinary original-Alice remote job completed once on new approved image; native views/old29jobs/otherdata exact, provider healthy+enabled',flush=True)

from modular_platform.contracts import validate_operations_view
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['credentials','job']);a=p.parse_args();globals()[a.action]()
