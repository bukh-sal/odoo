"""Run bounded rollback regressions before admission and after real upgrade."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('read_core20',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
f,j=m.f,m.j;f.OUTPUT=OUT
parser=argparse.ArgumentParser();parser.add_argument('--candidate',action='store_true');parser.add_argument('--candidate-readonly',action='store_true');parser.add_argument('--attempt',default='01',choices=['01','02']);args=parser.parse_args()
candidate=args.candidate or args.candidate_readonly
state,native=m.context();phase='window-candidate-readonly' if args.candidate_readonly else ('candidate' if candidate else 'window-installed')
if args.attempt!='01':phase+='-'+args.attempt
assert native.config['generation']==(27 if candidate else 28)
image=f.load(OUT/'candidate-admission.json')['image_id'] if candidate else state['image_id']
before=m.snapshot(state,'g7-read-'+phase+'-before');worker=m.worker(native,'g7-read-'+phase+'-worker-before')
adapter=ReferenceDispatchMaintenance(native);reference=adapter.policy_for(adapter.inspect())
paths=[OUT.parent/'20261102-cached-fields-01/native_cache.py',OUT.parent/'20261102-native-paths-01/native_paths.py',ROOT/'docs/evidence/G6/20261102-current-backend-audit-01/native_guards.py',ROOT/'docs/evidence/G6/20261101-notes7-upgrade-01/native_batch.py']
sources=[p.read_text() for p in paths];old="LC.LifecycleScope(FIXTURE['site_id'],self.release)";assert sources[3].count(old)==1
sources[3]=sources[3].replace(old,"LC.LifecycleScope(FIXTURE['site_id'],self.release,reference=REFERENCE)")
paths.append(OUT/'native_window.py');sources.append(paths[-1].read_text())
code="import json,sys,unittest\nscope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'REFERENCE':"+repr(reference)+",'__name__':'g7_cache_tests'}\n"
for path,source in zip(paths,sources):code+='exec(compile('+repr(source)+','+repr(path.name)+",'exec'),scope)\n"
classes=['ReadWindowTests','NativeCacheTests'] if args.candidate_readonly else ['ReadWindowTests','NativeCacheTests','NativePathTests','CurrentJobGuards','NativeBatchTests']
code+="suite=unittest.TestSuite()\nfor name in "+repr(classes)+":suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope[name]))\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)\nprint('MP_CACHE_NATIVE='+json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
label='g7-read-'+phase+'-native-01'
argv=['docker','run','-i','--name',state['project']+'-'+label,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','1536m','--pids-limit','128',
 '--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--mount','type=volume,source='+state['project']+'_bootstrap,target=/run/mp-bootstrap,readonly','--entrypoint','/venv/bin/python',image,'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0']
try:raw=f.command(label,argv,input=code.encode(),timeout=300)
except AssertionError:raw=(j.LOCAL/'logs'/label).with_suffix('.stdout').read_bytes()
rows=[json.loads(line.split('MP_CACHE_NATIVE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CACHE_NATIVE=')];assert len(rows)==1,'Inspect original helper; no replay'
result=rows[0]
assert m.snapshot(state,'g7-read-'+phase+'-after')==before and m.worker(native,'g7-read-'+phase+'-worker-after')==worker
f.save(phase+'-native-results.json',dict(result='passed' if result['successful'] else 'failed',**result,image=image,native_configuration_generation=native.config['generation'],installed_correction=not candidate,all36jobs_other16tables_worker_exact=True,all_fixtures_rolled_back=True,actual_classes_not_monkeypatched=True,test_sha256={str(p.relative_to(ROOT)):hashlib.sha256(s.encode()).hexdigest() for p,s in zip(paths,sources)},fixture_adaptation='Only retained lifecycle observer receives exact current reference policy. Candidate-only shell uses same unchanged schema, no HTTP/cron, read-only filestore, rollback-only fixtures; no admission/installed claim. Candidate-readonly uses existing Notes to avoid event creation correctly fenced by the mismatched installed release inventory.'))
print(json.dumps(result));raise SystemExit(0 if result['successful'] else 1)
