"""Current-authorized domain events; native bus wakes, durable receipts deliver."""
from dataclasses import dataclass
from datetime import datetime,timezone
import copy,json
from uuid import uuid4
import psycopg2,rfc8785
from jsonschema import Draft202012Validator
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable,event_store as store
from modular_platform.contracts import CONTRACTS,ContractError,FORMAT_CHECKER,validate
from .controllers import PublicError,result,bounded_body
from .dispatch import CallFrame,authorize_bound,authorize_origin
from .job_dispatch import _locked_scope

TOPICS={};CONSUMERS={}


@dataclass(frozen=True)
class Topic:
    ident:str
    plugin:str
    model:str
    service:str
    majors:tuple
    permission:str
    payload_schema:dict
    authorize_event:object
    method:str='get'
    validate_identity:object=None


@dataclass(frozen=True)
class Consumer:
    ident:str
    plugin:str
    topic:str
    permission:str
    authorize:object
    apply:object


@dataclass(frozen=True)
class ConsumerFrame:
    handler:str
    event_id:str
    workspace_id:int
    installation_id:int
    correlation_id:str


def register_topic(definition):
    if not isinstance(definition,Topic) or not definition.ident.startswith(definition.plugin+'.') or definition.ident in TOPICS:
        raise ValueError('Unique owned native topic required')
    durable._name(definition.ident);Draft202012Validator.check_schema(definition.payload_schema)
    if not callable(definition.authorize_event) or not definition.majors:raise ValueError('Native event authorization required')
    TOPICS[definition.ident]=definition


def register_consumer(definition):
    if not isinstance(definition,Consumer) or not definition.ident.startswith(definition.plugin+':') or definition.ident in CONSUMERS:
        raise ValueError('Unique owned native event consumer required')
    if not all(callable(fn) for fn in [definition.authorize,definition.apply]):raise ValueError('Explicit consumer authority/effect required')
    if not definition.permission.startswith(definition.plugin+':'):raise ValueError('Owned consumer permission required')
    CONSUMERS[definition.ident]=definition


def _utc(value):
    if isinstance(value,str):value=datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')


def _topic(ident):
    definition=TOPICS.get(ident)
    if not definition:raise PublicError('NOT_FOUND')
    return definition


def _authorize(env,definition,binding_id):
    scope=_locked_scope(env);release=current_release(env)
    try:durable._uuid(binding_id)
    except durable.QueueError:raise ContractError('Canonical event binding reference required') from None
    env.cr.execute("""SELECT b.descriptor,c.plugin_id,c.id FROM mp_service_binding b
        JOIN mp_plugin_installation c ON c.id=b.consumer_id
        WHERE b.public_id=%s AND b.workspace_id=%s AND b.state='active' FOR SHARE OF b,c""",[binding_id,scope.workspace_id])
    row=env.cr.fetchone()
    if not row:raise PublicError('DEPENDENCY_UNAVAILABLE')
    binding,plugin,installation_id=row
    frame=CallFrame(scope.principal_public_id,scope.workspace_public_id,release['site_id'],binding['consumer_installation_id'],plugin,())
    env=env(context={**env.context,'_mp_call_frame':frame})
    bound=authorize_bound(env,binding['alias'],definition.method);authorize_origin(env,scope,bound)
    if (bound.provider_plugin,bound.binding['service_id'])!=(definition.plugin,definition.service) or bound.binding['contract_major'] not in definition.majors:
        raise AccessError('Topic not granted by this binding')
    if bound.spec.action!='read' or bound.spec.permission!=definition.permission:raise AccessError('Registered read authority required')
    if request and request.db==env.cr.dbname:
        request._mp_consumer_id=bound.binding['consumer_installation_id'];request._mp_provider_id=bound.binding['provider_installation_id'];request._mp_provider_plugin=bound.provider_plugin
        label=request.httprequest.headers.get('X-MP-Consumer');request._mp_attribution_mismatch=bool(label and label!=bound.binding['consumer_installation_id'])
    storage=durable.DispatchScope(release['site_id'],scope.workspace_id,scope.principal_id,installation_id,release['release_digest'])
    return env,scope,bound,storage


