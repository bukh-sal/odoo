"""Installed real HTTP manager observations and native views; no mutation plans."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from activate import ROOT,OUT,j,f,MARKER,context,worker,PRIVATE,snapshot
import r1_probe
from modular_platform.contracts import validate
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified' and native.config['generation']==14
assert not (OUT/'http-readonly.json').exists()
fixture=f.load(j.LOCAL/'fixtures.json');before=snapshot(state,'core14-http-data-before');physical=worker(native,'core14-http-worker-before')
operator=r1_probe.Client(state,fixture,'operator');checks=[]
status,response=operator.request('/api/v1/operations/context');assert status==200 and response['data']['can_request']
checks.append('Actual operator authority and client-release discovery succeed on installed core14')
status,response=operator.request('/api/v1/operations/installed');assert status==200
view=response['data'];validate('manager-view',view)
provider=next(r for r in view['items'] if r['runtime']=='external_service')
assert provider['plugin_id']=='org.example.document_stats' and provider['version']=='0.1.1' and provider['health']['state']=='healthy'
assert provider['database_state']=='installed' and provider['native_version'] is None and len(provider['features'])==1 and provider['features'][0]['availability']=='enabled'
assert all(r['health']['state']!='healthy' for r in view['items'] if r['runtime']=='native')
f.save('installed-http.json',view);checks.append('External health independently observed; native registry does not invent liveness or fake addon')
status,response=operator.request('/api/v1/operations/details?digest='+provider['artifact_digest']);assert status==200
validate('manager-view',response['data']);assert response['data']['manifest']['runtime']==dict(kind='external_service')
assert not response['data']['native_trusted_code'];checks.append('Actual exact external details use metadata-only runtime with separate trust display')
status,response=operator.request('/api/v1/operations/prepare',dict(schema_version=1,operation='prepare',operation_type='suspend',
    plugin_id=provider['plugin_id'],site_id=native.config['sites'][0]['site_id'],workspace_ids=[provider['features'][0]['workspace_id']],cascade=False,runtime='native'),
    headers={'X-CSRFToken':operator.csrf})
assert status==400 and 'error' in response;checks.append('Actual manager rejects forged browser runtime before any plan record')
alice=r1_probe.Client(state,fixture,'alice')
status,response=alice.request('/api/v1/operations/installed');assert status==403
checks.append('Workspace administrator cannot read independent operation manager without application-operator role')
for name in ['A','B','C']:
    views=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
    assert set(views['views'])=={'list','form'} and '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
checks.append('Actual original-user native Odoo list/form views remain available in A/B/C, including viewer B')
after=snapshot(state,'core14-http-data-after');assert after==before
assert worker(native,'core14-http-worker-after')==physical==f.load(PRIVATE/'worker-before.json')
f.save('http-readonly.json',dict(result='passed_installed_core14_readonly_http',checks=checks,actual_http=True,source_substitution=False,
    native_Odoo_standard_views=True,all17tables_exact=True,external_worker_and_publication_exact=True,created_mutation_plans=0,
    limits=['HTTP native view definitions, not browser rendering.','No actual manager-created metadata lifecycle operation, outage or external recovery tested yet.']))
f.guard(state);print('Installed core14 HTTP health/details/role/forged-runtime checks and native A/B/C list/form pass; original data/worker exact')
