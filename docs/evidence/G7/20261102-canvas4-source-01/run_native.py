"""Actual installed empty-array persistence; all test writes roll back."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('canvas4_installed',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==27
assert f.load(m.MARKER)['state']=='preservation_verified'
before=m.snapshot(state,'canvas4-native-before');worker=m.worker(native,'canvas4-native-worker-before');assert len(before['mp_example_canvas_board'])==1
path=OUT/'native_empty.py';source=path.read_text()
code="import json,sys,unittest\nscope={'ENV':env,'FIXTURE':"+repr(f.load(m.j.LOCAL/'fixtures.json'))+",'__name__':'canvas4_actual_tests'}\nexec(compile("+repr(source)+",'native_empty.py','exec'),scope)\nsuite=unittest.defaultTestLoader.loadTestsFromTestCase(scope['EmptyBoardTests'])\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)\nprint('MP_CANVAS4_NATIVE='+json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors])))\nenv.cr.rollback();raise SystemExit(not result.wasSuccessful())"
label='g7-canvas4-native-01'
try:raw=f.native(state,label,[],code)
except AssertionError:raw=(m.j.LOCAL/'logs'/label).with_suffix('.stdout').read_bytes()
rows=[json.loads(line.split('MP_CANVAS4_NATIVE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CANVAS4_NATIVE=')];assert len(rows)==1,'Inspect original helper, do not replay'
result=rows[0];assert m.snapshot(state,'canvas4-native-after')==before and m.worker(native,'canvas4-native-worker-after')==worker
f.save('native-results.json',dict(result='passed' if result['successful'] else 'failed',**result,image=state['image_id'],configuration_generation=27,Canvas='0.1.4',actual_installed_source=True,all36jobs_30Notes_oneboard_other_tables_worker_exact=True,all_test_writes_rolled_back=True,no_runtime_source_replacement=True,test_sha256=hashlib.sha256(source.encode()).hexdigest(),scope='Default/explicit empty create, actual native NULL storage/reload, strict bound get/save schemas and nonempty-empty round trip, CAS, viewer/foreign/missing scope, Note references and native Notes views. One explicitly seeded upgrade board retained.'))
print(json.dumps(result));raise SystemExit(not result['successful'])
