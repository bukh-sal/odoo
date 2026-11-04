"""Actual resumed native/API/session/plan fences and required-provider preview."""
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0,str(Path(__file__).parent));import probe as p
from modular_platform.catalog import Catalog
from modular_platform.plans import data_digest

state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='restored_resumed_needs_verification'
operation=record['operation_id'];before=p.load(p.PRIVATE/'data-closed.json')
assert p.snapshot(state,'native-uninstall-current-resumed02-before')==before
assert native._inspect(state['project']+'-edge-1')['State']['Running']
status=native.store.status(operation);assert status['state']=='revoked' and status['traffic_resumed']
ready=p.load(native.store.root/'recoveries'/operation/'result.json')['dispatch']
dispatch=p.ReferenceDispatchMaintenance(native).inspect()
assert dispatch['control']['state']=='enabled' and dispatch['control']['generation']==ready['control']['generation']+1
fixture=p.load(p.LOCAL/'fixtures.json');p.r1_probe.r1.r0.LOCAL=p.LOCAL
alice=p.r1_probe.Client(state,fixture,'alice');bob=p.r1_probe.Client(state,fixture,'bob')
for client,scope in [(alice,'A'),(bob,'B')]:
    assert len(client.call('list',dict(limit=25),scope)['items'])==1
    views=client.native('get_views',workspace=scope,kwargs=dict(views=[[False,'list'],[False,'form']],options={}))
    assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
release=alice.request('/api/v1/client-release')[1]['data']
assert release['generation']==native.config['generation'] and release['inventory_digest']==state['inventory_digest']
old=p.load(p.PRIVATE/'old-session.json')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
request=urllib.request.Request(alice.base+'/api/v1/session',headers={'Cookie':'session_id='+old['session_id']})
try:response=opener.open(request,timeout=30)
except urllib.error.HTTPError as error:response=error
with response:
    value=json.loads(response.read());assert response.code==401 and value['error']['code']=='UNAUTHENTICATED'
body=dict(api_version='1.0',request_id='old-release-recovery-probe',input=dict(limit=25))
code,value=alice.request('/api/v1/services/org.example.notes.documents/list',body,workspace='A',headers={
    'X-CSRFToken':alice.csrf,'X-MP-Binding':fixture['bindings']['A']['binding_id'],'X-MP-Client-Release':old['release_token']})
assert code==409 and value['error']['code']=='CONFLICT' and value['error']['details']['field']=='client_release'
old_native=alice.request('/web/dataset/call_kw/mp.example.note.get_views',dict(jsonrpc='2.0',method='call',id=1,
    params=dict(model='mp.example.note',method='get_views',args=[],kwargs=dict(views=[[False,'list'],[False,'form']],options={}))),
    workspace='A',headers={'X-MP-Client-Release':old['release_token']})
assert old_native[0]==200 and old_native[1]['error']['data']['name'].endswith('ClientReleaseMismatch')
retired=subprocess.run(p.prefix()+['plugin','apply',operation]+p.options(native),capture_output=True,timeout=180)
(p.PRIVATE/'retired-plan02.stdout').write_bytes(retired.stdout);(p.PRIVATE/'retired-plan02.stderr').write_bytes(retired.stderr)
assert retired.returncode and native.store.status(operation)==status
catalog=Catalog(native.catalog_root,native.validator,readonly=True);obs=native.observer.read()
impact=native.observer.native_impact(obs,catalog,site_id=state['site_id'],requested=['mp_example_notes'])
assert {row['plugin_id'] for row in impact['plugins']}=={'org.example.notes','org.example.notes_labels','org.example.notes_stats','org.example.canvas'}
assert sum(len(row['workspace_ids']) for row in impact['plugins'])==8
operator=p.r1_probe.Client(state,fixture,'operator')
nomination=dict(schema_version=1,operation='prepare',operation_type='uninstall',plugin_id='org.example.notes',
    site_id=state['site_id'],workspace_ids=[],cascade=False)
code,value=operator.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':operator.csrf})
assert code==400
code,value=operator.request('/api/v1/operations/prepare',nomination|dict(cascade=True),headers={'X-CSRFToken':operator.csrf})
assert code==200;draft=value['data']
code,value=operator.request('/api/v1/operations/bundle/'+draft['operation_id']);assert code==200
draft_bundle=value['data'];assert len(draft_bundle['operation_lock']['targets'])==8
assert draft_bundle['operation_lock']['native_uninstall_impact']==impact
p.save('required-provider-preview.json',dict(result='passed_installed_required_native_provider_closure',
    independent_impact=impact,manager_preview=draft,manager_bundle=draft_bundle,
    cascade_false_refused=True,scopes=8,independent_operation_registered=False,
    limits=['One unrequested application draft demonstrates the closure. No request/import/approval or native operation for Notes.']))
assert p.snapshot(state,'native-uninstall-current-resumed02-after')==before
assert p.worker(native,'native-uninstall-current-resumed02-worker')==p.load(p.PRIVATE/'worker-before.json')
p.f.guard(state)
p.save('resumed-http.json',dict(result='passed_current_restored_native_HTTP_and_security_fences',operation_id=operation,
    configuration_generation=native.config['generation'],dispatch_generation=dispatch['control']['generation'],
    native_list_form_A_B=True,old_session_401=True,old_gateway_client_release_409=True,
    old_native_client_release_mismatch=True,retired_plan_refused_journal_exact=True,
    all17tables_worker_exact=True,required_provider_closure_plugins=4,required_provider_closure_scopes=8,
    one_unrequested_application_preview=draft['operation_id'],browser_rendering=False))
record['state']='resumed_http_verified';p.write(p.PRIVATE/'state.json',record)
print(json.dumps(dict(result='restored_native_HTTP_session_plan_and_required_closure_passed',generation=native.config['generation'])),flush=True)
