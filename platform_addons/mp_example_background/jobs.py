import hashlib
import json

from odoo.addons.mp_core import events, job_dispatch, registry
from odoo.addons.mp_identity.scopes import current_scope

from .models import PLUGIN, SERVICE


def shape(**properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


UUID = dict(type='string', format='uuid')
POSITIVE = dict(type='integer', minimum=1, maximum=2147483647)
REMINDER = shape(task=UUID, revision=POSITIVE)
RESULT = shape(outcome=dict(enum=['obsolete', 'notified']))
REPORT = shape(first=POSITIVE, last=POSITIVE)
POINTS = dict(type='integer', minimum=0, maximum=1000)
DATA = shape(points=dict(type='array', items=POINTS, maxItems=500))
SUMMARY = shape(count=dict(type='integer', minimum=0, maximum=500),
                points=dict(type='integer', minimum=0, maximum=500000),
                digest=dict(type='string', pattern=r'^[a-f0-9]{64}$'))
MODEL = 'mp.background.task'
PERMISSION = PLUGIN + ':jobs.read'
TOPIC = PLUGIN + '.notification'


def reminder_resource(env, values, bound):
    return bound.model._task_by_public(values['task'])


def reminder_apply(env, values, prepared, computed, bound):
    row = reminder_resource(env, values, bound)
    env.cr.execute('SELECT id FROM mp_background_task WHERE id=%s FOR UPDATE', [row.id])
    row.invalidate_recordset(['revision', 'due_at', 'done', 'assignee_id'])
    if (row.revision != values['revision'] or row.done or not row.due_at or not row.assignee_id
            or not row._active_recipient(lock=True)):
        return dict(outcome='obsolete')
    row._mp_guard('write')
    # Scheduler metadata and notification storage are private. The scoped
    # actor and current task grant have already been checked under this fence.
    env['mp.background.notification'].sudo().create(dict(
        task_id=row.id, recipient_id=row.assignee_id.id, revision=row.revision))
    events.emit(env, TOPIC, row.public_id, values, sequence=row.revision, action='write')
    return dict(outcome='notified')


def report_resource(env, values, bound):
    from odoo.exceptions import ValidationError
    if not 0 <= values['last']-values['first'] < 500:
        raise ValidationError('A report is limited to 500 task IDs.')
    bound.model._mp_guard('read')


def report_prepare(env, values, bound):
    points = []
    for first in range(values['first'], values['last']+1, 100):
        rows = bound.model.search([('id','>=',first), ('id','<=',min(first+99,values['last']))],
                                  order='id', limit=100)
        points.extend(rows.mapped('points'))
    return dict(points=points)


def report_compute(values, _):
    points = values['points']
    # A fixed CPU cost makes the sample useful for measuring contention.
    data = json.dumps(points, separators=(',', ':')).encode()
    digest = hashlib.pbkdf2_hmac('sha256', data, b'modular-bg-reference-v1', 5_000_000).hex()
    return dict(count=len(points), points=sum(points), digest=digest)


class BackgroundService:
    methods = {
        'authority': registry.Method(MODEL, '_mp_service_job_authority', 'get_input',
            'documents.schema.json', PERMISSION, False, 'read', shape()),
    }


registry.register(SERVICE, '1.0', PLUGIN, BackgroundService.methods)
for handler, pool, inputs, prepared, computed, output, authorize, prepare, compute, apply in [
    ('remind', 'urgent', REMINDER, REMINDER, REMINDER, RESULT, reminder_resource,
     lambda env, data, bound: data, lambda data, context: data, reminder_apply),
    ('report', 'bulk', REPORT, DATA, SUMMARY, SUMMARY, report_resource,
     report_prepare, report_compute, lambda env, data, prepared, result, bound: result),
]:
    job_dispatch.register(job_dispatch.JobDefinition(
        PLUGIN+':'+handler, 1, PLUGIN, SERVICE, '1.0', 'authority',
        inputs, prepared, computed, output, authorize, prepare, compute, apply, pool=pool))


def authorize_event(env, event, bound):
    from odoo.exceptions import AccessError
    if event['workspace_id'] != current_scope(env).workspace_id:
        raise AccessError('Notification scope mismatch.')
    task = bound.model._task_by_public(event['payload']['task'])
    if task.assignee_id.id != current_scope(env).principal_id:
        raise AccessError('Notification recipient changed.')


events.register_topic(events.Topic(TOPIC, PLUGIN, MODEL, SERVICE, (1,), PERMISSION,
                                   REMINDER, authorize_event, method='authority'))
