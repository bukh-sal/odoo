"""Actual recovered native HTTP and retired-plan refusal; provider stays suspended."""
import json,subprocess,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from recover import ROOT,context,base,f,j,OUT,PRIVATE,MARKER
from authority import AUTH,physical,op
from modular_platform.plans import data_digest
from modular_platform.contracts import validate
import suspend as s
state,native=context();record=f.load(MARKER);assert record['state']=='resumed' and native.config['generation']==22
status=native.store.status(record['operation_id']);assert status['state']=='revoked' and status['traffic_resumed']
assert native._inspect(native.observer._container('edge'))['State']['Running']
assert base.snapshot(state,'image-resumed-before')==f.load(PRIVATE/'data-closed.json')
authority=f.load(AUTH);assert authority['state']=='old_resume_refused' and op(native).publisher._document()['generation']==10
assert physical(native,authority,'image-resumed-worker-before')==f.load(PRIVATE/'image-authority-worker-before.json')
client=s.client(state,'alice');code,response=client.request('/api/v1/client-release');assert code==200 and response['data']['generation']==22
for workspace in ['A','B','C']:
    views=client.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace)
    assert set(views['views'])=={'list','form'} and '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
saved=f.load(j.LOCAL/'notes-stats-remote-01/positive.json');assert client.call('get',dict(note_id=saved['note_id']),workspace='C')['revision']==saved['revision']
manifest=f.load(native.store.root/'checkpoints'/record['operation_id']/'manifest.json');old=manifest['previous_release']['release_lock']
token=data_digest(dict(protocol=1,site_id=state['site_id'],generation=20,release_digest=data_digest(old),inventory_digest=old['core_inventory_digest']))
fixture=f.load(j.LOCAL/'fixtures.json');body=dict(api_version='1.0',request_id=str(uuid4()),input=dict(note_id=saved['note_id']))
code,response=client.request('/api/v1/services/org.example.notes.documents/get',body,workspace='C',headers={
    'X-CSRFToken':client.csrf,'X-MP-Binding':fixture['bindings']['C']['binding_id'],'X-MP-Client-Release':token})
assert code==409 and response['error']['code']=='CONFLICT' and response['error']['details']['field']=='client_release'
operator=s.client(state);code,response=operator.request('/api/v1/operations/installed');assert code==200;validate('manager-view',response['data'])
row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert row['features'][0]['availability']=='suspended' and row['health']['state']!='healthy'
result=subprocess.run(base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),capture_output=True,cwd=ROOT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(PRIVATE/'retired-upgrade.stdout').write_bytes(result.stdout);(PRIVATE/'retired-upgrade.stderr').write_bytes(result.stderr);assert result.returncode==2
assert base.snapshot(state,'image-resumed-after')==f.load(PRIVATE/'data-closed.json')
assert physical(native,authority,'image-resumed-worker-after')==f.load(PRIVATE/'image-authority-worker-before.json')
f.save('resumed-http.json',dict(result='passed_actual_changed_image_recovery_resume_with_current_revocation',generation=22,
    native_A_B_C_list_form=True,saved_note_revision_preserved=True,old_epoch20_gateway409=True,retired_original_upgrade_exit2=True,
    original_failed_plan_remains_revoked=True,all29job_outcomes_and_other17tables_exact=True,current_OS_publication10_revocation_preserved=True,
    worker06_image548202_config7_not_rolled_back=True,provider_feature_suspended=True,manager_health=row['health'],browser_rendering_tested=False,
    limits='Host records resumed; provider remains unavailable until separate runtime approval and NEW metadata upgrade/enable. No remote success claim yet.'))
f.write(PRIVATE/'recovery-finish.json',dict(state='verified',generation=22,publication=10));f.phase(state,'image_recovery_resumed_HTTP_verified')
print('Recovered22 native views/Note/manager and old20/retired-plan fences pass;29jobs/data exact, independent revocation10 preserved',flush=True)
