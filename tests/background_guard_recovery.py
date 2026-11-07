"""Phase-recorded BX-04 guarded claims and rotation across fresh recovery."""
import argparse
from pathlib import Path

from background_capacity_upgrade import snapshot as business
from background_recurrence import API_PROBE
from background_retention_lifecycle import approved, fail_after_publish
from background_site import configuration, load, write
from background_sustained import native
from background_workers import Probe, wait
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor


SEED="""
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
import json
from uuid import uuid4
from odoo import api
from odoo.service.model import retrying
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import durable,job_fairness as fairness
from modular_platform.job_runner import _claim_guard
release=current_release(env);workspace=FIXTURE['workspaces']['A']
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),workspace['public_id'])
row=DATA['A'];now=datetime.now(timezone.utc)
def enqueue(when,key):
    return jobs.enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:report',
        dict(first=row['first'],last=row['last']),key,version=2,
        schedule=durable.JobSchedule(when,when+timedelta(minutes=40),20))
pending=enqueue(now+timedelta(minutes=20),'bx04-recovery-pending')
running=enqueue(now,'bx04-recovery-running');env.cr.commit()
with env.registry.cursor() as cr:
    ticket=fairness.read(cr,release['site_id'],release['release_digest'],'bulk')
assert fairness.reserve(env.registry,ticket,workspace['id'])
with env.registry.cursor() as cr:
    with _claim_guard(cr,'bulk',workspace['id']) as allowed:
        assert allowed
        metadata=api.Environment(cr,1,{})
        invocation=retrying(lambda:jobs.prepare_one(metadata,str(uuid4()),pool='bulk',workspace_id=workspace['id']),metadata)
        assert invocation.claim.job_id==running
with env.registry.cursor() as cr:
    ticket=fairness.read(cr,release['site_id'],release['release_digest'],'bulk')
claim=invocation.claim
print('BX04_RESULT='+json.dumps(dict(pending=pending,running=running,
    claim=dict(job_id=claim.job_id,generation=claim.generation,owner=claim.owner),ticket=asdict(ticket))))
"""


def runtime(probe):
    return StagedNativeExecutor(probe.operator.store,probe.site.private/'target.json',
        probe.site.private/'catalog',configuration(probe.site.private/'trust.json'))


def state(probe):
    return dict(
        occurrences=probe.sql("SELECT md5(string_agg(md5(to_jsonb(r)::text),'' ORDER BY site_id,schedule_id,nominal_at)) FROM mp_job_occurrence r"),
        schedule_cursors=probe.sql("SELECT md5(string_agg(md5(jsonb_build_array(public_id,config_version,rule,input_digest,creation_digest,next_at,considered_at,outstanding_job_id)::text),'' ORDER BY public_id)) FROM mp_job_schedule"),
        rotation=probe.sql("SELECT md5(string_agg(value,'' ORDER BY key)) FROM ir_config_parameter WHERE key LIKE 'mp.jobs.rotation.%'"))


