"""Compile targeted changed functions into real native job classes/registrations."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
marker=j.LOCAL/'detached-job-provenance-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
code='import ast,json,sys,types,unittest\n'
for module,path,package in [
    ('modular_platform.worker_dispatch','packages/platform_sdk/modular_platform/worker_dispatch.py','modular_platform'),
    ('modular_platform.worker_authority','packages/platform_sdk/modular_platform/worker_authority.py','modular_platform'),
    ('odoo.addons.mp_core.external_authority','platform_addons/mp_core/external_authority.py','odoo.addons.mp_core'),
    ('odoo.addons.mp_core.external_job','platform_addons/mp_core/external_job.py','odoo.addons.mp_core'),
]:
    code+='m=types.ModuleType('+repr(module)+');m.__package__='+repr(package)+';sys.modules[m.__name__]=m\nexec(compile('+repr((ROOT/path).read_text())+",'host_new_module','exec'),m.__dict__)\n"
code+="from odoo.addons.mp_core import job_dispatch as jobs\ntree=ast.parse("+repr((ROOT/'platform_addons/mp_core/job_dispatch.py').read_text())+");tree.body=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in {'Invocation','prepare_one','compute','_safe_code'}]\nexec(compile(tree,'host_targeted_job_context','exec'),jobs.__dict__)\n"
code+="scope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'__name__':'native_job_provenance'}\nexec(compile("+repr((OUT/'native_tests.py').read_text())+",'native_job_provenance_tests','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['JobProvenanceTests']))\nprint('MP_JOB_PROVENANCE='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,'detached-job-provenance-01',[],code)
except AssertionError:raw=(j.LOCAL/'logs/detached-job-provenance-01.stdout').read_bytes()
rows=[json.loads(l.split('MP_JOB_PROVENANCE=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_JOB_PROVENANCE=')];assert len(rows)==1,'Inspect exact helper; never replay runner or provisioning'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],installed_image=state['image_id'],all_mutations_rolled_back=True,source_mode='Targeted changed Invocation/prepare/compute/error mapper in real native registry; existing job definitions, metadata and business guards unchanged; new bridge modules import successfully',limits=['Does not exercise real fresh-cursor/OS authority/remote compute bridge or guarded runner error branch yet; committed fixture, installed image and Notes integration remain required.'])
f.save('native-source-01.json',result);f.write(marker,dict(state='completed',**result));f.phase(state,'detached_job_source_'+('verified' if result['successful'] else 'failed'));f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'],errors=len(result['errors']),failures=len(result['failures']))));raise SystemExit(0 if result['successful'] else 1)
