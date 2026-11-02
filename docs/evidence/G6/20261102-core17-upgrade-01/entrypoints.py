"""Actual current native views and prior-release refusals; no browser claim."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
import activate as base
from activate import context,MARKER,PRIVATE,f,j,worker
import r1_probe
from modular_platform.contracts import validate
from modular_platform.plans import data_digest
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified'
before=base.snapshot(state,'core17-http-before');remote=worker(native,'core17-http-worker-before')
fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
code,response=alice.request('/api/v1/client-release');assert code==200
assert response['data']['generation']==20 and response['data']['inventory_digest']==state['inventory_digest']
for name in ['A','B','C']:
    value=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
    assert set(value['views'])=={'list','form'} and '<list' in value['views']['list']['arch'] and '<form' in value['views']['form']['arch']
old=f.load(base.OUT/'state-before.json')['release_lock']
oldtoken=data_digest(dict(protocol=1,site_id=state['site_id'],generation=19,release_digest=data_digest(old),inventory_digest=old['core_inventory_digest']))
saved=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
assert alice.call('get',dict(note_id=saved['note_id']),workspace='C')['revision']==saved['revision']
body=dict(api_version='1.0',request_id=str(uuid4()),input=dict(note_id=saved['note_id']))
code,response=alice.request('/api/v1/services/org.example.notes.documents/get',body,workspace='C',headers={
    'X-CSRFToken':alice.csrf,'X-MP-Binding':fixture['bindings']['C']['binding_id'],'X-MP-Client-Release':oldtoken})
assert code==409 and response['error']['code']=='CONFLICT' and response['error']['details']['field']=='client_release'
body=dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method='get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}}))
code,response=alice.request('/web/dataset/call_kw/mp.example.note.get_views',body,workspace='C',headers={'X-MP-Client-Release':oldtoken})
assert code==200 and response.get('error',{}).get('data',{}).get('name','').endswith('ClientReleaseMismatch')
operator=r1_probe.Client(state,fixture,'operator');code,response=operator.request('/api/v1/operations/installed')
assert code==200;validate('manager-view',response['data'])
row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert row['health']['state']=='healthy' and row['features'][0]['availability']=='enabled'
assert base.snapshot(state,'core17-http-after')==before
assert worker(native,'core17-http-worker-after')==remote==f.load(PRIVATE/'worker-before.json')
f.save('entrypoints.json',dict(result='passed_actual_core17_native_HTTP_and_prior_epoch_fences',generation=20,
    native_A_B_C_list_form=True,saved_note_readable=True,old_epoch19_gateway409=True,old_native_RPC_ClientReleaseMismatch=True,
    manager_provider_healthy_enabled=True,all17tables_29jobs_exact=True,independent_worker_unchanged=True,browser_rendering_tested=False))
f.guard(state);print('Current20 native A/B/C views/Note read and manager healthy; old19 gateway/nativeRPC refused; all data/worker exact')
