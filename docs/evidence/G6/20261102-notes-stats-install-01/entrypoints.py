"""Real installed service status/native view/scope proof without enqueuing jobs."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from install import context,MARKER,PRIVATE,base,f,j
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified'
before=base.snapshot(state,'notes-stats-http-before');remote=base.worker(native,'notes-stats-http-worker-before')
bundle=f.load(Path(__file__).parent/'manager-bundle.json');target=bundle['operation_lock']['targets'][0]
jobs=next(r for r in bundle['operation_lock']['bindings'] if r['consumer_installation_id']==target['installation_id'] and r['alias']=='jobs')
workspace=next(r for r in before['mp_workspace'] if r['public_id']==target['workspace_id'])
note=next(r for r in before['mp_example_note'] if r['workspace_id']==workspace['id'])
fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
status,response=alice.request('/api/v1/context?plugin_id=org.example.notes_stats',workspace='C')
assert status==200 and response['data']['context']['installation_id']==target['installation_id']
body=dict(api_version='1.0',request_id='stats-status-'+uuid4().hex,input=dict(note_id=note['public_id']))
headers={'X-CSRFToken':alice.csrf,'X-MP-Binding':jobs['binding_id']}
status,response=alice.request('/api/v1/services/org.example.notes_stats.jobs/status',body,workspace='C',headers=headers)
assert status==200 and response['data']==dict(job=None),(status,response.get('error',{}).get('code'))
for name in ['A','B']:
    status,response=alice.request('/api/v1/context?plugin_id=org.example.notes_stats',workspace=name)
    assert status==409 and response['error']['code']=='PLUGIN_SUSPENDED'
    status,response=alice.request('/api/v1/services/org.example.notes_stats.jobs/status',body,workspace=name,headers=headers)
    assert status==404 and response['error']['code']=='NOT_FOUND',(name,status,response.get('error',{}).get('code'))
for name in ['A','B','C']:
    views=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
    assert set(views['views'])=={'list','form'}
assert base.snapshot(state,'notes-stats-http-after')==before and base.worker(native,'notes-stats-http-worker-after')==remote
f.save('entrypoints.json',dict(result='passed_actual_installed_connector_status_scope_and_native_views',configuration_generation=18,dispatch_generation=88,
    original_actor_C_context200_status200_no_job=True,not_installed_A_B_context409_and_foreign_binding404=True,
    native_notes_A_B_C_list_form_retained=True,all17tables_and_running_worker_exact=True,browser_rendering_tested=False,
    limits=['Read-only status path; durable enqueue/real remote computation follows separately.']))
f.guard(state);print('Actual installed connector C context/status pass; A/B unavailable/foreign binding404; native Notes views/data/worker retained')
