"""Installed correction: actual bridge cancellation, fixed-code faults, normal CLI.

Only registered compute callbacks are fault-instrumented; the inventoried runner,
native authority, queue, fresh bridge claim gate and finalization are untouched.
"""
import ast,dataclasses,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerOperator
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);fixture=f.load(j.LOCAL/'fixtures.json')
marker=j.LOCAL/'core12-runner-01.json';assert not marker.exists()
target=f.load(j.LOCAL/'operator/target.json');assert target['generation']==10
worker_path=j.LOCAL/'operator/worker-target.json';worker=f.load(worker_path)
assert worker['helper_image']==target['image_id']
f.write(marker,dict(state='starting',image_id=state['image_id']))
store=OperatorStore(j.LOCAL/'operator/control');operator=WorkerOperator(store,j.LOCAL/'operator/target.json',worker_path)
source=(ROOT/'docs/evidence/G6/20261101-core11-runner-01/run.py').read_text()
old="if mode=='unavailable':raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE',sent=True)"
new="if mode!='cancel':raise WorkerDispatchError({'unavailable':'DEPENDENCY_UNAVAILABLE','suspended':'PLUGIN_SUSPENDED','missing':'NOT_FOUND','deadline':'DEADLINE_EXCEEDED','forbidden':'FORBIDDEN','untrusted':'MP_PRIVATE_COMPUTE_CANARY'}.get(mode,'INTERNAL_ERROR'),sent=True)"
assert old in source;source=source.replace(old,new)
tree=ast.parse(source);tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'native','snapshot','seed','cli','create','start','finish'} or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='native_base' for t in n.targets)]
exec(compile(tree,'retained_fixture_handlers_with_explicit_compute_faults','exec'))
before=json.loads(f.sql(state,'core12-runner-before',"SELECT jsonb_build_object('jobs',(SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j),'notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'events',(SELECT jsonb_agg(to_jsonb(e) ORDER BY id) FROM mp_outbox e),'membership',(SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m),'control',(SELECT to_jsonb(c) FROM mp_dispatch_control c));"))
assert len(before['jobs'])==10 and before['control']['generation']==43
f.write(j.LOCAL/'core12-runner-before.json',before)
cases=[]
for mode,code in [('unavailable','DEPENDENCY_UNAVAILABLE'),('suspended','PLUGIN_SUSPENDED'),('missing','NOT_FOUND'),('deadline','DEADLINE_EXCEEDED'),('forbidden','FORBIDDEN'),('untrusted','INTERNAL_ERROR'),('cancel',None)]:
    job=seed('core12-'+mode+'-seed',False);name,ident=create('core12-'+mode+'-runner',mode);handle=start('core12-'+mode+'-runner',name)
    rows=finish(handle);observed=snapshot('core12-'+mode+'-observed',job)
    if mode=='cancel':
        assert rows==[dict(job_id=job['job_id'],state='claim_lost')]
        assert observed['state']=='running' and observed['cancel_requested'] and observed['attempts']==1 and 0<=observed['lease_remaining']<=30
        f.write(marker,dict(state='cancel_claim_lost_waiting_bounded_reaper',container_id=ident,job_id=job['job_id']))
        print('Installed real bridge cancellation reports claim_lost/exit0; waiting for ordinary bounded reaper',flush=True)
        time.sleep(observed['lease_remaining']+0.2);cli('core12-cancel-reaper-normal-cli')
        observed=snapshot('core12-cancel-terminal',job);assert observed['state']=='cancelled' and observed['attempts']==1
    else:
        assert rows==[dict(job_id=job['job_id'],state='dead_letter',error_code=code)]
        assert observed['state']=='dead_letter' and observed['error_code']==code and observed['attempts']==1
    assert 'MP_PRIVATE_COMPUTE_CANARY' not in handle[3].read_text() and 'MP_PRIVATE_COMPUTE_CANARY' not in handle[4].read_text()
    cases.append(dict(mode=mode,state=observed['state'],error_code=code,attempts=1,exit_code=0,job_id=job['job_id']))
normal=seed('core12-normal-seed',False);result=cli('core12-normal-cli')
assert result['results']==[dict(job_id=normal['job_id'],state='completed')]
observed=snapshot('core12-normal-completed',normal);assert observed['state']=='completed' and observed['attempts']==1 and observed['result']==dict(note_id=normal['note_id'],revision=normal['revision'])
after=json.loads(f.sql(state,'core12-runner-after',"SELECT jsonb_build_object('jobs',(SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j),'notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'events',(SELECT jsonb_agg(to_jsonb(e) ORDER BY id) FROM mp_outbox e),'membership',(SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m),'control',(SELECT to_jsonb(c) FROM mp_dispatch_control c));"))
assert after['notes']==before['notes'] and after['events']==before['events'] and after['membership']==before['membership'] and after['control']==before['control']
byid={row['id']:row for row in after['jobs']};assert all(byid[row['id']]==row for row in before['jobs'])
assert all(row['state'] in {'completed','cancelled','dead_letter'} for row in after['jobs'])
f.write(j.LOCAL/'core12-runner-after.json',after)
f.save('processes.json',dict(result='passed_installed_core12_error_and_cancel_correction',image_id=state['image_id'],cases=cases,normal_cli_job=normal['job_id'],normal_attempts=1,normal_runner_source_substitution=False,compute_fault_instrumentation_only=True,actual_cancel_flag_and_real_bridge_claim_gate=True,private_error_canary_absent=True,all_previous_data_and_authority_exact=True,all_jobs_terminal=True,current_job_states={key:sum(row['state']==key for row in after['jobs']) for key in sorted({row['state'] for row in after['jobs']})},limits=['Safe-code/error/cancellation kernel qualification; not real remote transport/outage/degraded UI or external recovery proof.']))
f.write(marker,dict(state='processes_verified',jobs=len(after['jobs']),notes=len(after['notes']),events=len(after['events'])));f.phase(state,'core12_runner_processes_verified');f.guard(state)
print('Installed core12 seven error/cancel cases and normal CLI pass; all18jobs terminal, no Note/event/authority change')
