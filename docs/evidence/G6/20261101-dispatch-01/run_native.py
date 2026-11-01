"""Test new private host helper in a short-lived native process, not deployment."""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
parser=argparse.ArgumentParser();parser.add_argument('--label',default='fence-01');parser.add_argument('--case');args=parser.parse_args()
assert re.fullmatch('[a-z0-9-]{1,35}',args.label)
assert state['phase'] in ({'dispatch_counterexamples_verified','dispatch_fence_failed','dispatch_fence_verified'} if args.case else {'dispatch_counterexamples_verified','dispatch_fence_failed','dispatch_history_source_verified'})
helper=ROOT/'packages/platform_sdk/modular_platform/dispatch_lifecycle.py';tests=OUT/'native_tests.py'
marker=j.LOCAL/('dispatch-'+args.label+'.json');assert not marker.exists();f.write(marker,dict(state='running'))
selector="suite.addTest(scope['DispatchLifecycleTests']("+repr(args.case)+"))" if args.case else "suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope['DispatchLifecycleTests']))"
code="import json,sys,types,unittest\nenv.cr.rollback()\nmodule=types.ModuleType('modular_platform.dispatch_lifecycle_probe');module.__package__='modular_platform';sys.modules[module.__name__]=module\nexec(compile("+repr(helper.read_text())+",'dispatch_lifecycle_probe','exec'),module.__dict__)\nscope={'ENV':env,'FIXTURE':json.loads("+repr((j.LOCAL/'fixtures.json').read_text())+"),'LC':module,'__name__':'g6_native_lifecycle'}\nexec(compile("+repr(tests.read_text())+",'native_lifecycle_tests','exec'),scope)\nsuite=unittest.TestSuite()\n"+selector+"\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)\nprint('MP_LIFECYCLE_FENCE='+json.dumps(dict(tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors],successful=result.wasSuccessful())))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,'dispatch-'+args.label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/('dispatch-'+args.label+'.stdout')).read_bytes()
rows=[json.loads(line.split('MP_LIFECYCLE_FENCE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_LIFECYCLE_FENCE=')];assert len(rows)==1,'Inspect exact child/logs before continuation'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],image_id=state['image_id'],helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),test_sha256=hashlib.sha256(tests.read_bytes()).hexdigest(),limits=['Source helper evaluated in disposable native process; not a deployed helper or integrated executor/recovery qualification.','Test business/queue writes rollback and are snapshot-checked. Real producer/drain concurrency case commits the operator fence: control generation advances by two and outstanding receipt metadata is invalidated; producer/business/history rows are retained.'])
f.write(marker,dict(state='completed',**result));f.save(args.label+'.json',result);f.phase(state,'dispatch_fence_verified' if result['successful'] else 'dispatch_fence_failed');f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'],errors=len(result['errors']),failures=len(result['failures']))));raise SystemExit(0 if result['successful'] else 1)
