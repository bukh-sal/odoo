"""Actual original-actor demotion before dispatch and after real remote I/O."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-notes-stats-remote-01'))
import remote as positive
context,base,f,j=positive.context,positive.base,positive.f,positive.j
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'remote-role-01';MARKER=PRIVATE/'qualification.json'

# A test-only debugger-style pause at the existing post-compute line. No
# authorization, transport, result, startup guard or runner function is replaced.
WRAPPER='''import hashlib,json,linecache,pathlib,runpy,sys,time
def trace(frame,event,arg):
 if event=='line' and frame.f_code.co_name=='run_once' and frame.f_code.co_filename.endswith('/modular_platform/job_runner.py') and 'computed' in frame.f_locals and linecache.getline(frame.f_code.co_filename,frame.f_lineno).strip()=='with registry.cursor() as cr:':
  sys.settrace(None);frame.f_trace=None
  invocation=frame.f_locals['invocation'];computed=frame.f_locals['computed']
  print('MP_POST_IO='+json.dumps({'job_id':invocation.claim.job_id,'computed_sha256':hashlib.sha256(json.dumps(computed,sort_keys=True).encode()).hexdigest()}),flush=True)
  deadline=time.monotonic()+20
  while not pathlib.Path('/tmp/mp-g6-post-io-release').exists():
   if time.monotonic()>deadline:raise TimeoutError('Bounded post-IO test barrier expired')
   time.sleep(.02)
 return trace
sys.argv=['modular_platform.job_runner','--once'];sys.settrace(trace)
runpy.run_module('modular_platform.job_runner',run_name='__main__')
'''

def phase(record,state):record['state']=state;f.write(MARKER,record)
def member(alice,principal,operation,role=None):
    body=dict(operation=operation,principal_id=principal)
    if role:body['role']=role
    status,response=alice.request('/api/v1/workspace/members',body,workspace='C',headers={'X-CSRFToken':alice.csrf})
    assert status==200 and response['data']==dict(principal_id=principal,changed=True),(status,response.get('error',{}).get('code'))
def enqueue(bob,record,case):
    response=positive.call(bob,record,'analyze',dict(note_id=record['note_id'],expected_revision=record['revision']),'role-'+case+'-'+uuid4().hex)
    assert response['job']['state']=='pending';return response['job']['id']
def status(bob,record,job):
    result=positive.call(bob,record,'status',dict(note_id=record['note_id']))['job']
    assert result['id']==job and result['state']=='dead_letter' and result['error_code']=='FORBIDDEN' and result['attempts']==1 and result['result'] is None
    return result
def denied(bob,record):
    body=dict(api_version='1.0',request_id='denied-'+uuid4().hex,input=dict(note_id=record['note_id']))
    code,response=bob.request('/api/v1/services/org.example.notes_stats.jobs/status',body,workspace='C',headers={'X-CSRFToken':bob.csrf,'X-MP-Binding':record['jobs_binding']})
    assert code==403 and response['error']['code']=='FORBIDDEN',(code,response.get('error',{}).get('code'))

def run():
    state,native=context();assert native.config['generation']==18
    continuation=PRIVATE.exists()
    if continuation:
        # Initial read-only assertion was wrong: a viewer can read own status.
        # The single enqueued job has not run. Revoke membership to remove the
        # actual read authority; never re-enqueue or replay an uncertain run.
        record=f.load(MARKER);assert record['state']=='demoting_before_dispatch' and len(record['jobs'])==1
        before=f.load(PRIVATE/'data-before.json');worker=f.load(PRIVATE/'worker-before.json')
        live=base.snapshot(state,'remote-role-continuation-before')
        row=next(r for r in live['mp_job'] if r['public_id']==record['jobs'][0]);assert row['state']=='pending' and row['attempts']==0
        assert len(live['mp_job'])==23 and base.worker(native,'remote-role-continuation-worker')==worker
    else:
        protect_directory(PRIVATE)
        before=base.snapshot(state,'remote-role-before');worker=base.worker(native,'remote-role-worker-before')
    assert len(before['mp_job'])==22 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    original=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
    if not continuation:record={k:original[k] for k in ('note_id','revision','jobs_binding')}
    fixture=f.load(j.LOCAL/'fixtures.json');bob_principal=next(r for r in before['mp_principal'] if r['user_id']==fixture['users']['bob']['id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==fixture['workspaces']['C']['public_id'])
    assert not any(r['principal_id']==bob_principal['id'] and r['workspace_id']==workspace['id'] for r in before['mp_membership'])
    if not continuation:
        record.update(bob_principal=bob_principal['public_id'],bob_principal_id=bob_principal['id'],workspace_id=workspace['id'],jobs=[])
        f.write(PRIVATE/'data-before.json',before);f.write(PRIVATE/'worker-before.json',worker);phase(record,'baseline_captured')
    alice=positive.client(state);bob=positive.r1_probe.Client(state,fixture,'bob')
    if not continuation:
        phase(record,'adding_disposable_bob_C_editor');member(alice,record['bob_principal'],'add','editor');phase(record,'bob_C_editor')
        phase(record,'pre_dispatch_enqueue');job=enqueue(bob,record,'pre');record['jobs'].append(job);phase(record,'pre_dispatch_enqueued')
        phase(record,'demoting_before_dispatch');member(alice,record['bob_principal'],'update','viewer')
    job=record['jobs'][0]
    phase(record,'revoking_membership_before_dispatch');member(alice,record['bob_principal'],'remove');denied(bob,record);phase(record,'pre_dispatch_revoked')
    args=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    phase(record,'pre_dispatch_running');result=json.loads(f.command('remote-role-before-dispatch-run',args,timeout=180));f.save('pre-dispatch-run.json',result)
    assert result['results']==[dict(job_id=job,state='dead_letter',error_code='FORBIDDEN')]
    phase(record,'restoring_editor_after_pre_dispatch');member(alice,record['bob_principal'],'add','editor');f.save('pre-dispatch-status.json',status(bob,record,job));phase(record,'pre_dispatch_verified')
    print('Before-dispatch current role denial verified through ordinary independent CLI',flush=True)
    phase(record,'post_io_enqueue');job=enqueue(bob,record,'post');record['jobs'].append(job);phase(record,'post_io_enqueued')
    op=WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json');op.publisher._authorize()
    observation=native.observer.read();operation=str(uuid4());arguments=op._job_arguments(observation['runtime'],operation)
    assert arguments[-3:]==['-m','modular_platform.job_runner','--once'];arguments[-3:]=['-c',WRAPPER]
    name=arguments[arguments.index('--name')+1];record.update(test_runner_operation=operation,test_runner_container=name)
    # The immediately preceding ordinary runner validated the mounted current
    # authority; before/after independent attestation checks it again below.
    stdout=PRIVATE/'post-io.stdout';stderr=PRIVATE/'post-io.stderr';phase(record,'launching_post_io_runner')
    with stdout.open('xb') as out,stderr.open('xb') as err:
        process=subprocess.Popen(arguments,stdout=out,stderr=err,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        record['pid']=process.pid;phase(record,'waiting_post_io_barrier');deadline=time.monotonic()+90
        while True:
            lines=[line.split('MP_POST_IO=',1)[1] for line in stdout.read_text(encoding='utf8').splitlines() if line.startswith('MP_POST_IO=')]
            if lines:break
            assert process.poll() is None,'Inspect original runner/claim; no automatic replay'
            assert time.monotonic()<deadline,'Inspect still-live runner; observation timeout is not terminal'
            time.sleep(.05)
        assert len(lines)==1;barrier=json.loads(lines[0]);assert barrier['job_id']==job
        record['barrier']=barrier;phase(record,'real_remote_result_received_before_finalize')
        phase(record,'revoking_after_real_remote_result');member(alice,record['bob_principal'],'remove');denied(bob,record);phase(record,'post_io_revoked')
        f.command('remote-role-release-post-io',['docker','exec',name,'/venv/bin/python','-c',"from pathlib import Path;Path('/tmp/mp-g6-post-io-release').touch()"])
        phase(record,'post_io_runner_released');assert process.wait(timeout=45)==0,'Inspect exact terminal runner/claim'
    rows=[json.loads(line) for line in stdout.read_text(encoding='utf8').splitlines() if line.startswith('{')]
    result=next(r for r in rows if r.get('job_id')==job);assert result==dict(job_id=job,state='dead_letter',error_code='FORBIDDEN'),result
    f.save('post-io-run.json',dict(operation_id=operation,result=result,barrier=barrier,unchanged_runner_test_only_post_compute_trace=True))
    phase(record,'restoring_editor_after_post_io');member(alice,record['bob_principal'],'add','editor');f.save('post-io-status.json',status(bob,record,job));phase(record,'post_io_verified')
    phase(record,'removing_disposable_bob_C_membership');member(alice,record['bob_principal'],'remove');phase(record,'fixture_authority_restored')
    after=base.snapshot(state,'remote-role-after')
    for table,rows in before.items():
        actual=after[table]
        if table=='mp_job':
            new=[r for r in actual if r['public_id'] in record['jobs']];assert len(new)==2
            assert all(r['actor_id']==record['bob_principal_id'] and r['state']=='dead_letter' and r['attempts']==1 and r['error_code']=='FORBIDDEN' and r['result'] is None for r in new)
            actual=[r for r in actual if r['public_id'] not in record['jobs']]
        elif table=='mp_membership':
            new=[r for r in actual if r['principal_id']==record['bob_principal_id'] and r['workspace_id']==record['workspace_id']]
            assert len(new)==1 and new[0]['state']=='revoked' and new[0]['role']=='editor'
            actual=[r for r in actual if r['id']!=new[0]['id']]
        elif table=='mp_workspace':
            actual=[dict(r) for r in actual]
            for row in actual:
                if row['id']==record['workspace_id']:
                    old=next(r for r in rows if r['id']==row['id']);assert row['policy_generation']==old['policy_generation']+7
                    row['policy_generation']=old['policy_generation'];row['write_date']=old['write_date'];row['write_uid']=old['write_uid']
        assert actual==rows,table
    assert base.worker(native,'remote-role-worker-after')==worker
    assert json.loads(f.command('remote-role-no-retained-runner',['docker','ps','--all','--filter','name=^/'+name+'$','--format','{{json .}}']).decode() or 'null') is None
    report=dict(result='passed_actual_original_actor_role_before_dispatch_and_after_remote_IO',source_commit='79145cc2',configuration_generation=18,dispatch_generation=88,
        pre_dispatch_ordinary_independent_CLI=True,post_IO_actual_inventoried_runner_startup_compute_transport_finalize=True,test_only_trace_barrier_no_function_replacement=True,
        original_actor_user_id=fixture['users']['bob']['id'],jobs=record['jobs'],one_attempt_each_no_result=True,live_HTTP_membership_and_revoked_status_denial=True,
        original22jobs_and_other_data_exact=True,explicit_footprint=dict(new_revoked_test_membership=1,workspace_C_policy_increments=7,new_dead_letter_jobs=2),
        same_running_worker_and_independent_authority=True,no_persistent_Docker_assets_added=True,
        wrapper_sha256=hashlib.sha256(WRAPPER.encode()).hexdigest(),
        limits=['Actual role changes only; resource revision/binding/grant/credential/feature/publication in-flight cases, recovery, changedimage and browser remain required. Native plugins remain fully trusted.'])
    f.save('qualification.json',report);phase(record,'verified');f.phase(state,'remote_role_verified');f.guard(state)
    print('Actual original-actor role revocation before dispatch and after real remote result refuses both jobs; fixture access restored, old data and worker exact',flush=True)

if __name__=='__main__':run()
