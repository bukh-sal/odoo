"""Private transactional recurrence storage, not an authorization entry point.

Trusted native adapters must provide current scope/resource authorization and
the existing one-off enqueue callback. No connection, commit, secret or RPC is
owned here. The native schema and lifecycle integration are not enabled yet.
"""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import re
from uuid import uuid4

from . import durable
from .recurrence import RecurrenceRule,_utc,cursor_after,occurrence_key,select


TERMINAL={'completed','dead_letter','cancelled'}
ACTIVE={'pending','running','retry','held','outcome_unknown'}
SCHEDULE_COLUMNS=dict(id='int4',public_id='varchar',site_id='varchar',workspace_id='int4',
    actor_id='int4',installation_id='int4',idempotency_key='varchar',release_digest='varchar',
    handler='varchar',handler_version='int4',config_version='int4',rule='jsonb',payload='jsonb',
    input_digest='varchar',creation_digest='varchar',state='varchar',next_at='timestamp',considered_at='timestamp',
    outstanding_job_id='varchar',last_tick_at='timestamp',last_tick='jsonb',created_at='timestamp',error_code='varchar')
OCCURRENCE_COLUMNS=dict(id='int4',site_id='varchar',schedule_id='varchar',nominal_at='timestamp',
    job_public_id='varchar',config_version='int4',input_digest='varchar',release_digest='varchar',created_at='timestamp')


def _time(value):
    if isinstance(value,str):value=datetime.fromisoformat(value)
    if not isinstance(value,datetime):raise durable.QueueError('Stored recurrence timestamp required')
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else _utc(value)


def _db(value):return _utc(value).replace(tzinfo=None)


def _scope(scope):
    if not isinstance(scope,durable.DispatchScope):raise durable.QueueError('Typed recurrence scope required')


@contextmanager
def _atomic(cr):
    name='recurrence_'+uuid4().hex
    cr.execute('SAVEPOINT '+name)
    try:yield
    except BaseException:
        cr.execute('ROLLBACK TO SAVEPOINT '+name)
        raise
    finally:cr.execute('RELEASE SAVEPOINT '+name)


def _configuration(handler,version,payload,rule):
    durable._name(handler);durable._bounded(version,1,1000)
    if not isinstance(rule,RecurrenceRule) or not isinstance(payload,dict):
        raise durable.QueueError('Versioned rule and private native payload required')
    data,digest=durable._json(dict(handler=handler,version=version,rule=rule.wire(),payload=payload))
    return durable._json(payload)[0],durable._json(rule.wire())[0],digest


def _locked(cr,scope,ident,*,revision=None):
    _scope(scope);durable._uuid(ident)
    durable.control(cr,scope.site_id,scope.release_digest)
    cr.execute("""SELECT to_jsonb(s) FROM mp_job_schedule s WHERE public_id=%s AND site_id=%s
        AND workspace_id=%s AND actor_id=%s AND installation_id=%s AND release_digest=%s FOR UPDATE""",
        [ident,scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id,scope.release_digest])
    found=cr.fetchone()
    if not found:raise durable.QueueError('Schedule unavailable in the current scope and release')
    row=found[0]
    if revision is not None:
        durable._bounded(revision,1,2**31-1)
        if row['config_version']!=revision:raise durable.QueueError('Schedule revision changed')
    return row


def create(cr,scope,handler,version,payload,rule,key,*,authorize):
    _scope(scope)
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',key) or not callable(authorize):
        raise durable.QueueError('Bounded schedule key and native authorizer required')
    data,wire,digest=_configuration(handler,version,payload,rule)
    durable.control(cr,scope.site_id,scope.release_digest)
    row=dict(site_id=scope.site_id,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        installation_id=scope.installation_id,release_digest=scope.release_digest,
        handler=handler,handler_version=version,payload=payload,rule=rule.wire())
    authorize(row)
    ident=str(uuid4())
    cr.execute("""INSERT INTO mp_job_schedule(public_id,site_id,workspace_id,actor_id,installation_id,
        idempotency_key,release_digest,handler,handler_version,config_version,rule,payload,input_digest,creation_digest,state,next_at,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s::jsonb,%s::jsonb,%s,%s,'active',%s,timezone('UTC',clock_timestamp()))
        ON CONFLICT(site_id,workspace_id,actor_id,installation_id,idempotency_key) DO NOTHING RETURNING public_id""",
        [ident,scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id,key,scope.release_digest,
         handler,version,wire,data,digest,digest,_db(rule.anchor_at)])
    found=cr.fetchone()
    if found:return found[0]
    cr.execute("""SELECT public_id,creation_digest,release_digest FROM mp_job_schedule WHERE site_id=%s
        AND workspace_id=%s AND actor_id=%s AND installation_id=%s AND idempotency_key=%s""",
        [scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id,key])
    found=cr.fetchone()
    if not found or found[1:]!=(digest,scope.release_digest):
        raise durable.QueueError('Schedule idempotency input or release conflict')
    return found[0]


def edit(cr,scope,ident,revision,*,handler,version,payload,rule,authorize):
    row=_locked(cr,scope,ident,revision=revision)
    if revision>=2**31-1:raise durable.QueueError('Schedule revision exhausted')
    data,wire,digest=_configuration(handler,version,payload,rule)
    old=RecurrenceRule.from_wire(row['rule'])
    if rule.anchor_at!=old.anchor_at:raise durable.QueueError('Schedule anchor is immutable')
    proposed=dict(row,handler=handler,handler_version=version,payload=payload,rule=rule.wire())
    authorize(proposed)
    next_at=cursor_after(rule,_time(row['considered_at'])) if row['considered_at'] else rule.anchor_at
    cr.execute("""UPDATE mp_job_schedule SET handler=%s,handler_version=%s,payload=%s::jsonb,rule=%s::jsonb,
        input_digest=%s,next_at=%s,config_version=config_version+1 WHERE id=%s""",
        [handler,version,data,wire,digest,_db(next_at),row['id']])
    return revision+1


