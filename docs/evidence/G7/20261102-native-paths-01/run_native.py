"""Run actual installed ID03 cases plus retained native job/batch regressions."""
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('core18_current',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
base,f,j=m,m.f,m.j;f.OUTPUT=OUT
state,native=m.context();assert native.config['generation']==25 and f.load(m.MARKER)['state']=='preservation_verified'
private=j.LOCAL/'g7-native-paths-01';marker=private/'native-marker.json';assert not marker.exists()
before=m.snapshot(state,'g7-id03-native-before');worker=m.worker(native,'g7-id03-native-worker-before')
adapter=ReferenceDispatchMaintenance(native);observed=adapter.inspect();reference=adapter.policy_for(observed)
assert reference['profile']=='r1-reference-stateless-v1'
paths=[OUT/'native_paths.py',ROOT/'docs/evidence/G6/20261102-current-backend-audit-01/native_guards.py',ROOT/'docs/evidence/G6/20261101-notes7-upgrade-01/native_batch.py']
sources=[p.read_text() for p in paths]
old="LC.LifecycleScope(FIXTURE['site_id'],self.release)";assert sources[2].count(old)==1
sources[2]=sources[2].replace(old,"LC.LifecycleScope(FIXTURE['site_id'],self.release,reference=REFERENCE)")
f.write(marker,dict(state='running',container=state['project']+'-g7-id03-native-01'))
code="import json,sys,unittest\nscope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'REFERENCE':"+repr(reference)+",'__name__':'g7_native_paths'}\n"
for path,source in zip(paths,sources):code+='exec(compile('+repr(source)+','+repr(path.name)+",'exec'),scope)\n"
code+="suite=unittest.TestSuite()\nfor name in ['NativePathTests','CurrentJobGuards','NativeBatchTests']:suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope[name]))\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)\nprint('MP_ID03_NATIVE='+json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,'g7-id03-native-01',[],code)
except AssertionError:raw=(j.LOCAL/'logs/g7-id03-native-01.stdout').read_bytes()
rows=[json.loads(line.split('MP_ID03_NATIVE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_ID03_NATIVE=')];assert len(rows)==1,'Inspect original process/log; no blind replay'
result=rows[0]
assert m.snapshot(state,'g7-id03-native-after')==before and m.worker(native,'g7-id03-native-worker-after')==worker
f.save('native-results.json',dict(result='passed' if result['successful'] else 'failed',**result,
    native_generation=25,image=state['image_id'],native_core='19.0.0.1.18',identity='19.0.0.1.3',
    all36originaljobs_other16tables_worker_authority_exact=True,all_fixture_changes_rolled_back=True,installed_source_not_replaced=True,
    test_sha256={str(p.relative_to(ROOT)):hashlib.sha256(source.encode()).hexdigest() for p,source in zip(paths,sources)},
    fixture_adaptation='Retained batch observer receives exact independently reconstructed reference policy for current external metadata; product handlers/authorization are unchanged. Export permission group granted only within rolled-back native test.'))
f.write(marker,dict(state='terminal',**result));print(json.dumps(result));raise SystemExit(0 if result['successful'] else 1)
