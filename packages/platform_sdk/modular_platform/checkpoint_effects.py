"""Read-only semantic core-effect footprint for completed-checkpoint recovery.

Only normal lifecycle epoch rewrites are ignored. Results, claims, receipts,
deliveries, consumer state and compact history remain exact. This cannot prove
arbitrary trusted native code had no effects outside the supported platform.
"""
import re
from uuid import UUID

from .dispatch_lifecycle import observe, PHYSICAL_SCHEMA
from .dispatch_operator import DispatchMaintenance
from .operator_os import OperatorError
from .plans import data_digest


POLICY = 'native-checkpoint-effects-v1'
EPOCH_FIELDS = {
    'mp_job': ('release_digest', 'dispatch_generation', 'claim_generation'),
    'mp_outbox': ('release_digest', 'dispatch_generation'),
}


def _table_sql(table):
    # No caller- or artifact-selected SQL identifiers or exclusion policy.
    if table not in EPOCH_FIELDS:
        raise OperatorError('Only fixed core epoch-bearing tables are supported')
    names = ','.join("'"+name+"'" for name in EPOCH_FIELDS[table])
    return ("SELECT count(*),encode(sha256(convert_to(COALESCE(string_agg("
            "encode(sha256(convert_to((to_jsonb(t)-ARRAY["+names+"])::text,'UTF8')),'hex'),"
            "'' ORDER BY id),''),'UTF8')),'hex') FROM public."+table+' t')


def observe_effects(cr, scope):
    cr.execute('SHOW transaction_isolation')
    if cr.fetchone()[0] not in {'repeatable read','serializable'}:
        raise OperatorError('Effect comparison requires a consistent transaction snapshot')
    cr.execute('SHOW transaction_read_only')
    if cr.fetchone()[0] != 'on':
        raise OperatorError('Effect inspection requires an explicit read-only transaction')
    snapshot = DispatchMaintenance.require_native(observe(cr, scope))
    tables = snapshot.get('tables')
    if (not isinstance(tables,dict) or not {'mp_dispatch_control','mp_job','mp_outbox'} <= tables.keys()
            or not tables.keys() <= PHYSICAL_SCHEMA.keys()
            or snapshot['schema_digest'] != data_digest({name:PHYSICAL_SCHEMA[name] for name in tables})):
        raise OperatorError('Exact known core-effect schema is required')
    if snapshot.get('job_states',{}).get('running',0):
        raise OperatorError('Running native claims must be reconciled before checkpoint recovery')
    if 'mp_event_delivery' in tables:
        cr.execute("SELECT count(*) FROM public.mp_event_delivery WHERE state='leased'")
        if cr.fetchone()[0]:
            raise OperatorError('Leased event delivery requires independent effect reconciliation')
    semantic = {name:dict(value) for name,value in tables.items() if name != 'mp_dispatch_control'}
    for table in EPOCH_FIELDS:
        cr.execute(_table_sql(table))
        count, digest = cr.fetchone()
        if type(count) is not int or count != tables[table]['rows']:
            raise OperatorError('Core-effect rows changed during snapshot inspection')
        semantic[table] = dict(rows=count,sha256=digest)
    body = dict(policy=POLICY,site_id=scope.site_id,schema_digest=snapshot['schema_digest'],tables=semantic)
    packet = body | dict(digest=data_digest(body))
    validate_footprint(packet)
    return packet


def validate_footprint(value):
    if (not isinstance(value,dict) or set(value) != {'policy','site_id','schema_digest','tables','digest'}
            or value['policy'] != POLICY or not isinstance(value['tables'],dict)
            or not {'mp_job','mp_outbox'} <= value['tables'].keys()
            or 'mp_dispatch_control' in value['tables'] or not value['tables'].keys() <= PHYSICAL_SCHEMA.keys()):
        raise OperatorError('Exact semantic core-effect footprint required')
    try:
        if not isinstance(value['site_id'],str) or str(UUID(value['site_id'])) != value['site_id']:
            raise ValueError()
    except (ValueError,AttributeError):
        raise OperatorError('Canonical core-effect site identity required') from None
    expected = {'mp_dispatch_control':PHYSICAL_SCHEMA['mp_dispatch_control']}
    expected.update({name:PHYSICAL_SCHEMA[name] for name in value['tables']})
    if value['schema_digest'] != data_digest(expected):
        raise OperatorError('Core-effect footprint schema does not match known tables')
    for row in value['tables'].values():
        if (not isinstance(row,dict) or set(row) != {'rows','sha256'} or type(row['rows']) is not int or row['rows'] < 0
                or not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):
            raise OperatorError('Invalid core-effect table footprint')
    if value['digest'] != data_digest({key:item for key,item in value.items() if key != 'digest'}):
        raise OperatorError('Core-effect footprint digest changed')
    return value


def require_same_effects(checkpoint, source):
    validate_footprint(checkpoint); validate_footprint(source)
    if checkpoint != source:
        raise OperatorError('Checkpoint and current semantic effects differ; keep restored traffic and workers closed')
