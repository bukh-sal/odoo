"""Continue after incorrect expectation of a private exception in redacted logs.

Do not replay seeds/compute/kill/role changes. Inspect terminal cancel process,
classify the installed mapper/failure-writer mismatch, reap only via normal CLI,
then prove the original dataset and authority exact.
"""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
fixture=f.load(j.LOCAL/'fixtures.json');baseline=f.load(j.LOCAL/'core11-runner-before.json');job=f.load(j.LOCAL/'core11-cancel-seed.json')
name=state['project']+'-core11-cancel-runner'
container=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
assert not container['State']['Running'] and container['State']['ExitCode']==1
rows=[json.loads(line) for line in (j.LOCAL/'logs/core11-cancel-runner.stdout').read_text().splitlines() if line.startswith('{')]
assert rows==[dict(state='error',error_code='INTERNAL_ERROR')]
snapshot=json.loads(f.sql(state,'core11-resume-cancel-observe',"SELECT jsonb_build_object('state',state,'attempts',attempts,'cancel_requested',cancel_requested,'lease_remaining',GREATEST(0,extract(epoch FROM lease_until-timezone('UTC',clock_timestamp())))) FROM mp_job WHERE public_id='"+job['job_id']+"';"))
assert snapshot['state']=='running' and snapshot['attempts']==1 and snapshot['cancel_requested'] and 0<=snapshot['lease_remaining']<=30
if snapshot['lease_remaining']:time.sleep(snapshot['lease_remaining']+0.2)
cli=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'worker','--store',str(j.LOCAL/'operator/control'),'--deployment-config',str(j.LOCAL/'operator/target.json'),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
f.command('core11-resume-cancel-reaper',cli,timeout=180)
code="""import json
from uuid import uuid4
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import durable
from modular_platform.worker_dispatch import WorkerDispatchError
assert jobs._safe_code(WorkerDispatchError('CANCELLED'))=='CANCELLED'
try:durable.fail(env.cr,durable.Claim(JOB_ID,1,str(uuid4())),'CANCELLED')
except durable.QueueError:pass
else:raise AssertionError('Expected installed cancellation/failure code mismatch')
print('MP_CANCEL_MAPPING='+json.dumps(dict(mapper_code='CANCELLED',failure_writer_rejects=True)))
env.cr.rollback()
"""
raw=f.native(state,'core11-cancel-mapping-proof',[],'JOB_ID='+repr(job['job_id'])+'\n'+code)
proof=[json.loads(line.split('MP_CANCEL_MAPPING=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CANCEL_MAPPING=')];assert len(proof)==1
after=json.loads(f.sql(state,'core11-runner-after',"SELECT jsonb_build_object('jobs',(SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j),'notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'events',(SELECT jsonb_agg(to_jsonb(e) ORDER BY id) FROM mp_outbox e),'membership',(SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m),'control',(SELECT to_jsonb(c) FROM mp_dispatch_control c));"))
for key in ['jobs','notes','events']:
    current={row['id']:row for row in after[key]};assert all(current[row['id']]==row for row in baseline[key]),key
assert after['membership']==baseline['membership'] and after['control']==baseline['control']
assert not any(row['state'] in {'pending','running','retry'} for row in after['jobs'])
cancelled=next(row for row in after['jobs'] if row['public_id']==job['job_id']);assert cancelled['state']=='cancelled' and cancelled['attempts']==1
unavailable=f.load(j.LOCAL/'core11-unavailable-seed.json');unavailable_row=next(row for row in after['jobs'] if row['public_id']==unavailable['job_id'])
assert unavailable_row['state']=='dead_letter' and unavailable_row['error_code']=='DEPENDENCY_UNAVAILABLE' and unavailable_row['attempts']==1
f.write(j.LOCAL/'core11-runner-after.json',after)
f.save('errors.json',dict(result='unavailable_passed_cancel_defect_reproduced',image_id=state['image_id'],unavailable_error_preserved=True,cancellation_uses_actual_bridge_snapshot_and_real_cancel_flag=True,installed_mapping=proof[0],outer_runner_reported='INTERNAL_ERROR',cancelled_owned_job_reaped_without_replay=True,privacy_guard_omits_exception_text=True,fixture_correction='Initial assertion wrongly expected suppressed private exception text; actual minimal log was correct. Resume observes same terminal process/job, proves mapping directly without mutation and reaps expired owned claim once.'))
f.save('checkpoint.json',dict(result='installed_lease_revocation_passed_cancel_defect_open',image_id=state['image_id'],generation=9,dispatch_generation=40,original_jobs_notes_events_memberships_control_exact=True,current_jobs=len(after['jobs']),current_notes=len(after['notes']),current_events=len(after['events']),job_states={key:sum(row['state']==key for row in after['jobs']) for key in sorted({row['state'] for row in after['jobs']})},pending_or_running_jobs=0,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['packages/platform_sdk/modular_platform/job_runner.py','platform_addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/durable.py','platform_addons/mp_example_notes/jobs.py','platform_addons/mp_core/external_job.py']},limits=['Trace pauses for death/revocation; registered compute callback deliberately injects unavailable or delegates real bridge cancellation fence. Actual runner/claim/authorization/finalization code unchanged.','CANCELLED must be treated as claim loss, not passed to durable.fail. Fix via immutable versioned rollout and requalify; JOB01/02 remain invalidated.']))
f.write(j.LOCAL/'core11-runner-01.json',dict(state='completed_with_cancel_defect',jobs=len(after['jobs']),notes=len(after['notes']),events=len(after['events'])));f.phase(state,'core11_runner_cancel_defect_reproduced');f.guard(state)
print('Original data/authority/control exact; all10jobs terminal. Actual installed cancellation mapping defect recorded without replay.')
