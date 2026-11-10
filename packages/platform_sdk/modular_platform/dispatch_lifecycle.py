"""Private native dispatch inspection/fencing for the independent operator.

Caller owns connection, transaction, site/deployment locks and authorization.
No commits, business-model writes, public RPC or external-effect reconciliation.
Executor integration must bind these observations into its exact reviewed state.
"""
from dataclasses import dataclass
import hashlib
import re
from . import durable
from .plans import data_digest


class DispatchLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class LifecycleScope:
    site_id: str
    release_digest: str
    control_release: str | None = None
    reference: dict | None = None
    recurrence: dict | None = None


def _columns(*groups):
    result={'id':'int4'}
    for kind,names in groups:
        result.update({name:kind for name in names.split()})
    return result


SCHEMA={
 'mp_dispatch_control':_columns(('varchar','site_id release_digest state'),('int4','generation')),
 'mp_job':_columns(('varchar','public_id site_id handler release_digest input_digest idempotency_key effect_mode state lease_owner error_code'),('int4','workspace_id actor_id installation_id handler_version attempts max_attempts claim_generation dispatch_generation progress'),('jsonb','payload result'),('timestamp','lease_until available_at deadline_at created_at finished_at'),('bool','cancel_requested effect_started')),
 'mp_outbox':_columns(('varchar','public_id site_id plugin_id topic aggregate_id correlation_id causation_id release_digest state'),('int4','workspace_id actor_id installation_id schema_version aggregate_sequence dispatch_generation'),('timestamp','occurred_at'),('jsonb','payload')),
 'mp_event_subscription':_columns(('varchar','public_id site_id topic release_digest origin_installation_id idempotency_key input_digest state'),('int4','workspace_id actor_id installation_id'),('jsonb','binding'),('timestamp','created_at expires_at')),
 'mp_event_delivery':_columns(('varchar','public_id state receipt error_code'),('int4','subscription_id event_id generation attempts replays'),('timestamp','lease_until available_at acknowledged_at')),
 'mp_event_consumption':_columns(('varchar','public_id handler'),('int4','workspace_id actor_id installation_id event_id'),('timestamp','created_at')),
 'mp_event_consumer_state':_columns(('varchar','handler'),('int4','workspace_id installation_id generation')),
}
BASE=frozenset({'mp_dispatch_control','mp_job','mp_outbox'})
EVENTS=frozenset(SCHEMA)-BASE
# The public uninstall impact DTO continues to report its frozen table set.
# The independent lifecycle additionally recognizes this private registry.
JOB_IDENTITY = 'mp_job_identity'
EVENT_HISTORY = 'mp_event_history'
SCHEDULE_TABLE = 'mp_job_schedule'
OCCURRENCE_TABLE = 'mp_job_occurrence'
RECURRENCE = frozenset({SCHEDULE_TABLE, OCCURRENCE_TABLE})
COMPACT = frozenset({JOB_IDENTITY, EVENT_HISTORY, OCCURRENCE_TABLE})
PHYSICAL_SCHEMA = SCHEMA | {
    JOB_IDENTITY: _columns(
        ('varchar', 'site_id handler idempotency_key job_public_id input_digest release_digest effect_mode terminal_state'),
        ('int4', 'workspace_id actor_id installation_id handler_version'),
        ('timestamp', 'finished_at archived_at'),
    ),
    EVENT_HISTORY: _columns(('varchar', 'site_id kind public_id scope_key'),
                            ('int4', 'workspace_id'), ('jsonb', 'metadata'), ('timestamp', 'archived_at')),
    # Keep the host-injected lifecycle helper usable in retained older images
    # which do not contain the new recurrence module yet.
    SCHEDULE_TABLE: _columns(
        ('varchar','public_id site_id idempotency_key release_digest handler input_digest creation_digest state outstanding_job_id error_code'),
        ('int4','workspace_id actor_id installation_id handler_version config_version'),
        ('jsonb','rule payload last_tick'),
        ('timestamp','next_at considered_at last_tick_at created_at')),
    OCCURRENCE_TABLE: _columns(
        ('varchar','site_id schedule_id job_public_id input_digest release_digest'),
        ('int4','config_version'),('timestamp','nominal_at created_at')),
}
UNIQUE={
 'mp_dispatch_control':{('site_id',)},
 'mp_job':{('public_id',),('site_id','workspace_id','actor_id','installation_id','handler','handler_version','idempotency_key')},
 'mp_outbox':{('public_id',)},
 'mp_event_subscription':{('public_id',),('site_id','workspace_id','actor_id','installation_id','idempotency_key')},
 'mp_event_delivery':{('public_id',),('subscription_id','event_id')},
 'mp_event_consumption':{('public_id',),('installation_id','workspace_id','handler','event_id')},
 'mp_event_consumer_state':{('installation_id','workspace_id','handler')},
 JOB_IDENTITY:{('id',),('job_public_id',),('site_id','workspace_id','actor_id','installation_id','handler','handler_version','idempotency_key')},
 EVENT_HISTORY:{('id',),('kind','public_id'),('site_id','kind','scope_key')},
 SCHEDULE_TABLE:{('id',),('public_id',),('site_id','workspace_id','actor_id','installation_id','idempotency_key')},
 OCCURRENCE_TABLE:{('id',),('job_public_id',),('site_id','schedule_id','nominal_at')},
}
JOB_STATES=frozenset({'pending','running','retry','completed','dead_letter','cancelled','outcome_unknown','held'})
UNFINISHED=('pending','running','retry','held','outcome_unknown')
MAX_ROWS=100000


