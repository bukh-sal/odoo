"""Once-only bounded current-image event checks; exact private marker first."""
import hashlib,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.contracts import validate
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
corrected=sys.argv[1:]==['--after-schema-correction'];assert not sys.argv[1:] or corrected
assert state['phase']==('host-event-native-01' if corrected else 'host_event_proxy_serving')
assert f.load(j.LOCAL/'host-event-proxy-01.json')['state']=='stopped'
browser=f.load(OUT/'browser-observation.json');assert len(browser['checks'])==4 and not browser['failures'] and browser['native_Odoo_default']
if corrected:
    old=f.load(j.LOCAL/'host-event-native-01.json');assert old['state']=='starting' and len(old['idempotency_key'])==32 and all(c in '0123456789abcdef' for c in old['idempotency_key'])
    count=f.command('host-event-schema-reconcile-01',['docker','exec',state['project']+'-db-1','psql','-U','postgres','-d',state['active_db'],'-Atc',"SELECT count(*) FROM mp_event_subscription WHERE idempotency_key='"+old['idempotency_key']+"'"])
    assert count.strip()==b'0'
label='host-event-native-02' if corrected else 'host-event-native-01'
marker=j.LOCAL/(label+'.json');assert not marker.exists();key=str(uuid4())
validate('event-transport',dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=key))
f.write(marker,dict(state='starting',idempotency_key=key))
code='ENV=env\nFIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nKEY='+repr(key)+'\n'+(OUT/'native_current.py').read_text()
raw=f.native(state,label,[],code);rows=[json.loads(l.split('MP_CURRENT_EVENTS=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CURRENT_EVENTS=')];assert len(rows)==1
result=dict(**rows[0],image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=8,test_sha256=hashlib.sha256((OUT/'native_current.py').read_bytes()).hexdigest());f.save('native-current.json',result)
f.write(marker,dict(state='completed',idempotency_key=key,**result));f.phase(state,'host_events_current_native_verified');f.guard(state)
print('Three actual current-image rollback/bus/scope cases pass; one test stream retained closed, no business mutation committed.')
