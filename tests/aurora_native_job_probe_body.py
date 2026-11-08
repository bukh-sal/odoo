"""Executed once by the disposable AT-01 native shell, never in a live site."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tomllib
from uuid import uuid4

from odoo import api, Command, fields
from odoo.exceptions import AccessError
from odoo.addons.mp_core import job_dispatch as jobs, native_jobs
from modular_platform import durable

PLUGIN='dev.aurora.tasks'
HANDLER=PLUGIN+':reminder-probe'
cr=env.cr
results={}
site=str(uuid4());release='sha256:'+'7'*64
inventory='sha256:'+hashlib.sha256(Path('/opt/modular/distribution-inventory.json').read_bytes()).hexdigest()
for key,value in {'mp.site_id':site,'mp.release_generation':'1','mp.release_digest':release,
                  'mp.active_inventory_digest':inventory}.items():
    env['ir.config_parameter'].set_param(key,value)
durable.set_control(cr,site,release,'enabled')
manifest=tomllib.loads(Path('/opt/modular/probe_plugin.toml').read_text())
installation=env['mp.plugin.installation'].create(dict(plugin_id=PLUGIN,version='0.1.0',
    runtime='native',artifact_digest='sha256:14f9af4bf48e0b8c38c3a3b31a2fb73b2d3f878e343bd9d96c78d759f93968d3',
    manifest=manifest,state='installed'))
group=env.ref('base.group_user')
owner,member,recipient,outsider=env['res.users'].with_context(no_reset_password=True).create([
    dict(name='AT native '+role,login='at.native.'+role,group_ids=[Command.set([group.id])])
    for role in ('owner','member','recipient','outsider')])
native=lambda user:api.Environment(cr,user.id,{},su=False)
owner_env=native(owner);member_env=native(member);recipient_env=native(recipient)
board=owner_env['mp.aurora.task.list'].create(dict(name='AT feasibility list',member_ids=[Command.link(member.id)]))
cr.execute('CREATE TABLE at_native_reminder_effect(task_id integer NOT NULL,recipient_id integer NOT NULL, occurrence text NOT NULL, UNIQUE(task_id,occurrence))')
env.flush_all();cr.commit()


@contextmanager
def denied():
    try:
        with cr.savepoint():yield
    except AccessError:return
    raise AssertionError('Expected a real native access denial')


def resource(actor,values,bound):
    assert not actor.su
    task=actor['mp.aurora.task'].browse(values['task']).exists()
    if not task:raise AccessError('Task missing')
    task.check_access('write')
    return task


def apply(actor,values,prepared,computed,bound):
    task=resource(actor,values,bound)
    cr.execute('SELECT id FROM mp_aurora_task WHERE id=%s FOR UPDATE',[task.id])
    task.invalidate_recordset(['name','assignee_id','active','stage_id'])
    if task.name!=values['expected'] or not task.active or task.stage_id.done or not task.assignee_id:
        return dict(outcome='obsolete')
    target=task.assignee_id
    cr.execute('SELECT id FROM res_users WHERE id=%s AND active AND NOT share FOR SHARE',[target.id])
    if not cr.fetchone():return dict(outcome='obsolete')
    task.with_user(target).check_access('read')
    cr.execute('INSERT INTO at_native_reminder_effect(task_id,recipient_id,occurrence) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
               [task.id,target.id,values['expected']])
    return dict(outcome='notified')


empty=dict(type='object',properties={},additionalProperties=False)
schema=dict(type='object',properties=dict(task=dict(type='integer',minimum=1),expected=dict(type='string',maxLength=100)),
            required=['task','expected'],additionalProperties=False)
jobs.register(jobs.JobDefinition(HANDLER,1,PLUGIN,'','','',schema,empty,empty,
    dict(type='object',properties=dict(outcome=dict(enum=['obsolete','notified'])),required=['outcome'],additionalProperties=False),
    resource,lambda actor,values,bound:{},lambda values,context:{},apply,
    pool='urgent',authority='native',addon='mp_aurora_tasks'))


def task(name,assignee=recipient):
    row=owner_env['mp.aurora.task'].create(dict(name=name,list_id=board.id,assignee_id=assignee.id))
    env.flush_all();cr.commit()
    return row


def submit(row,actor=owner_env):
    schedule=durable.JobSchedule(datetime.now(timezone.utc)-timedelta(seconds=1),
                                 datetime.now(timezone.utc)+timedelta(minutes=10),30)
    values=dict(task=row.id,expected=row.name)
    ident=native_jobs.enqueue_scheduled(actor,HANDLER,values,'task:'+str(row.id),schedule=schedule)
    env.flush_all();cr.commit()
    return ident,values,schedule


def prepare():
    key=durable.native_claim_guard_key(site,'urgent',installation.id)
    cr.execute('SELECT pg_advisory_lock(%s)',[key]);cr.commit()
    try:
        value=jobs.prepare_one(env,str(uuid4()),pool='urgent',native_installation_id=installation.id)
        env.flush_all();cr.commit()
        return value
    finally:
        cr.execute('SELECT pg_advisory_unlock(%s)',[key]);cr.commit()


def effect_count(row):
    cr.execute('SELECT count(*) FROM at_native_reminder_effect WHERE task_id=%s',[row.id])
    return cr.fetchone()[0]


def finish(invocation):
    result=jobs.finish_one(env,invocation,jobs.compute(invocation))
    env.flush_all();cr.commit()
    return result


positive=task('Native queued reminder')
ident,values,schedule=submit(positive)
assert native_jobs.enqueue_scheduled(owner_env,HANDLER,values,'task:'+str(positive.id),schedule=schedule)==ident
env.flush_all();cr.commit()
cr.execute('SELECT count(*) FROM mp_job WHERE public_id=%s AND workspace_id IS NULL',[ident]);assert cr.fetchone()[0]==1
assert durable.claim(cr,site,release,str(uuid4()),[HANDLER]) is None
cr.commit()
invocation=prepare();assert invocation.claim.job_id==ident
assert finish(invocation)==dict(outcome='notified')
assert effect_count(positive)==1
assert native_jobs.enqueue_scheduled(owner_env,HANDLER,values,'task:'+str(positive.id),schedule=schedule)==ident
env.flush_all();cr.commit()
assert prepare() is None
results['native_delivery_original_actor_no_workspace']=True
results['null_scope_dedup_before_and_after_completion']=True
results['legacy_workspace_claim_excludes_native']=True

with denied():native_jobs.enqueue_scheduled(native(outsider),HANDLER,values,'outsider',schedule=schedule)
cr.execute('SELECT count(*) FROM mp_principal WHERE user_id=%s',[outsider.id]);assert cr.fetchone()[0]==0
results['outsider_submission_denied_and_identity_rolled_back']=True

revoked=task('Revoked member reminder',assignee=owner)
revoked_job,_,_=submit(revoked,member_env)
pending=prepare();assert pending.claim.job_id==revoked_job
board.write({'member_ids':[Command.unlink(member.id)]});env.flush_all();cr.commit()
result=finish(pending)
assert result['state']=='dead_letter' and result['error_code']=='FORBIDDEN' and effect_count(revoked)==0
results['resource_revocation_between_prepare_and_apply']=True

actor_task=task('Suspended originating actor')
actor_job,_,_=submit(actor_task)
pending=prepare();assert pending.claim.job_id==actor_job
env['mp.principal'].search([('user_id','=',owner.id)]).write({'state':'suspended'})
env.flush_all();cr.commit()
result=finish(pending)
assert result['error_code']=='FORBIDDEN' and effect_count(actor_task)==0
env['mp.principal'].search([('user_id','=',owner.id)]).write({'state':'active'})
env.flush_all();cr.commit()
results['actor_revocation_between_prepare_and_apply']=True

stale=task('Stale occurrence')
stale_job,_,_=submit(stale)
pending=prepare();assert pending.claim.job_id==stale_job
stale.write({'name':'Replacement occurrence'});env.flush_all();cr.commit()
assert finish(pending)==dict(outcome='obsolete') and effect_count(stale)==0
results['stale_business_occurrence_suppressed']=True

cancelled=task('Cancelled occurrence')
cancel_job,_,_=submit(cancelled)
pending=prepare();assert pending.claim.job_id==cancel_job
cr.execute('SELECT actor_id FROM mp_job WHERE public_id=%s',[cancel_job]);actor_id=cr.fetchone()[0]
assert durable.cancel_scheduled(cr,cancel_job,actor_id=actor_id,workspace_id=None)
cr.commit()
try:finish(pending)
except durable.ClaimLost:cr.rollback()
else:raise AssertionError('Cancelled claim applied')
assert effect_count(cancelled)==0
results['scheduled_cancellation_fences_apply']=True

paused=task('Paused dispatch occurrence')
paused_job,_,_=submit(paused)
pending=prepare();assert pending.claim.job_id==paused_job
durable.set_control(cr,site,release,'paused');cr.commit()
try:finish(pending)
except durable.DispatchPaused:cr.rollback()
else:raise AssertionError('Paused dispatch applied')
assert effect_count(paused)==0
results['dispatch_pause_fences_native_apply']=True
durable.set_control(cr,site,release,'enabled');cr.commit()

cr.execute('SELECT count(*) FROM mp_workspace');assert cr.fetchone()[0]==0
cr.execute('SELECT count(*) FROM mp_membership');assert cr.fetchone()[0]==0
cr.execute('SELECT count(*) FROM mp_service_binding');assert cr.fetchone()[0]==0
assert durable.claim_guard_key(site,'urgent',installation.id)!=durable.native_claim_guard_key(site,'urgent',installation.id)
results['no_workspace_membership_or_service_binding_created']=True
results['distinct_workspace_native_claim_lock_keys']=True
cr.execute('SELECT count(*) FROM at_native_reminder_effect');assert cr.fetchone()[0]==1
results['one_database_notification_effect_total']=True
env.flush_all();cr.commit()
print('MP_AT_NATIVE='+json.dumps(dict(result='passed_native_job_authority_feasibility',checks=results,
    limitations=['Draft source overlay on core47, not an attested release image.',
                 'Managed supervisor/native partition fairness, application inbox/UI and lifecycle upgrade/recovery remain unqualified.'])))
