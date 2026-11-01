"""Source-bound carry-forward tests on the existing populated native fixture."""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
parser=argparse.ArgumentParser();parser.add_argument('--label',default='native-01');parser.add_argument('--case');args=parser.parse_args();assert re.fullmatch('[a-z0-9-]{1,35}',args.label)
assert state['phase'] in ({'dispatch_job_repeat_source_verified','carryforward_tests_failed','carryforward_tests_verified','carryforward_host_preview_verified'} if args.case else {'dispatch_job_repeat_source_verified','carryforward_tests_failed'})
sources={name:ROOT/path for name,path in [('store','packages/platform_sdk/modular_platform/durable.py'),('LC','packages/platform_sdk/modular_platform/dispatch_lifecycle.py'),('jobs','platform_addons/mp_core/job_dispatch.py')]}
code="import json,sys,types,unittest\nfrom odoo.addons.mp_core import job_dispatch as original\nenv.cr.rollback()\n"
for name,path in sources.items():
    module='modular_platform.'+name+'_carryforward_probe' if name!='jobs' else 'odoo.addons.mp_core.jobs_carryforward_probe'
    package=module.rsplit('.',1)[0]
    code+=name+"=types.ModuleType("+repr(module)+");"+name+".__package__="+repr(package)+";sys.modules["+name+".__name__]="+name+"\nexec(compile("+repr(path.read_text())+","+repr(module)+",'exec'),"+name+".__dict__)\n"
code+="jobs.durable=store\nscope={'ENV':env,'FIXTURE':json.loads("+repr((j.LOCAL/'fixtures.json').read_text())+"),'LC':LC,'jobs':jobs,'store':store,'DEFINITIONS':original.DEFINITIONS.copy(),'__name__':'g6_carryforward_native'}\nexec(compile("+repr((OUT/'native_tests.py').read_text())+",'carryforward_native_tests','exec'),scope)\nsuite=unittest.TestSuite()\n"
code+=("suite.addTest(scope['CarryForwardTests']("+repr(args.case)+"))" if args.case else "suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope['CarryForwardTests']))")
code+="\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)\nprint('MP_CARRYFORWARD='+json.dumps(dict(tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors],successful=result.wasSuccessful())))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
marker=j.LOCAL/('carryforward-'+args.label+'.json');assert not marker.exists();f.write(marker,dict(state='running'))
try:raw=f.native(state,'carryforward-'+args.label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/('carryforward-'+args.label+'.stdout')).read_bytes()
rows=[json.loads(line.split('MP_CARRYFORWARD=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CARRYFORWARD=')];assert len(rows)==1,'Inspect exact retained process before continuing'
record=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],image_id=state['image_id'],source_sha256={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sources.values()},test_sha256=hashlib.sha256((OUT/'native_tests.py').read_bytes()).hexdigest(),limits=['Corrected source in short-lived native process against real PG; no actual immutable upgrade or independently reviewed executor recovery exercised.','All fixture writes roll back; full scheduler/receipt/control snapshot and Note count restored after every case.'])
f.write(marker,dict(state='completed',**record));f.save(args.label+'.json',record);f.phase(state,'carryforward_tests_verified' if rows[0]['successful'] else 'carryforward_tests_failed');f.guard(state)
print(json.dumps(dict(result=record['result'],tests=record['tests'],errors=len(record['errors']),failures=len(record['failures']))));raise SystemExit(0 if record['successful'] else 1)
