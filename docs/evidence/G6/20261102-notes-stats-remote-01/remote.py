"""One actual original-actor HTTP job through the installed remote bridge."""
import argparse,hashlib,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-notes-stats-install-01'))
from install import context,base,f,j
from modular_platform.operator_os import protect_directory
import r1_probe
r1_probe.r1.r0.LOCAL=j.LOCAL
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'notes-stats-remote-01';MARKER=PRIVATE/'positive.json'

def client(state):return r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),'alice')
def call(c,record,method,values,key=None):
    body=dict(api_version='1.0',request_id='remote-'+uuid4().hex,input=values)
    if key:body['idempotency_key']=key
    status,response=c.request('/api/v1/services/org.example.notes_stats.jobs/'+method,body,workspace='C',headers={'X-CSRFToken':c.csrf,'X-MP-Binding':record['jobs_binding']})
    assert status==200,(method,status,response.get('error',{}).get('code'))
    return response['data']

def baseline():
    state,native=context();assert native.config['generation']==18 and not PRIVATE.exists();protect_directory(PRIVATE)
    data=base.snapshot(state,'notes-stats-remote-before');assert len(data['mp_job'])==19 and all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
    fixture=f.load(j.LOCAL/'fixtures.json');workspace=next(r for r in data['mp_workspace'] if r['public_id']==fixture['workspaces']['C']['public_id'])
    note=next(r for r in data['mp_example_note'] if r['workspace_id']==workspace['id'] and isinstance(r['body'],str) and r['body'])
    installation=next(r for r in data['mp_plugin_installation'] if r['plugin_id']=='org.example.notes_stats')
    binding=next(r for r in data['mp_service_binding'] if r['consumer_id']==installation['id'] and r['alias']=='jobs')
    record=dict(state='baseline_captured',note_id=note['public_id'],revision=note['revision'],body_sha256=hashlib.sha256(note['body'].encode()).hexdigest(),
        expected_statistics=dict(characters=len(note['body']),words=len(note['body'].split()),lines=len(note['body'].splitlines())),jobs_binding=binding['public_id'],gateway_key='remote-first-'+uuid4().hex)
    f.write(PRIVATE/'data-before.json',data);f.write(PRIVATE/'worker-before.json',base.worker(native,'notes-stats-remote-worker-before'));f.write(MARKER,record)
    print('Fresh19-terminal-job baseline and original saved Note revision captured privately; no job enqueued')

def enqueue():
    state,native=context();record=f.load(MARKER);assert record['state']=='baseline_captured'
    c=client(state);values=dict(note_id=record['note_id'],expected_revision=record['revision'])
    record['state']='requesting';f.write(MARKER,record)
    response=call(c,record,'analyze',values,record['gateway_key']);job=response['job'];assert job['state']=='pending'
    record.update(state='enqueued',job_id=job['id']);f.write(MARKER,record);f.save('enqueue.json',response)
    assert call(c,record,'analyze',values,record['gateway_key'])==response
    after=base.snapshot(state,'notes-stats-remote-after-enqueue');before=f.load(PRIVATE/'data-before.json')
    for table in before:
        if table=='mp_job':
            old={r['public_id'] for r in before[table]};new=[r for r in after[table] if r['public_id'] not in old]
            assert len(new)==1 and new[0]['public_id']==job['id'] and new[0]['state']=='pending' and new[0]['attempts']==0
            assert [r for r in after[table] if r['public_id'] in old]==before[table]
        else:assert after[table]==before[table],table
    f.save('enqueue-qualification.json',dict(result='passed_actual_original_actor_gateway_enqueue_and_same_key_replay',job_id=job['id'],one_new_pending_job=True,old19jobs_and_other16tables_exact=True,no_note_text_in_public_evidence=True))
    print('Original-actor real gateway enqueued exactly1job; same-key replay returns same outcome; old data unchanged')

def run():
    state,native=context();record=f.load(MARKER);assert record['state']=='enqueued';record['state']='running';f.write(MARKER,record)
    command=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    result=json.loads(f.command('notes-stats-remote-run-once',command,timeout=240));f.save('run-once.json',result)
    record['state']='runner_terminal_needs_verification';f.write(MARKER,record);print('Ordinary independently configured job runner finished; inspect actual outcome before any retry')

def verify():
    state,native=context();record=f.load(MARKER);assert record['state']=='runner_terminal_needs_verification'
    c=client(state);response=call(c,record,'status',dict(note_id=record['note_id']));job=response['job']
    assert job['id']==record['job_id'] and job['state']=='completed' and job['attempts']==1 and job['error_code'] is None,(job['state'],job['error_code'])
    expected=dict(note_id=record['note_id'],revision=record['revision'],statistics=record['expected_statistics']);assert job['result']==expected
    before=f.load(PRIVATE/'data-before.json');after=base.snapshot(state,'notes-stats-remote-after-run')
    for table in before:
        actual=after[table]
        if table=='mp_job':actual=[r for r in actual if r['public_id']!=record['job_id']]
        assert actual==before[table],table+' changed outside the single new analysis job'
    row=next(r for r in after['mp_job'] if r['public_id']==record['job_id'])
    fixture=f.load(j.LOCAL/'fixtures.json');principal=next(r for r in after['mp_principal'] if r['user_id']==fixture['users']['alice']['id'])
    assert row['actor_id']==principal['id'] and row['handler']=='org.example.notes_stats:analyze' and row['effect_mode']=='idempotent'
    def has_text_key(value):
        return isinstance(value,dict) and ('text' in value or any(has_text_key(v) for v in value.values())) or isinstance(value,list) and any(has_text_key(v) for v in value)
    assert not has_text_key(row['payload']) and row['result']==expected
    assert base.worker(native,'notes-stats-remote-worker-after')==f.load(PRIVATE/'worker-before.json')
    f.save('positive-qualification.json',dict(result='passed_actual_installed_original_actor_remote_analysis_job',job_id=job['id'],configuration_generation=18,dispatch_generation=88,
        actual_independent_runner_and_installed_bridge_without_source_substitution=True,one_completed_job_one_attempt=True,
        original_actor_uid=fixture['users']['alice']['id'],revision_and_structured_statistics_exact=True,note_body_sha256=record['body_sha256'],
        statistics=record['expected_statistics'],old19jobs_and_all16_other_tables_exact=True,no_note_text_in_job_payload=True,worker_identity_key_config3_publication5_exact=True,
        limits=['Positive remote path and gateway replay only; worker duplicate/outage/scoped/in-flight authority/external recovery/changedimage/browser still required.']))
    record['state']='verified';f.write(MARKER,record);f.phase(state,'notes_stats_first_remote_verified');f.guard(state)
    print('Actual remote analysis completed once as original actor; structured stats/revision exact, old data/19jobs/worker preserved')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','enqueue','run','verify']);a=p.parse_args();globals()[a.action]()
