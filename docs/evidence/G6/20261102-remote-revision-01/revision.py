"""Actual saved Note revision changes after real worker response; no stale apply."""
import json,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-remote-role-01'))
from role import positive,context,base,f,j,WRAPPER
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'remote-revision-01';MARKER=PRIVATE/'qualification.json'

def phase(record,value):record['state']=value;f.write(MARKER,record)
def run():
    state,native=context();assert native.config['generation']==18 and not PRIVATE.exists();protect_directory(PRIVATE)
    before=base.snapshot(state,'remote-revision-before');worker=base.worker(native,'remote-revision-worker-before')
    assert len(before['mp_job'])==24 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    f.write(PRIVATE/'data-before.json',before);f.write(PRIVATE/'worker-before.json',worker)
    prior=f.load(j.LOCAL/'notes-stats-remote-01/positive.json');record=dict(jobs_binding=prior['jobs_binding']);phase(record,'baseline_captured')
    alice=positive.client(state)
    phase(record,'creating_disposable_note')
    note=alice.call('create',dict(title='G6 remote revision race',body='Original saved version'),workspace='C',key='remote-revision-create-'+uuid4().hex)
    assert note['revision']==1;record.update(note_id=note['id'],revision=1);phase(record,'disposable_note_created')
    phase(record,'enqueuing_original_revision')
    result=positive.call(alice,record,'analyze',dict(note_id=record['note_id'],expected_revision=1),'remote-revision-'+uuid4().hex)
    assert result['job']['state']=='pending';record['job_id']=result['job']['id'];phase(record,'enqueued')
    op=WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json');op.publisher._authorize()
    observation=native.observer.read();operation=str(uuid4());arguments=op._job_arguments(observation['runtime'],operation)
    assert arguments[-3:]==['-m','modular_platform.job_runner','--once'];arguments[-3:]=['-c',WRAPPER]
    name=arguments[arguments.index('--name')+1];record.update(test_runner_operation=operation,test_runner_container=name)
    stdout=PRIVATE/'post-io.stdout';stderr=PRIVATE/'post-io.stderr';phase(record,'launching_post_io_runner')
    with stdout.open('xb') as out,stderr.open('xb') as err:
        process=subprocess.Popen(arguments,stdout=out,stderr=err,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        record['pid']=process.pid;phase(record,'waiting_post_io_barrier');deadline=time.monotonic()+90
        while True:
            lines=[line.split('MP_POST_IO=',1)[1] for line in stdout.read_text(encoding='utf8').splitlines() if line.startswith('MP_POST_IO=')]
            if lines:break
            assert process.poll() is None,'Inspect original runner/claim; no automatic replay'
            assert time.monotonic()<deadline,'Inspect still-live handle; timeout does not imply termination'
            time.sleep(.05)
        assert len(lines)==1;barrier=json.loads(lines[0]);assert barrier['job_id']==record['job_id']
        record['barrier']=barrier;phase(record,'real_remote_result_received_before_finalize')
        phase(record,'updating_note_after_real_remote_response')
        updated=alice.call('update',dict(note_id=record['note_id'],expected_revision=1,body='Newer saved version'),workspace='C',key='remote-revision-update-'+uuid4().hex)
        assert updated['revision']==2;phase(record,'new_note_revision_committed')
        f.command('remote-revision-release',['docker','exec',name,'/venv/bin/python','-c',"from pathlib import Path;Path('/tmp/mp-g6-post-io-release').touch()"])
        phase(record,'runner_released');assert process.wait(timeout=45)==0,'Inspect exact original terminal runner/claim'
    rows=[json.loads(line) for line in stdout.read_text(encoding='utf8').splitlines() if line.startswith('{')]
    result=next(r for r in rows if r.get('job_id')==record['job_id'])
    assert result==dict(job_id=record['job_id'],state='dead_letter',error_code='CONFLICT'),result
    status=positive.call(alice,record,'status',dict(note_id=record['note_id']))['job']
    assert status['id']==record['job_id'] and status['state']=='dead_letter' and status['attempts']==1 and status['error_code']=='CONFLICT' and status['result'] is None
    assert alice.call('get',dict(note_id=record['note_id']),workspace='C')==updated
    phase(record,'terminal_conflict_verified')
    after=base.snapshot(state,'remote-revision-after');added={}
    for table,old in before.items():
        old_ids={r['id'] for r in old};added[table]=[r for r in after[table] if r['id'] not in old_ids]
        assert [r for r in after[table] if r['id'] in old_ids]==old,table+' old rows changed'
        if table not in ('mp_example_note','mp_job','mp_outbox','mp_event_delivery'):assert not added[table],table+' unexpected rows'
    assert len(added['mp_example_note'])==1
    row=added['mp_example_note'][0];assert row['public_id']==record['note_id'] and row['revision']==2 and row['body']=='Newer saved version'
    assert len(added['mp_job'])==1
    row=added['mp_job'][0];assert row['public_id']==record['job_id'] and row['state']=='dead_letter' and row['error_code']=='CONFLICT' and row['result'] is None
    assert len(added['mp_outbox'])==2 and all(r['aggregate_id']==record['note_id'] for r in added['mp_outbox'])
    event_ids={r['id'] for r in added['mp_outbox']};assert all(r['event_id'] in event_ids for r in added['mp_event_delivery'])
    assert base.worker(native,'remote-revision-worker-after')==worker
    assert not f.command('remote-revision-no-retained-runner',['docker','ps','--all','--filter','name=^/'+name+'$','--format','{{.ID}}']).strip()
    f.save('qualification.json',dict(result='passed_actual_saved_note_revision_change_after_remote_IO',source_commit='79145cc2',configuration_generation=18,dispatch_generation=88,
        job_id=record['job_id'],note_id=record['note_id'],computed_before_revision_change=True,barrier=barrier,
        unchanged_native_runner_startup_bridge_transport_finalize=True,test_only_trace_no_function_replacement=True,
        normal_gateway_saved_revision1_to2=True,one_terminal_conflict_attempt_no_stale_result=True,newer_note_retained=True,
        all_old24jobs_29notes_and_other17table_rows_exact=True,
        explicit_new_footprint={table:len(rows) for table,rows in added.items() if rows},
        same_running_worker_and_independent_authority=True,no_persistent_Docker_assets_added=True,
        limits=['Revision race only; binding/grant/feature/credential/publication current integration coverage review, external recovery, changed-image and browser remain.']))
    phase(record,'verified');f.phase(state,'remote_revision_verified');f.guard(state)
    print('Real remote result for revision1 rejected as CONFLICT after normal saved revision2; old24jobs/29Notes/metadata and worker exact',flush=True)

if __name__=='__main__':run()
