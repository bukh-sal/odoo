"""Source-bound native prerequisite; not an installed image or metadata lifecycle pass."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
marker=j.LOCAL/'external-authority-source-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
source=ROOT/'platform_addons/mp_core/external_authority.py'
code="import json,sys,types,unittest\nmodule=types.ModuleType('odoo.addons.mp_core.external_authority');module.__package__='odoo.addons.mp_core';sys.modules[module.__name__]=module\n"
code+='exec(compile('+repr(source.read_text())+",'source_external_authority','exec'),module.__dict__)\n"
code+="scope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'PROVIDER':"+repr(f.load(ROOT/'packages/contracts/examples/v1/manifest-external.json'))+",'ENDPOINT':"+repr(f.load(ROOT/'packages/contracts/examples/v1/endpoint.json'))+",'IMAGE':"+repr(f.load(ROOT/'services/document_stats/image.lock.json')['reference'])+",'authorize_analysis':module.authorize_analysis,'__name__':'native_external_authority'}\n"
code+='exec(compile('+repr((OUT/'native_tests.py').read_text())+",'native_external_authority_tests','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['ExternalAuthorityTests']))\nprint('MP_EXTERNAL_AUTH='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
try:raw=f.native(state,'external-authority-source-01',[],code)
except AssertionError:raw=(j.LOCAL/'logs/external-authority-source-01.stdout').read_bytes()
rows=[json.loads(l.split('MP_EXTERNAL_AUTH=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_EXTERNAL_AUTH=')];assert len(rows)==1,'Inspect exact child; no provisioning or runner replay'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],installed_image=state['image_id'],source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,OUT/'native_tests.py']},all_fixture_changes_rolled_back=True,source_injection='New private module compiled into one disposable native process; existing Scope/model/job/dispatch classes unchanged',limits=['Not installed native integration or independent endpoint publisher/key provisioning proof. No external metadata artifact installed; synthetic native metadata fixtures rolled back.','Fresh detached-job/issuer/public authority projection/Notes integration and versioned deployment/revalidation still required; no acceptance credit.'])
f.save('native-source-01.json',result);f.write(marker,dict(state='completed',**result));f.phase(state,'external_authority_source_'+('verified' if result['successful'] else 'failed'));f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'],failures=len(result['failures']),errors=len(result['errors']))));raise SystemExit(0 if result['successful'] else 1)
