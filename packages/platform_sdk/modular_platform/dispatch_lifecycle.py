"""Private native dispatch inspection/fencing for the independent operator.

Caller owns connection, transaction, site/deployment locks and authorization.
No commits, business-model writes, public RPC or external-effect reconciliation.
Executor integration must bind these observations into its exact reviewed state.
"""
from dataclasses import dataclass
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
UNIQUE={
 'mp_dispatch_control':{('site_id',)},
 'mp_job':{('public_id',),('site_id','workspace_id','actor_id','installation_id','handler','handler_version','idempotency_key')},
 'mp_outbox':{('public_id',)},
 'mp_event_subscription':{('public_id',),('site_id','workspace_id','actor_id','installation_id','idempotency_key')},
 'mp_event_delivery':{('public_id',),('subscription_id','event_id')},
 'mp_event_consumption':{('public_id',),('installation_id','workspace_id','handler','event_id')},
 'mp_event_consumer_state':{('installation_id','workspace_id','handler')},
}
JOB_STATES=frozenset({'pending','running','retry','completed','dead_letter','cancelled','outcome_unknown','held'})
UNFINISHED=('pending','running','retry','held','outcome_unknown')
MAX_ROWS=100000


def _reference(cr,scope):
    """Private OS-selected profile, never a DB flag or general remote allowlist.

    The host verifies catalog/release/publication provenance. This transaction
    checks its exact physical metadata footprint again, including tombstones.
    Supported authority is outbound-only, to the stateless reference worker.
    """
    value=scope.reference
    keys={'profile','site_id','runtime_image','publication_digest','registrations'}
    transition=value.get('worker_transition') if isinstance(value,dict) else None
    transitioning=isinstance(value,dict) and value.get('profile')=='r1-reference-stateless-transition-v1'
    if (not isinstance(value,dict) or set(value)!=(keys|{'worker_transition'} if transitioning else keys)
            or value['profile'] not in {'r1-reference-stateless-v1','r1-reference-stateless-transition-v1'}
            or value['site_id']!=scope.site_id or not isinstance(value['runtime_image'],str)
            or not re.fullmatch(r'modular-document-stats@sha256:[0-9a-f]{64}',value['runtime_image'])
            or not isinstance(value['publication_digest'],str) or not re.fullmatch('sha256:[0-9a-f]{64}',value['publication_digest'])
            or not isinstance(value['registrations'],list) or len(value['registrations'])>256):
        raise DispatchLifecycleError('Exact independently selected reference profile required')
    if transitioning:
        fields={'operation_id','plan_hash','installation_id','base_version','base_artifact_digest','base_manifest_digest','base_image',
                'target_version','target_artifact_digest','target_manifest_digest','target_image','workspaces'}
        if not isinstance(transition,dict) or set(transition)!=fields:
            raise DispatchLifecycleError('Exact private reviewed image transition required')
        try:
            durable._uuid(transition['operation_id']);durable._uuid(transition['installation_id'])
            from packaging.version import Version
            if Version(transition['target_version'])<=Version(transition['base_version']):raise ValueError()
            for key in ('plan_hash','base_artifact_digest','base_manifest_digest','target_artifact_digest','target_manifest_digest'):
                if not re.fullmatch(r'sha256:[0-9a-f]{64}',transition[key]):raise ValueError()
            if (not re.fullmatch(r'modular-document-stats@sha256:[0-9a-f]{64}',transition['base_image'])
                    or transition['target_image']!=value['runtime_image'] or transition['base_image']==transition['target_image']
                    or not isinstance(transition['workspaces'],list) or not transition['workspaces']
                    or transition['workspaces']!=sorted(set(transition['workspaces']))):raise ValueError()
            for workspace in transition['workspaces']:durable._uuid(workspace)
        except (ValueError,TypeError,KeyError):raise DispatchLifecycleError('Invalid private reviewed image transition') from None
    expected=[]
    for row in value['registrations']:
        if (not isinstance(row,dict) or set(row)!={'installation_id','plugin_id','version','artifact_digest','manifest_digest','state','features'}
                or row['plugin_id']!='org.example.document_stats' or row['state'] not in {'installed','removed'}
                or any(not isinstance(row[k],str) or not re.fullmatch('sha256:[0-9a-f]{64}',row[k]) for k in ['artifact_digest','manifest_digest'])
                or not isinstance(row['features'],list) or len(row['features'])>256):
            raise DispatchLifecycleError('Unknown external registration is outside the reference profile')
        durable._uuid(row['installation_id'])
        for feature in row['features']:
            if (not isinstance(feature,dict) or set(feature)!={'workspace_id','feature_state'}
                    or feature['feature_state'] not in {'enabled','suspended'}
                    or row['state']=='removed' and feature['feature_state']!='suspended'):
                raise DispatchLifecycleError('Exact retained reference feature scope required')
            durable._uuid(feature['workspace_id'])
        if len({f['workspace_id'] for f in row['features']})!=len(row['features']):
            raise DispatchLifecycleError('Duplicate reference workspace scope')
        expected.append(row)
    if len({r['installation_id'] for r in expected})!=len(expected):raise DispatchLifecycleError('Duplicate reference installation')
    cr.execute("SELECT id,public_id,plugin_id,version,artifact_digest,state,manifest FROM mp_plugin_installation WHERE runtime<>'native' ORDER BY public_id")
    actual=[];used_transition=False
    for ident,public,plugin,version,digest,state,manifest in cr.fetchall():
        if (not isinstance(manifest,dict) or manifest.get('runtime')!={'kind':'external_service'}
                or not isinstance(manifest.get('external_service'),dict)
                or not re.fullmatch(r'modular-document-stats@sha256:[0-9a-f]{64}',manifest['external_service'].get('expected_image',''))):
            raise DispatchLifecycleError('External image/runtime differs from independently selected reference')
        cr.execute('''SELECT w.public_id,f.availability,f.plugin_id FROM mp_workspace_plugin f JOIN mp_workspace w ON w.id=f.workspace_id
            WHERE f.installation_id=%s ORDER BY w.public_id''',[ident])
        features=cr.fetchall()
        if any(p!=plugin for _,_,p in features):raise DispatchLifecycleError('Reference feature ownership changed')
        if state!='removed' and manifest['external_service']['expected_image']!=value['runtime_image']:
            if (not transitioning or used_transition or state!='installed' or public!=transition['installation_id']
                    or plugin!='org.example.document_stats' or version!=transition['base_version'] or digest!=transition['base_artifact_digest']
                    or data_digest(manifest)!=transition['base_manifest_digest'] or manifest['external_service']['expected_image']!=transition['base_image']
                    or sorted(w for w,_,_ in features)!=transition['workspaces'] or any(a!='suspended' for _,a,_ in features)):
                raise DispatchLifecycleError('External image/runtime differs from independently selected reference')
            used_transition=True
        actual.append(dict(installation_id=public,plugin_id=plugin,version=version,artifact_digest=digest,
            manifest_digest=data_digest(manifest),state=state,features=[dict(workspace_id=w,feature_state=a) for w,a,_ in features]))
    if actual!=sorted(expected,key=lambda r:r['installation_id']):
        raise DispatchLifecycleError('Reference metadata changed after independent observation')
    if transitioning and not used_transition:raise DispatchLifecycleError('Unused image transition proof cannot authorize another profile')
    return data_digest(value)


