"""Native BX-03 service adapter and managed producer qualification."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from background_site import Catalog,configuration,load,write,ROOT
from background_workers import Probe,docker,wait
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.release_staging import StageStore,prepare_staged_plan


PROVISION="""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib,json
from odoo import api
from odoo.addons.mp_identity.scopes import resolve_scope
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core import recurrence_dispatch as recurring
from modular_platform.recurrence import RecurrenceRule
assert env.cr.dbname==EXPECTED_DB
release=current_release(env)
installation=env['mp.plugin.installation'].search([('plugin_id','=','org.example.background')])
assert len(installation)==1
result={}
group_field='group_ids' if 'group_ids' in env['res.users']._fields else 'groups_id'
for label in ('A','B'):
    workspace=FIXTURE['workspaces'][label]
    user=env['res.users'].with_context(no_reset_password=True,mail_create_nosubscribe=True,tracking_disable=True).create(
        dict(name='BX-03 native service '+label,login='bx03-service-'+label.lower(),active=True,
             **{group_field:[(6,0,[env.ref('base.group_user').id])]}))
    principal=env['mp.principal'].create(dict(name='BX-03 scoped service '+label,user_id=user.id,kind='service'))
    env['mp.membership'].create(dict(principal_id=principal.id,workspace_id=workspace['id'],role='viewer'))
    credential=env['mp.service.credential'].create(dict(name='BX-03 fictional credential '+label,
        principal_id=principal.id,workspace_id=workspace['id'],installation_public_id=installation.public_id,
        token_digest=hashlib.sha256(('fictional bx03 '+label).encode()).hexdigest(),audience='mp-host-v1',
        actions='read',expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).replace(tzinfo=None)))
    actor=api.Environment(env.cr,user.id,{})
    scope=resolve_scope(actor,workspace['public_id'])
    scope=resolve_scope(actor,workspace['public_id'],previous=replace(scope,credential_id=credential.id,allowed_actions=frozenset({'read'})))
    actor=actor(context={'_mp_scope':scope,'_mp_call_frame':CallFrame(principal.public_id,workspace['public_id'],
        release['site_id'],installation.public_id,'org.example.background',())})
    rule=RecurrenceRule(datetime.now(timezone.utc).replace(microsecond=0),60,3600,5)
    schedule=recurring.create_schedule(actor,'jobs','org.example.background:report',dict(first=1,last=1),
        'reference',rule=rule,version=2)
    assert recurring.create_schedule(actor,'jobs','org.example.background:report',dict(first=1,last=1),
        'reference',rule=rule,version=2)==schedule
    revision=recurring.pause_schedule(actor,schedule,1)
    assert revision==2
    result[label]=dict(user_id=user.id,principal_id=principal.id,principal_public_id=principal.public_id,
        credential_id=credential.id,workspace_id=workspace['id'],workspace_public_id=workspace['public_id'],
        installation_id=installation.id,installation_public_id=installation.public_id,schedule=schedule,revision=revision,rule=rule.wire())
env.cr.commit()
print('BX03_RESULT='+json.dumps(result))
"""


API_PROBE="""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib,json,time
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError,MissingError,ValidationError
from odoo.addons.mp_identity.scopes import resolve_scope,scoped_environment
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core import recurrence_dispatch as recurring
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import durable
from modular_platform.recurrence import RecurrenceRule
from modular_platform.job_runner import run_once
assert env.cr.dbname==EXPECTED_DB
release=current_release(env);checks={}
def actor(label,credential=None):
    row=SERVICES[label]
    native=api.Environment(env.cr,row['user_id'],{})
    scope=resolve_scope(native,row['workspace_public_id'])
    scope=resolve_scope(native,row['workspace_public_id'],previous=replace(scope,
        credential_id=credential or row['credential_id'],allowed_actions=frozenset({'read'})))
    return native(context={'_mp_scope':scope,'_mp_call_frame':CallFrame(row['principal_public_id'],row['workspace_public_id'],
        release['site_id'],row['installation_public_id'],'org.example.background',())})
def row(ident):
    env.cr.execute('SELECT to_jsonb(s) FROM mp_job_schedule s WHERE public_id=%s',[ident]);return env.cr.fetchone()[0]
