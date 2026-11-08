"""Private PostgreSQL scheduler/outbox primitives over native-owned tables.

Callers are trusted adapters: they must validate the registered payload schema
and current actor/plugin/grants at enqueue and execution. This module grants
no authority, opens no connections, commits no transactions and dispatches no
arbitrary handler. Business handlers require run_fenced in their transaction.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
class NativeDispatchScope:
    """Private native application routing; never a workspace authorization grant."""
    site_id: str
    actor_id: int
    installation_id: int
    release_digest: str

    def __post_init__(self):
        _uuid(self.site_id)
        for value in (self.actor_id, self.installation_id):
            _bounded(value, 1, 2**31-1)
        if not isinstance(self.release_digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', self.release_digest):
            raise QueueError('Invalid dispatch release')

    @property
    def workspace_id(self):
        return None


@dataclass(frozen=True)
class ExecutionPartition:
    """A real workspace or native installation, never a synthetic workspace."""
    kind: str
    ident: int

    def __post_init__(self):
        if self.kind not in ('workspace','native'):raise QueueError('Known execution partition required')
        _bounded(self.ident,1,2**31-1)

    @property
    def key(self):
        return ('w:' if self.kind=='workspace' else 'n:')+f'{self.ident:010d}'

    @classmethod
    def from_key(cls,value):
        if not isinstance(value,str) or not re.fullmatch(r'[wn]:[0-9]{10}',value):
            raise QueueError('Canonical execution partition key required')
        result=cls('workspace' if value[0]=='w' else 'native',int(value[2:]))
        if result.key!=value:raise QueueError('Canonical execution partition key required')
        return result

    @property
    def claim_options(self):
        return {'workspace_id' if self.kind=='workspace' else 'native_installation_id':self.ident}

    def slot_key(self,site,pool):
        _uuid(site)
        if pool not in ('urgent','bulk'):raise QueueError('Managed pool required')
        prefix='mp-job' if self.kind=='workspace' else 'mp-native-job'
        return int.from_bytes(hashlib.sha256(f'{prefix}:{site}:{pool}:{self.ident}'.encode()).digest()[:8],'big',signed=True)


@dataclass(frozen=True)
class Claim:
    job_id: str
    generation: int
    owner: str
    budget_until: datetime | None = None
    ready_ms: int | None = None


@dataclass(frozen=True)
class JobSchedule:
    """Absolute timestamps for a scheduled occurrence, with a separate attempt budget."""
    run_at: datetime
    expires_at: datetime
    attempt_seconds: int

    def __post_init__(self):
        for name in ('run_at', 'expires_at'):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise QueueError('Timezone-aware schedule required')
            object.__setattr__(self, name, value.astimezone(timezone.utc))
        _bounded(self.attempt_seconds, 1, 3600)
        if not timedelta(seconds=self.attempt_seconds) <= self.expires_at-self.run_at <= timedelta(days=1):
            raise QueueError('Invalid job validity window')

    def wire(self):
        return dict(run_at=self.run_at.isoformat(), expires_at=self.expires_at.isoformat(),
                    attempt_seconds=self.attempt_seconds)

    @classmethod
    def from_wire(cls, value):
        if not isinstance(value, dict) or set(value) != {'run_at', 'expires_at', 'attempt_seconds'}:
            raise QueueError('Invalid job schedule')
        try:
            schedule = cls(datetime.fromisoformat(value['run_at']), datetime.fromisoformat(value['expires_at']),
                           value['attempt_seconds'])
        except (TypeError, ValueError, OverflowError):
            raise QueueError('Invalid job schedule') from None
        if value != schedule.wire():
            raise QueueError('Noncanonical job schedule')
        return schedule


class RetryJob(Exception):
    """A declared transient failure in a replay-safe job."""


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


def _reserve_identity(cr, identity):
    # An UPDATE on conflict is intentional. Under repeatable read a stale
    # transaction must fail if an archiver changed the row after its snapshot.
    cr.execute("""INSERT INTO mp_job_identity AS receipt
        (site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)
        DO UPDATE SET idempotency_key=receipt.idempotency_key
        RETURNING id,job_public_id,input_digest,release_digest,effect_mode""", identity)
    return cr.fetchone()


def enqueue(cr, scope, handler, version, payload, key, *, effect_mode='idempotent', max_attempts=5, timeout_seconds=120, deduplication=None, on_new=None, schedule=None, retain_identity=False):
    if not isinstance(scope, (DispatchScope, NativeDispatchScope)):
        raise QueueError('Validated private dispatch scope required')
    _name(handler); _bounded(version, 1, 1000); _bounded(max_attempts, 1, 16); _bounded(timeout_seconds, 1, 86400)
    if effect_mode not in {'idempotent', 'reconcile'} or not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', key):
        raise QueueError('Invalid job effect or deduplication policy')
    if schedule is not None and (not isinstance(schedule, JobSchedule) or not isinstance(payload, dict)
                                 or payload.get('schema_version') != 2 or payload.get('schedule') != schedule.wire()):
        raise QueueError('Scheduled dispatch envelope required')
    if on_new is not None and not callable(on_new):
        raise QueueError('Trusted new-job preflight callback required')
    data, digest = _json(payload)
    if deduplication is not None:
        _, digest = _json(deduplication)
    if schedule is not None:
        _, digest = _json(dict(input_digest=digest, schedule=schedule.wire()))
    generation = control(cr, scope.site_id, scope.release_digest)
    identity = [scope.site_id, scope.workspace_id, scope.actor_id, scope.installation_id, handler, version, key]
    if retain_identity:
        _, archived_id, archived_digest, archived_release, archived_effect = _reserve_identity(cr, identity)
        if archived_id is not None:
            if (archived_digest, archived_release, archived_effect) != (digest, scope.release_digest, effect_mode):
                raise QueueError('Job deduplication input or release conflict')
            return archived_id
    public_id = str(uuid4())
    cr.execute("""INSERT INTO mp_job(public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key,
        release_digest,payload,input_digest,effect_mode,state,attempts,max_attempts,claim_generation,dispatch_generation,
        available_at,deadline_at,cancel_requested,effect_started,progress,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,'pending',0,%s,0,%s,
                COALESCE(%s,timezone('UTC',clock_timestamp())),
                COALESCE(%s,timezone('UTC',clock_timestamp())+(%s*interval '1 second')),false,false,0,timezone('UTC',clock_timestamp()))
        ON CONFLICT(site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key) DO NOTHING RETURNING public_id""",
        [public_id, *identity, scope.release_digest, data, digest, effect_mode, max_attempts, generation,
         schedule.run_at.replace(tzinfo=None) if schedule else None,
         schedule.expires_at.replace(tzinfo=None) if schedule else None, timeout_seconds])
    inserted = cr.fetchone()
    if inserted:
        # Only the unique insertion winner validates new-work preconditions.
        # Caller must roll back this reservation if that callback fails.
        if schedule is not None:
            cr.execute("""SELECT deadline_at>timezone('UTC',clock_timestamp())
                AND available_at<=timezone('UTC',clock_timestamp())+interval '30 days'
                FROM mp_job WHERE public_id=%s""", [public_id])
            if not cr.fetchone()[0]:
                raise QueueError('Schedule expired or beyond scheduling horizon')
        if on_new is not None:on_new()
        return inserted[0]
    cr.execute("""SELECT public_id,input_digest,release_digest,effect_mode FROM mp_job
        WHERE site_id=%s AND workspace_id IS NOT DISTINCT FROM %s AND actor_id=%s AND installation_id=%s AND handler=%s AND handler_version=%s AND idempotency_key=%s""", identity)
    old = cr.fetchone()
    if not old or tuple(old[1:]) != (digest, scope.release_digest, effect_mode):
        raise QueueError('Job deduplication input or release conflict')
    return old[0]


_ARCHIVE_FIELDS = """id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key,
    public_id,input_digest,release_digest,effect_mode,state,COALESCE(finished_at,deadline_at)"""
_ARCHIVE_ELIGIBLE = """state IN ('completed','dead_letter','cancelled')
    AND effect_mode='idempotent' AND NOT effect_started
    AND deadline_at<=%s AND COALESCE(finished_at,deadline_at)<=%s"""


def _archive_cutoff(cutoff):
    if not isinstance(cutoff, datetime) or cutoff.utcoffset() is None:
        raise QueueError('Timezone-aware archive cutoff required')
    return cutoff.astimezone(timezone.utc).replace(tzinfo=None)


def terminal_archive_candidates(cr, site_id, *, cutoff, limit):
    """Read the bounded batch under the caller's dispatch control lock."""
    _uuid(site_id)
    _bounded(limit, 1, 1000)
    cutoff = _archive_cutoff(cutoff)
    cr.execute(f"""SELECT {_ARCHIVE_FIELDS} FROM mp_job
        WHERE site_id=%s AND {_ARCHIVE_ELIGIBLE}
        AND %s<=timezone('UTC',statement_timestamp())
        ORDER BY id LIMIT %s""", [site_id, cutoff, cutoff, cutoff, limit])
    return cr.fetchall()