def set_state(cr,scope,ident,revision,state,*,authorize):
    if state not in {'active','paused'}:raise durable.QueueError('Explicit schedule pause or resume required')
    row=_locked(cr,scope,ident,revision=revision)
    if revision>=2**31-1:raise durable.QueueError('Schedule revision exhausted')
    authorize(row)
    cr.execute('UPDATE mp_job_schedule SET state=%s,error_code=NULL,config_version=config_version+1 WHERE id=%s',[state,row['id']])
    return revision+1


def hold(cr,scope,ident,revision,code):
    if code not in {'FORBIDDEN','DEPENDENCY_UNAVAILABLE','CONFLICT','VALIDATION_FAILED','INTERNAL_ERROR'}:
        raise durable.QueueError('Safe schedule hold reason required')
    row=_locked(cr,scope,ident,revision=revision)
    cr.execute("UPDATE mp_job_schedule SET state='held',error_code=%s WHERE id=%s",[code,row['id']])


def candidates(cr,site_id,release_digest,now,*,limit=100):
    durable._bounded(limit,1,100)
    durable.control(cr,site_id,release_digest)
    cr.execute("""SELECT public_id FROM mp_job_schedule WHERE site_id=%s AND release_digest=%s AND state='active'
        AND next_at<=%s ORDER BY last_tick_at NULLS FIRST,next_at,public_id LIMIT %s""",[site_id,release_digest,_db(now),limit])
    return [row[0] for row in cr.fetchall()]


def _job_state(cr,scope,job):
    durable._uuid(job)
    cr.execute("""SELECT state FROM mp_job WHERE public_id=%s AND site_id=%s AND workspace_id=%s
        AND actor_id=%s AND installation_id=%s""",[job,scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id])
    found=cr.fetchone()
    if not found:
        cr.execute("""SELECT terminal_state FROM mp_job_identity WHERE job_public_id=%s AND site_id=%s
            AND workspace_id=%s AND actor_id=%s AND installation_id=%s""",
            [job,scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id])
        found=cr.fetchone()
    if not found or found[0] not in TERMINAL|ACTIVE:
        raise durable.QueueError('Outstanding occurrence requires independent reconciliation')
    return found[0]


def advance(cr,scope,ident,now,*,authorize,submit):
    """Serialize on the schedule; caller commits receipt/cursor/job atomically."""
    with _atomic(cr):
        return _advance(cr,scope,ident,now,authorize=authorize,submit=submit)


def _advance(cr,scope,ident,now,*,authorize,submit):
    if not callable(authorize) or not callable(submit):raise durable.QueueError('Trusted native callbacks required')
    row=_locked(cr,scope,ident)
    if row['state']!='active':return dict(outcome='paused',schedule_id=ident)
    authorize(row)
    rule=RecurrenceRule.from_wire(row['rule'])
    if row['outstanding_job_id'] and _job_state(cr,scope,row['outstanding_job_id']) in ACTIVE:
        cr.execute('UPDATE mp_job_schedule SET last_tick_at=%s WHERE id=%s',[_db(now),row['id']])
        return dict(outcome='busy',schedule_id=ident,job_id=row['outstanding_job_id'])
    selection=select(rule,_time(row['next_at']),now)
    job=None;outcome='skipped'
    if selection.nominal_at is not None:
        cr.execute('SELECT job_public_id FROM mp_job_occurrence WHERE site_id=%s AND schedule_id=%s AND nominal_at=%s',
                   [scope.site_id,ident,_db(selection.nominal_at)])
        receipt=cr.fetchone()
        if receipt:
            job=receipt[0]
            _job_state(cr,scope,job)
            outcome='replayed'
        else:
            timing=durable.JobSchedule(selection.nominal_at,selection.nominal_at+timedelta(seconds=rule.validity_seconds),rule.attempt_seconds)
            job=submit(row,timing,occurrence_key(ident,selection.nominal_at))
            durable._uuid(job)
            _job_state(cr,scope,job)
            cr.execute("""INSERT INTO mp_job_occurrence(site_id,schedule_id,nominal_at,job_public_id,config_version,
                input_digest,release_digest,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,timezone('UTC',clock_timestamp()))""",
                [scope.site_id,ident,_db(selection.nominal_at),job,row['config_version'],row['input_digest'],scope.release_digest])
            outcome='emitted'
    cursor=_time(row['next_at'])
    considered=selection.next_at-timedelta(seconds=rule.interval_seconds) if selection.next_at!=cursor else row['considered_at']
    tick=dict(outcome=outcome if selection.next_at!=cursor else 'idle',skipped=selection.skipped)
    cr.execute("""UPDATE mp_job_schedule SET next_at=%s,considered_at=%s,outstanding_job_id=%s,
        last_tick_at=%s,last_tick=%s::jsonb,error_code=NULL WHERE id=%s""",
        [_db(selection.next_at),_db(_time(considered)) if considered else None,job,_db(now),durable._json(tick)[0],row['id']])
    return dict(schedule_id=ident,job_id=job,**tick)