def _subscription(env,ident,*,active=False,closing=False):
    scope=_locked_scope(env);release=current_release(env);durable._uuid(ident)
    env.cr.execute("SELECT binding,topic FROM mp_event_subscription WHERE public_id=%s AND site_id=%s AND workspace_id=%s AND actor_id=%s",[ident,release['site_id'],scope.workspace_id,scope.principal_id])
    row=env.cr.fetchone()
    if not row:raise PublicError('NOT_FOUND')
    old_binding,topic=row;env,scope,bound,storage=_authorize(env,_topic(topic),old_binding['binding_id'])
    # Match maintenance lock order: control before the mutable subscription.
    # Otherwise ACK/poll can hold this row while waiting for control, as drain
    # holds control while waiting to invalidate this row's receipt.
    if active:durable.control(env.cr,storage.site_id,storage.release_digest)
    elif closing:
        # Closing exposes no payload and remains valid while dispatch is
        # paused. Still take the same first lock to avoid a drain deadlock.
        env.cr.execute('SELECT generation FROM mp_dispatch_control WHERE site_id=%s AND release_digest=%s FOR SHARE',[storage.site_id,storage.release_digest])
        if not env.cr.fetchone():raise PublicError('DEPENDENCY_UNAVAILABLE')
    subscription=store.lock_subscription(env.cr,ident,storage,active=active)
    if not subscription:raise PublicError('NOT_FOUND')
    if subscription['binding']!=bound.binding or subscription['release_digest']!=storage.release_digest:
        raise PublicError('CONFLICT')
    if subscription['origin_installation_id']!=scope.authenticated_installation_id:raise AccessError('Event technical origin changed')
    return env,subscription,bound


def _envelope(env,definition,event,bound):
    if event['plugin_id']!=definition.plugin or event['schema_version']!=1:
        raise ContractError('Unsupported registered event payload')
    if not Draft202012Validator(definition.payload_schema,format_checker=FORMAT_CHECKER).is_valid(event['payload']):raise ContractError('Invalid registered event payload')
    if definition.validate_identity:definition.validate_identity(event['aggregate_id'],event['aggregate_sequence'],event['payload'])
    definition.authorize_event(env,event,bound)
    return dict(id=event['public_id'],topic=event['topic'],schema_version=event['schema_version'],owner_plugin_id=event['plugin_id'],aggregate_id=event['aggregate_id'],aggregate_sequence=event['aggregate_sequence'],site_id=event['site_id'],workspace_id=bound.binding['workspace_id'],occurred_at=_utc(event['occurred_at']),correlation_id=event['correlation_id'],causation_id=event['causation_id'],payload=copy.deepcopy(event['payload']))


def _wake(env,definition,scope):
    # Current eligible human subscribers receive a constant user-channel hint.
    # No workspace/topic/aggregate/payload is sent over the transient bus.
    env.cr.execute("""SELECT DISTINCT u.partner_id FROM mp_event_subscription s
        JOIN mp_principal p ON p.id=s.actor_id JOIN res_users u ON u.id=p.user_id
        JOIN mp_membership m ON m.principal_id=p.id AND m.workspace_id=s.workspace_id
        JOIN mp_service_binding b ON b.public_id=s.binding->>'binding_id' AND b.workspace_id=s.workspace_id
        JOIN mp_plugin_installation c ON c.id=s.installation_id
        JOIN mp_plugin_installation provider ON provider.public_id=s.binding->>'provider_installation_id'
        JOIN mp_workspace_plugin cf ON cf.installation_id=c.id AND cf.workspace_id=s.workspace_id
        JOIN mp_workspace_plugin pf ON pf.installation_id=provider.id AND pf.workspace_id=s.workspace_id
        WHERE s.workspace_id=%s AND s.topic=%s AND s.state='active' AND s.expires_at>timezone('UTC',clock_timestamp())
        AND p.kind='human' AND p.state='active' AND u.active AND m.state='active'
        AND b.state='active' AND b.descriptor=s.binding AND c.state='installed' AND provider.state='installed'
        AND cf.availability='enabled' AND pf.availability='enabled'
        AND (c.id=provider.id OR EXISTS(SELECT 1 FROM mp_plugin_grant g WHERE g.installation_id=c.id
            AND g.workspace_id=s.workspace_id AND g.capability=%s AND g.state='approved'))""",
        [scope.workspace_id,definition.ident,definition.permission])
    for partner, in env.cr.fetchall():env['bus.bus']._sendone(env['res.partner'].browse(partner),'mp_domain_events',dict(available=True))


