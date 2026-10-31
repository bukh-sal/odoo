"""Real authenticated event ingress and native CRUD; synthetic owned data only."""
import hashlib,json,sys,traceback
from pathlib import Path
from uuid import uuid4
import fixture as j
f=j.f;out=Path(__file__).resolve().parent
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL
from modular_platform.contracts import validate
state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='event_tests_verified'
marker=j.LOCAL/'http-01.json';assert not marker.exists()
f.write(marker,dict(state='running',checks=[]))
fixture=f.load(j.LOCAL/'fixtures.json');cases=[];subscriptions=[]
def record(name):
    cases.append(dict(name=name,result='passed'));f.write(marker,dict(state='running',checks=cases))
def control(label,value):
    code="from modular_platform import durable\nenv.cr.rollback()\nenv.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.site_id'\");site=env.cr.fetchone()[0]\nenv.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'\");release=env.cr.fetchone()[0]\ndurable.set_control(env.cr,site,release,"+repr(value)+");env.cr.commit();print('MP_EVENT_HTTP_CONTROL_OK')"
    assert b'MP_EVENT_HTTP_CONTROL_OK' in f.native(state,label,[],code)
def event(client,operation,workspace='A',expected=200,error=None,headers=None,**values):
    status,body=client.request('/api/v1/events',dict(protocol=1,kind=operation+'_request',request_id=str(uuid4()),**values),workspace,{'X-CSRFToken':client.csrf,**(headers or {})})
    assert status==expected,('Unexpected HTTP event status',operation,status,expected)
    if error:
        assert body.get('error',{}).get('code')==error,('Unexpected event error code',operation,status)
        assert 'data' not in body
    else:validate('event-transport',body['data'])
    return body.get('data',body)
def subscribe(client,plugin='org.example.notes',workspace='A'):
    ident=event(client,'subscribe',workspace,headers={'X-MP-Binding':bindings[(plugin,workspace)]},topic='org.example.notes.changed',idempotency_key=str(uuid4()))['subscription_id']
    subscriptions.append((client,workspace,ident));return ident
def drain(client,sub,workspace='A'):
    for _ in range(50):
        rows=event(client,'poll',workspace,subscription_id=sub,limit=50)['deliveries']
        if not rows:return
        event(client,'ack',workspace,subscription_id=sub,receipts=[dict(delivery_id=r['id'],receipt=r['receipt'],generation=r['generation']) for r in rows])
    raise AssertionError('Unexpected retained fixture history size')
