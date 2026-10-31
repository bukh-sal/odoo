"""Only affected job origin/normalization integration on the event image."""
import hashlib,json
from pathlib import Path
import fixture as j
f=j.f;out=Path(__file__).resolve().parent;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='browser-dispatch-enable-01'
source_path=f.ROOT/'docs/evidence/G6/20261029-job-auth-01/native_tests.py';source=source_path.read_text()
cases=['test_normalization_uses_original_native_user_and_safe_status','test_integration_grant_rechecked_before_dispatch','test_technical_identity_needs_live_scoped_credential']
marker=j.LOCAL/'job-origin-regression-01.json';assert not marker.exists();f.write(marker,dict(state='running',cases=cases))
code="import json,sys,unittest\nenv.cr.rollback()\nscope={'ENV':env,'FIXTURE':json.loads("+repr((j.LOCAL/'fixtures.json').read_text())+"),'__name__':'g6_event_job_regression'}\nexec(compile("+repr(source)+",'g6_event_job_regression','exec'),scope)\nsuite=unittest.TestSuite(scope['AuthorizedJobTests'](name) for name in "+repr(cases)+")\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)\nprint('MP_JOB_ORIGIN_REGRESSION='+json.dumps(dict(tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors],successful=result.wasSuccessful())))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,'job-origin-regression-01',[],code)
except AssertionError:raw=(j.LOCAL/'logs/job-origin-regression-01.stdout').read_bytes()
rows=[json.loads(line.split('MP_JOB_ORIGIN_REGRESSION=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_JOB_ORIGIN_REGRESSION=')];assert len(rows)==1
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],cases=cases,image_id=state['image_id'],source_path=source_path.relative_to(f.ROOT).as_posix(),source_sha256=hashlib.sha256(source.encode()).hexdigest(),limits=['Affected shared technical-origin authorization and native producer hooks only; prior actual process-kill/reclaim evidence retained on its original image.','Suite-owned unfinished jobs held, every row retained, dispatch paused.'])
f.write(marker,dict(state='completed',**result));f.write(out/'job-origin-regression.json',result);f.phase(state,'event_jobs_regression_verified' if rows[0]['successful'] else 'event_jobs_regression_failed');f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'])));raise SystemExit(0 if rows[0]['successful'] else 1)
