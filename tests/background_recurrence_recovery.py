"""BX-03: controlled release failure, coordinated restore and explicit repair.

Each mutation has a persisted phase; do not replay a failed phase blindly.
Only the owned recurrence qualification fixture is supported.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from background_recurrence import API_PROBE, RecurrenceProbe
from background_retention_lifecycle import approved, fail_after_publish
from background_site import load, write
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor


def runtime(probe):
    from background_site import configuration
    return StagedNativeExecutor(probe.operator.store,probe.site.private/'target.json',
        probe.site.private/'catalog',configuration(probe.site.private/'trust.json'))


def actor_source(probe):
    case=load(probe.site.local/'bx03-api-02.json')
    services={key:case[key] for key in ('A','B')}
    return 'SERVICES='+repr(services)+'\n'+API_PROBE.split('def row(',1)[0]


def snapshot(probe,schedule):
    return json.loads(probe.sql("""SELECT jsonb_build_object('receipts',
        (SELECT jsonb_agg(to_jsonb(o) ORDER BY nominal_at) FROM mp_job_occurrence o WHERE schedule_id=s.public_id),
        'cursor',s.next_at,'considered',s.considered_at,'outstanding',s.outstanding_job_id,
        'revision',s.config_version,'state',s.state,'release',s.release_digest)
        FROM mp_job_schedule s WHERE s.public_id='"""+schedule+"'"))


