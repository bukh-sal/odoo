"""Actual original-user availability and native views after metadata removal."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import context,MARKER,PRIVATE,f,base,j,worker
import r1_probe
from modular_platform.contracts import validate,ERROR_STATUS
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();cycle=f.load(MARKER);assert cycle['install']['state']=='preservation_verified'
before=base.snapshot(state,'manager-reregister02-entrypoints-before');remote=worker(native,'manager-reregister02-entrypoints-worker-before')
fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
status,response=alice.request('/api/v1/context?plugin_id=org.example.document_stats',workspace='C')
assert status==ERROR_STATUS['PLUGIN_SUSPENDED'] and response['error']['code']=='PLUGIN_SUSPENDED'
for name in ['A','B','C']:
    value=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
    assert set(value['views'])=={'list','form'} and '<list' in value['views']['list']['arch'] and '<form' in value['views']['form']['arch']
status,notes=alice.request('/api/v1/context?plugin_id=org.example.notes',workspace='C');assert status==200
operator=r1_probe.Client(state,fixture,'operator');status,response=operator.request('/api/v1/operations/installed');assert status==200;validate('manager-view',response['data'])
row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert row['metadata_state']=='installed' and row['database_state']=='installed' and row['native_version'] is None
assert row['health']['state']=='degraded' and 'separately managed' in row['health']['reason']
assert len(row['features'])==1 and row['features'][0]['availability']=='suspended'
assert base.snapshot(state,'manager-reregister02-entrypoints-after')==before
assert worker(native,'manager-reregister02-entrypoints-worker-after')==remote==f.load(PRIVATE/'register-worker-before.json')
f.save('entrypoints-suspended-stopped.json',dict(result='passed_actual_http_suspended_reregistration_with_stopped_worker',provider_context_409_suspended=True,native_A_B_C_list_form_retained=True,native_notes_C_context200=True,manager_reports_installed_suspended_and_degraded_provider=True,all17tables_and_independent_worker_exact=True,original_actor_uid=fixture['users']['alice']['id'],browser_rendering_tested=False))
f.guard(state);print('Suspended metadata context409; native A/B/C listform and NotesC retained; separately stopped worker still exact')