def job(ident):
    with env.registry.cursor() as cr:
        cr.execute('SELECT state,error_code,payload FROM mp_job WHERE public_id=%s',[ident]);return cr.fetchone()
def denied(fn):
    try:
        with env.cr.savepoint():fn()
    except (AccessError,MissingError,ValidationError,PublicError,durable.QueueError):return
    raise AssertionError('Expected current native authority or revision denial')
def finish(ident):
    env.cr.commit()
    for _ in range(20):
        current=job(ident)
        if current[0] in ('completed','dead_letter','cancelled'):return current
        run_once(env.registry,str(uuid4()),pool='bulk')
    raise AssertionError('Reference one-off job did not reach terminal state')
if CASE_KEY is not None:
    for label in ('A','B'):
        current=actor(label)
        case_rule=RecurrenceRule(datetime.now(timezone.utc).replace(microsecond=0),60,3600,5)
        schedule=recurring.create_schedule(current,'jobs','org.example.background:report',{'first':1,'last':1},CASE_KEY,rule=case_rule,version=2)
        revision=recurring.pause_schedule(current,schedule,1)
        SERVICES[label]=dict(SERVICES[label],schedule=schedule,revision=revision,rule=case_rule.wire())
    env.cr.commit()
    print('BX03_PROGRESS='+json.dumps(dict(phase='fresh_case_created',case=CASE_KEY)),flush=True)
a,b=actor('A'),actor('B');aid=SERVICES['A']['schedule'];bid=SERVICES['B']['schedule']
rule=RecurrenceRule.from_wire(SERVICES['A']['rule'])
human=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])['mp.background.task']._job_env()
denied(lambda:recurring.create_schedule(human,'jobs','org.example.background:report',{'first':1,'last':1},'human',rule=rule,version=2))
denied(lambda:recurring.create_schedule(api.Environment(env.cr,1,a.context),'jobs','org.example.background:report',{'first':1,'last':1},'admin',rule=rule,version=2))
denied(lambda:recurring.pause_schedule(b,aid,2))
checks.update(human_origin_denied=True,administrator_scope_substitution_denied=True,foreign_workspace_denied=True)
assert recurring.tick(env,aid)['outcome']=='paused'
version=recurring.resume_schedule(a,aid,2)
first=recurring.tick(env,aid)
assert first['outcome']=='emitted',first
assert recurring.tick(env,aid)['outcome']=='busy'
env.cr.execute('SELECT count(*) FROM mp_job_occurrence WHERE schedule_id=%s',[aid]);assert env.cr.fetchone()==(1,)
checks['one_outstanding_native_occurrence']=True
version=recurring.edit_schedule(a,aid,version,handler='org.example.background:report',values={'first':2,'last':2},rule=rule,version=2)
env.cr.execute('SELECT payload FROM mp_job WHERE public_id=%s',[first['job_id']]);assert env.cr.fetchone()[0]['input']=={'first':1,'last':1}
before=row(aid)
denied(lambda:recurring.edit_schedule(a,aid,version-1,handler='org.example.background:report',values={'first':3,'last':3},rule=rule,version=2))
denied(lambda:recurring.edit_schedule(a,aid,version,handler='org.example.background:report',values={'first':3,'last':3},rule=rule,version=999))
assert row(aid)==before
checks['edit_preserves_outstanding_input_and_rejects_stale_or_missing_versions']=True
env['mp.service.credential'].browse(SERVICES['A']['credential_id']).write({'state':'revoked'})
assert recurring.tick(env,aid)['outcome']=='held' and row(aid)['state']=='held'
env.cr.execute('SELECT state FROM mp_service_credential WHERE id=%s',[SERVICES['A']['credential_id']]);assert env.cr.fetchone()==('revoked',)
failed=finish(first['job_id'])
assert failed[:2]==('dead_letter','FORBIDDEN'),failed[:2]
with env.registry.cursor() as cr:
    cr.execute('SELECT state FROM mp_service_credential WHERE id=%s',[SERVICES['A']['credential_id']]);assert cr.fetchone()==('revoked',)
