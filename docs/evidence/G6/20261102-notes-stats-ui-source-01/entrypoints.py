"""Real installed scope, native asset compilation and existing terminal result."""
import hashlib,json,re,sys,urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).parent))
from upgrade import ROOT,OUT,PRIVATE,MARKER,context,base,f,j
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL;f.OUTPUT=OUT
state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified'
before=base.snapshot(state,'notes-ui-entry-03-before');worker=base.worker(native,'notes-ui-entry-03-worker-before')
client=r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),'alice')
slot='/api/v1/ui/slot?slot_id=org.example.notes:slot:detail_actions&major=1'
status,response=client.request(slot,workspace='C');assert status==200
actions=response['data'];assert isinstance(actions,list)
action=next(a for a in actions if a['id']=='org.example.notes_stats:action:analyze')
assert action['handler']=='org.example.notes_stats:action:analyze'
status,response=client.request('/api/v1/context?plugin_id=org.example.notes_stats',workspace='C')
assert status==200 and 'org.example.notes_stats:analysis.run' in response['data']['context']['capabilities']
for workspace in ['A','B']:
    status,response=client.request(slot,workspace=workspace);assert status==200
    assert all(a['id']!='org.example.notes_stats:action:analyze' for a in response['data'])
for workspace in ['A','B','C']:
    views=client.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace)
    assert set(views['views'])=={'list','form'}
saved=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
status,response=client.request('/api/v1/services/org.example.notes_stats.jobs/status',dict(api_version='1.0',request_id='ui-upgrade-status',input=dict(note_id=saved['note_id'])),workspace='C',headers={'X-CSRFToken':client.csrf,'X-MP-Binding':saved['jobs_binding']})
assert status==200
job=response['data']['job']
assert job['id']=='c7115fe8-b465-49a9-bb7a-b9570fa6e306' and job['state']=='completed' and job['attempts']==1
assert job['result']==dict(note_id=saved['note_id'],revision=2,statistics=saved['expected_statistics'])
with client.http.open(client.base+'/app/settings',timeout=60) as response:
    assert response.status==200;html=response.read().decode()
urls=[unescape(u) for u in re.findall(r'<script[^>]+src="([^"]+)"',html) if 'mp_shell.assets_host' in u and '.js' in u]
assert len(urls)==1,urls
parsed=urlsplit(urls[0]);assert not parsed.netloc and parsed.path.startswith('/web/assets/')
with client.http.open(client.base+urls[0],timeout=60) as response:
    assert response.status==200;script=response.read()
assert b'mp_example_notes_stats' in script and b'org.example.notes_stats:action:analyze' in script
assert b'Analysis is on hold.' in script and b'Saved revision ' in script
assert b'Could not get content' not in script and b'Error while parsing' not in script
assert base.snapshot(state,'notes-ui-entry-03-after')==before and base.worker(native,'notes-ui-entry-03-worker-after')==worker
f.save('entrypoints.json',dict(result='passed_installed_slot_native_compiled_asset_and_existing_result_HTTP',native_generation=24,
    action_visible_C_and_absent_A_B=True,capability_scoped=True,native_A_B_C_list_form_definitions_retained=True,
    existing_original_actor_job30_result_current_no_new_enqueue=True,asset_url=urls[0],asset_sha256=hashlib.sha256(script).hexdigest(),
    native_Odoo_bundle_compiled_and_served=True,all17tables_worker_approval_unchanged=True,browser_rendering_verified=False,
    limits=['HTTP/native bundle compilation is not browser execution, rendering, navigation cancellation or degraded UI proof.']))
record['state']='installed_HTTP_verified_browser_pending';f.write(MARKER,record);f.phase(state,'notes_stats_ui_installed_http_verified_browser_pending');f.guard(state)
print('Installed C-only action/native compiled bundle/current completed result pass; native views/data/worker retained; browser pending')
