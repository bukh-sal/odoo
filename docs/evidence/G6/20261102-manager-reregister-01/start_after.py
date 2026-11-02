"""Separate operator start after proving the installer left the worker stopped."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import context,MARKER,PRIVATE,base,f,j
from runtime import inspect,physical,operator,command,MARKER as RUNTIME_MARKER
from modular_platform.profile_channel import publish_profile
from modular_platform.catalog import Catalog
from modular_platform.contracts import ERROR_STATUS,validate
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();cycle=f.load(MARKER);m=f.load(RUNTIME_MARKER)
assert cycle['install']['state']=='preservation_verified' and m['state']=='stopped_registration_ready'
assert all((Path(__file__).parent/n).exists() for n in ['register-handoff-qualification.json','register-retirement.json','observation-retirement.json','entrypoints-suspended-stopped.json'])
row=inspect(m['container_id']);assert not row['State']['Running'] and row['State']['ExitCode']==0
assert physical(row)==physical(f.load(PRIVATE/'worker-stopped.json'))
before=base.snapshot(state,'manager-reregister01-before-separate-start');publication=operator(native).publisher._document()
m['state']='operator_starting_after_verified_registration';f.write(RUNTIME_MARKER,m)
command('operator-start-after-registration',['docker','start',m['container_id']])
deadline=time.monotonic()+45
while time.monotonic()<deadline:
    if inspect(m['container_id'])['State'].get('Health',{}).get('Status')=='healthy':break
    time.sleep(1)
op=operator(native);attested=op.observer(f.load(PRIVATE/'enabled-endpoint.json'),m['public_digest'],m['key_id'])
assert attested['container_id']==m['container_id'] and physical(inspect(m['container_id']))==physical(row)
assert op.publisher._document()==publication==f.load(PRIVATE/'publication5.json')
f.save('running-profile-publication.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
status,response=alice.request('/api/v1/context?plugin_id=org.example.document_stats',workspace='C')
assert status==ERROR_STATUS['PLUGIN_SUSPENDED'] and response['error']['code']=='PLUGIN_SUSPENDED'
client=r1_probe.Client(state,fixture,'operator');status,response=client.request('/api/v1/operations/installed');assert status==200;validate('manager-view',response['data'])
provider=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert provider['database_state']=='installed' and provider['health']['state']=='healthy' and provider['native_version'] is None
assert len(provider['features'])==1 and provider['features'][0]['availability']=='suspended'
assert base.snapshot(state,'manager-reregister01-after-separate-start')==before
f.save('separate-start-qualification.json',dict(result='passed_separate_operator_start_does_not_enable_metadata',same_worker_image_container_key_scope_retained=True,
    configuration_generation=16,dispatch_generation=79,publication_generation=5,endpoint_generation=3,
    metadata_feature_still_suspended=True,original_actor_context409=True,manager_reports_installed_suspended_healthy_without_native_addon=True,
    all17tables_exact_including_revoked_grants=True,no_automatic_feature_activation=True,browser_rendering_tested=False))
m['state']='operator_started_registration_verified';f.write(RUNTIME_MARKER,m);f.phase(state,'manager_reregister01_separate_start_verified');f.guard(state)
print('Separate operator start restored healthy process; metadata remains suspended/context409/grants revoked/data exact')
