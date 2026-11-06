"""BG-02 live probe, executed via the guarded disposable Odoo shell."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import threading
import time
from uuid import uuid4

from modular_platform import durable
from modular_platform.job_runner import run_once
from odoo import api, fields
from odoo.addons.mp_core import job_dispatch
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.exceptions import AccessError
from odoo.service.model import retrying


assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
registry = env.registry
release = current_release(env)
assert release['site_id'] == FIXTURE['site_id']
env.cr.execute("SELECT plugin_id FROM mp_plugin_installation WHERE plugin_id='org.example.background' AND state='installed'")
assert env.cr.fetchone()
durable.set_control(env.cr, release['site_id'], release['release_digest'], 'enabled')
env.cr.commit()


def scoped(cr, user, workspace):
    return scoped_environment(api.Environment(cr, FIXTURE['users'][user]['id'], {}),
                              FIXTURE['workspaces'][workspace]['public_id'])


def principal(cr, who):
    cr.execute('SELECT id FROM mp_principal WHERE public_id=%s', [FIXTURE['users'][who]['principal_id']])
    return cr.fetchone()[0]


def state(job):
    with registry.cursor() as cr:
        cr.execute('SELECT state,result,attempts,error_code FROM mp_job WHERE public_id=%s', [job])
        return cr.fetchone()


def rejected(callable_):
    try:
        callable_()
    except (PublicError, AccessError):
        return
    raise AssertionError('Foreign job access unexpectedly permitted')


with registry.cursor() as cr:
    task_model = scoped(cr, 'alice', 'A')['mp.background.task']
    data = dict(name='Synthetic task', assignee_id=principal(cr, 'alice'),
                due_at=fields.Datetime.now()+timedelta(seconds=10))
    rolled_back = task_model.create(data)._queue_current()
    cr.rollback()
assert state(rolled_back) is None

with registry.cursor() as cr:
    task_model = scoped(cr, 'alice', 'A')['mp.background.task']
    data = dict(name='Synthetic task', assignee_id=principal(cr, 'alice'),
                due_at=fields.Datetime.now()+timedelta(seconds=10))
    current, completed, changed, reassigned, cancelled = task_model.create([data]*5)
    current_job, completed_job, stale_job, reassigned_job, cancelled_job = [
        row._queue_current() for row in [current, completed, changed, reassigned, cancelled]]
    completed.write(dict(done=True))
    changed.write(dict(due_at=data['due_at']+timedelta(seconds=15)))
    rescheduled_job = changed._queue_current()
    assert rescheduled_job != stale_job
    reassigned.write(dict(assignee_id=principal(cr, 'operator')))
    current_id, reassigned_id = current.id, reassigned.id
    assert job_dispatch.cancel_scheduled(cancelled._job_env(), cancelled_job)
    assert job_dispatch.status(current._job_env(), current_job)['state'] == 'pending'
    foreign = scoped(cr, 'bob', 'B')['mp.background.task']
    rejected(lambda: job_dispatch.status(foreign._job_env(), current_job))
    rejected(lambda: job_dispatch.cancel_scheduled(foreign._job_env(), current_job))
    cr.commit()

# Both clients refer to the same immutable occurrence. Current resource rights
# are rechecked for each call, including the deduplication path.
barrier = threading.Barrier(2, timeout=10)
def duplicate(_):
    with registry.cursor() as cr:
        actor = scoped(cr, 'alice', 'A')
        barrier.wait()
        return retrying(lambda: actor['mp.background.task'].browse(current_id)._queue_current(), actor)

with ThreadPoolExecutor(max_workers=2) as pool:
    assert list(pool.map(duplicate, range(2))) == [current_job, current_job]
assert run_once(registry, str(uuid4()))['state'] == 'idle'

# A different origin loses workspace access between submission and dispatch.
with registry.cursor() as cr:
    actor = scoped(cr, 'bob', 'B')
    task = actor['mp.background.task'].create(dict(name='Revoked origin', assignee_id=principal(cr, 'bob'),
                                                   due_at=data['due_at']))
    revoked_job = task._queue_current()
    cr.execute("UPDATE mp_membership SET state='revoked' WHERE principal_id=%s AND workspace_id=%s",
               [principal(cr, 'bob'), FIXTURE['workspaces']['B']['id']])
    cr.commit()

limit = time.monotonic()+15
while time.monotonic() < limit:
    run_once(registry, str(uuid4()))
    if state(revoked_job)[0] != 'pending':
        break
    time.sleep(.1)

assert state(current_job) == ('completed', {'outcome': 'notified'}, 1, None), state(current_job)
for job in [completed_job, stale_job, reassigned_job]:
    assert state(job) == ('completed', {'outcome': 'obsolete'}, 1, None), state(job)
assert state(cancelled_job)[0] == 'cancelled'
assert state(revoked_job) == ('dead_letter', None, 1, 'FORBIDDEN'), state(revoked_job)
assert state(rescheduled_job)[0] == 'pending'
with registry.cursor() as cr:
    cr.execute("SELECT task_id,recipient_id,revision FROM mp_background_notification ORDER BY task_id")
    assert cr.fetchall() == [(current_id,principal(cr,'alice'),1),(reassigned_id,principal(cr,'operator'),2)]
    cr.execute("SELECT count(*) FROM mp_outbox WHERE topic='org.example.background.notification'")
    assert cr.fetchone()[0] == 2
    cr.execute("UPDATE mp_membership SET state='active' WHERE principal_id=%s AND workspace_id=%s",
               [principal(cr, 'bob'), FIXTURE['workspaces']['B']['id']])
    cr.commit()

print('MP_BG_RESULT='+json.dumps(dict(rollback=True, concurrent_duplicate=True, no_early_claim=True,
    completion_obsolete=True, due_change_obsolete=True, reassignment_obsolete=True, cancellation=True,
    cross_workspace_denial=True, revoked_origin_denied=True, notifications=2, outbox_events=2)))
