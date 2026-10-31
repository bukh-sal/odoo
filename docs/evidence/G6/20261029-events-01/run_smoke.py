"""Once-only rollback smoke driver; preserve native child/error evidence."""
import argparse,hashlib,json,re
from pathlib import Path
import fixture as j
parser=argparse.ArgumentParser();parser.add_argument('--label',default='event-smoke-01');args=parser.parse_args();assert re.fullmatch('event-smoke-[0-9]{2}',args.label)
f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase'] in {'event_fixture_ready','event_smoke_failed'}
out=Path(__file__).resolve().parent;source=(out/'native_smoke.py').read_text()
code="import json\nenv.cr.rollback()\nexec(compile(SOURCE,'/opt/modular/g6_event_smoke.py','exec'),{'ENV':env,'FIXTURE':json.loads(FIXTURE),'__name__':'g6_event_smoke'})\n".replace('compile(SOURCE,','compile('+repr(source)+',').replace('json.loads(FIXTURE)','json.loads('+repr((j.LOCAL/'fixtures.json').read_text())+')')
marker=j.LOCAL/(args.label+'.json');assert not marker.exists();f.write(marker,dict(state='running',image=state['image_id']))
try:raw=f.native(state,args.label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/(args.label+'.stdout')).read_bytes()
rows=[json.loads(line.split('MP_EVENT_SMOKE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_EVENT_SMOKE=')]
assert len(rows)==1,'Inspect exact native child and private diagnostics before any continuation'
result=rows[0];f.write(marker,dict(state='completed',**result));f.phase(state,'event_smoke_verified' if result['successful'] else 'event_smoke_failed')
report='native-smoke.json' if args.label=='event-smoke-01' else 'native-smoke-stored-revision.json'
assert not (out/report).exists();f.write(out/report,dict(result='passed' if result['successful'] else 'failed',**result,image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],database=state['active_db'],source_sha256=hashlib.sha256(source.encode()).hexdigest(),limits=['Rollback-only real native API/import wiring check; not complete EVT acceptance.','No event/business/subscription/receipt/counter/state row committed; exact zero counts after rollback.','Existing Note.unlink lacks a pending revision flush in same-transaction write/unlink. Defect remains required under ID-03; this corrected event-history smoke flushes the stored revision explicitly, as separate committed CRUD operations do.','Committed producer/concurrent allocation/consumer retry/authorization/HTTP/browser/lifecycle/recovery qualification remains required.']))
f.guard(state);print(json.dumps(dict(result='passed' if result['successful'] else 'failed',checks=len(result['checks']),rolled_back=True)))
raise SystemExit(0 if result['successful'] else 1)