def emit(env,topic,aggregate_id,payload,*,sequence,action):
    definition=_topic(topic);scope=_locked_scope(env);release=current_release(env)
    if not Draft202012Validator(definition.payload_schema,format_checker=FORMAT_CHECKER).is_valid(payload):raise ContractError('Invalid event payload')
    if definition.validate_identity:definition.validate_identity(aggregate_id,sequence,payload)
    durable._uuid(aggregate_id);durable._bounded(sequence,1,9007199254740991)
    if action not in {'create','write','unlink'}:raise AccessError('Explicit producer mutation required')
    env[definition.model]._mp_guard(action)
    env.cr.execute("""SELECT i.id FROM mp_plugin_installation i JOIN mp_workspace_plugin f ON f.installation_id=i.id
        WHERE i.plugin_id=%s AND i.state='installed' AND f.workspace_id=%s AND f.availability='enabled' FOR SHARE OF i,f""",[definition.plugin,scope.workspace_id])
    owner=env.cr.fetchone()
    if not owner:raise PublicError('PLUGIN_SUSPENDED')
    context=env.context.get('_mp_job_context');consumer=env.context.get('_mp_event_consumer')
    if isinstance(consumer,ConsumerFrame):correlation,causation=consumer.correlation_id,consumer.event_id
    elif isinstance(context,dict):correlation,causation=context['trace_id'],context['job_id']
    else:
        correlation=(getattr(request,'_mp_server_request_id',None) or getattr(request,'_mp_event_correlation',None)) if request and request.db==env.cr.dbname else None
        correlation=correlation or str(uuid4());causation=None
        if request and request.db==env.cr.dbname:request._mp_event_correlation=correlation
    storage=durable.DispatchScope(release['site_id'],scope.workspace_id,scope.principal_id,owner[0],release['release_digest'])
    ident=durable.append_event(env.cr,storage,plugin_id=definition.plugin,topic=topic,version=1,aggregate_id=aggregate_id,payload=payload,correlation_id=correlation,causation_id=causation,sequence=sequence)
    _wake(env,definition,scope);return ident


class _BatchFull(Exception):pass


def poll(env,subscription,bound,limit):
    store.expire_leases(env.cr,subscription);rows=store.candidates(env.cr,subscription,limit+1);definition=_topic(subscription['topic'])
    value=dict(protocol=1,kind='poll_result',subscription_id=subscription['public_id'],deliveries=[],has_more=len(rows)>limit,dead_letter_count=store.dead_letter_count(env.cr,subscription),next_poll_ms=2000)
    for event in rows[:limit]:
        envelope=_envelope(env,definition,event,bound)
        try:
            with env.cr.savepoint():
                lease=store.lease(env.cr,subscription,event)
                item=dict(id=lease['public_id'],receipt=lease['receipt'],generation=lease['generation'],attempt=lease['attempts'],lease_expires_at=_utc(lease['lease_until']),event=envelope)
                if len(rfc8785.dumps(dict(value,deliveries=value['deliveries']+[item])))>65536:raise _BatchFull()
            value['deliveries'].append(item)
        except _BatchFull:value['has_more']=True;break
    return value


def dispatch(env,message,*,binding_id=None):
    validate('event-transport',message)
    if not message['kind'].endswith('_request'):raise ContractError('Event request kind required')
    operation=message['kind'].removesuffix('_request')
    try:
        if operation=='subscribe':
            definition=_topic(message['topic']);env,scope,bound,storage=_authorize(env,definition,binding_id)
            env.cr.execute("SELECT count(*) FROM mp_event_subscription WHERE actor_id=%s AND workspace_id=%s AND state='active' AND expires_at>timezone('UTC',clock_timestamp())",[scope.principal_id,scope.workspace_id])
            if env.cr.fetchone()[0]>=40:
                env.cr.execute('SELECT 1 FROM mp_event_subscription WHERE actor_id=%s AND workspace_id=%s AND idempotency_key=%s',[scope.principal_id,scope.workspace_id,message['idempotency_key']])
                if not env.cr.fetchone():raise PublicError('RATE_LIMITED')
            subscription=store.open_subscription(env.cr,storage,definition.ident,bound.binding,message['idempotency_key'],scope.authenticated_installation_id)
            value=dict(protocol=1,kind='subscribe_result',subscription_id=subscription['public_id'],topic=definition.ident,expires_at=_utc(subscription['expires_at']),replay_window_seconds=604800,ack_lease_seconds=15,max_attempts=5,max_replays=3)
        else:
            env,subscription,bound=_subscription(env,message['subscription_id'],active=operation in {'poll','ack','replay'},closing=operation=='close')
            value=dict(protocol=1,kind=operation+'_result',subscription_id=subscription['public_id'])
            if operation=='poll':value=poll(env,subscription,bound,message['limit'])
            elif operation=='ack':value['acknowledged']=[store.acknowledge(env.cr,subscription,receipt) for receipt in message['receipts']]
            elif operation=='close':store.close(env.cr,subscription);value['closed']=True
            elif operation=='status':
                rows=store.delivery_status(env.cr,subscription)
                value.update(state='expired' if subscription['expired'] else subscription['state'],truncated=len(rows)>50,deliveries=[dict(id=r['public_id'],event_id=_event_public_id(env.cr,r['event_id']),state=r['state'],attempts=r['attempts'],replays=r['replays'],error_code=r['error_code'] if r['error_code'] in {None,'ACK_EXPIRED','CONSUMER_FAILED'} else 'CONSUMER_FAILED') for r in rows[:50]])
            elif operation=='replay':
                env.cr.execute("""SELECT to_jsonb(o) FROM mp_outbox o WHERE public_id=ANY(%s) AND site_id=%s AND workspace_id=%s
                    AND topic=%s AND state IN ('pending','published') AND occurred_at>=timezone('UTC',clock_timestamp())-interval '7 days'""",
                    [message['event_ids'],subscription['site_id'],subscription['workspace_id'],subscription['topic']])
                rows=[r[0] for r in env.cr.fetchall()]
                if len(rows)!=len(message['event_ids']):raise PublicError('NOT_FOUND')
                for event in rows:_envelope(env,_topic(subscription['topic']),event,bound)
                value['replayed']=store.replay(env.cr,subscription,rows)
        return validate('event-transport',value)
    except durable.DispatchPaused:raise PublicError('DEPENDENCY_UNAVAILABLE') from None
    except durable.QueueError:raise PublicError('CONFLICT') from None


