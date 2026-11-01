"""Run actual installed classes/registry, no code injection; all writes rollback."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
label=sys.argv[1] if len(sys.argv)>1 else 'core12-installed-guards'
assert label in {'core12-installed-guards','core12-installed-guards-02'}
marker=j.LOCAL/('core12-guards-01.json' if label=='core12-installed-guards' else label+'.json');assert not marker.exists();f.write(marker,dict(state='running'))
code="import json,sys,unittest\nscope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'__name__':'current_installed_job_guards'}\nexec(compile("+repr((OUT/'native_guards.py').read_text())+",'current_installed_job_guards','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['CurrentJobGuards']))\nprint('MP_CURRENT_GUARDS='+json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/(label+'.stdout')).read_bytes()
rows=[json.loads(line.split('MP_CURRENT_GUARDS=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CURRENT_GUARDS=')];assert len(rows)==1,'Inspect exact child; never replay writes'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],image_id=state['image_id'],source_substitution=False,all_writes_rolled_back=True,test_sha256=hashlib.sha256((OUT/'native_guards.py').read_bytes()).hexdigest())
f.save('native-guards-02.json' if label.endswith('-02') else 'native-guards.json',result);f.write(marker,dict(state='completed',**result));f.guard(state);print(json.dumps(dict(result=result['result'],tests=result['tests'],errors=len(result['errors']),failures=len(result['failures']))));raise SystemExit(0 if result['successful'] else 1)
