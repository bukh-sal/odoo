"""Real-image Tasks model, native authority, reminder and inbox qualification."""
from datetime import timedelta
import json
from uuid import uuid4

from odoo import api, fields
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.addons.mp_core import native_jobs
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable
from modular_platform.job_runner import run_once

assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
registry = env.registry
checks = []


def actor(cr, who):
    return api.Environment(cr, FIXTURE['users'][who]['id'], {}, su=False)


def denied(cr, callback, expected=AccessError):
    try:
        with cr.savepoint(): callback()
    except expected:
        return
    raise AssertionError('Expected denial did not occur')


def job(cr, task):
    cr.execute('SELECT job_id FROM mp_aurora_reminder WHERE task_id=%s AND revision=%s', [task.id, task.reminder_revision])
    found = cr.fetchone()
    return found[0] if found else None


def job_state(ident):
    with registry.cursor() as cr:
        cr.execute('SELECT state,error_code,attempts,result FROM mp_job WHERE public_id=%s', [ident])
        return cr.fetchone()


with registry.cursor() as cr:
    alice, bob, assignee, outsider = [actor(cr, who) for who in ['alice', 'bob', 'operator', 'worker']]
    listing = alice['mp.aurora.task.list'].create(dict(name='Release tasks', member_ids=[(6, 0, [bob.uid])]))
    stages = alice['mp.aurora.task.stage'].search([('list_id', '=', listing.id)])
    assert len(stages) == 2 and len(stages.filtered('done')) == 1
    bob['mp.aurora.task.list'].browse(listing.id).write(dict(description='Shared editing'))
    denied(cr, lambda: bob['mp.aurora.task.list'].browse(listing.id).write(dict(member_ids=[(5,)])))
    denied(cr, lambda: outsider['mp.aurora.task.list'].browse(listing.id).read(['name']))
    checks.append('default stages and native owner/member/outsider list permissions')
    task = alice['mp.aurora.task'].create(dict(name='Assigned externally', list_id=listing.id, assignee_id=assignee.uid))
    assigned = assignee['mp.aurora.task'].browse(task.id)
    assert assigned.read(['name'])[0]['name'] == task.name
    denied(cr, lambda: assignee['mp.aurora.task.list'].browse(listing.id).read(['name']))
    denied(cr, lambda: assignee['mp.aurora.task.stage'].browse(task.stage_id.id).read(['name']))
    assigned.action_complete(); assert assigned.completed
    assigned.action_reopen(); assert not assigned.completed
    denied(cr, lambda: outsider['mp.aurora.task'].browse(task.id).write(dict(name='Foreign mutation')))
    denied(cr, lambda: outsider['mp.aurora.task'].create(dict(name='Foreign create', list_id=listing.id)))
    denied(cr, lambda: task.stage_id.write(dict(done=True)), ValidationError)
    denied(cr, lambda: task.stage_id.unlink(), ValidationError)
    checks.append('external assignee completion/reopen without list/stage browsing; foreign operations refused')
    denied(cr, lambda: task.write(dict(reminder_revision=999)))
    denied(cr, lambda: task.write(dict(reminder='0')), ValidationError)
    denied(cr, lambda: task.write(dict(due_date=fields.Datetime.now()+timedelta(days=31), reminder='0')), ValidationError)
    denied(cr, lambda: task.write(dict(due_date=fields.Datetime.now()-timedelta(days=2), reminder='0')), ValidationError)
    checks.append('protected reminder state and explicit missing/long-future/expired scheduling validation')
    due = fields.Datetime.now()-timedelta(seconds=2)
    current = alice['mp.aurora.task'].create(dict(name='Current title', list_id=listing.id, assignee_id=assignee.uid, due_date=due, reminder='0'))
    current_job = job(cr, current); assert current_job and current.reminder_status == 'queued'
    current.write(dict(name='Updated title before delivery', description='Never copy this description'))
    revision = current.reminder_revision
    current.write(dict(due_date=due, reminder='0'))
    assert current.reminder_revision == revision and job(cr, current) == current_job
    current._queue_current(strict=True); assert job(cr, current) == current_job
    checks.append('transactional original-human queue and unchanged/name-only edits preserve occurrence identity')
    cancelled = alice['mp.aurora.task'].create(dict(name='Cancelled by completion', list_id=listing.id, assignee_id=alice.uid, due_date=due, reminder='0'))
    cancelled_job = job(cr, cancelled); cancelled.action_complete()
    cr.execute('SELECT state FROM mp_job WHERE public_id=%s', [cancelled_job]); assert cr.fetchone() == ('cancelled',)
    changed = alice['mp.aurora.task'].create(dict(name='Rescheduled', list_id=listing.id, assignee_id=alice.uid, due_date=due, reminder='0'))
    stale_job = job(cr, changed)
    changed.write(dict(due_date=due+timedelta(days=1)))
    assert job(cr, changed) != stale_job
    cr.execute('SELECT state FROM mp_job WHERE public_id=%s', [stale_job]); assert cr.fetchone() == ('cancelled',)
    checks.append('completion and due changes cancel old occurrence atomically')
    cr.execute('SELECT installation_id,workspace_id,actor_id FROM mp_job WHERE public_id=%s', [current_job])
    installation, workspace, principal = cr.fetchone(); assert workspace is None
    cr.execute('SELECT user_id FROM mp_principal WHERE id=%s', [principal]); assert cr.fetchone() == (alice.uid,)
    release = current_release(alice)
    durable.set_control(cr, release['site_id'], release['release_digest'], 'enabled')
    ids = dict(list=listing.id, task=current.id, cancelled=cancelled.id, changed=changed.id)
    cr.commit()