def _event_public_id(cr,ident):
    cr.execute('SELECT public_id FROM mp_outbox WHERE id=%s',[ident]);return cr.fetchone()[0]


def _authorize_consumer(env,subscription,definition,bound):
    scope=_locked_scope(env);origin=scope.authenticated_installation_id
    if origin and origin!=subscription['binding']['consumer_installation_id']:
        env.cr.execute("""SELECT g.id FROM mp_plugin_grant g JOIN mp_plugin_installation i ON i.id=g.installation_id
            WHERE i.public_id=%s AND g.workspace_id=%s AND g.capability=%s AND g.state='approved' FOR SHARE OF g""",
            [origin,scope.workspace_id,definition.permission])
        if not env.cr.fetchone():raise AccessError('Technical origin cannot acquire consumer write authority')
    definition.authorize(env,bound)


def consume_registered(env,subscription_id,handler):
    """Native hook: original-user effect, tombstone and ACK share one tx."""
    definition=CONSUMERS.get(handler)
    if not definition:raise PublicError('NOT_FOUND')
    env,subscription,bound=_subscription(env,subscription_id,active=True)
    env.cr.execute('SELECT plugin_id FROM mp_plugin_installation WHERE id=%s',[subscription['installation_id']])
    if (env.cr.fetchone()[0],subscription['topic'])!=(definition.plugin,definition.topic):raise AccessError('Native consumer scope mismatch')
    _authorize_consumer(env,subscription,definition,bound)
    store.lock_consumer(env.cr,subscription,handler)
    batch=poll(env,subscription,bound,1)
    if not batch['deliveries']:return dict(state='idle')
    item=batch['deliveries'][0];receipt=dict(delivery_id=item['id'],receipt=item['receipt'],generation=item['generation'])
    env.cr.execute('SELECT to_jsonb(o) FROM mp_outbox o WHERE public_id=%s',[item['event']['id']]);event=env.cr.fetchone()[0]
    try:
        with env.cr.savepoint():
            store.lock_delivery(env.cr,subscription,receipt)
            fresh=store.consume_once(env.cr,subscription,event,handler)
            if fresh:
                frame=ConsumerFrame(handler,event['public_id'],subscription['workspace_id'],subscription['installation_id'],event['correlation_id'])
                _authorize_consumer(env,subscription,definition,bound)
                definition.apply(env(context={**env.context,'_mp_event_consumer':frame}),item['event'],bound)
                env.flush_all()
            store.acknowledge(env.cr,subscription,receipt)
        return dict(state='applied' if fresh else 'duplicate',event_id=event['public_id'])
    except (psycopg2.OperationalError,psycopg2.IntegrityError):raise
    except durable.QueueError:
        return dict(state='claim_lost',event_id=event['public_id'],error_code='CONFLICT')
    except Exception:
        # A consumer error never escapes as raw text or undoes producer commit.
        store.consumer_failed(env.cr,subscription,receipt)
        return dict(state='retry',event_id=event['public_id'],error_code='CONSUMER_FAILED')


class EventGateway(http.Controller):
    @http.route('/api/v1/events',type='http',auth='public',methods=['POST'],csrf=False,max_content_length=65536)
    def events(self):
        def run():
            try:message=bounded_body('event-transport')
            except RecursionError:raise ContractError('Event JSON exceeds supported depth') from None
            return dispatch(request.env,message,binding_id=request.httprequest.headers.get('X-MP-Binding'))
        return result(run)
