"""Current original-user positive gate after independently approved enable."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import context,MARKER,PRIVATE,f,base,j
from modular_platform.contracts import validate
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();cycle=f.load(MARKER);assert cycle['enable']['state']=='preservation_verified'
before=base.snapshot(state,'manager-enable02-http-data-before');remote=base.worker(native,'manager-enable02-http-worker-before')
fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
status,response=alice.request('/api/v1/context?plugin_id=org.example.document_stats',workspace='C')
assert status==200 and response['data']['context']['workspace_id']==cycle['scope']['workspace_id']
preimage=f.load(PRIVATE/'enable-data-before.json')
workspace=next(r for r in preimage['mp_workspace'] if r['public_id']==cycle['scope']['workspace_id'])
assert response['data']['context']['policy_generation']==workspace['policy_generation']+1
for name in ['A','B','C']:
    views=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
    assert set(views['views'])=={'list','form'} and '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
client=r1_probe.Client(state,fixture,'operator');status,response=client.request('/api/v1/operations/installed');assert status==200;validate('manager-view',response['data'])
row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert row['metadata_state']=='installed' and row['database_state']=='installed' and row['native_version'] is None
assert row['health']['state']=='healthy' and len(row['features'])==1 and row['features'][0]['availability']=='enabled'
assert base.snapshot(state,'manager-enable02-http-data-after')==before
assert base.worker(native,'manager-enable02-http-worker-after')==remote==f.load(PRIVATE/'worker-before.json')
f.save('enabled-entrypoints.json',dict(result='passed_actual_current17_enabled_provider_http_native_gates',configuration_generation=17,dispatch_generation=85,
    original_actor_context200_with_fresh_policy=True,native_A_B_C_list_form_retained=True,manager_reports_installed_enabled_healthy_no_native_addon=True,
    all17tables_and_independent_worker_exact=True,browser_rendering_tested=False,
    limits=['Host/native view definitions only; actual Notes connector and remote computation remain required.']))
f.guard(state);print('Current17 provider C context200/fresh policy/native views/healthy manager pass; data/worker exact')