checks['revocation_holds_producer_and_refuses_saved_job_authority']=True
old=env['mp.service.credential'].browse(SERVICES['A']['credential_id'])
replacement=env['mp.service.credential'].create(dict(name='BX-03 rotated fictional credential',principal_id=old.principal_id.id,
    workspace_id=old.workspace_id.id,installation_public_id=old.installation_public_id,actions='read',audience='mp-host-v1',
    token_digest=hashlib.sha256(b'fictional bx03 rotated A').hexdigest(),expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).replace(tzinfo=None)))
renewed=actor('A',replacement.id)
denied(lambda:recurring.resume_schedule(renewed,aid,version))
assert row(aid)['state']=='held'
fast=replace(rule,interval_seconds=1)
version=recurring.edit_schedule(renewed,aid,version,handler='org.example.background:report',values={'first':2,'last':2},rule=fast,version=2)
assert row(aid)['state']=='held' and row(aid)['outstanding_job_id']==first['job_id']
version=recurring.resume_schedule(renewed,aid,version)
time.sleep(1.1)
second=recurring.tick(env,aid)
assert second['outcome']=='emitted' and second['job_id']!=first['job_id'],second
assert finish(second['job_id'])[0]=='completed'
env.cr.execute('SELECT count(*),count(DISTINCT nominal_at) FROM mp_job_occurrence WHERE schedule_id=%s',[aid]);assert env.cr.fetchone()==(2,2)
checks['credential_rotation_requires_edit_resume_and_preserves_schedule_occurrences']=True
version=recurring.pause_schedule(renewed,aid,version)
bversion=recurring.resume_schedule(b,bid,SERVICES['B']['revision'])
bjob=recurring.tick(env,bid);assert bjob['outcome']=='emitted'
membership=env['mp.membership'].search([('principal_id','=',SERVICES['B']['principal_id']),('workspace_id','=',SERVICES['B']['workspace_id'])])
membership.write({'state':'revoked'})
assert recurring.tick(env,bid)['outcome']=='held'
assert finish(bjob['job_id'])[:2]==('dead_letter','FORBIDDEN')
membership.write({'state':'active'})
assert row(bid)['state']=='held'
checks['membership_repair_does_not_automatically_resume_schedule']=True
expiry_rule=RecurrenceRule(datetime.now(timezone.utc).replace(microsecond=0),60,3600,5)
expired=recurring.create_schedule(renewed,'jobs','org.example.background:report',{'first':1,'last':1},'expired',rule=expiry_rule,version=2)
original_expiry=replacement.expires_at
replacement.write({'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=2)).replace(tzinfo=None)})
assert recurring.tick(env,expired)['outcome']=='held'
replacement.write({'expires_at':original_expiry})
assert row(expired)['state']=='held'
checks['expired_credential_holds_without_auto_resume']=True
env.cr.commit()
print('BX03_RESULT='+json.dumps(dict(checks=checks,A=dict(SERVICES['A'],credential_id=replacement.id,revision=version),
    B=dict(SERVICES['B'],revision=bversion),first_job=first['job_id'],second_job=second['job_id'],expiry_schedule=expired)))
"""


class RecurrenceProbe(Probe):
    def __init__(self):
        site_state=load(ROOT/'.local/background-qualification/bx-03-recurrence-01/state.json')
        super().__init__('bx-03-recurrence-01',extra_phase=site_state['phase'] if site_state['phase'].startswith('bx03-') else None)
        self.state['phase']='bg02_probed'

    def shell(self,tag,source):
        prefix='EXPECTED_DB='+repr(self.state['database'])+'\nFIXTURE='+repr(self.fixture)+'\n'
        raw=self.site.native(dict(self.state),'bx03-'+tag,[],prefix+source).decode()
        write(self.site.local/'state.json',self.state)
        rows=[json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BX03_RESULT=')]
        assert len(rows)==1
        return rows[0]

    def upgrade(self,candidate,attempt):
        path=self.site.local/f'bx03-native-upgrade-{attempt:02d}.json'
        assert not path.exists(),'Inspect recorded operation before retrying'
        target=self.site.private/'target.json'
        catalog_path=self.site.private/'catalog'
        validator=configuration(self.site.private/'trust.json')
        catalog=Catalog(catalog_path,validator,readonly=True)
        store=self.operator.store
        observer=DockerObserver(self.target)
        observed=observer.read();before=observer.state(observed,catalog.snapshot())
        stages=StageStore(store,self.target,catalog)
        descriptor=stages.stage(load(candidate)['image_id']);_,staged=stages.load(descriptor)
        targets=[{key:row[key] for key in ('installation_id','site_id','workspace_id','plugin_id')}|{'action':'deploy'}
                 for row in before['state']['installations']]
        operation=str(uuid4())
        bundle=prepare_staged_plan(before,observed['sites'],catalog.snapshot(),staged['runtime'],descriptor,
            targets=targets,operation_type='core_upgrade',operation_id=operation,
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=observed['runtime'])
        executor=StagedNativeExecutor(store,target,catalog_path,validator)
        validate=executor._validate()
        store.register(bundle,validate)
        store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
            acknowledgments={'destructive':True,'trust_expansion':True,'permission_expansion':False})
        write(path,dict(operation=operation,phase='applying',image=load(candidate)['image_id']))
        result=executor.apply(operation)
        assert result['state']=='completed' and result['traffic_resumed']
        write(path,dict(operation=operation,phase='passed',image=load(candidate)['image_id'],result=result))
        print(json.dumps(dict(phase='upgraded',operation=operation)),flush=True)

    def provision(self):
        path=self.site.local/'bx03-services.json'
        assert not path.exists()
        result=self.shell('provision',PROVISION)
        write(path,result)
        print(json.dumps(dict(phase='scoped_services_provisioned',schedules=2,creation_retries_stable=True)),flush=True)

    def api(self,attempt):
        path=self.site.local/f'bx03-api-{attempt:02d}.json'
        assert not path.exists()
        services=load(self.site.local/'bx03-services.json')
        result=self.shell(f'api-{attempt:02d}','SERVICES='+repr(services)+'\nCASE_KEY='+repr(f'api-{attempt:02d}')+'\n'+API_PROBE)
        write(path,result)
        print(json.dumps(dict(phase='native_api_passed',checks=len(result['checks']))),flush=True)

    def roles(self,attempt):
        path=self.site.local/'bx03-roles.json'
        assert not path.exists()
        case=load(self.site.local/f'bx03-api-{attempt:02d}.json')
        services={key:case[key] for key in ('A','B')}
        review=self.operator.run('profile-review',urgent_lanes=1,bulk_lanes=1,producer_lanes=1)
        record=dict(phase='starting',approval=review['approval'])
        write(path,record)
        status=self.operator.run('profile-apply',approval=review['approval'])
        assert status['state']=='ready',status
        assert all(status['pools'][pool]['ready']==1 for pool in ('urgent','bulk','producer'))
        record.update(phase='ready',status=status)
        write(path,record)
        actor_source='SERVICES='+repr(services)+'\n'+API_PROBE.split('def row(',1)[0]
        baseline=int(self.sql("SELECT count(*) FROM mp_job_occurrence WHERE schedule_id='"+services['A']['schedule']+"'"))
        active=self.shell('producer-activate',actor_source+"""
env.cr.execute('SELECT config_version,state FROM mp_job_schedule WHERE public_id=%s',[SERVICES['A']['schedule']])
revision,state=env.cr.fetchone();assert state=='paused'
revision=recurring.resume_schedule(actor('A'),SERVICES['A']['schedule'],revision)
env.cr.commit()
print('BX03_RESULT='+json.dumps(dict(revision=revision)))
""")
        schedule=services['A']['schedule']
        samples=[]
        def progressed():
            value=json.loads(self.sql("""SELECT jsonb_build_object('receipts',count(*),'distinct',count(DISTINCT o.nominal_at),
                'completed',count(*) FILTER (WHERE j.state='completed'),
                'unfinished',count(*) FILTER (WHERE j.state IN ('pending','running','retry','held','outcome_unknown')))
                FROM mp_job_occurrence o JOIN mp_job j ON j.public_id=o.job_public_id WHERE o.schedule_id='"""+schedule+"'") )
            samples.append(value)
            assert value['unfinished']<=1 and value['receipts']==value['distinct'],value
            return value if value['completed']>=baseline+2 else None
        measured=wait(progressed,40)
        producer=self.project+'-job-producer-1'
        before=json.loads(docker('inspect',producer))[0]
        restart=self.kill(producer)
        record.update(phase='restart_requested',restart=restart,measured=measured,baseline=baseline,activation=active,samples=samples,
                      restart_before=dict(started_at=before['State']['StartedAt'],restart_count=before['RestartCount']))
        write(path,record)
        def healthy():
            row=json.loads(docker('inspect',producer))[0]
            return row if row['State']['Running'] and row['State'].get('Health',{}).get('Status')=='healthy' and row['State']['StartedAt']!=before['State']['StartedAt'] else None
        restarted=wait(healthy,40)
        count=measured['completed']
        def after_restart():
            value=progressed()
            return value if value and value['completed']>count else None
        recovered=wait(after_restart,40)
        paused=self.shell('producer-pause',actor_source+"""
env.cr.execute('SELECT config_version FROM mp_job_schedule WHERE public_id=%s',[SERVICES['A']['schedule']])
revision,=env.cr.fetchone()
revision=recurring.pause_schedule(actor('A'),SERVICES['A']['schedule'],revision)
env.cr.commit()
print('BX03_RESULT='+json.dumps(dict(revision=revision)))
""")
        count_before=int(self.sql("SELECT count(*) FROM mp_job_occurrence WHERE schedule_id='"+schedule+"'"))
        time.sleep(2)
        assert int(self.sql("SELECT count(*) FROM mp_job_occurrence WHERE schedule_id='"+schedule+"'"))==count_before
        drained=self.operator.run('drain')
        assert drained['state']=='paused' and not self.operator._lanes()
        record.update(phase='passed',baseline=baseline,activation=active,measured=measured,recovered=recovered,
            restart=restart,restart_count=restarted['RestartCount'],samples=samples,pause=paused,
            paused_receipt_count=count_before,drain=drained)
        write(path,record)
        print(json.dumps(dict(phase='producer_roles_passed',receipts=count_before,restart=restart,no_overlap=True,drained=True)),flush=True)

    def finish_roles(self,attempt):
        path=self.site.local/'bx03-roles.json'
        record=load(path)
        assert record['phase'] in {'ready','restart_requested'}
        case=load(self.site.local/f'bx03-api-{attempt:02d}.json');services={key:case[key] for key in ('A','B')}
        actor_source='SERVICES='+repr(services)+'\n'+API_PROBE.split('def row(',1)[0]
        producer=self.project+'-job-producer-1'
        before=json.loads(docker('inspect',producer))[0]
        original=next(row for row in record['status']['lanes'] if row['pool']=='producer')
        assert before['Id']==original['container'] and before['State']['Running'] and before['State']['Health']['Status']=='healthy'
        schedule=services['A']['schedule']
        count=int(self.sql("SELECT count(*) FROM mp_job_occurrence WHERE schedule_id='"+schedule+"'"))
        record.update(phase='child_crash_requested',manual_kill_recovered=dict(started_at=before['State']['StartedAt'],
            finished_at=before['State']['FinishedAt'],restart_count=before['RestartCount'],healthy=True),receipts_before_child_crash=count)
        write(path,record)
        docker('exec',producer,'/venv/bin/python','-c',
            "import json,os,signal; p=json.load(open('/tmp/mp-job-health.json')); assert p['pool']=='producer'; os.kill(p['pid'],signal.SIGKILL)")
        def recovered():
            row=json.loads(docker('inspect',producer))[0]
            return row if row['RestartCount']>before['RestartCount'] and row['State']['Running'] and row['State'].get('Health',{}).get('Status')=='healthy' else None
        after=wait(recovered,40)
        def advanced():
            value=json.loads(self.sql("""SELECT jsonb_build_object('receipts',count(*),'distinct',count(DISTINCT o.nominal_at),
                'unfinished',count(*) FILTER (WHERE j.state IN ('pending','running','retry','held','outcome_unknown')))
                FROM mp_job_occurrence o JOIN mp_job j ON j.public_id=o.job_public_id WHERE o.schedule_id='"""+schedule+"'"))
            assert value['receipts']==value['distinct'] and value['unfinished']<=1,value
            return value if value['receipts']>count else None
        observed=wait(advanced,30)
        paused=self.shell('producer-recovered-pause',actor_source+"""
env.cr.execute('SELECT config_version FROM mp_job_schedule WHERE public_id=%s',[SERVICES['A']['schedule']])
revision,=env.cr.fetchone()
revision=recurring.pause_schedule(actor('A'),SERVICES['A']['schedule'],revision)
env.cr.commit()
print('BX03_RESULT='+json.dumps(dict(revision=revision)))
""")
        final=int(self.sql("SELECT count(*) FROM mp_job_occurrence WHERE schedule_id='"+schedule+"'"))
        time.sleep(2)
        assert int(self.sql("SELECT count(*) FROM mp_job_occurrence WHERE schedule_id='"+schedule+"'"))==final
        drained=self.operator.run('drain')
        assert drained['state']=='paused' and not self.operator._lanes()
        record.update(phase='passed',automatic_child_restart=dict(restart_count=after['RestartCount'],started_at=after['State']['StartedAt']),
            after_restart=observed,pause=paused,paused_receipt_count=final,drain=drained,
            initial_diagnostic='Manual Docker kill used explicit start; requiring RestartCount growth incorrectly timed out despite healthy recovery.')
        write(path,record)
        print(json.dumps(dict(phase='producer_roles_passed',receipts=final,automatic_child_restart=True,no_overlap=True,drained=True)),flush=True)

    def drain_roles(self,attempt):
        path=self.site.local/'bx03-roles.json';record=load(path)
        assert record['phase']=='child_crash_requested'
        case=load(self.site.local/f'bx03-api-{attempt:02d}.json');services={key:case[key] for key in ('A','B')}
        producer=self.project+'-job-producer-1'
        observed=json.loads(docker('inspect',producer))[0]
        original=next(row for row in record['status']['lanes'] if row['pool']=='producer')
        assert observed['Id']==original['container'] and observed['RestartCount']>=1 and observed['State']['Health']['Status']=='healthy'
        actor_source='SERVICES='+repr(services)+'\n'+API_PROBE.split('def row(',1)[0]
        paused=self.shell('producer-final-pause',actor_source+"""
from odoo.service.model import retrying
current=actor('A')
def pause():
    env.cr.execute('SELECT config_version FROM mp_job_schedule WHERE public_id=%s',[SERVICES['A']['schedule']])
    revision,=env.cr.fetchone()
    return recurring.pause_schedule(current,SERVICES['A']['schedule'],revision)
revision=retrying(pause,current)
print('BX03_RESULT='+json.dumps(dict(revision=revision)))
""")
        schedule=services['A']['schedule']
        sql="""SELECT jsonb_build_object('receipts',count(*),'distinct',count(DISTINCT o.nominal_at),
            'unfinished',count(*) FILTER (WHERE j.state IN ('pending','running','retry','held','outcome_unknown')))
            FROM mp_job_occurrence o JOIN mp_job j ON j.public_id=o.job_public_id WHERE o.schedule_id='"""+schedule+"'"
        final=json.loads(self.sql(sql));assert final['receipts']==final['distinct'] and final['unfinished']<=1
        time.sleep(2)
        assert json.loads(self.sql(sql))['receipts']==final['receipts']
        drained=self.operator.run('drain');assert drained['state']=='paused' and not self.operator._lanes()
        record.update(phase='passed',automatic_child_restart=dict(restart_count=observed['RestartCount'],started_at=observed['State']['StartedAt']),
            final=final,pause=paused,drain=drained,
            diagnostics=['Manual Docker kill recovered by explicit start; RestartCount assumption was invalid.',
                         'Pause fixture evaluated actor initialization before fetching its SQL result; fetching first fixed the harness.'])
        write(path,record)
        print(json.dumps(dict(phase='producer_roles_passed',receipts=final['receipts'],automatic_child_restart=True,no_overlap=True,drained=True)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['upgrade','provision','api','roles','finish-roles','drain-roles'])
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--attempt',type=int,default=2)
    args=parser.parse_args()
    probe=RecurrenceProbe()
    if args.action=='upgrade':probe.upgrade(args.candidate,args.attempt)
    elif args.action=='api':probe.api(args.attempt)
    elif args.action=='roles':probe.roles(args.attempt)
    elif args.action=='finish-roles':probe.finish_roles(args.attempt)
    elif args.action=='drain-roles':probe.drain_roles(args.attempt)
    else:getattr(probe,args.action)()
