"""Phase-recorded populated chunk upgrade failure, fresh restore and resume."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from background_chunks import BASIC,upgrade
from background_chunks_process import VERIFY
from background_site import configuration,load,write
from background_sustained import native
from background_workers import Probe,wait
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor


def runtime(probe):
    return StagedNativeExecutor(probe.operator.store,probe.site.private/'target.json',probe.site.private/'catalog',
        configuration(probe.site.private/'trust.json'))


def tables(probe):
    return {table:probe.sql("SELECT md5(string_agg(md5(to_jsonb(r)::text),'' ORDER BY id)) FROM "+table+' r')
        for table in ('mp_background_task','mp_background_report','mp_example_note')}


def main(phase,candidate):
    probe=Probe('bx-05-chunks-01');path=probe.site.local/'bx05-recovery.json'
    record=load(path) if path.exists() else {}
    prefix=BASIC.split("model=actor('alice','A');other=actor('bob','B')",1)[0]
    if phase=='prepare':
        assert not record and not probe.operator._lanes()
        assert load(probe.site.local/'bx05-cancel.json')['phase']=='passed'
        fixture=load(probe.site.local/'bx05-atomicity.json')['result']
        record=dict(phase='starting',original_target=probe.target);write(path,record)
        review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
        assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='ready'
        seed=native(probe,'bx05-recovery-start',prefix+"""
model=actor('alice','A');ident=model._start_report(FIRST,LAST,'bx05-recovery');env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(run=ident)))
""",FIRST=fixture['big_first'],LAST=fixture['big_last'])
        ident=seed['run'];record.update(phase='running',run=ident,old_profile=review['approval']);write(path,record)
        def progressed():
            cursor=int(probe.sql("SELECT cursor FROM mp_background_report WHERE public_id='"+ident+"'"))
            return cursor if 200<=cursor<4000 else None
        wait(progressed,30)
        drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
        prepared=native(probe,'bx05-recovery-claim',prefix+"""
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform.job_runner import _claim_guard
from odoo.service.model import retrying
model=actor('alice','A');row=model._report_row(RUN)
assert row['state']=='running' and 200<=row['cursor']<4500
env.cr.commit()
with env.registry.cursor() as cr:
    with _claim_guard(cr,'bulk',FIXTURE['workspaces']['A']['id']) as allowed:
        assert allowed
        metadata=api.Environment(cr,1,{})
        invocation=retrying(lambda:jobs.prepare_one(metadata,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['A']['id']),metadata)
        assert invocation.claim.job_id==row['job_public_id']
claim=invocation.claim
env.cr.rollback();env.invalidate_all();row=model._report_row(RUN);env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(row=row,claim=dict(job_id=claim.job_id,generation=claim.generation,owner=claim.owner))))
""",RUN=ident)
        record.update(phase='prepared',seed=prepared,before=tables(probe),drain=drained)
    elif phase=='fault':
        assert record['phase']=='prepared' and not probe.operator._lanes()
        record.update(phase='applying',candidate=str(candidate));write(path,record)
        result=upgrade(probe,candidate,fault=True)
        assert result['phase']=='recovery_required' and not result['status']['traffic_resumed']
        record.update(phase='recovery_required',fault=result,operation=result['operation'])
    elif phase=='restore':
        assert record['phase']=='recovery_required' and not probe.operator._lanes()
        executor=RestoreExecutor(runtime(probe));decision=executor.prepare(record['operation'])
        record.update(phase='restoring',restore_digest=data_digest(decision));write(path,record)
        result=executor.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
        assert result['state']=='restored_verified' and result['keep_traffic_closed']
        after=Probe('bx-05-chunks-01')
        assert after.state['database']!=record['original_target']['sites'][0]['database']
        assert after.target['image_id']==record['original_target']['image_id']
        assert tables(after)==record['before']
        assert after.sql('SELECT state FROM mp_dispatch_control')=='paused'
        assert after.sql("SELECT count(*) FROM mp_service_credential WHERE state='active'")=='0'
        state=after.row(record['seed']['claim']['job_id'])
        assert state['state']=='pending' and state['owner'] is None and state['generation']>record['seed']['claim']['generation']
        executor_native=runtime(after)
        assert not executor_native._inspect(executor_native.observer._container('edge',stopped=True))['State']['Running']
        record.update(phase='restored_closed',result=result,restored_target=after.target,restored_tables=tables(after))
    elif phase=='resume':
        assert record['phase']=='restored_closed'
        executor=RestoreExecutor(runtime(probe));decision=executor.prepare_resume(record['operation'])
        record.update(phase='resuming',resume_digest=data_digest(decision));write(path,record)
        result=executor.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        assert probe.sql('SELECT state FROM mp_dispatch_control')=='enabled'
        record.update(phase='resumed',resume_result=result)
    elif phase=='prove':
        assert record['phase']=='resumed' and not probe.operator._lanes()
        fenced=native(probe,'bx05-restored-fence',prefix+"""
from modular_platform import durable
model=actor('alice','A');row=model._report_row(RUN)
for key in ('cursor','points','total','snapshot','snapshot_digest','result_digest'):
    assert row[key]==SAVED[key],key
try:durable.run_fenced(env.cr,durable.Claim(**OLD),lambda row:(_ for _ in ()).throw(AssertionError('Old apply entered')))
except durable.ClaimLost:env.cr.rollback()
else:raise AssertionError('Old claim survived restore')
print('BX04_RESULT='+json.dumps(dict(old_claim_denied=True,saved_cursor=SAVED['cursor'])))
""",RUN=record['run'],SAVED=record['seed']['row'],OLD=record['seed']['claim'])
        try:probe.operator.run('profile-apply',approval=record['old_profile'])
        except OperatorError as error:stale=str(error)
        else:raise AssertionError('Old profile survived fresh database')
        review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
        record.update(phase='continuing',fence=fenced,stale_profile=stale,new_profile=review['approval']);write(path,record)
        assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='ready'
        wait(lambda:probe.sql("SELECT state FROM mp_background_report WHERE public_id='"+record['run']+"'")=='completed',150)
        verified=native(probe,'bx05-recovery-verify',prefix+VERIFY,RUN=record['run'])
        drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
        record.update(phase='passed',verified=verified,final_drain=drained)
    elif phase=='advance':
        assert record['phase']=='passed' and not probe.operator._lanes()
        record.update(phase='advancing');write(path,record)
        result=upgrade(probe,Path(record['candidate']),attempt=2)
        assert result['phase']=='passed'
        after=Probe('bx-05-chunks-01')
        assert after.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_example_background'")=='19.0.0.3.3'
        record.update(phase='qualified',successful_upgrade=result)
    else:raise ValueError(phase)
    write(path,record);print(dict(phase=record['phase'],operation=record.get('operation')),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['prepare','fault','restore','resume','prove','advance'])
    parser.add_argument('--candidate',type=Path);args=parser.parse_args();main(args.phase,args.candidate)
