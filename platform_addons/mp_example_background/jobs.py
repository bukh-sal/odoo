import hashlib
import json
import time
import urllib.request

from modular_platform.durable import RetryJob
from modular_platform.job_supervisor import report_progress

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
FAULT = shape(mode=dict(enum=['claim','heartbeat','timeout','retry','send']))
LOAD = shape(iterations=dict(type='integer',enum=[250000,1000000,5000000]))
LOAD_RESULT = shape(iterations=dict(type='integer',enum=[250000,1000000,5000000]),
    digest=dict(type='string',pattern=r'^[a-f0-9]{64}$'))


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


def load_compute(values,_):
    """Bounded variable CPU cost for the disposable capacity qualification."""
    return dict(iterations=values['iterations'],digest=hashlib.pbkdf2_hmac('sha256',b'capacity',
        b'modular-bg-capacity-v1',values['iterations']).hex())


def fault_compute(values, context):
    """Only the disposable reference profile includes fault injection."""
    mode=values['mode']
    if mode=='send':
        job_dispatch.mark_external_effect(context)
        # A private deterministic qualification sink, with no provider or
        # caller-controlled URL. It deliberately delays its acknowledgment.
        request=urllib.request.Request('http://bg-effect-sink:8077/effect',
            data=context['job_id'].encode(),method='POST')
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=12) as response:
            assert response.status==204
    elif mode=='retry':
        if context['_native_job']['claim']['generation']==1:
            raise RetryJob()
    else:
        for value in (25,50,75):
            report_progress(value)
            time.sleep(3)
    return values


class BackgroundService:
    methods = {
        'authority': registry.Method(MODEL, '_mp_service_job_authority', 'get_input',
            'documents.schema.json', PERMISSION, False, 'read', shape()),
    }


registry.register(SERVICE, '1.0', PLUGIN, BackgroundService.methods)
for handler, version, pool, inputs, prepared, computed, output, authorize, prepare, compute, apply in [
    ('remind', 1, 'urgent', REMINDER, REMINDER, REMINDER, RESULT, reminder_resource,
     lambda env, data, bound: data, lambda data, context: data, reminder_apply),
    # Retire report v1 in this fixture to exercise incompatible carry-forward.
    ('report', 2, 'bulk', REPORT, DATA, SUMMARY, SUMMARY, report_resource,
     report_prepare, report_compute, lambda env, data, prepared, result, bound: result),
]:
    job_dispatch.register(job_dispatch.JobDefinition(
        PLUGIN+':'+handler, version, PLUGIN, SERVICE, '1.0', 'authority',
        inputs, prepared, computed, output, authorize, prepare, compute, apply, pool=pool))

job_dispatch.register(job_dispatch.JobDefinition(
    PLUGIN+':load',1,PLUGIN,SERVICE,'1.0','authority',LOAD,LOAD,LOAD_RESULT,LOAD_RESULT,
    lambda env,data,bound:bound.model._mp_guard('read'),lambda env,data,bound:data,
    load_compute,lambda env,data,prepared,result,bound:result,pool='bulk'))

job_dispatch.register(job_dispatch.JobDefinition(
    PLUGIN+':fault', 1, PLUGIN, SERVICE, '1.0', 'authority', FAULT, FAULT, FAULT, FAULT,
    lambda env, data, bound: bound.model._mp_guard('read'), lambda env, data, bound: data,
    fault_compute, lambda env, data, prepared, result, bound: result,
    effect_mode='reconcile', pool='bulk', max_attempts=2))


def authorize_event(env, event, bound):
    from odoo.exceptions import AccessError
    if event['workspace_id'] != current_scope(env).workspace_id:
        raise AccessError('Notification scope mismatch.')
    task = bound.model._task_by_public(event['payload']['task'])
    if task.assignee_id.id != current_scope(env).principal_id:
        raise AccessError('Notification recipient changed.')


events.register_topic(events.Topic(TOPIC, PLUGIN, MODEL, SERVICE, (1,), PERMISSION,
                                   REMINDER, authorize_event, method='authority'))