def reference_policy(cr,scope):
    """Opaque external reference policy; only a reviewed host source may supply it.

    The generic SDK deliberately has no fixed application/profile identity. A
    private optional reference source overrides this function in the fenced child
    and returns the exact profile and policy digest after independent validation.
    """
    raise DispatchLifecycleError('External reference profile requires an optional reviewed operator source')


def _scope(cr,scope):
    if not isinstance(scope,LifecycleScope):raise DispatchLifecycleError('Typed independent lifecycle scope required')
    if scope.reference is not None and scope.recurrence is not None:
        raise DispatchLifecycleError('Combined reference and recurrence maintenance is not qualified')
    try:durable._uuid(scope.site_id)
    except durable.QueueError:raise DispatchLifecycleError('Canonical lifecycle site required') from None
    if not isinstance(scope.release_digest,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',scope.release_digest):
        raise DispatchLifecycleError('Exact lifecycle release required')
    if scope.control_release is not None and (not isinstance(scope.control_release,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',scope.control_release)):
        raise DispatchLifecycleError('Exact prior control release required')
    cr.execute("SELECT key,value FROM ir_config_parameter WHERE key IN ('mp.site_id','mp.release_digest')")
    if dict(cr.fetchall())!={'mp.site_id':scope.site_id,'mp.release_digest':scope.release_digest}:
        raise DispatchLifecycleError('Lifecycle site or published release changed')


def _schema(cr):
    cr.execute("""SELECT c.relname,a.attname,t.typname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
        JOIN pg_type t ON t.oid=a.atttypid WHERE n.nspname='public' AND c.relname=ANY(%s)
        AND a.attnum>0 AND NOT a.attisdropped AND c.relkind='r' ORDER BY c.relname,a.attnum""",[list(PHYSICAL_SCHEMA)])
    actual={}
    for table,column,kind in cr.fetchall():actual.setdefault(table,{})[column]=kind
    if not actual:return None
    tables=set(actual)
    live = tables-COMPACT-{SCHEDULE_TABLE}
    if (live not in (BASE,frozenset(SCHEMA)) or any(actual[t]!=PHYSICAL_SCHEMA[t] for t in tables)
            or EVENT_HISTORY in tables and (JOB_IDENTITY not in tables or not EVENTS<=live)
            or RECURRENCE.intersection(tables) and not (RECURRENCE|{JOB_IDENTITY,EVENT_HISTORY}<=tables and EVENTS<=live)):
        raise DispatchLifecycleError('Unknown or partial native dispatch schema')
    cr.execute("""SELECT c.relname,ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY AS q(attnum,ord)
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=q.attnum ORDER BY q.ord)
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname=ANY(%s) AND k.contype IN ('u','p')""",[sorted(tables)])
    found={t:set() for t in tables}
    for table,columns in cr.fetchall():found[table].add(tuple(columns))
    if any(not UNIQUE[t]<=found[t] for t in tables):raise DispatchLifecycleError('Native dispatch deduplication constraint missing')
    return sorted(tables)


def _control(cr,scope,*,lock=False):
    cr.execute('SELECT site_id,release_digest,state,generation FROM mp_dispatch_control'+(' FOR UPDATE' if lock else ''))
    rows=cr.fetchall()
    if not rows:return None
    if len(rows)!=1:raise DispatchLifecycleError('Unexpected dispatch site footprint')
    site,release,state,generation=rows[0]
    if site!=scope.site_id or release!=(scope.control_release or scope.release_digest) or state not in {'enabled','paused','restoring'} or type(generation) is not int or not 0<generation<2**31:
        raise DispatchLifecycleError('Dispatch identity, release or generation mismatch')
    return dict(site_id=site,release_digest=release,state=state,generation=generation)


def _table(cr,table):
    # table is selected only from the static schema, never an artifact/input.
    assert table in PHYSICAL_SCHEMA and table not in COMPACT
    cr.execute('SELECT count(*) FROM public.'+table);count=cr.fetchone()[0]
    if count>MAX_ROWS:raise DispatchLifecycleError('Dispatch profile row bound exceeded; independent reconciliation required')
    cr.execute("SELECT encode(sha256(convert_to(COALESCE(string_agg(encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex'),'' ORDER BY id),''),'UTF8')),'hex') FROM public."+table+' t')
    return dict(rows=count,sha256=cr.fetchone()[0])


def history_pressure(cr, scope):
    """Return bounded table counts even when the lifecycle snapshot refuses."""
    _scope(cr, scope)
    tables = _schema(cr)
    if tables is None:
        raise DispatchLifecycleError('Native dispatch schema unavailable')
    _control(cr, scope)
    warning_rows = MAX_ROWS * 4 // 5
    report = {}
    for table in tables:
        if table in COMPACT:
            continue  # The compact registry is not subject to the live cap.
        # _schema admits only known names. A large table costs at most one
        # more visible row than the lifecycle can accept.
        cr.execute(
            'SELECT count(*) FROM (SELECT 1 FROM public.' + table + ' LIMIT %s) AS bounded',
            [MAX_ROWS + 1],
        )
        rows, = cr.fetchone()
        if rows > MAX_ROWS:
            status = 'over_limit'
        elif rows == MAX_ROWS:
            status = 'at_limit'
        elif rows >= warning_rows:
            status = 'approaching_limit'
        else:
            status = 'below_warning'
        report[table] = dict(
            rows_observed=rows,
            count_is_lower_bound=rows > MAX_ROWS,
            rows_until_limit=max(0, MAX_ROWS - rows),
            status=status,
        )
    return dict(row_limit=MAX_ROWS, warning_rows=warning_rows, tables=report)


def _identity_snapshot(cr, site_id, table=JOB_IDENTITY):
    """Hash in primary-key pages without applying the live queue row cap."""
    assert table in COMPACT
    digest = hashlib.sha256()
    position = -(2**31) - 1
    rows = 0
    while True:
        cr.execute(f"""SELECT count(*),max(id),
            count(*) FILTER (WHERE id<=0 OR site_id IS DISTINCT FROM %s),
            string_agg(encode(sha256(convert_to(to_jsonb(page)::text,'UTF8')),'hex'),'' ORDER BY id)
            FROM (SELECT * FROM public.{table} WHERE id>%s ORDER BY id LIMIT 4096) page""",
            [site_id, position])
        count, last, foreign, hashes = cr.fetchone()
        if foreign:
            raise DispatchLifecycleError('Invalid compact history row or scope')
        if not count:
            break
        digest.update(hashes.encode('ascii'))
        rows += count
        position = last
    return dict(rows=rows, sha256=digest.hexdigest())


def observe(cr,scope,*,lock=False):
    """Consistent caller-owned transaction required; returns no raw payloads."""
    _scope(cr,scope);tables=_schema(cr)
    if tables is None:return None
    if lock:
        cr.execute('SHOW transaction_isolation')
        if cr.fetchone()[0]!='read committed':
            raise DispatchLifecycleError('Drain requires a fresh read-committed transaction after native lock waits')
    control=_control(cr,scope,lock=lock)
    if lock:
        # Native writers hold a shared control row through business commit.
        # Only take these metadata table locks after that row wait finishes.
        # READ COMMITTED ensures the new snapshot includes a producer which
        # committed while we waited; a pre-wait repeatable-read snapshot can
        # miss its newly committed queue rows without a serialization error.
        cr.execute('LOCK TABLE '+','.join(tables)+' IN SHARE ROW EXCLUSIVE MODE')
    snapshots={table:(_identity_snapshot(cr,scope.site_id,table) if table in COMPACT else _table(cr,table)) for table in tables}
    if control is None and any(value['rows'] for value in snapshots.values()):
        raise DispatchLifecycleError('Missing dispatch control for populated queues')
    cr.execute("SELECT state,count(*) FROM mp_job GROUP BY state");states=dict(cr.fetchall())
    if not set(states)<=JOB_STATES:raise DispatchLifecycleError('Unknown native job outcome')
    for table in ['mp_job','mp_outbox']+(['mp_event_subscription'] if EVENTS<=set(tables) else [])+([SCHEDULE_TABLE] if SCHEDULE_TABLE in tables else []):
        cr.execute('SELECT count(*) FROM '+table+' WHERE site_id<>%s OR site_id IS NULL',[scope.site_id])
        if cr.fetchone()[0]:raise DispatchLifecycleError('Foreign native dispatch scope')
    cr.execute("SELECT count(*) FROM mp_outbox WHERE state NOT IN ('pending','published','held')")
    if cr.fetchone()[0]:raise DispatchLifecycleError('Unknown native outbox state')
    if EVENTS<=set(tables):
        cr.execute("SELECT count(*) FROM mp_event_subscription WHERE state NOT IN ('active','closed')")
        if cr.fetchone()[0]:raise DispatchLifecycleError('Unknown subscription state')
        cr.execute("""SELECT count(*) FROM mp_event_delivery d JOIN mp_event_subscription s ON s.id=d.subscription_id
            JOIN mp_outbox o ON o.id=d.event_id WHERE s.site_id<>o.site_id OR s.workspace_id<>o.workspace_id
            OR s.topic<>o.topic OR d.state NOT IN ('pending','leased','acknowledged','dead_letter')""")
        if cr.fetchone()[0]:raise DispatchLifecycleError('Unknown or foreign event delivery')
    cr.execute("SELECT count(*) FROM mp_plugin_installation WHERE runtime<>'native'");external=cr.fetchone()[0]
    cr.execute("SELECT count(*) FROM mp_service_credential WHERE state='active'");credentials=cr.fetchone()[0]
    cr.execute('SELECT count(*) FROM res_users_apikeys');keys=cr.fetchone()[0]
    cr.execute("SELECT count(*) FROM mp_job WHERE state='outcome_unknown' OR (effect_mode='reconcile' AND effect_started AND state NOT IN ('completed','cancelled','dead_letter'))");uncertain=cr.fetchone()[0]
    body=dict(profile='r1-native-dispatch-v1',site_id=scope.site_id,release_digest=scope.release_digest,
        schema_digest=data_digest({table:PHYSICAL_SCHEMA[table] for table in tables}),control=control,tables=snapshots,
        job_states=states,event_receipts=EVENTS<=set(tables),external_installations=external,active_credentials=credentials,api_keys=keys,uncertain_jobs=uncertain)
    if SCHEDULE_TABLE in tables:
        cr.execute("SELECT count(*) FROM mp_job_schedule WHERE state NOT IN ('active','paused','held')")
        if cr.fetchone()[0]:raise DispatchLifecycleError('Unknown recurring schedule state')
        body['recurring_schedules']=snapshots[SCHEDULE_TABLE]['rows']
    if scope.reference is not None:
        policy=reference_policy(cr,scope)
        if (not isinstance(policy,dict) or set(policy)!={'profile','digest'}
                or not isinstance(policy['profile'],str) or not re.fullmatch(r'[a-z0-9-]+',policy['profile'])
                or not isinstance(policy['digest'],str) or not re.fullmatch('sha256:[0-9a-f]{64}',policy['digest'])):
            raise DispatchLifecycleError('Exact external reference policy result required')
        body.update(profile=policy['profile'],reference_policy_digest=policy['digest'])
    if scope.recurrence is not None:
        if not RECURRENCE<=set(tables) or external or keys:
            raise DispatchLifecycleError('Known native recurrence schema without external registrations or API keys required')
        from .recurrence_authority import validate
        approved=validate(cr,scope.site_id,scope.recurrence)
        if approved['active_credentials']!=credentials:
            raise DispatchLifecycleError('Recurrence credentials changed during inspection')
        body.update(profile='r1-native-recurring-dispatch-v1',recurrence_policy_digest=data_digest(scope.recurrence))
    return body|dict(state_digest=data_digest(body))


def fence(cr,scope,operation_id,*,state='paused'):
    """Fence metadata atomically; caller must persist/commit its operator record.

    Every call deliberately advances generations, including already paused sites.
    An interrupted operator must reconcile the saved observation, never assume a
    repeated fence is its original operation. No claim of remote rollback.
    """
    try:durable._uuid(operation_id)
    except durable.QueueError:raise DispatchLifecycleError('Canonical operation correlation required') from None
    if state not in {'paused','restoring'}:raise DispatchLifecycleError('Closed dispatch state required')
    before=observe(cr,scope,lock=True)
    if before is None:return None
    if before.get('recurring_schedules',0) and scope.recurrence is None:
        raise DispatchLifecycleError('Recurring schedules require the independently reviewed recurrence maintenance profile')
    if before['external_installations'] and scope.reference is None or before['active_credentials'] and scope.recurrence is None or before['api_keys']:
        raise DispatchLifecycleError('External effects or live technical credentials require the external reconciliation profile')
    if before['control'] and before['control']['generation']>=2**31-1:
        raise DispatchLifecycleError('Dispatch generation exhausted')
    cr.execute('SELECT count(*) FROM mp_job WHERE state=ANY(%s) AND claim_generation>=%s',[list(UNFINISHED),2**31-1])
    if cr.fetchone()[0]:raise DispatchLifecycleError('Job claim generation exhausted')
    if before['event_receipts']:
        cr.execute("SELECT count(*) FROM mp_event_delivery WHERE state='leased' AND generation>=%s",[2**31-1])
        if cr.fetchone()[0]:raise DispatchLifecycleError('Event receipt generation exhausted')
    cr.execute("""INSERT INTO mp_dispatch_control(site_id,release_digest,state,generation) VALUES(%s,%s,%s,1)
        ON CONFLICT(site_id) DO UPDATE SET release_digest=EXCLUDED.release_digest,state=EXCLUDED.state,generation=mp_dispatch_control.generation+1
        RETURNING generation""",[scope.site_id,scope.release_digest,state]);generation=cr.fetchone()[0]
    cr.execute("""UPDATE mp_job SET state=CASE WHEN effect_mode='reconcile' AND (effect_started OR state='outcome_unknown')
        THEN 'outcome_unknown' WHEN cancel_requested THEN 'cancelled' ELSE 'held' END,
        claim_generation=claim_generation+1,dispatch_generation=%s,lease_owner=NULL,lease_until=NULL,
        error_code=COALESCE(error_code,'DEPENDENCY_UNAVAILABLE') WHERE state=ANY(%s)""",[generation,list(UNFINISHED)])
    if before['event_receipts']:
        cr.execute("UPDATE mp_event_subscription SET state='closed' WHERE state='active'")
        cr.execute("""UPDATE mp_event_delivery SET state=CASE WHEN attempts>=5 THEN 'dead_letter' ELSE 'pending' END,
            generation=generation+1,receipt=NULL,lease_until=NULL,error_code='ACK_EXPIRED',
            available_at=timezone('UTC',clock_timestamp()) WHERE state='leased'""")
    after=observe(cr,LifecycleScope(scope.site_id,scope.release_digest,reference=scope.reference,recurrence=scope.recurrence))
    for table in ['mp_outbox','mp_event_consumption','mp_event_consumer_state',*sorted(COMPACT)]:
        if table in before['tables'] and before['tables'][table]!=after['tables'][table]:
            raise DispatchLifecycleError('Fencing changed producer or consumer history')
    return dict(operation_id=operation_id,before=before,after=after,requires_reviewed_resume=True)


def enable(cr,scope,expected_digest):
    """After independent caller approval and persisted current reconciliation.

    The caller must record the conservative 'effects may resume' journal fence
    BEFORE committing this transaction, including when ingress is still closed.
    """
    before=observe(cr,scope,lock=True)
    if before and before.get('recurring_schedules',0) and scope.recurrence is None:
        raise DispatchLifecycleError('Recurring schedules require the independently reviewed recurrence resume profile')
    if (before is None or before['state_digest']!=expected_digest or not before['control']
            or before['control']['state']!='paused' or before['control']['release_digest']!=scope.release_digest
            or before['control']['generation']>=2**31-1):
        raise DispatchLifecycleError('Exact paused dispatch snapshot required before resume')
    if (before['external_installations'] and scope.reference is None or before['active_credentials'] and scope.recurrence is None or before['api_keys']
            or before['job_states'].get('running') or before['job_states'].get('outcome_unknown')):
        raise DispatchLifecycleError('Unreconciled effects or credentials prevent native dispatch resume')
    cr.execute("SELECT count(*) FROM mp_job WHERE (state IN ('pending','retry') AND (release_digest<>%s OR effect_mode<>'idempotent')) OR (effect_mode='reconcile' AND effect_started AND state NOT IN ('completed','cancelled','dead_letter'))",[scope.release_digest])
    if cr.fetchone()[0]:raise DispatchLifecycleError('Pending work requires explicit current-release effect reconciliation')
    if before['event_receipts']:
        cr.execute("SELECT count(*) FROM mp_event_subscription WHERE state='active'")
        if cr.fetchone()[0]:raise DispatchLifecycleError('Obsolete event subscriptions remain active')
        cr.execute("SELECT count(*) FROM mp_event_delivery WHERE state='leased'")
        if cr.fetchone()[0]:raise DispatchLifecycleError('Obsolete event receipts remain leased')
    durable.set_control(cr,scope.site_id,scope.release_digest,'enabled')
    return dict(before=before,after=observe(cr,LifecycleScope(scope.site_id,scope.release_digest,reference=scope.reference,recurrence=scope.recurrence)),dispatch_enabled=True)
