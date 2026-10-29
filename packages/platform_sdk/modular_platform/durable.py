"""Private PostgreSQL scheduler/outbox primitives over native-owned tables.

Callers are trusted adapters: they must validate the registered payload schema
and current actor/plugin/grants at enqueue and execution. This module grants
no authority, opens no connections, commits no transactions and dispatches no
arbitrary handler. Business handlers require run_fenced in their transaction.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import re
from uuid import UUID, uuid4

import rfc8785


class QueueError(ValueError):
    pass


class ClaimLost(QueueError):
    pass


class DispatchPaused(QueueError):
    pass


@dataclass(frozen=True)
class DispatchScope:
    site_id: str
    workspace_id: int
    actor_id: int
    installation_id: int
    release_digest: str

    def __post_init__(self):
        _uuid(self.site_id)
        if any(type(v) is not int or not 0 < v < 2**31 for v in [self.workspace_id, self.actor_id, self.installation_id]):
            raise QueueError('Invalid private dispatch scope')
        if not isinstance(self.release_digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', self.release_digest):
            raise QueueError('Invalid dispatch release')


@dataclass(frozen=True)
class Claim:
    job_id: str
    generation: int
    owner: str


def _uuid(value):
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise QueueError('Canonical dispatch UUID required') from None
    return value


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_.:-]{0,159}', value):
        raise QueueError('Invalid registered dispatch name')
    return value


def _bounded(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise QueueError('Invalid dispatch bound')
    return value


def _json(value):
    try:
        raw = rfc8785.dumps(value)
    except (ValueError, TypeError, rfc8785.CanonicalizationError):
        raise QueueError('Invalid dispatch JSON') from None
    if len(raw) > 65536:
        raise QueueError('Dispatch payload exceeds limit')
    return raw.decode(), 'sha256:' + hashlib.sha256(raw).hexdigest()


def control(cr, site_id, release_digest):
    """Hold the current control row through the caller transaction."""
    cr.execute("SELECT generation FROM mp_dispatch_control WHERE site_id=%s AND release_digest=%s AND state='enabled' FOR SHARE", [site_id, release_digest])
    row = cr.fetchone()
    if not row:
        raise DispatchPaused('Dispatch is paused or release incompatible')
    return row[0]


def set_control(cr, site_id, release_digest, state):
    """Independent operator adapter only; never an HTTP/ORM public method."""
    _uuid(site_id)
    if state not in {'enabled', 'paused', 'restoring'} or not re.fullmatch(r'sha256:[0-9a-f]{64}', release_digest):
        raise QueueError('Invalid dispatch control')
    cr.execute("""INSERT INTO mp_dispatch_control(site_id,release_digest,state,generation)
        VALUES (%s,%s,%s,1) ON CONFLICT(site_id) DO UPDATE
        SET release_digest=EXCLUDED.release_digest,state=EXCLUDED.state,
            generation=mp_dispatch_control.generation+1
        WHERE (mp_dispatch_control.release_digest,mp_dispatch_control.state)
           IS DISTINCT FROM (EXCLUDED.release_digest,EXCLUDED.state)
        RETURNING generation""", [site_id, release_digest, state])
    row = cr.fetchone()
    if row:
        return row[0]
    cr.execute('SELECT generation FROM mp_dispatch_control WHERE site_id=%s', [site_id])
    return cr.fetchone()[0]


def enqueue(cr, scope, handler, version, payload, key, *, effect_mode='idempotent', max_attempts=5, timeout_seconds=120, deduplication=None):
    if not isinstance(scope, DispatchScope):
        raise QueueError('Validated private dispatch scope required')
    _name(handler); _bounded(version, 1, 1000); _bounded(max_attempts, 1, 16); _bounded(timeout_seconds, 1, 86400)
    if effect_mode not in {'idempotent', 'reconcile'} or not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', key):
        raise QueueError('Invalid job effect or deduplication policy')
    data, digest = _json(payload)
    if deduplication is not None:
        _, digest = _json(deduplication)
    generation = control(cr, scope.site_id, scope.release_digest)
    identity = [scope.site_id, scope.workspace_id, scope.actor_id, scope.installation_id, handler, version, key]
    public_id = str(uuid4())
    cr.execute("""INSERT INTO mp_job(public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key,
        release_digest,payload,input_digest,effect_mode,state,attempts,max_attempts,claim_generation,dispatch_generation,
        available_at,deadline_at,cancel_requested,effect_started,progress,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,'pending',0,%s,0,%s,
                timezone('UTC',clock_timestamp()),timezone('UTC',clock_timestamp())+(%s*interval '1 second'),false,false,0,timezone('UTC',clock_timestamp()))
        ON CONFLICT(site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key) DO NOTHING RETURNING public_id""",
        [public_id, *identity, scope.release_digest, data, digest, effect_mode, max_attempts, generation, timeout_seconds])
    inserted = cr.fetchone()
    if inserted:
        return inserted[0]
    cr.execute("""SELECT public_id,input_digest,release_digest,effect_mode FROM mp_job
        WHERE site_id=%s AND workspace_id=%s AND actor_id=%s AND installation_id=%s AND handler=%s AND handler_version=%s AND idempotency_key=%s""", identity)
    old = cr.fetchone()
    if not old or tuple(old[1:]) != (digest, scope.release_digest, effect_mode):
        raise QueueError('Job deduplication input or release conflict')
    return old[0]


def claim(cr, site_id, release_digest, owner, handlers, *, lease_seconds=30):
    _uuid(site_id); _uuid(owner); _bounded(lease_seconds, 1, 300)
    if not isinstance(handlers, (list, tuple)) or not 1 <= len(handlers) <= 100:
        raise QueueError('Explicit handler allowlist required')
    for name in handlers:
        _name(name)
    generation = control(cr, site_id, release_digest)
    # Lease loss is observable state. Reconcile uncertain non-idempotent work;
    # never reinterpret an expired external attempt as proof of rollback.
    cr.execute("""WITH expired AS (SELECT id FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
        AND state='running' AND lease_until<=timezone('UTC',clock_timestamp()) FOR UPDATE SKIP LOCKED)
        UPDATE mp_job j SET state=CASE WHEN effect_mode='reconcile' AND effect_started THEN 'outcome_unknown'
            WHEN cancel_requested THEN 'cancelled' WHEN attempts>=max_attempts OR deadline_at<=timezone('UTC',clock_timestamp())
            THEN 'dead_letter' ELSE 'retry' END,
            error_code='LEASE_EXPIRED',lease_owner=NULL,lease_until=NULL,available_at=timezone('UTC',clock_timestamp())
        FROM expired WHERE j.id=expired.id""", [site_id, release_digest, list(handlers)])
    cr.execute("""WITH expired AS (SELECT id FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
        AND state IN ('pending','retry') AND deadline_at<=timezone('UTC',clock_timestamp()) FOR UPDATE SKIP LOCKED)
        UPDATE mp_job j SET state='dead_letter',error_code='DEADLINE_EXCEEDED',finished_at=timezone('UTC',clock_timestamp())
        FROM expired WHERE j.id=expired.id""", [site_id, release_digest, list(handlers)])
    cr.execute("""WITH next AS (SELECT id FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
        AND state IN ('pending','retry') AND NOT cancel_requested AND attempts<max_attempts
        AND available_at<=timezone('UTC',clock_timestamp()) AND deadline_at>timezone('UTC',clock_timestamp())
        ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1)
        UPDATE mp_job j SET state='running',attempts=attempts+1,claim_generation=claim_generation+1,
            dispatch_generation=%s,lease_owner=%s,lease_until=LEAST(deadline_at,timezone('UTC',clock_timestamp())+(%s*interval '1 second')),
            effect_started=false,error_code=NULL FROM next WHERE j.id=next.id
        RETURNING j.public_id,j.claim_generation""", [site_id, release_digest, list(handlers), generation, owner, lease_seconds])
    row = cr.fetchone()
    return Claim(row[0], row[1], owner) if row else None


def _lock(cr, value):
    if not isinstance(value, Claim):
        raise ClaimLost('Current claim required')
    _uuid(value.job_id); _uuid(value.owner); _bounded(value.generation, 1, 2**31-1)
    cr.execute("""SELECT site_id,release_digest FROM mp_job WHERE public_id=%s""", [value.job_id])
    row = cr.fetchone()
    if not row:
        raise ClaimLost('Claim unavailable')
    generation = control(cr, *row)
    cr.execute("""SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s AND state='running' AND claim_generation=%s
        AND lease_owner=%s AND dispatch_generation=%s AND NOT cancel_requested
        AND lease_until>timezone('UTC',clock_timestamp()) AND deadline_at>timezone('UTC',clock_timestamp()) FOR UPDATE""",
        [value.job_id, value.generation, value.owner, generation])
    row = cr.fetchone()
    if not row:
        raise ClaimLost('Claim expired, superseded or cancelled')
    return row[0]


@contextmanager
def _savepoint(cr):
    if hasattr(cr, 'savepoint'):
        with cr.savepoint():
            yield
        return
    name = 'mp_job_' + uuid4().hex
    cr.execute('SAVEPOINT ' + name)
    try:
        yield
    except BaseException:
        cr.execute('ROLLBACK TO SAVEPOINT ' + name)
        raise
    finally:
        cr.execute('RELEASE SAVEPOINT ' + name)


def run_fenced(cr, value, work, *, flush=None):
    """Run a registered DB business handler and finalization atomically.

    The caller owns/commits the transaction. Odoo callers supply env.flush_all;
    its savepoint manager also invalidates native caches on rollback.
    """
    with _savepoint(cr):
        record = _lock(cr, value)
        result = work(record)
        if flush:
            flush()
        data, _ = _json(result)
        cr.execute("""UPDATE mp_job SET state='completed',result=%s::jsonb,progress=100,finished_at=timezone('UTC',clock_timestamp()),
            lease_owner=NULL,lease_until=NULL WHERE public_id=%s AND state='running' AND claim_generation=%s AND lease_owner=%s
            AND NOT cancel_requested AND lease_until>timezone('UTC',clock_timestamp()) AND deadline_at>timezone('UTC',clock_timestamp()) RETURNING id""",
            [data, value.job_id, value.generation, value.owner])
        if not cr.fetchone():
            raise ClaimLost('Claim expired before business finalization')
        return result


def heartbeat(cr, value, *, lease_seconds=30, progress=0):
    _bounded(lease_seconds, 1, 300); _bounded(progress, 0, 99); _lock(cr, value)
    cr.execute("UPDATE mp_job SET lease_until=LEAST(deadline_at,timezone('UTC',clock_timestamp())+(%s*interval '1 second')),progress=%s WHERE public_id=%s", [lease_seconds, progress, value.job_id])


def effect_started(cr, value):
    """Commit this marker before a separately authorized external request."""
    _lock(cr, value)
    cr.execute('UPDATE mp_job SET effect_started=true WHERE public_id=%s', [value.job_id])


def fail(cr, value, code, *, retryable=False):
    if code not in {'DEPENDENCY_UNAVAILABLE','DEADLINE_EXCEEDED','FORBIDDEN','PLUGIN_SUSPENDED','CONFLICT','INTERNAL_ERROR','VALIDATION_FAILED','NOT_FOUND'} or type(retryable) is not bool:
        raise QueueError('Safe registered failure code required')
    row = _lock(cr, value)
    state = ('outcome_unknown' if row['effect_mode']=='reconcile' and row['effect_started'] else
             'retry' if retryable and row['attempts']<row['max_attempts'] else 'dead_letter')
    delay = min(60, 2**(row['attempts']-1))
    cr.execute("""UPDATE mp_job SET state=%s,error_code=%s,lease_owner=NULL,lease_until=NULL,
        available_at=timezone('UTC',clock_timestamp())+(%s*interval '1 second'),
        finished_at=CASE WHEN %s='retry' THEN NULL ELSE timezone('UTC',clock_timestamp()) END WHERE public_id=%s""", [state, code, delay, state, value.job_id])
    return state


def cancel(cr, job_id, *, actor_id, workspace_id):
    """After fresh scope authorization; cannot claim external rollback."""
    _uuid(job_id)
    cr.execute("""UPDATE mp_job SET cancel_requested=true,state=CASE WHEN state IN ('pending','retry','held') THEN 'cancelled' ELSE state END
        WHERE public_id=%s AND actor_id=%s AND workspace_id=%s AND state IN ('pending','retry','running','held') RETURNING public_id""", [job_id, actor_id, workspace_id])
    return bool(cr.fetchone())


def append_event(cr, scope, *, plugin_id, topic, version, aggregate_id, payload, correlation_id, causation_id=None, sequence=None):
    if not isinstance(scope, DispatchScope):
        raise QueueError('Validated private producer scope required')
    _name(plugin_id); _name(topic); _bounded(version, 1, 1000); _uuid(aggregate_id); _uuid(correlation_id)
    if causation_id is not None:
        _uuid(causation_id)
    if sequence is not None:
        _bounded(sequence, 1, 2**31-1)
    data, _ = _json(payload)
    generation = control(cr, scope.site_id, scope.release_digest)
    event = str(uuid4())
    cr.execute("""INSERT INTO mp_outbox(public_id,site_id,workspace_id,actor_id,installation_id,plugin_id,topic,schema_version,
        aggregate_id,aggregate_sequence,occurred_at,correlation_id,causation_id,payload,release_digest,dispatch_generation,state)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,timezone('UTC',clock_timestamp()),%s,%s,%s::jsonb,%s,%s,'pending')""",
        [event,scope.site_id,scope.workspace_id,scope.actor_id,scope.installation_id,plugin_id,topic,version,aggregate_id,sequence,correlation_id,causation_id,data,scope.release_digest,generation])
    return event
