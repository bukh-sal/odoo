"""Capture actual committed event tests; preserve attempts and queues."""
import argparse,hashlib,json,re
from pathlib import Path
import fixture as j
f=j.f;out=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--label',default='backend-01');parser.add_argument('--case');args=parser.parse_args();assert re.fullmatch('[a-z0-9-]{1,35}',args.label)
state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase'] in ({'event_tests_failed','event_tests_verified'} if args.case else {'event_smoke_verified'})
source=(out/'native_tests.py').read_text();selector="suite.addTest(scope['NativeEventTests']("+repr(args.case)+"))" if args.case else "suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope['NativeEventTests']))"
code=f"""import json,sys,unittest
env.cr.rollback()
scope={{'ENV':env,'FIXTURE':json.loads({(j.LOCAL/'fixtures.json').read_text()!r}),'__name__':'g6_native_events','__file__':'/opt/modular/g6_native_events.py'}}
exec(compile({source!r},scope['__file__'],'exec'),scope)
suite=unittest.TestSuite()
{selector}
result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
print('MP_NATIVE_EVENTS='+json.dumps(dict(tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors],successful=result.wasSuccessful())))
env.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)
"""
marker=j.LOCAL/(args.label+'.json');assert not marker.exists();f.write(marker,dict(state='running',image_id=state['image_id'],case=args.case))
label='events-'+args.label
try:raw=f.native(state,label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/(label+'.stdout')).read_bytes()
rows=[json.loads(line.split('MP_NATIVE_EVENTS=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_NATIVE_EVENTS=')]
assert len(rows)==1,'Inspect exact retained native process/private logs before any continuation'
result=rows[0];f.write(marker,dict(state='completed',**result));f.phase(state,'event_tests_verified' if result['successful'] else 'event_tests_failed')
target=out/('native-'+args.label+'.json');assert not target.exists();f.write(target,dict(result='passed' if result['successful'] else 'failed',**result,image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],database=state['active_db'],container=state['project']+'-'+label,source_sha256=hashlib.sha256(source.encode()).hexdigest(),limits=['Actual native/PostgreSQL committed tests; HTTP/browser/protected-source qualification remains required before EVT acceptance.','Only suite-created subscriptions closed; every event/receipt/consumer effect retained, dispatch paused after suite.','Known same-transaction pending-revision unlink defect remains required ID-03 fix; no claim of full G6 lifecycle/recovery or R1 completion.']))
f.guard(state);print(json.dumps(dict(result='passed' if result['successful'] else 'failed',tests=result['tests'],failures=len(result['failures']),errors=len(result['errors']))));raise SystemExit(0 if result['successful'] else 1)
