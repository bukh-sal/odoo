"""One ordinary original-actor reference job after restored traffic resumes."""
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).parent));import probe as p
from modular_platform.catalog import Catalog

state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='resumed_http_verified'
marker=p.PRIVATE/'ordinary-job-state.json';assert not marker.exists()
job_record=dict(state='observing',key='restored-core23-'+uuid4().hex);p.write(marker,job_record)
before=p.snapshot(state,'native-uninstall-current-ordinary-job-before')
assert before==p.load(p.PRIVATE/'data-closed.json')
fixture=p.load(p.LOCAL/'fixtures.json');p.r1_probe.r1.r0.LOCAL=p.LOCAL;alice=p.r1_probe.Client(state,fixture,'alice')
document=native.observer.state(native.observer.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
workspace=fixture['workspaces']['A']['public_id']
installation=next(row['installation_id'] for row in document['installations'] if row['plugin_id']=='org.example.notes_stats' and row['workspace_id']==workspace)
binding=next(row for row in document['bindings'] if row['consumer_installation_id']==installation and row['workspace_id']==workspace and row['alias']=='jobs')
def call(method,values,key=None):
    body=dict(api_version=binding['api_version'],request_id=str(uuid4()),input=values)
    if key:body['idempotency_key']=key
    code,value=alice.request('/api/v1/services/'+binding['service_id']+'/'+method,body,workspace='A',
        headers={'X-CSRFToken':alice.csrf,'X-MP-Binding':binding['binding_id']})
    assert code==200 and 'data' in value,(method,code,value.get('error',{}).get('code'))
    return value['data']
note=alice.call('list',dict(limit=25))['items'][0];note=alice.call('get',dict(note_id=note['id']))
job_record['state']='enqueuing';p.write(marker,job_record)
result=call('analyze',dict(note_id=note['id'],expected_revision=note['revision']),job_record['key'])
assert result['job']['state']=='pending'
job_record.update(state='enqueued',job_id=result['job']['id']);p.write(marker,job_record)
job_record['state']='ordinary_runner_running';p.write(marker,job_record)
args=p.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),
    '--worker-config',str(p.LOCAL/'operator/worker-target.json'),'run-job-once']
runner=json.loads(p.f.command('native-uninstall-current-ordinary-job-runner',args,timeout=240));p.save('ordinary-runner.json',runner)
job_record['state']='runner_terminal_needs_verification';p.write(marker,job_record)
actual=call('status',dict(note_id=note['id']))['job']
assert actual['id']==job_record['job_id'] and actual['state']=='completed' and actual['attempts']==1 and actual['error_code'] is None
expected=dict(characters=len(note['body']),words=len(note['body'].split()),lines=len(note['body'].splitlines()))
assert actual['result']==dict(note_id=note['id'],revision=note['revision'],statistics=expected)
after=p.snapshot(state,'native-uninstall-current-ordinary-job-after')
for table,rows in before.items():
    if table=='mp_job':
        assert [row for row in after[table] if row['public_id']!=job_record['job_id']]==rows
        new=[row for row in after[table] if row['public_id']==job_record['job_id']];assert len(new)==1
        assert new[0]['actor_id']==rows[0]['actor_id'] and new[0]['workspace_id']==rows[0]['workspace_id']
    else:assert after[table]==rows,table
assert p.worker(native,'native-uninstall-current-ordinary-job-worker')==p.load(p.PRIVATE/'worker-before.json')
p.save('ordinary-job.json',dict(result='passed_actual_restored_original_actor_reference_job',configuration_generation=native.config['generation'],
    job=actual,ordinary_independent_CLI=True,original_actor='alice',attempts=1,expected_statistics=expected,
    all_old_job_history_and_other16tables_exact=True,same_worker_process_image_key_publication=True,
    new_completed_job_rows=1,new_business_records_or_outbox_events=0,
    limits=['Bounded stateless reference worker only; no generic non-idempotent effect reconciliation claim.']))
job_record['state']='verified';p.write(marker,job_record);record['state']='ordinary_job_verified';p.write(p.PRIVATE/'state.json',record)
p.write(p.PRIVATE/'data-final.json',after);p.f.guard(state)
print(json.dumps(dict(result='restored_original_actor_ordinary_job_passed',job_id=job_record['job_id'])),flush=True)
