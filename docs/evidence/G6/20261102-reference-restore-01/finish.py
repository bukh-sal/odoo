"""Recovered native/HTTP compatibility, revoked-plan fence and ordinary remote job."""
import json,subprocess,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from recovery import ROOT,context,base,f,j,OUT,PRIVATE,MARKER,positive
from modular_platform.plans import data_digest
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
FINISH=PRIVATE/'finish.json'

state,native=context();recovery=f.load(MARKER);assert recovery['state']=='resumed' and not FINISH.exists() and native.config['generation']==19
assert native.store.status(recovery['operation_id'])['traffic_resumed']
assert native._inspect(native.observer._container('edge'))['State']['Running']
before=f.load(PRIVATE/'data-closed.json');assert base.snapshot(state,'reference-finish-before')==before
assert base.worker(native,'reference-finish-worker-before')==f.load(PRIVATE/'worker-current.json')
f.save('current-planning-publication.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
client=positive.client(state)
release=client.request('/api/v1/client-release')[1]['data'];assert release['generation']==19 and release['inventory_digest']==state['inventory_digest']
for workspace in ('A','B','C'):
    views=client.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace)
    assert set(views['views'])=={'list','form'} and '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
original=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
assert client.call('get',dict(note_id=original['note_id']),workspace='C')['revision']==original['revision']
old=f.load(OUT/'bundle.json')['operation_lock']['release'];doc=dict(protocol=1,site_id=state['site_id'],generation=18,release_digest=data_digest(old),inventory_digest=old['core_inventory_digest']);old_token=data_digest(doc)
payload=dict(api_version='1.0',request_id=str(uuid4()),input=dict(note_id=original['note_id']))
fixture=f.load(j.LOCAL/'fixtures.json')
code,response=client.request('/api/v1/services/org.example.notes.documents/get',payload,workspace='C',headers={'X-CSRFToken':client.csrf,'X-MP-Binding':fixture['bindings']['C']['binding_id'],'X-MP-Client-Release':old_token})
assert code==409 and response['error']['code']=='CONFLICT' and response['error']['details']['field']=='client_release'
native_body=dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method='get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}}))
code,response=client.request('/web/dataset/call_kw/mp.example.note.get_views',native_body,workspace='C',headers={'X-MP-Client-Release':old_token})
assert code==200 and response.get('error',{}).get('data',{}).get('name','').endswith('ClientReleaseMismatch')
# The retired original plan cannot mutate the restored epoch.
args=base.prefix()+['plugin','apply',recovery['operation_id']]+base.options(native)
retired=subprocess.run(args,capture_output=True,cwd=ROOT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(PRIVATE/'retired-plan.stdout').write_bytes(retired.stdout);(PRIVATE/'retired-plan.stderr').write_bytes(retired.stderr);assert retired.returncode==2
assert base.snapshot(state,'reference-finish-after-compatibility-fences')==before
f.save('resumed-http.json',dict(result='passed_restored_native_HTTP_and_release_plan_fences',generation=19,native_A_B_C_list_form=True,saved_Note_readable=True,old_epoch18_gateway409=True,old_native_RPC_ClientReleaseMismatch=True,retired_plan_exit2=True,all17tables_28jobs_exact=True,browser_rendering_tested=False))
record=dict(state='requesting',gateway_key='reference-restored-'+uuid4().hex);f.write(FINISH,record)
response=positive.call(client,original,'analyze',dict(note_id=original['note_id'],expected_revision=original['revision']),record['gateway_key']);assert response['job']['state']=='pending'
record.update(state='enqueued',job_id=response['job']['id']);f.write(FINISH,record)
args=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
record['state']='running';f.write(FINISH,record);result=json.loads(f.command('reference-restored-ordinary-runner',args,timeout=180));f.save('resumed-runner.json',result)
record['state']='runner_terminal_needs_verification';f.write(FINISH,record)
actual=positive.call(client,original,'status',dict(note_id=original['note_id']))['job']
assert actual['id']==record['job_id'] and actual['state']=='completed' and actual['attempts']==1 and actual['error_code'] is None
assert actual['result']==dict(note_id=original['note_id'],revision=original['revision'],statistics=original['expected_statistics'])
after=base.snapshot(state,'reference-finish-after-real-job')
for table in before:
    current=[r for r in after[table] if r['public_id']!=record['job_id']] if table=='mp_job' else after[table]
    assert current==before[table],table
assert base.worker(native,'reference-finish-worker-after')==f.load(PRIVATE/'worker-current.json')
operator=positive.r1_probe.Client(state,fixture,'operator');code,response=operator.request('/api/v1/operations/installed');assert code==200
row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats');assert row['health']['state']=='healthy' and row['features'][0]['availability']=='enabled'
f.save('resumed-remote.json',dict(result='passed_actual_recovered_ordinary_original_actor_remote_job_with_current_key',configuration_generation=19,job=actual,actual_ordinary_independent_CLI=True,current_publication7_endpoint5_key_recovery19=True,all_old28jobs_and_other16tables_exact=True,same_current_rotated_worker=True,current_manager_healthy_provider_enabled=True,no_new_note_or_business_schema=True,
    limits=['Stateless reference result only; actual non-idempotent uncertain effect/reconciliation remains separate JOB03. Changed-worker-image and browser/G7 still pending.']))
record['state']='verified';f.write(FINISH,record);f.phase(state,'reference_recovery_resumed_remote_verified');f.guard(state)
print('Actual restored native/API and old-epoch/retired-plan fences pass; ordinary original-actor remote job completes once under new key; all old data exact',flush=True)