def main(phase,candidate):
    extra={'capture-seed':'bx04-guard-recovery-seed','finish-prepare':'bx04-guard-recovery-occurrence'}.get(phase)
    probe=Probe('bx-04-capacity-01',extra_phase=extra)
    assert not probe.operator._lanes()
    path=probe.site.local/'bx04-guard-recovery.json';record=load(path) if path.exists() else {}
    if phase in ('prepare','capture-seed','finish-prepare'):
        burst=load(probe.site.local/'bx04-recurring-burst.json');assert burst['phase']=='passed'
        if phase=='prepare':
            assert not record
            record=dict(phase='preparing',original_target=probe.target,business=business(probe),services=burst['services'])
            write(path,record)
            seed=native(probe,'bx04-guard-recovery-seed',SEED,DATA=load(probe.site.local/'bx04-sustained-setup.json')['data'])
        elif phase=='capture-seed':
            assert record['phase']=='preparing'
            probe.state['phase']='background_installed'
            seed=native(probe,'bx04-guard-recovery-capture',"""
from dataclasses import asdict
import json
from odoo.addons.mp_identity.release import current_release
from modular_platform import job_fairness as fairness
rows={}
for label in ('pending','running'):
    env.cr.execute('SELECT public_id,state,claim_generation,lease_owner FROM mp_job WHERE idempotency_key=%s',['bx04-recovery-'+label])
    found=env.cr.fetchall();assert len(found)==1
    rows[label]=found[0]
assert rows['pending'][1:]==('pending',0,None)
assert rows['running'][1]=='running' and rows['running'][2]==1 and rows['running'][3]
release=current_release(env)
ticket=fairness.read(env.cr,release['site_id'],release['release_digest'],'bulk')
assert ticket.after==FIXTURE['workspaces']['A']['id']
print('BX04_RESULT='+json.dumps(dict(pending=rows['pending'][0],running=rows['running'][0],
    claim=dict(job_id=rows['running'][0],generation=rows['running'][2],owner=rows['running'][3]),ticket=asdict(ticket))))
""")
            record['harness_diagnostic']='Original seed committed and prepared; output failed on optional datetime field. Captured exact rows/claim/ticket read-only; no seed replay.'
        else:
            assert record['phase']=='guard_seeded'
            seed=record['seed'];probe.state['phase']='background_installed'
            record['occurrence_harness_diagnostic']='Anchor edit was refused before mutation; retained original recurrence grid and resumed its current coalesce-latest occurrence.'
        record.update(phase='guard_seeded',seed=seed);write(path,record)
        actors='SERVICES='+repr(burst['services'])+'\n'+API_PROBE.split('def row(',1)[0]
        recurring=native(probe,'bx04-guard-recovery-occurrence'+('-02' if phase=='finish-prepare' else ''),actors+"""
current=actor('A');aid=SERVICES['A']['schedule']
env.cr.execute('SELECT config_version FROM mp_job_schedule WHERE public_id=%s',[aid]);revision,=env.cr.fetchone()
revision=recurring.resume_schedule(current,aid,revision);env.cr.commit()
emitted=recurring.tick(env,aid);assert emitted['outcome']=='emitted',emitted
revision=recurring.pause_schedule(current,aid,revision);env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(schedule=aid,job=emitted['job_id'],revision=revision)))
""",DATA=load(probe.site.local/'bx04-sustained-setup.json')['data'])
        review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2,producer_lanes=1,paused=True)
        assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='paused'
        record.update(phase='prepared',seed=seed,recurring=recurring,before=state(probe),old_profile=review['approval'])
    elif phase=='fault':
        assert record['phase']=='prepared'
        operation,executor=approved(probe,load(candidate)['image_id'],'core_upgrade')
        record.update(phase='applying',operation=operation,candidate=load(candidate)['image_id']);write(path,record)
        fail_after_publish(operation,executor)
        record.update(phase='recovery_required',failed_status=executor.store.status(operation))
    elif phase=='restore':
        assert record['phase']=='recovery_required'
        executor=RestoreExecutor(runtime(probe));decision=executor.prepare(record['operation'])
        record.update(phase='restoring',restore_digest=data_digest(decision));write(path,record)
        result=executor.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
        after=Probe('bx-04-capacity-01')
        assert result['state']=='restored_verified' and result['keep_traffic_closed']
        assert after.target['image_id']==record['original_target']['image_id']
        assert after.state['database']!=record['original_target']['sites'][0]['database']
        assert business(after)==record['business']
        assert after.sql("SELECT count(*) FROM mp_service_credential WHERE state='active'")=='0'
        assert after.sql('SELECT state FROM mp_dispatch_control')=='paused'
        assert after.row(record['recurring']['job'])['state']=='held'
        # A still-authorized idempotent human job is carried forward, while
        # the old lease/generation is invalidated. Revoked service work holds.
        restored_claim=after.row(record['seed']['running'])
        assert restored_claim['state']=='pending' and restored_claim['owner'] is None
        assert restored_claim['generation']>record['seed']['claim']['generation']
        assert after.row(record['seed']['pending'])['state']=='pending'
        restored=state(after)
        assert restored['occurrences']==record['before']['occurrences']
        assert restored['schedule_cursors']==record['before']['schedule_cursors']
        assert restored['rotation']==record['before']['rotation']
        assert not runtime(after)._inspect(runtime(after).observer._container('edge',stopped=True))['State']['Running']
        record.update(phase='restored_closed',result=result,restored=restored)
    elif phase=='resume':
        assert record['phase']=='restored_closed'
        executor=RestoreExecutor(runtime(probe));decision=executor.prepare_resume(record['operation'])
        record.update(phase='resuming',resume_digest=data_digest(decision));write(path,record)
        result=executor.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        assert probe.sql('SELECT state FROM mp_dispatch_control')=='enabled'
        record.update(phase='resumed',resume_result=result)
    elif phase=='prove':
        assert record['phase']=='resumed'
        proof=native(probe,'bx04-guard-recovery-proof',"""
import json
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import durable,job_fairness as fairness
release=current_release(env);workspace=FIXTURE['workspaces']['A']
old=durable.Claim(**SEED['claim'])
try:durable.run_fenced(env.cr,old,lambda row:dict(unexpected=True))
except (durable.ClaimLost,durable.DispatchPaused):env.cr.rollback()
else:raise AssertionError('Old claim survived fresh restore')
try:fairness.reserve(env.registry,fairness.Ticket(**SEED['ticket']),workspace['id'])
except durable.DispatchPaused:pass
else:raise AssertionError('Old rotation epoch survived fresh restore')
with env.registry.cursor() as cr:
    fresh=fairness.read(cr,release['site_id'],release['release_digest'],'bulk');assert fresh.after==0
assert fairness.reserve(env.registry,fresh,workspace['id'])
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),workspace['public_id'])
row=DATA['A'];now=datetime.now(timezone.utc);created=[]
for index in range(2):
    created.append(jobs.enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:report',
        dict(first=row['first'],last=row['last']),'bx04-restored-new-'+str(index),version=2,
        schedule=durable.JobSchedule(now,now+timedelta(seconds=180),20)))
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(old_claim_denied=True,old_rotation_denied=True,new_rotation_reset=True,jobs=created)))
""",SEED=record['seed'],DATA=load(probe.site.local/'bx04-sustained-setup.json')['data'])
        try:probe.operator.run('profile-apply',approval=record['old_profile'])
        except OperatorError as error:stale=str(error)
        else:raise AssertionError('Old profile survived fresh database pins')
        review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2,producer_lanes=0)
        assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='ready'
        wait(lambda:all(probe.row(job)['state']=='completed' for job in proof['jobs']),90)
        assert all(probe.row(job)['attempts']==1 for job in proof['jobs'])
        recovered=probe.row(record['seed']['running'])
        assert recovered['state']=='completed' and recovered['attempts']==2
        assert recovered['generation']>record['seed']['claim']['generation']
        assert business(probe)==record['business']
        assert probe.sql("SELECT count(*) FROM mp_service_credential WHERE state='active'")=='0'
        drained=probe.operator.run('drain');assert drained['state']=='paused'
        record.update(phase='passed',proof=proof,recovered_claim=recovered,stale_profile_denied=stale,new_approval=review['approval'],drain=drained)
    elif phase=='advance':
        assert record['phase']=='passed'
        operation,executor=approved(probe,record['candidate'],'core_upgrade')
        record.update(phase='advancing',successful_operation=operation);write(path,record)
        result=executor.apply(operation)
        assert result['state']=='completed' and result['traffic_resumed']
        after=Probe('bx-04-capacity-01')
        assert after.target['image_id']==record['candidate'] and business(after)==record['business']
        assert after.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_core'")=='19.0.0.1.45'
        assert after.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_example_background'")=='19.0.0.2.1'
        record.update(phase='qualified',successful_result=result,reference_unchanged=True)
    else:raise ValueError(phase)
    write(path,record);print(dict(phase=record['phase'],operation=record.get('operation')),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['prepare','capture-seed','finish-prepare','fault','restore','resume','prove','advance'])
    parser.add_argument('--candidate',type=Path);args=parser.parse_args();main(args.phase,args.candidate)
