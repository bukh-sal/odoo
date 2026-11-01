"""Isolated source prerequisite using real deployed native tables/guards."""
import ast,hashlib,json,sys,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.contracts import normalize_manifest
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
label=sys.argv[1] if len(sys.argv)>1 else 'notes-analysis-source-01'
assert label in {'notes-analysis-source-01','notes-analysis-source-02','notes-analysis-source-03'}
marker=j.LOCAL/(label+'.json');assert not marker.exists();f.write(marker,dict(state='running'))
code='import ast,json,sys,types,unittest\n'
code+="pkg=types.ModuleType('odoo.addons.mp_example_notes_stats');pkg.__path__=[];sys.modules[pkg.__name__]=pkg\n"
sources=[]
for module,path,package in [
    ('modular_platform.worker_dispatch','packages/platform_sdk/modular_platform/worker_dispatch.py','modular_platform'),
    ('modular_platform.worker_authority','packages/platform_sdk/modular_platform/worker_authority.py','modular_platform'),
    ('odoo.addons.mp_core.external_authority','platform_addons/mp_core/external_authority.py','odoo.addons.mp_core'),
    ('odoo.addons.mp_core.external_job','platform_addons/mp_core/external_job.py','odoo.addons.mp_core'),
    ('odoo.addons.mp_example_notes_stats.contracts','platform_addons/mp_example_notes_stats/contracts.py','odoo.addons.mp_example_notes_stats'),
    ('odoo.addons.mp_example_notes_stats.models','platform_addons/mp_example_notes_stats/models.py','odoo.addons.mp_example_notes_stats'),
    ('odoo.addons.mp_example_notes_stats.services','platform_addons/mp_example_notes_stats/services.py','odoo.addons.mp_example_notes_stats'),
    ('odoo.addons.mp_example_notes_stats.jobs','platform_addons/mp_example_notes_stats/jobs.py','odoo.addons.mp_example_notes_stats'),
]:
    sources.append(path)
    code+='m=types.ModuleType('+repr(module)+');m.__package__='+repr(package)+';sys.modules[m.__name__]=m\n'
    code+='exec(compile('+repr((ROOT/path).read_text())+",'source_connector_module','exec'),m.__dict__)\n"
    if module.endswith('notes_stats.models'):
        code+="env.registry.load(types.SimpleNamespace(name='mp_example_notes_stats'));env.registry._setup_models__(env.cr,['mp.example.notes.stats'])\n"
manifest=normalize_manifest(tomllib.loads((ROOT/'plugins/notes_stats/plugin.toml').read_text()))
code+="scope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'MANIFEST':"+repr(manifest)+",'__name__':'native_notes_analysis'}\nexec(compile("+repr((OUT/'native_tests.py').read_text())+",'native_notes_analysis_tests','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['NotesAnalysisTests']))\nprint('MP_NOTES_ANALYSIS='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/(label+'.stdout')).read_bytes()
rows=[json.loads(l.split('MP_NOTES_ANALYSIS=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_NOTES_ANALYSIS=')];assert len(rows)==1,'Inspect exact helper; never replay mutations'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],installed_image=state['image_id'],all_mutations_rolled_back=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},limits=['Connector abstract model loaded/setup from source in one isolated native registry; metadata fixtures rollback. Not installed module or approved native lifecycle proof.','No remote compute, fresh committed bridge, publisher, mount, runner error branch or UI proof; no new acceptance credit.'])
f.save(label+'.json',result);f.write(marker,dict(state='completed',**result));f.phase(state,'notes_analysis_source_'+('verified' if result['successful'] else 'failed'));f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'],errors=len(result['errors']),failures=len(result['failures']))));raise SystemExit(0 if result['successful'] else 1)