def run(phase,candidate=None):
    probe=RecurrenceProbe()
    assert not probe.operator._lanes()
    path=probe.site.local/'bx03-recovery.json'
    record=load(path) if path.exists() else {}
    if phase=='prepare':
        assert not record
        pending=probe.shell('restore-pending',actor_source(probe)+"""
current=actor('A');aid=SERVICES['A']['schedule']
env.cr.execute('SELECT config_version,state FROM mp_job_schedule WHERE public_id=%s',[aid])
revision,state=env.cr.fetchone();assert state=='paused'
revision=recurring.resume_schedule(current,aid,revision)
emitted=recurring.tick(env,aid);assert emitted['outcome']=='emitted',emitted
revision=recurring.pause_schedule(current,aid,revision)
env.cr.commit()
env.cr.execute('SELECT state FROM mp_job WHERE public_id=%s',[emitted['job_id']]);assert env.cr.fetchone()==('pending',)
print('BX03_RESULT='+json.dumps(dict(schedule=aid,job=emitted['job_id'],revision=revision)))
""")
        record=dict(phase='prepared',seed=pending,before=snapshot(probe,pending['schedule']),original_target=probe.target)
    elif phase=='fault':
        assert record['phase']=='prepared'
        operation,native=approved(probe,load(candidate)['image_id'],'core_upgrade')
        record.update(operation=operation,candidate=load(candidate)['image_id'],phase='applying')
        write(path,record)
        fail_after_publish(operation,native)
        manifest=load(native.store.root/'checkpoints'/operation/'manifest.json')
        record.update(phase='recovery_required',checkpoint=manifest['dispatch_profile'],
            failed_status=native.store.status(operation))
    elif phase=='guard':
        assert record['phase']=='recovery_required'
        native=runtime(probe);executor=RestoreExecutor(native)
        baseline=executor.prepare(record['operation'])
        synthetic=str(uuid4());record.update(phase='guard_injecting',synthetic_job=synthetic)
        write(path,record)
        probe.sql("""INSERT INTO mp_job_occurrence(site_id,schedule_id,nominal_at,job_public_id,
            config_version,input_digest,release_digest,created_at)
            SELECT site_id,schedule_id,nominal_at+interval '366 days','"""+synthetic+"""',
            config_version,input_digest,release_digest,created_at FROM mp_job_occurrence
            WHERE schedule_id='"""+record['seed']['schedule']+"' ORDER BY nominal_at DESC LIMIT 1")
        try:
            executor.prepare(record['operation'])
        except OperatorError as error:
            assert 'occurrence history changed' in str(error),str(error)
            record['history_guard']=str(error)
        else:raise AssertionError('Changed source receipt must refuse restore')
        assert probe.sql("SELECT count(*) FROM pg_database WHERE datname='"+baseline['fresh_database']+"'")=='0'
        probe.sql("DELETE FROM mp_job_occurrence WHERE job_public_id='"+synthetic+"'")
        clean=executor.prepare(record['operation'])
        assert clean['source_dispatch']['tables']['mp_job_occurrence']==record['checkpoint']['tables']['mp_job_occurrence']
        record.update(phase='guard_passed',no_fresh_target_after_refusal=True)
    elif phase=='restore':
        assert record['phase']=='guard_passed'
        executor=RestoreExecutor(runtime(probe));decision=executor.prepare(record['operation'])
        write(probe.site.local/'bx03-restore-decision.json',decision)
        record.update(phase='restoring',restore_digest=data_digest(decision));write(path,record)
        result=executor.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
        assert result['state']=='restored_verified' and result['keep_traffic_closed']
        after=RecurrenceProbe();native=runtime(after)
        state=snapshot(after,record['seed']['schedule'])
        for key in ('receipts','cursor','considered','outstanding','revision'):
            assert state[key]==record['before'][key],(key,state[key],record['before'][key])
        assert state['state']=='held'
        assert after.sql("SELECT count(*) FROM mp_service_credential WHERE state='active'")=='0'
        assert after.row(record['seed']['job'])['state']=='held'
        assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
        assert after.sql('SELECT state FROM mp_dispatch_control')=='paused'
        assert after.state['database']!=record['original_target']['sites'][0]['database']
        record.update(phase='restored_closed',restored=state,result=result,restored_target=after.target)
    elif phase=='resume':
        assert record['phase']=='restored_closed'
        executor=RestoreExecutor(runtime(probe));decision=executor.prepare_resume(record['operation'])
        write(probe.site.local/'bx03-resume-decision.json',decision)
        record.update(phase='resuming',resume_digest=data_digest(decision));write(path,record)
        result=executor.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        assert probe.sql('SELECT state FROM mp_dispatch_control')=='enabled'
        assert probe.sql("SELECT count(*) FROM mp_service_credential WHERE state='active'")=='0'
        record.update(phase='resumed',resume_result=result)
    elif phase=='repair':
        assert record['phase']=='resumed'
        source=actor_source(probe)+"""
def denied(fn):
    try:
        with env.cr.savepoint():fn()
    except (AccessError,MissingError,ValidationError,PublicError,durable.QueueError):return
    raise AssertionError('Expected revoked or foreign authority denial')
aid=SERVICES['A']['schedule']
denied(lambda:actor('A'))
denied(lambda:actor('B'))
old=env['mp.service.credential'].browse(SERVICES['A']['credential_id'])
replacement=env['mp.service.credential'].create(dict(name='BX-03 restored fictional credential',principal_id=old.principal_id.id,
    workspace_id=old.workspace_id.id,installation_public_id=old.installation_public_id,actions='read',audience='mp-host-v1',
    token_digest=hashlib.sha256(b'fictional bx03 restored A').hexdigest(),expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).replace(tzinfo=None)))
current=actor('A',replacement.id)
env.cr.execute('SELECT to_jsonb(s) FROM mp_job_schedule s WHERE public_id=%s',[aid]);row=env.cr.fetchone()[0]
assert row['state']=='held'
denied(lambda:recurring.resume_schedule(current,aid,row['config_version']))
revision=recurring.edit_schedule(current,aid,row['config_version'],handler=row['handler'],values=row['payload']['input'],
    rule=RecurrenceRule.from_wire(row['rule']),version=row['handler_version'])
env.cr.execute('SELECT state,outstanding_job_id FROM mp_job_schedule WHERE public_id=%s',[aid]);assert env.cr.fetchone()==('held',OLD_JOB)
assert recurring.cancel_outstanding(current,aid,revision)
env.cr.execute('SELECT state FROM mp_job WHERE public_id=%s',[OLD_JOB]);assert env.cr.fetchone()==('cancelled',)
revision=recurring.resume_schedule(current,aid,revision)
env.cr.commit();time.sleep(1.1)
emitted=recurring.tick(env,aid);assert emitted['outcome']=='emitted',emitted
assert emitted['job_id']!=OLD_JOB
env.cr.commit()
for _ in range(20):
    run_once(env.registry,str(uuid4()),pool='bulk')
    with env.registry.cursor() as cr:
        cr.execute('SELECT state FROM mp_job WHERE public_id=%s',[emitted['job_id']]);state,=cr.fetchone()
    if state=='completed':break
assert state=='completed',state
revision=recurring.pause_schedule(current,aid,revision);env.cr.commit()
env.cr.execute('SELECT count(*),count(DISTINCT nominal_at) FROM mp_job_occurrence WHERE schedule_id=%s',[aid])
count,distinct=env.cr.fetchone();assert count==distinct
print('BX03_RESULT='+json.dumps(dict(new_credential=replacement.id,old_job_cancelled=True,
    new_job=emitted['job_id'],receipts=count,distinct=distinct,revision=revision,old_authority_denied=True,
    explicit_edit_resume_required=True)))
"""
        record.update(phase='repairing');write(path,record)
        repaired=probe.shell('restore-repair','OLD_JOB='+repr(record['seed']['job'])+'\n'+source)
        final=snapshot(probe,record['seed']['schedule'])
        assert final['receipts'][:-1]==record['before']['receipts']
        assert len(final['receipts'])==len(record['before']['receipts'])+1
        record.update(phase='passed',repair=repaired,final=final)
    elif phase=='adopt':
        assert record['phase']=='passed' and 'profile_adoption' not in record
        old=load(probe.site.local/'bx03-roles.json')['approval']
        try:probe.operator.run('profile-apply',approval=old)
        except OperatorError as error:stale=str(error)
        else:raise AssertionError('Old target profile must not start restored roles')
        assert not probe.operator._lanes()
        review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=1,producer_lanes=1,paused=True)
        result=probe.operator.run('profile-apply',approval=review['approval'])
        assert result['state']=='paused' and not probe.operator._lanes()
        record['profile_adoption']=dict(stale_profile_denied=stale,new_approval=review['approval'],result=result)
    else:raise ValueError(phase)
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],operation=record.get('operation'))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','fault','guard','restore','resume','repair','adopt'])
    parser.add_argument('--candidate',type=Path)
    args=parser.parse_args();run(args.phase,args.candidate)