def archive_terminal_jobs(cr, site_id, release_digest, *, cutoff, limit, expected=None):
    """Private bounded batch. The independently authorized caller commits."""
    control(cr, site_id, release_digest)
    candidates = terminal_archive_candidates(cr, site_id, cutoff=cutoff, limit=limit)
    if expected is not None and candidates != expected:
        raise QueueError('Reviewed archive batch changed')
    cutoff = _archive_cutoff(cutoff)
    archived = []
    for candidate in candidates:
        job_id, *identity = candidate[:8]
        receipt_id, previous_job, *_ = _reserve_identity(cr, identity)
        # The identity row always comes before the live row. Retry or
        # settlement could have changed eligibility since nomination.
        cr.execute(f"""SELECT {_ARCHIVE_FIELDS} FROM mp_job
            WHERE id=%s AND site_id=%s AND {_ARCHIVE_ELIGIBLE} FOR UPDATE""", [job_id, site_id, cutoff, cutoff])
        if previous_job is not None or cr.fetchone() != candidate:
            raise QueueError('Archive candidate changed or has an existing terminal record')
        job = candidate[8:]
        cr.execute("""UPDATE mp_job_identity
            SET job_public_id=%s,input_digest=%s,release_digest=%s,effect_mode=%s,
                terminal_state=%s,finished_at=%s,archived_at=timezone('UTC',clock_timestamp())
            WHERE id=%s""", [*job, receipt_id])
        cr.execute('DELETE FROM mp_job WHERE id=%s', [job_id])
        archived.append(job[0])
    return archived


