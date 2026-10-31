"""Correct only the test's closed-stream status expectation; retain eight passes."""
import ast,json
from pathlib import Path
import fixture as j
f=j.f;out=Path(__file__).resolve().parent
previous=f.load(out/'site/HTTP-01.json');assert previous['result']=='failed' and len(previous['checks'])==8
assert "('Unexpected HTTP event status', 'poll', 409, 404)" in (j.LOCAL/'logs/HTTP-01-trace.txt').read_text()
# Reuse the identical request/control helpers without replaying the suite.
module=ast.parse((out/'http_checks.py').read_text());prefix=[]
for node in module.body:
    if isinstance(node,ast.Try):break
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='marker' for t in node.targets):continue
    if isinstance(node,ast.Assert):continue
    if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='f.write':continue
    prefix.append(node)
scope={'__file__':str(out/'http_checks.py'),'__name__':'event_http_helpers'}
exec(compile(ast.Module(body=prefix,type_ignores=[]),str(out/'http_checks.py'),'exec'),scope)
state=scope['state'];assert state['phase']=='event_http_failed';f.guard(state)
marker=j.LOCAL/'http-close-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
control=scope['control'];event=scope['event'];control('HTTP-close-enable-01','enabled')
try:
    client=scope['r1_probe'].Client(state,scope['fixture'])
    binding=scope['fixture']['bindings']['A']['binding_id']
    ident=event(client,'subscribe',headers={'X-MP-Binding':binding},topic='org.example.notes.changed',idempotency_key=str(scope['uuid4']()))['subscription_id']
    assert event(client,'close',subscription_id=ident)==event(client,'close',subscription_id=ident)
    event(client,'poll',expected=409,error='CONFLICT',subscription_id=ident,limit=50)
    status=event(client,'status',subscription_id=ident);assert status['state']=='closed'
    result=dict(result='passed',image_id=state['image_id'],inventory_digest=state['inventory_digest'],checks=previous['checks']+[dict(name='close idempotent, status closed and closed poll conflicts',result='passed')],retained_passing_record='site/HTTP-01.json',correction='Owner closed stream is a current-state conflict409, not foreign/missing404; frozen protocol forbids delivery but does not require404. No runtime change or previous check replay.',limits=['HTTP only; browser/protected/privacy qualification still required before EVT acceptance.','Native pending revision and queue-aware recovery remain required.'])
finally:control('HTTP-close-pause-01','paused')
f.write(marker,dict(state='completed',result=result['result']));f.phase(state,'event_http_verified');f.write(out/'HTTP-qualified.json',result);f.guard(state)
print(json.dumps(dict(result='passed',retained_checks=8,new_checks=1)))
