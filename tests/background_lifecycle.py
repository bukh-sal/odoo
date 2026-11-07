"""Exercise populated background queues through the approved release lifecycle."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

from background_workers import Probe
from background_site import assemble,Catalog,configuration,load,ROOT,write
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore,prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor


PLUGIN='org.example.background'
SEED="""
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform import durable
from uuid import uuid4
assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),
                          FIXTURE['workspaces']['A']['public_id'])
env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']])
assignee=env.cr.fetchone()[0]
future=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(minutes=20)
task=actor['mp.background.task'].create(dict(name='Populated upgrade fixture',
    assignee_id=assignee,due_at=future.replace(tzinfo=None)))
reminder=task._queue_current()
now=datetime.now(timezone.utc)
def report(when):
    return enqueue_scheduled(task._job_env(),'jobs','org.example.background:report',dict(first=1,last=500),
        str(uuid4()),version=REPORT_VERSION,schedule=durable.JobSchedule(when,when+timedelta(seconds=180),20))
retired=report(future)
running=report(now)
release=current_release(env)
old=durable.claim(env.cr,release['site_id'],release['release_digest'],str(uuid4()),
                  ['org.example.background:report'],lease_seconds=30)
assert old.job_id==running
env.cr.commit()
print('BG_LIFECYCLE='+json.dumps(dict(reminder=reminder,retired=retired,running=running,
    owner=old.owner,generation=old.generation)))
"""


def queue(probe, seed):
    ids=','.join("'"+seed[key]+"'" for key in ('reminder','retired','running'))
    return json.loads(probe.sql(f"""SELECT jsonb_object_agg(public_id,jsonb_build_object(
        'state',state,'at',available_at,'deadline',deadline_at,'actor',actor_id,'workspace',workspace_id,
        'generation',claim_generation,'attempts',attempts,'error',error_code))
        FROM mp_job WHERE public_id IN ({ids})"""))


def shell(probe,label,code):
    result=probe.site.native(dict(probe.state),label,[],code)
    write(probe.site.local/'state.json',probe.state)
    return result.decode()


def seed_jobs(probe, *, report_version=1):
    raw=shell(probe,'bg03-lifecycle-seed',f'import json\nFIXTURE={probe.fixture!r}\nREPORT_VERSION={report_version!r}\n'+SEED)
    value,=[json.loads(row.split('=',1)[1]) for row in raw.splitlines() if row.startswith('BG_LIFECYCLE=')]
    return value


def assert_stale(probe, seed, label):
    raw=shell(probe,label,f"""
