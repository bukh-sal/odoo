"""Current-image permission, cancellation, transaction and stale-claim edges."""
import json
import time
from datetime import timedelta
from uuid import uuid4
from odoo import api,fields
from odoo.exceptions import AccessError,ValidationError
from odoo.addons.mp_core import job_dispatch,native_jobs
from modular_platform import durable
from modular_platform.job_runner import run_once,_claim_guard

registry=env.registry
checks=[]

def user(cr,key):return api.Environment(cr,FIXTURE['users'][key]['id'],{},su=False)
def denied(cr,fn,expected=AccessError):
    try:
        with cr.savepoint():fn()
    except expected:return
    raise AssertionError('Expected denial')
def occurrence(cr,t):
    cr.execute('SELECT job_id FROM mp_aurora_reminder WHERE task_id=%s AND revision=%s',[t.id,t.reminder_revision])
    row=cr.fetchone();return row[0] if row else None
def state(cr,j):
    cr.execute('SELECT state FROM mp_job WHERE public_id=%s',[j]);return cr.fetchone()[0]

with registry.cursor() as cr:
    owner,member,assigned,outsider=[user(cr,k) for k in ['alice','bob','operator','worker']]
    listing=owner['mp.aurora.task.list'].create(dict(name='Edge list',member_ids=[(6,0,[member.uid])]))
    owned=owner['mp.aurora.task'].create(dict(name='Archive rights',list_id=listing.id,assignee_id=assigned.uid))
    denied(cr,lambda:owned.write(dict(active=False)))
    assigned['mp.aurora.task'].browse(owned.id).write(dict(active=False))
    assigned['mp.aurora.task'].with_context(active_test=False).browse(owned.id).write(dict(active=True))
    denied(cr,lambda:owned.write(dict(active=False,assignee_id=owner.uid)),ValidationError)
    denied(cr,lambda:member['mp.aurora.task.list'].browse(listing.id).write(dict(active=False)))
    denied(cr,lambda:member['mp.aurora.task.list'].browse(listing.id).unlink())
    denied(cr,lambda:owned.write(dict(creator_id=member.uid)))
    denied(cr,lambda:listing.write(dict(owner_id=member.uid)))
    denied(cr,lambda:listing.write(dict(member_ids=[(6,0,[env.ref('base.public_user').id])])),ValidationError)
    denied(cr,lambda:owned.write(dict(assignee_id=env.ref('base.public_user').id)),ValidationError)
    checks.append('native archive/owner/creator/internal-user rules reject forged mutations')
    made=member['mp.aurora.task'].create(dict(name='Creator retained',list_id=listing.id))
    listing.write(dict(member_ids=[(5,)]))
    made.write(dict(description='Creator still has original task rights'))
    denied(cr,lambda:member['mp.aurora.task'].create(dict(name='New forbidden',list_id=listing.id)))
    made.unlink()
    checks.append('former member retains creator task rights but cannot create in inaccessible list')
    listing.write(dict(member_ids=[(6,0,[member.uid])]))
    due=fields.Datetime.now()+timedelta(hours=1)
    configured=owner['mp.aurora.task.stage'].create(dict(name='Configured now',list_id=listing.id,done=False))
    configured.write(dict(done=True))
    completed=owner['mp.aurora.task'].create(dict(name='Newly configured completion',list_id=listing.id,
        stage_id=configured.id,assignee_id=owner.uid,due_date=due,reminder='0'))
    assert completed.completed and occurrence(cr,completed) is None
    checks.append('same-request stage configuration is flushed before completion/reminder SQL reads')
    task=owner['mp.aurora.task'].create(dict(name='Edge reminder',list_id=listing.id,assignee_id=assigned.uid,due_date=due,reminder='0'))
    old=occurrence(cr,task)
    assigned['mp.aurora.task'].browse(task.id).write(dict(assignee_id=owner.uid))
    assert state(cr,old)=='cancelled'
    assert occurrence(cr,task) is None  # Former assignee lost authority; never submit as another user.
    owner['mp.aurora.task'].browse(task.id).write(dict(due_date=due+timedelta(minutes=1)))
    old=occurrence(cr,task);assert old
    task.write(dict(assignee_id=False));assert state(cr,old)=='cancelled' and occurrence(cr,task) is None
    task.write(dict(assignee_id=owner.uid));old=occurrence(cr,task);assert old
    task.write(dict(reminder='none'));assert state(cr,old)=='cancelled'
    task.write(dict(reminder='0'));old=occurrence(cr,task)
    listing.write(dict(active=False));assert state(cr,old)=='cancelled' and occurrence(cr,task) is None
    listing.write(dict(active=True));assert occurrence(cr,task)
    checks.append('reassignment/lost authority, unassignment, opt-out and list archive invalidate occurrences')
    old=occurrence(cr,task);task.unlink();assert state(cr,old)=='cancelled'
    orphan=owner['mp.aurora.task'].create(dict(name='Cascade cancelled',list_id=listing.id,assignee_id=owner.uid,due_date=due,reminder='0'))
    old=occurrence(cr,orphan);listing.unlink();assert state(cr,old)=='cancelled'
    checks.append('task/list deletion cancels queued delivery before business cascade')
    cr.rollback()

