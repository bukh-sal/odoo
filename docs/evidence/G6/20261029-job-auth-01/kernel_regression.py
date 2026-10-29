"""Recheck default enqueue semantics after adding explicit semantic dedup."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_job_fixture as j
j.select_profile('runner');f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='job_processes_verified'
source=(ROOT/'docs/evidence/G6/20261029-durable-01/native_tests.py').read_text()
validation=(ROOT/'tests/test_durable_validation.py').read_text()
code=f"""import json,sys,types,unittest
env.cr.rollback()
scope={{'ENV':env,'FIXTURE':json.loads({(j.LOCAL/'fixtures.json').read_text()!r}),'__name__':'g6_kernel_regression','__file__':'/opt/modular/g6_kernel_regression.py'}}
exec(compile({source!r},scope['__file__'],'exec'),scope)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(scope['DurablePostgresTests'])
unit=types.ModuleType('g6_validation');unit.__file__='/opt/modular/tests/test_durable_validation.py'
exec(compile({validation!r},unit.__file__,'exec'),unit.__dict__)
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(unit.DurableValidationTests))
result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
print('MP_REGRESSION='+json.dumps(dict(tests=result.testsRun,failures=[test.id() for test,_ in result.failures],errors=[test.id() for test,_ in result.errors],successful=result.wasSuccessful())))
env.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)
"""
try:raw=f.native(state,'kernel-regression-01',[],code)
except AssertionError:raw=(j.LOCAL/'logs/kernel-regression-01.stdout').read_bytes()
rows=[json.loads(line.split('MP_REGRESSION=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_REGRESSION=')];assert len(rows)==1
result=rows[0];f.write(OUTPUT/'kernel-regression.json',dict(result='passed' if result['successful'] else 'failed',**result,image_id=state['image_id'],inventory_digest=state['inventory_digest'],source_sha256=hashlib.sha256(source.encode()).hexdigest(),reason='Explicit semantic dedup must preserve qualified default enqueue/claims/fences/outbox behavior.',native_PostgreSQL_tests=11,Linux_input_validation_tests=4))
f.phase(state,'job_processes_and_kernel_verified' if result['successful'] else 'kernel_regression_failed');f.guard(state)
print(json.dumps(result));raise SystemExit(0 if result['successful'] else 1)
