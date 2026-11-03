"""One actual original-actor job proves new host helper/old worker interop."""
import importlib.util,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('core21_remote_activation',OUT/'activate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old=ROOT/'docs/evidence/G6/20261102-worker-image-success-01/remote.py'
spec=importlib.util.spec_from_file_location('core21_remote_original',old);previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
f=m.f;f.OUTPUT=OUT
from modular_platform.contracts import validate
state,native=m.context();assert native.config['generation']==30 and f.load(m.MARKER)['state']=='preservation_verified'
marker=m.PRIVATE/'remote-job.json';assert not marker.exists()
before=m.snapshot(state,'core21-remote-before');worker=m.worker(native,'core21-remote-worker-before')
f.write(m.PRIVATE/'remote-data-before.json',before)
client=previous.s.client(state,'alice');saved=f.load(m.j.LOCAL/'notes-stats-remote-01/positive.json')
views={}
for workspace in ['A','B','C']:
 result=client.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace)
 assert set(result['views'])=={'list','form'};views[workspace]=sorted(result['views'])
record=dict(state='requesting',key='core21-remote-'+uuid4().hex);f.write(marker,record)
values=dict(note_id=saved['note_id'],expected_revision=saved['revision'])
response=previous.positive.call(client,saved,'analyze',values,record['key']);assert response['job']['state']=='pending'
record.update(state='enqueued',job_id=response['job']['id']);f.write(marker,record)
assert previous.positive.call(client,saved,'analyze',values,record['key'])==response
record['state']='running';f.write(marker,record)
args=m.base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(m.j.LOCAL/'operator/worker-target.json'),'run-job-once']
runner=json.loads(f.command('core21-remote-ordinary-runner',args,timeout=240));f.save('remote-runner.json',runner)
record['state']='runner_terminal_needs_verification';f.write(marker,record)
actual=previous.positive.call(client,saved,'status',dict(note_id=saved['note_id']))['job']
assert actual['id']==record['job_id'] and actual['state']=='completed' and actual['attempts']==1 and actual['error_code'] is None
assert actual['result']==dict(note_id=saved['note_id'],revision=saved['revision'],statistics=saved['expected_statistics'])
after=m.snapshot(state,'core21-remote-after')
for table,rows in before.items():
 remaining=[r for r in after[table] if r['public_id']!=record['job_id']] if table=='mp_job' else after[table]
 assert remaining==rows,table+' changed beyond one new test job'
assert len(after['mp_job'])==len(before['mp_job'])+1 and m.worker(native,'core21-remote-worker-after')==worker
code,response=previous.s.client(state).request('/api/v1/operations/installed');assert code==200;validate('manager-view',response['data'])
provider=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert provider['health']['state']=='healthy' and provider['features'][0]['availability']=='enabled'
f.save('remote-job.json',dict(result='passed_current_core21_original_actor_remote_job',job_id=record['job_id'],attempts=1,idempotent_gateway_replay=True,
 native_views=views,statistics_match_saved_note_revision=True,old_jobs_preserved=len(before['mp_job']),other16tables_worker_exact=True,
 actual_helper_image=state['image_id'],independent_worker_image=worker['image_id'] if 'image_id' in worker else 'retained_original548',manager_healthy_enabled=True,
 limits=['New host/helper Python dependencies interoperate with old approved worker; updated worker image still requires its own build/approval/qualification.','No browser rendering, full proxy/security or recovery qualification.']))
record['state']='verified';f.write(marker,record);f.phase(state,'core21_remote_interop_verified');f.guard(state)
print(json.dumps(dict(result='current_host_remote_job_passed',old_jobs=len(before['mp_job']),new_total=len(after['mp_job']),attempts=1)))