try:
    control('HTTP-dispatch-enable-01','enabled')
    alice=r1_probe.Client(state,fixture);bob=r1_probe.Client(state,fixture,'bob')
    binding_rows=json.loads(f.sql(state,'HTTP-event-bindings-01',"SELECT jsonb_agg(jsonb_build_object('plugin',i.plugin_id,'workspace',w.public_id,'alias',b.alias,'id',b.public_id)) FROM mp_service_binding b JOIN mp_plugin_installation i ON i.id=b.consumer_id JOIN mp_workspace w ON w.id=b.workspace_id WHERE b.state='active';"))
    bindings={(r['plugin'],name):r['id'] for r in binding_rows for name,w in fixture['workspaces'].items() if r['workspace']==w['public_id'] and r['alias']=='documents'}
    canvas_own=next(r['id'] for r in binding_rows if r['plugin']=='org.example.canvas' and r['workspace']==fixture['workspaces']['A']['public_id'] and r['alias']!='documents')
    body=dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4()))
    for extra,expected,code in [({},403,'FORBIDDEN'),({'X-CSRFToken':'synthetic-invalid'},403,'FORBIDDEN'),({'X-CSRFToken':alice.csrf,'X-MP-Client-Release':'sha256:'+'0'*64},409,'CONFLICT'),({'X-CSRFToken':alice.csrf,'Origin':'http://foreign.invalid'},403,None)]:
        status,result=alice.request('/api/v1/events',body,'A',{'X-MP-Binding':bindings[('org.example.notes','A')],**extra});assert status==expected,('Boundary status',status,expected)
        if code:assert result.get('error',{}).get('code')==code
    record('missing/invalid CSRF, stale client release and foreign Origin refused')
    for patch in [{'actor_id':fixture['users']['bob']['principal_id']},{'workspace_id':fixture['workspaces']['B']['public_id']},{'kind':'subscribe_result'}]:
        status,result=alice.request('/api/v1/events',{**body,**patch},'A',{'X-CSRFToken':alice.csrf,'X-MP-Binding':bindings[('org.example.notes','A')]});assert status==400 and result['error']['code']=='VALIDATION_FAILED'
    record('strict request schema rejects actor/workspace overrides and result kinds')
    for binding,expected,code in [(None,400,'VALIDATION_FAILED'),('not-a-uuid',400,'VALIDATION_FAILED'),(str(uuid4()),503,'DEPENDENCY_UNAVAILABLE'),(canvas_own,403,'FORBIDDEN')]:
        event(alice,'subscribe',expected=expected,error=code,headers={'X-MP-Binding':binding} if binding else {},topic='org.example.notes.changed',idempotency_key=str(uuid4()))
    event(alice,'subscribe',expected=404,error='NOT_FOUND',headers={'X-MP-Binding':bindings[('org.example.notes','A')]},topic='org.example.notes.unknown',idempotency_key=str(uuid4()))
    record('missing/invalid/unknown binding, mismatched Canvas boards binding and unknown topic refused')
    sub=subscribe(alice,'org.example.notes_labels');drain(alice,sub)
    note=alice.call('create',dict(title='Event HTTP owned '+uuid4().hex,body='Synthetic body must never enter event payload'),key=uuid4().hex)
    rows=event(alice,'poll',subscription_id=sub,limit=50,headers={'X-MP-Actor':'administrator','X-MP-Consumer':'forged'})['deliveries'];assert len(rows)==1
    row=rows[0];envelope=row['event'];assert envelope['site_id']==state['site_id'] and envelope['workspace_id']==fixture['workspaces']['A']['public_id']
    assert envelope['payload']==dict(note_id=note['id'],revision=1,change='created') and envelope['correlation_id']
    receipt=dict(delivery_id=row['id'],receipt=row['receipt'],generation=row['generation'])
    assert event(alice,'ack',subscription_id=sub,receipts=[receipt])==event(alice,'ack',subscription_id=sub,receipts=[receipt])
    assert event(alice,'poll',subscription_id=sub,limit=50)['deliveries']==[]
    record('real HTTP producer delivers minimized scoped event, ACK is idempotent and removes pending delivery')
    for operation,values in [('poll',dict(limit=50)),('status',{}),('replay',dict(event_ids=[envelope['id']]))]:
        event(bob,operation,'B',expected=404,error='NOT_FOUND',subscription_id=sub,**values)
        event(alice,operation,'B',expected=404,error='NOT_FOUND',subscription_id=sub,**values)
    foreign=subscribe(bob,workspace='B');drain(bob,foreign,'B')
    event(bob,'replay','B',expected=404,error='NOT_FOUND',subscription_id=foreign,event_ids=[envelope['id']])
    record('foreign actor/workspace subscriptions and cross-workspace replay disclose no payload')
    viewer=subscribe(alice,workspace='B');drain(alice,viewer,'B')
    bnote=bob.call('create',dict(title='Viewer read event '+uuid4().hex,body='Synthetic'),workspace='B',key=uuid4().hex)
    bitems=event(alice,'poll','B',subscription_id=viewer,limit=50)['deliveries'];assert len(bitems)==1 and bitems[0]['event']['aggregate_id']==bnote['id']
    alice.call('update',dict(note_id=bnote['id'],expected_revision=1,title='Denied viewer'),workspace='B',expect=403,code='FORBIDDEN')
    drain(alice,viewer,'B')
    record('current viewer may read authorized events but cannot mutate standard records')
    private={name:json.loads(f.sql(state,'HTTP-private-'+name.replace('.','-')+'-01','SELECT COALESCE(min(id),0) FROM '+name.replace('.','_')+';')) for name in ['mp.event.subscription','mp.event.delivery','mp.event.consumption','mp.event.consumer.state','mp.job','mp.outbox','mp.dispatch.control']}
    for model,ident in private.items():
        for method,args in [('read',[[ident or 1]]),('create',[{}]),('write',[[ident or 1],{}]),('unlink',[[ident or 1]])]:alice.native(method,args,model=model,deny=True)
    record('28 direct native CRUD attempts across all private event/job/outbox/control models denied')
    for client,workspace in [(alice,'A'),(alice,'B'),(bob,'B')]:
        views=client.native('get_views',kwargs={'views':[[False,'list'],[False,'form']],'options':{'toolbar':False}},workspace=workspace);assert {'list','form'}<=set(views['views'])
    updated=alice.call('update',dict(note_id=note['id'],expected_revision=1,title='Updated HTTP event proof'),key=uuid4().hex);assert updated['revision']==2
    alice.call('update',dict(note_id=note['id'],expected_revision=1,title='Stale'),expect=409,code='CONFLICT')
    alice.call('delete',dict(note_id=note['id'],expected_revision=2),key=uuid4().hex)
    history=event(alice,'poll',subscription_id=sub,limit=50)['deliveries'];assert [r['event']['payload']['change'] for r in history]==['updated','deleted']
    assert [r['event']['payload']['revision'] for r in history]==[2,3];drain(alice,sub)
    bob.call('delete',dict(note_id=bnote['id'],expected_revision=1),workspace='B',key=uuid4().hex)
    record('native Odoo list/form available in three role contexts; committed CRUD/CAS emits update/delete history')
    event(alice,'close',subscription_id=sub);event(alice,'close',subscription_id=sub)
    event(alice,'poll',expected=404,error='NOT_FOUND',subscription_id=sub,limit=50)
    record('close idempotent and closed stream cannot fetch')
    result=dict(result='passed',image_id=state['image_id'],inventory_digest=state['inventory_digest'],checks=cases,limits=['HTTP integration only; browser, protected/source/privacy qualification still required before EVT acceptance.','Known same-transaction pending-revision defect and queue-aware recovery remain required; committed CRUD is a distinct tested path.'])
except Exception as error:
    result=dict(result='failed',checks=cases,error_class=type(error).__name__,next='Inspect owner-private HTTP trace and exact marker before continuing; no fixture or operation replay.')
    (j.LOCAL/'logs/HTTP-01-trace.txt').write_text(traceback.format_exc(),encoding='utf8')
finally:
    for client,workspace,ident in subscriptions:
        try:event(client,'close',workspace,subscription_id=ident)
        except Exception:pass
    control('HTTP-dispatch-pause-01','paused')
    f.write(marker,dict(state='completed',**result));f.phase(state,'event_http_verified' if result['result']=='passed' else 'event_http_failed')
    f.save('HTTP-01.json',result);f.guard(state)
print(json.dumps(dict(result=result['result'],checks=len(cases))))
raise SystemExit(0 if result['result']=='passed' else 1)