def _scope(cr,scope):
    if not isinstance(scope,LifecycleScope):raise DispatchLifecycleError('Typed independent lifecycle scope required')
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
        AND a.attnum>0 AND NOT a.attisdropped AND c.relkind='r' ORDER BY c.relname,a.attnum""",[list(SCHEMA)])
    actual={}
    for table,column,kind in cr.fetchall():actual.setdefault(table,{})[column]=kind
    if not actual:return None
    tables=set(actual)
    if not BASE<=tables or tables not in (BASE,frozenset(SCHEMA)) or any(actual[t]!=SCHEMA[t] for t in tables):
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
    assert table in SCHEMA
    cr.execute('SELECT count(*) FROM public.'+table);count=cr.fetchone()[0]
    if count>MAX_ROWS:raise DispatchLifecycleError('Dispatch profile row bound exceeded; independent reconciliation required')
    cr.execute("SELECT encode(sha256(convert_to(COALESCE(string_agg(encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex'),'' ORDER BY id),''),'UTF8')),'hex') FROM public."+table+' t')
    return dict(rows=count,sha256=cr.fetchone()[0])


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
    snapshots={table:_table(cr,table) for table in tables}
    if control is None and any(value['rows'] for value in snapshots.values()):
        raise DispatchLifecycleError('Missing dispatch control for populated queues')
    cr.execute("SELECT state,count(*) FROM mp_job GROUP BY state");states=dict(cr.fetchall())
    if not set(states)<=JOB_STATES:raise DispatchLifecycleError('Unknown native job outcome')
    for table in ['mp_job','mp_outbox']+(['mp_event_subscription'] if EVENTS<=set(tables) else []):
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
        schema_digest=data_digest({table:SCHEMA[table] for table in tables}),control=control,tables=snapshots,
        job_states=states,event_receipts=EVENTS<=set(tables),external_installations=external,active_credentials=credentials,api_keys=keys,uncertain_jobs=uncertain)
    if scope.reference is not None:
        body.update(profile='r1-reference-stateless-dispatch-v1',reference_policy_digest=_reference(cr,scope))
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
    if before['external_installations'] and scope.reference is None or before['active_credentials'] or before['api_keys']:
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
    after=observe(cr,LifecycleScope(scope.site_id,scope.release_digest,reference=scope.reference))
    for table in ['mp_outbox','mp_event_consumption','mp_event_consumer_state']:
        if table in before['tables'] and before['tables'][table]!=after['tables'][table]:
            raise DispatchLifecycleError('Fencing changed producer or consumer history')
    return dict(operation_id=operation_id,before=before,after=after,requires_reviewed_resume=True)


def enable(cr,scope,expected_digest):
    """After independent caller approval and persisted current reconciliation.

    The caller must record the conservative 'effects may resume' journal fence
    BEFORE committing this transaction, including when ingress is still closed.
    """
    before=observe(cr,scope,lock=True)
    if (before is None or before['state_digest']!=expected_digest or not before['control']
            or before['control']['state']!='paused' or before['control']['release_digest']!=scope.release_digest
            or before['control']['generation']>=2**31-1):
        raise DispatchLifecycleError('Exact paused dispatch snapshot required before resume')
    if (before['external_installations'] and scope.reference is None or before['active_credentials'] or before['api_keys']
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
    return dict(before=before,after=observe(cr,LifecycleScope(scope.site_id,scope.release_digest,reference=scope.reference)),dispatch_enabled=True)