with registry.cursor() as cr:
    owner=user(cr,'alice')
    listing=owner['mp.aurora.task.list'].create(dict(name='Rolled back'))
    task=owner['mp.aurora.task'].create(dict(name='No committed job',list_id=listing.id,assignee_id=owner.uid,
        due_date=fields.Datetime.now()-timedelta(seconds=1),reminder='0'))
    rolled=occurrence(cr,task);cr.rollback()
with registry.cursor() as cr:
    cr.execute('SELECT count(*) FROM mp_job WHERE public_id=%s',[rolled]);assert cr.fetchone()==(0,)
checks.append('business transaction rollback leaves no job or notification')

# Commit a real claim, let its actual lease expire, reclaim via the normal runner,
# then try the obsolete invocation. No timestamp rewriting or fake dispatch effect.
with registry.cursor() as cr:
    owner=user(cr,'alice')
    listing=owner['mp.aurora.task.list'].create(dict(name='Interrupted reminder'))
    task=owner['mp.aurora.task'].create(dict(name='Recover after abandoned claim',list_id=listing.id,assignee_id=owner.uid,
        due_date=fields.Datetime.now()-timedelta(seconds=1),reminder='0'))
    ident=occurrence(cr,task);task_id=task.id
    cr.execute('SELECT installation_id FROM mp_job WHERE public_id=%s',[ident]);installation=cr.fetchone()[0]
    cr.commit()
with registry.cursor() as cr:
    with _claim_guard(cr,'urgent',None,installation) as allowed:
        assert allowed
        old=job_dispatch.prepare_one(api.Environment(cr,1,{}),str(uuid4()),pool='urgent',native_installation_id=installation,lease_seconds=1)
        assert old.claim.job_id==ident
        cr.commit()
time.sleep(1.2)
result=run_once(registry,str(uuid4()),pool='urgent',native_installation_id=installation)
assert result.get('job_id')==ident and result['state']=='completed',result
with registry.cursor() as cr:
    denied(cr,lambda:job_dispatch.finish_one(api.Environment(cr,1,{}),old,{}),durable.ClaimLost)
    cr.execute('SELECT attempts,state FROM mp_job WHERE public_id=%s',[ident]);assert cr.fetchone()==(2,'completed')
    cr.execute('SELECT count(*) FROM mp_aurora_notification WHERE task_id=%s',[task_id]);assert cr.fetchone()==(1,)
checks.append('actual committed claim/lease expiry/reclaim completes once; obsolete invocation cannot apply')
reclaimed_ident=ident

with registry.cursor() as cr:
    owner=user(cr,'alice')
    task=owner['mp.aurora.task'].create(dict(name='Cancel committed running claim',list_id=listing.id,
        assignee_id=owner.uid,due_date=fields.Datetime.now()-timedelta(seconds=1),reminder='0'))
    ident=occurrence(cr,task);task_id=task.id
    cr.commit()
with registry.cursor() as cr:
    with _claim_guard(cr,'urgent',None,installation) as allowed:
        assert allowed
        running=job_dispatch.prepare_one(api.Environment(cr,1,{}),str(uuid4()),pool='urgent',native_installation_id=installation)
        assert running.claim.job_id==ident
        cr.commit()
with registry.cursor() as cr:
    user(cr,'alice')['mp.aurora.task'].browse(task_id).action_complete()
    assert state(cr,ident)=='cancelled'
    cr.commit()
with registry.cursor() as cr:
    denied(cr,lambda:job_dispatch.finish_one(api.Environment(cr,1,{}),running,{}),durable.ClaimLost)
    cr.execute('SELECT count(*) FROM mp_aurora_notification WHERE task_id=%s',[task_id]);assert cr.fetchone()==(0,)
checks.append('completion cancels a committed running claim; its late result cannot notify')
print('MP_AT_EDGES='+json.dumps(dict(result='passed',checks=checks,interrupted_job=reclaimed_ident,
    cancelled_running_job=ident),sort_keys=True))