def claim_guard_key(site,pool,workspace):
    """Separate key from the long-lived compute slot; no authority is granted."""
    _uuid(site);_bounded(workspace,1,2**31-1)
    if pool not in ('urgent','bulk'):raise QueueError('Explicit native pool required')
    return int.from_bytes(hashlib.sha256(f'mp-job-claim:{site}:{pool}:{workspace}'.encode()).digest()[:8],'big',signed=True)


def native_claim_guard_key(site,pool,installation):
    _uuid(site);_bounded(installation,1,2**31-1)
    if pool not in ('urgent','bulk'):raise QueueError('Explicit native pool required')
    return int.from_bytes(hashlib.sha256(f'mp-native-job-claim:{site}:{pool}:{installation}'.encode()).digest()[:8],'big',signed=True)


def claim(cr, site_id, release_digest, owner, handlers, *, lease_seconds=30, workspace_id=None, routes=None,pool=None, native_installation_id=None):
    _uuid(site_id); _uuid(owner); _bounded(lease_seconds, 1, 300)
    if not isinstance(handlers, (list, tuple)) or not 1 <= len(handlers) <= 100:
        raise QueueError('Explicit handler allowlist required')
    for name in handlers:
        _name(name)
    if workspace_id is not None:_bounded(workspace_id,1,2**31-1)
    if native_installation_id is not None:
        _bounded(native_installation_id,1,2**31-1)
        if workspace_id is not None:raise QueueError('Choose one execution partition')
    if routes is not None:
        if not isinstance(routes,(list,tuple)) or not 1<=len(routes)<=100:
            raise QueueError('Explicit versioned handler routes required')
        routes=[f'{_name(name)}:{_bounded(version,1,1000)}' for name,version in routes]
    partition = ('workspace_id IS NULL AND installation_id=%s' if native_installation_id is not None
                 else 'workspace_id=COALESCE(%s,workspace_id)')
    filters=[site_id,release_digest,list(handlers),routes,routes,
             native_installation_id if native_installation_id is not None else workspace_id]
    if pool is not None:
        if (workspace_id is None and native_installation_id is None) or routes is None:
            raise QueueError('Pooled claims require an execution partition and registered routes')
        key=(native_claim_guard_key(site_id,pool,native_installation_id) if native_installation_id is not None
             else claim_guard_key(site_id,pool,workspace_id))&(2**64-1)
        cr.execute("""SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid()
            AND classid::bigint=%s AND objid::bigint=%s AND objsubid=1 AND granted AND mode='ExclusiveLock')""",[key>>32,key&0xffffffff])
        if not cr.fetchone()[0]:raise QueueError('Fresh-cursor pooled claim guard required')
    generation = control(cr, site_id, release_digest)
    # Lease loss is observable state. Reconcile uncertain non-idempotent work;
    # never reinterpret an expired external attempt as proof of rollback.
    cr.execute("""WITH expired AS (SELECT id FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
        AND (%s::text[] IS NULL OR handler||':'||handler_version=ANY(%s::text[])) AND {partition}
        AND state='running' AND lease_until<=timezone('UTC',clock_timestamp()) FOR UPDATE SKIP LOCKED)
        UPDATE mp_job j SET state=CASE WHEN effect_mode='reconcile' AND effect_started THEN 'outcome_unknown'
            WHEN cancel_requested THEN 'cancelled' WHEN attempts>=max_attempts OR deadline_at<=timezone('UTC',clock_timestamp())
            THEN 'dead_letter' ELSE 'retry' END,
            error_code='LEASE_EXPIRED',lease_owner=NULL,lease_until=NULL,available_at=timezone('UTC',clock_timestamp())
        FROM expired WHERE j.id=expired.id""".format(partition=partition), filters)
    if pool is not None:
        # Include expired but row-locked attempts: a concurrent heartbeat or
        # finalization may still be settling them. The reaper above handles
        # expired unlocked rows. Never admit a different valid claim while
        # any previous running row remains in this workspace/pool.
        cr.execute("""SELECT 1 FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
            AND (%s::text[] IS NULL OR handler||':'||handler_version=ANY(%s::text[]))
            AND {partition} AND state='running' LIMIT 1""".format(partition=partition),filters)
        if cr.fetchone():return None
    cr.execute("""WITH expired AS (SELECT id FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
        AND (%s::text[] IS NULL OR handler||':'||handler_version=ANY(%s::text[])) AND {partition}
        AND state IN ('pending','retry') AND deadline_at<=timezone('UTC',clock_timestamp()) FOR UPDATE SKIP LOCKED)
        UPDATE mp_job j SET state='dead_letter',error_code='DEADLINE_EXCEEDED',finished_at=timezone('UTC',clock_timestamp())
        FROM expired WHERE j.id=expired.id""".format(partition=partition), filters)
    cr.execute("""WITH stamp AS (SELECT timezone('UTC',clock_timestamp()) AS now),
        next AS (SELECT id,CASE WHEN payload->>'schema_version'='2'
            THEN LEAST(deadline_at,stamp.now+((payload->'schedule'->>'attempt_seconds')::integer*interval '1 second'))
            END AS budget_until,stamp.now,available_at FROM mp_job CROSS JOIN stamp
        WHERE site_id=%s AND release_digest=%s AND handler=ANY(%s)
        AND (%s::text[] IS NULL OR handler||':'||handler_version=ANY(%s::text[])) AND {partition}
        AND state IN ('pending','retry') AND NOT cancel_requested AND attempts<max_attempts
        AND available_at<=timezone('UTC',clock_timestamp()) AND deadline_at>timezone('UTC',clock_timestamp())
        ORDER BY available_at,id FOR UPDATE OF mp_job SKIP LOCKED LIMIT 1)
        UPDATE mp_job j SET state='running',attempts=attempts+1,claim_generation=claim_generation+1,
            dispatch_generation=%s,lease_owner=%s,lease_until=LEAST(j.deadline_at,next.budget_until,next.now+(%s*interval '1 second')),
            effect_started=false,error_code=NULL FROM next WHERE j.id=next.id
        RETURNING j.public_id,j.claim_generation,next.budget_until,
            (extract(epoch FROM (next.now-next.available_at))*1000)::bigint""".format(partition=partition),
        [*filters,generation,owner,lease_seconds])
    row = cr.fetchone()
    return Claim(row[0], row[1], owner, row[2], max(0,row[3])) if row else None