from modular_platform import durable
old=durable.Claim({seed['running']!r},{seed['generation']!r},{seed['owner']!r})
try:durable.run_fenced(env.cr,old,lambda row:{{'unexpected':True}})
except (durable.ClaimLost,durable.DispatchPaused):print('BG_OLD_CLAIM_DENIED')
else:raise AssertionError('Old worker escaped its release fence')
""")
    assert 'BG_OLD_CLAIM_DENIED' in raw


def run(candidate_path, phase):
    probe=Probe('bg-03-01')
    assert not probe.operator._lanes()
    path=probe.site.local/'bg03-release-queue.json'
    if phase=='fault':
        assert not path.exists()
        seed=seed_jobs(probe)
        original=queue(probe,seed)
        record={'seed':seed,'original':original}
        write(path,record)
    else:
        record=load(path)
        assert record['phase']=='restored_and_resumed'
        seed,original=record['seed'],record['original']

    candidate=load(candidate_path)
    target_path=probe.site.private/'target.json'
    base=load(target_path)
    trust_path=probe.site.private/'trust.json'
    catalog_path=probe.site.private/'catalog'
    digest=candidate['artifacts'][PLUGIN]['digest']
    trust=load(trust_path)
    if digest not in trust['approved_digests']:
        assert phase=='fault'
        _, payload,_=assemble(ROOT,'plugins/background/plugin.toml')
        assert 'sha256:'+hashlib.sha256(payload).hexdigest()==digest
        artifact=probe.site.private/candidate['artifacts'][PLUGIN]['file']
        with artifact.open('xb') as stream:
            stream.write(payload)
        trust['approved_digests'].append(digest)
        trust['generation']+=1
        write(trust_path,trust)
        Catalog(catalog_path,configuration(trust_path)).add(artifact,expected_digest=digest)
    validator=configuration(trust_path)
    catalog=Catalog(catalog_path,validator,readonly=True)
    store=OperatorStore(probe.site.private/'control')
    observer=DockerObserver(base)
    observed=observer.read()
    before=observer.state(observed,catalog.snapshot())
    stages=StageStore(store,base,catalog)
    descriptor=stages.stage(candidate['image_id'])
    _,staged=stages.load(descriptor)
    targets=[{key:row[key] for key in ('installation_id','site_id','workspace_id','plugin_id')}
             | {'action':'upgrade'} for row in before['state']['installations'] if row['plugin_id']==PLUGIN]
    operation=str(uuid4())
    bundle=prepare_staged_plan(before,observed['sites'],catalog.snapshot(),staged['runtime'],descriptor,
        targets=targets,operation_type='upgrade',operation_id=operation,
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=observed['runtime'])
    executor=StagedNativeExecutor(store,target_path,catalog_path,validator)
    validate=executor._validate()
    store.register(bundle,validate)
    review=store.review(operation,validate)
    approval=store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
        acknowledgments={'destructive':False,'trust_expansion':True,'permission_expansion':False})
    record[phase]=dict(operation=operation,review=data_digest(review),approval=data_digest(approval))
    record['phase']='applying_'+phase
    write(path,record)
    if phase=='fault':
        advance=store.advance
        def inject(selected,locks,state,**details):
            result=advance(selected,locks,state,**details)
            if selected==operation and state=='release_published':
                raise OperatorError('Background qualification fault after publish')
            return result
        with patch.object(store,'advance',side_effect=inject):
            try:
                executor.apply(operation)
            except OperatorError as error:
                assert 'Background qualification fault' in str(error),str(error)
            else:
                raise AssertionError('Injection did not run')
        failed=store.status(operation)
        assert failed['state']=='recovery_required' and not failed['traffic_resumed']
        record['phase']='recovery_required'
        write(path,record)
        recovery=RestoreExecutor(StagedNativeExecutor(store,target_path,catalog_path,validator))
        decision=recovery.prepare(operation)
        recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
        restored=load(target_path)
        assert restored['image_id']==base['image_id']
        assert restored['sites'][0]['database']!=base['sites'][0]['database']
        recovery=RestoreExecutor(StagedNativeExecutor(store,target_path,catalog_path,validator))
        resume=recovery.prepare_resume(operation)
        recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True)
        probe=Probe('bg-03-01')
        after=queue(probe,seed)
        assert after[seed['reminder']]['state']==after[seed['retired']]['state']=='pending'
        assert_stale(probe,seed,'bg03-restored-stale')
        record['fault'].update(restore_digest=data_digest(decision),resume_digest=data_digest(resume),
                               restored_to_new_db=True,stale_claim_denied=True)
        record['phase']='restored_and_resumed'
    else:
        result=executor.apply(operation)
        assert result['state']=='completed' and result['traffic_resumed']
        probe=Probe('bg-03-01')
        assert probe.target['image_id']==candidate['image_id']
        after=queue(probe,seed)
        assert after[seed['reminder']]['state']=='pending'
        assert after[seed['retired']]['state']==after[seed['running']]['state']=='held'
        assert after[seed['retired']]['error']=='DEPENDENCY_UNAVAILABLE'
        assert_stale(probe,seed,'bg03-successor-stale')
        record['successor'].update(stale_claim_denied=True,target_image=candidate['image_id'],
                                   compatible_pending=True,incompatible_held=2)
        record['phase']='passed'
    for key in ('reminder','retired'):
        assert {field:after[seed[key]][field] for field in ('at','deadline','actor','workspace')}=={
            field:original[seed[key]][field] for field in ('at','deadline','actor','workspace')}
    record[phase]['timing_and_scope_preserved']=True
    write(path,record)
    print(json.dumps(dict(phase=record['phase'])),flush=True)


def switch_core(candidate_path):
    """Replace the confirmed bootstrap-order failure with a reviewed core image."""
    probe=Probe('bg-03-01')
    assert not probe.operator._lanes()
    path=probe.site.local/'bg03-managed-core-switch.json'
    assert not path.exists()
    candidate=load(candidate_path)
    target_path=probe.site.private/'target.json'
    catalog_path=probe.site.private/'catalog'
    validator=configuration(probe.site.private/'trust.json')
    catalog=Catalog(catalog_path,validator,readonly=True)
    store=OperatorStore(probe.site.private/'control')
    observer=DockerObserver(probe.target)
    observed=observer.read()
    before=observer.state(observed,catalog.snapshot())
    stages=StageStore(store,probe.target,catalog)
    descriptor=stages.stage(candidate['image_id'])
    _,staged=stages.load(descriptor)
    targets=[{key:row[key] for key in ('installation_id','site_id','workspace_id','plugin_id')}
             | {'action':'deploy'} for row in before['state']['installations']]
    operation=str(uuid4())
    bundle=prepare_staged_plan(before,observed['sites'],catalog.snapshot(),staged['runtime'],descriptor,
        targets=targets,operation_type='core_upgrade',operation_id=operation,
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=observed['runtime'])
    executor=StagedNativeExecutor(store,target_path,catalog_path,validator)
    validate=executor._validate()
    store.register(bundle,validate)
    store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
        acknowledgments={'destructive':True,'trust_expansion':True,'permission_expansion':False})
    record=dict(operation=operation,phase='applying')
    write(path,record)
    result=executor.apply(operation)
    assert result['state']=='completed' and result['traffic_resumed']
    record.update(phase='passed',image=candidate['image_id'])
    write(path,record)
    print(json.dumps(record),flush=True)


if __name__=='__main__':
    if sys.argv[2]=='core':
        switch_core(Path(sys.argv[1]))
    else:
        run(Path(sys.argv[1]),sys.argv[2])