result = run_once(registry, str(uuid4()), pool='urgent', native_installation_id=installation)
assert result.get('job_id') == current_job and result['state'] == 'completed', result
assert job_state(current_job)[0] == 'completed'
assert run_once(registry, str(uuid4()), pool='urgent', native_installation_id=installation)['state'] == 'idle'
checks.append('real registered native reminder through claim/prepare/compute/fenced apply, then idle')

with registry.cursor() as cr:
    recipient = actor(cr, 'operator'); alice = actor(cr, 'alice'); outsider = actor(cr, 'worker')
    inbox = recipient['mp.aurora.notification'].search([])
    assert len(inbox) == 1
    assert inbox.title == 'Updated title before delivery' and not inbox.is_read
    assert inbox.action_open_task()['res_id'] == ids['task']
    inbox.write(dict(is_read=True)); assert inbox.is_read
    assert not alice['mp.aurora.notification'].search([])
    assert not outsider['mp.aurora.notification'].search([])
    denied(cr, lambda: alice['mp.aurora.notification'].browse(inbox.id).read(['title']))
    denied(cr, lambda: outsider['mp.aurora.notification'].browse(inbox.id).write(dict(is_read=True)))
    denied(cr, lambda: inbox.write(dict(title='forged')))
    denied(cr, lambda: inbox.unlink())
    denied(cr, lambda: recipient['mp.aurora.notification'].create(dict(title='forged', recipient_id=recipient.uid, revision=99)))
    task = alice['mp.aurora.task'].browse(ids['task']); assert task.reminder_status == 'sent'
    cr.execute('SELECT count(*) FROM mp_aurora_notification WHERE task_id=%s', [task.id]); assert cr.fetchone() == (1,)
    checks.append('one current title snapshot, recipient-only inbox/read state and denied arbitrary CRUD')
    task.write(dict(assignee_id=alice.uid))
    denied(cr, lambda: inbox.action_open_task())
    assert inbox.title == 'Updated title before delivery'
    checks.append('historical recipient snapshot retained; task opening rechecks current access after reassignment')
    # Rollback the reassignment and read flag so later browser fixtures retain a useful unread inbox.
    cr.rollback()

with registry.cursor() as cr:
    alice = actor(cr, 'alice'); bob = actor(cr, 'bob'); outsider = actor(cr, 'worker')
    listing = alice['mp.aurora.task.list'].browse(ids['list'])
    revoked = alice['mp.aurora.task'].create(dict(name='Revoked origin', list_id=listing.id, assignee_id=alice.uid,
                                                due_date=fields.Datetime.now()-timedelta(seconds=1)))
    bob['mp.aurora.task'].browse(revoked.id).write(dict(reminder='0'))
    revoked_job = job(cr, revoked)
    denied(cr, lambda: native_jobs.cancel(outsider, revoked_job))
    listing.write(dict(member_ids=[(5,)]))
    revoked_id = revoked.id
    cr.commit()
result = run_once(registry, str(uuid4()), pool='urgent', native_installation_id=installation)
assert result.get('job_id') == revoked_job and result['state'] != 'completed', result
with registry.cursor() as cr:
    cr.execute('SELECT count(*) FROM mp_aurora_notification WHERE task_id=%s', [revoked_id]); assert cr.fetchone() == (0,)
checks.append('current origin resource revocation blocks actual delivery; outsider cancellation denied')

with registry.cursor() as cr:
    cr.execute('SELECT (SELECT count(*) FROM mp_workspace),(SELECT count(*) FROM mp_membership),(SELECT count(*) FROM mp_workspace_plugin)')
    assert cr.fetchone() == (0, 0, 0)
checks.append('all native application jobs ran with zero workspaces/memberships/features')
print('MP_AT_RESULT='+json.dumps(dict(result='passed', checks=checks, ids=ids, jobs=dict(current=current_job,
    cancelled=cancelled_job, stale=stale_job, revoked=revoked_job), native_installation=installation), sort_keys=True))
