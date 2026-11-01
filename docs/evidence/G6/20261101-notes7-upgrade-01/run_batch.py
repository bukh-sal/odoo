"""Run the bounded rollback matrix on the actual immutable installed image."""
import hashlib,json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
from activate import context,j,f,MARKER,ROOT
state,record,native=context();assert state['phase']=='notes7_completed_needs_verification' and native.config['generation']==8
marker=j.LOCAL/'notes7-native-batch-01.json';assert not marker.exists();f.write(marker,dict(state='running',image_id=state['image_id']))
code='import json,sys,unittest\nFIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\n'
code+="from odoo.modules import module\nassert module.get_manifest('mp_example_notes')['version']=='19.0.0.2.7'\n"
code+="scope={'ENV':env,'FIXTURE':FIXTURE,'__name__':'native_batch'}\nexec(compile("+repr((OUT/'native_batch.py').read_text())+",'native_batch_tests','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['NativeBatchTests']))\nprint('MP_NATIVE_BATCH='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,'notes7-native-batch-01',[],code)
except AssertionError:raw=(j.LOCAL/'logs/notes7-native-batch-01.stdout').read_bytes()
rows=[json.loads(l.split('MP_NATIVE_BATCH=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_NATIVE_BATCH=')];assert len(rows)==1,'Inspect exact child; do not rerun upgrade'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=8,installed_source=True,source_substitution=False,all_test_writes_rolled_back=True,test_sha256=hashlib.sha256((OUT/'native_batch.py').read_bytes()).hexdigest(),limits=['Bounded native batch/CAS regression; other ID-03 final source/native-path audits, event host/browser and external/G7 remain.'])
f.save('native-batch-01.json',result);f.write(marker,dict(state='completed',**result));f.phase(state,'notes7_native_batch_'+('verified' if result['successful'] else 'failed'));f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'],failures=len(result['failures']),errors=len(result['errors']))));raise SystemExit(0 if result['successful'] else 1)