def ready_workspaces(cr,site,release,routes,*,after=None):
    """Bounded lane candidates; the lane holds a session slot before claiming."""
    control(cr,site,release)
    keys=[f'{_name(name)}:{_bounded(version,1,1000)}' for name,version in routes]
    if after is not None:_bounded(after,0,2**31-1)
    order='min(available_at),workspace_id' if after is None else '(workspace_id<=%s),workspace_id'
    cr.execute("""SELECT workspace_id FROM mp_job WHERE site_id=%s AND release_digest=%s
        AND handler||':'||handler_version=ANY(%s) AND workspace_id IS NOT NULL
        AND ((state IN ('pending','retry') AND LEAST(available_at,deadline_at)<=timezone('UTC',clock_timestamp()))
            OR (state='running' AND lease_until<=timezone('UTC',clock_timestamp())))
        GROUP BY workspace_id ORDER BY """+order+' LIMIT 64', [site,release,keys]+([] if after is None else [after]))
    return [row[0] for row in cr.fetchall()]


def ready_partitions(cr,site,release,routes,*,after=''):
    """Bounded cyclic selection across both kinds; a hint conveys no authority."""
    control(cr,site,release)
    if after:ExecutionPartition.from_key(after)
    keys=[f'{_name(name)}:{_bounded(version,1,1000)}' for name,version in routes]
    cr.execute("""SELECT partition FROM (
        SELECT CASE WHEN workspace_id IS NULL THEN 'n:'||lpad(installation_id::text,10,'0')
            ELSE 'w:'||lpad(workspace_id::text,10,'0') END AS partition
        FROM mp_job WHERE site_id=%s AND release_digest=%s AND handler||':'||handler_version=ANY(%s)
        AND ((state IN ('pending','retry') AND LEAST(available_at,deadline_at)<=timezone('UTC',clock_timestamp()))
             OR (state='running' AND lease_until<=timezone('UTC',clock_timestamp())))
        GROUP BY partition
        ) ready ORDER BY (partition<=%s),partition LIMIT 64""",[site,release,keys,after])
    return [ExecutionPartition.from_key(row[0]) for row in cr.fetchall()]


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
    _bounded(lease_seconds, 1, 300); _bounded(progress, 0, 99); row = _lock(cr, value)
    if isinstance(row['payload'],dict) and row['payload'].get('schema_version') == 2 and value.budget_until is None:
        raise ClaimLost('Scheduled claim budget required')
    cr.execute("""UPDATE mp_job SET lease_until=LEAST(deadline_at,%s::timestamp,
        timezone('UTC',clock_timestamp())+(%s*interval '1 second')),progress=GREATEST(progress,%s)
        WHERE public_id=%s""", [value.budget_until, lease_seconds, progress, value.job_id])


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
        WHERE public_id=%s AND actor_id=%s AND workspace_id IS NOT DISTINCT FROM %s AND state IN ('pending','retry','running','held') RETURNING public_id""", [job_id, actor_id, workspace_id])
    return bool(cr.fetchone())


def cancel_scheduled(cr, job_id, *, actor_id, workspace_id):
    """Fence database apply immediately and preserve any possible remote effect."""
    _uuid(job_id)
    cr.execute("""UPDATE mp_job SET cancel_requested=true,
        state=CASE WHEN effect_mode='reconcile' AND effect_started THEN 'outcome_unknown' ELSE 'cancelled' END,
        error_code=CASE WHEN effect_mode='reconcile' AND effect_started THEN 'CANCELLED' ELSE NULL END,
        lease_owner=NULL,lease_until=NULL,finished_at=timezone('UTC',clock_timestamp())
        WHERE public_id=%s AND actor_id=%s AND workspace_id IS NOT DISTINCT FROM %s AND payload->>'schema_version'='2'
        AND state IN ('pending','retry','running','held') RETURNING public_id""", [job_id, actor_id, workspace_id])
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
