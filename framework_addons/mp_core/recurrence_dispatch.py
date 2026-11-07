"""Trusted native recurrence adapter; no controller or public ORM submission API."""
import copy
from datetime import timedelta,timezone
from uuid import NAMESPACE_URL,uuid5

from odoo.exceptions import AccessError,MissingError,ValidationError
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable,recurrence_store as store
from modular_platform.contracts import ContractError
from modular_platform.recurrence import RecurrenceRule

from . import job_dispatch as jobs
from .controllers import PublicError
from .dispatch import CallFrame


def _definition(ident,version):
    durable._bounded(version,1,1000)
    definition=jobs.DEFINITIONS.get((ident,version))
    if not definition or definition.pool not in {'urgent','bulk'}:
        raise PublicError('DEPENDENCY_UNAVAILABLE')
    return definition


def _submission(env,alias,ident,version,values,token):
    definition=_definition(ident,version)
    values=copy.deepcopy(values)
    jobs._validate(definition.input_schema,values)
    scope,release,bound=jobs._authorize(env,definition,alias)
    if scope.principal_kind!='service':raise AccessError('Recurring work requires an explicit scoped service identity')
    definition.authorize_resource(env,values,bound)
    env.cr.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s',[bound.binding['consumer_installation_id']])
    installation=env.cr.fetchone()
    if not installation:raise PublicError('DEPENDENCY_UNAVAILABLE')
    storage=durable.DispatchScope(release['site_id'],scope.workspace_id,scope.principal_id,installation[0],release['release_digest'])
    request=str(uuid5(NAMESPACE_URL,':'.join((release['site_id'],scope.principal_public_id,
        scope.workspace_public_id,bound.binding['consumer_installation_id'],token))))
    context=dict(binding=bound.binding,alias=alias,request_id=request,trace_id=request,
        credential_id=scope.credential_id,authenticated_installation_id=scope.authenticated_installation_id,
        allowed_actions=sorted(scope.allowed_actions))
    return storage,dict(protocol=1,input=values,context=context)


def _saved(metadata_env,row):
    value=row['payload']
    if not isinstance(value,dict) or set(value)!={'protocol','input','context'} or type(value['protocol']) is not int or value['protocol']!=1:
        raise ContractError('Versioned native recurrence context required')
    rule=RecurrenceRule.from_wire(row['rule'])
    timing=durable.JobSchedule(rule.anchor_at,rule.anchor_at+timedelta(seconds=rule.validity_seconds),rule.attempt_seconds)
    # Reuse the one-off worker's actor/credential reconstruction. No scope is
    # accepted from serialized application input or an administrator fallback.
    envelope=dict(schema_version=2,input=value['input'],context=value['context'],schedule=timing.wire())
    env,_=jobs._environment(metadata_env,dict(row,payload=envelope))
    definition=_definition(row['handler'],row['handler_version'])
    scope,release,bound=jobs._authorize(env,definition,value['context']['alias'])
    if scope.principal_kind!='service':raise AccessError('Recurring human impersonation is forbidden')
    if (release['site_id'],release['release_digest'],bound.binding)!=(row['site_id'],row['release_digest'],value['context']['binding']):
        raise PublicError('CONFLICT')
    jobs._validate(definition.input_schema,value['input'])
    definition.authorize_resource(env,value['input'],bound)
    return env,definition,value


def create_schedule(env,alias,ident,values,key,*,rule,version=1):
    if not isinstance(rule,RecurrenceRule):raise ContractError('Typed recurrence rule required')
    if not isinstance(key,str):raise ContractError('Bounded recurrence creation key required')
    scope,payload=_submission(env,alias,ident,version,values,'create:'+key)
    return store.create(env.cr,scope,ident,version,payload,rule,key,authorize=lambda row:_live(env,row))


def _owned(env,ident):
    durable._uuid(ident)
    scope=jobs._locked_scope(env)
    frame=env.context.get('_mp_call_frame');release=current_release(env)
    if (scope.principal_kind!='service' or not isinstance(frame,CallFrame)
            or (frame.principal_id,frame.workspace_id,frame.site_id)!=(scope.principal_public_id,scope.workspace_public_id,release['site_id'])):
        raise AccessError('Current scoped service frame required')
    env.cr.execute("""SELECT to_jsonb(s) FROM mp_job_schedule s JOIN mp_plugin_installation i ON i.id=s.installation_id
        WHERE s.public_id=%s AND s.site_id=%s AND s.release_digest=%s AND s.workspace_id=%s AND s.actor_id=%s
        AND i.public_id=%s""",[ident,release['site_id'],release['release_digest'],scope.workspace_id,
                               scope.principal_id,frame.provider_installation_id])
    found=env.cr.fetchone()
    if not found:raise PublicError('NOT_FOUND')
    return found[0]


def edit_schedule(env,ident,revision,*,handler,values,rule,version=1):
    current=_owned(env,ident)
    scope,payload=_submission(env,current['payload']['context']['alias'],handler,version,values,f'edit:{ident}:{revision}')
    if (scope.actor_id,scope.workspace_id,scope.installation_id)!=(current['actor_id'],current['workspace_id'],current['installation_id']):
        raise AccessError('Schedule origin cannot change')
    return store.edit(env.cr,scope,ident,revision,handler=handler,version=version,payload=payload,
                      rule=rule,authorize=lambda row:_saved(env,row))


def _live(env,row):
    definition=_definition(row['handler'],row['handler_version'])
    _,_,bound=jobs._authorize(env,definition,row['payload']['context']['alias'])
    definition.authorize_resource(env,row['payload']['input'],bound)


def pause_schedule(env,ident,revision):
    row=_owned(env,ident)
    scope=durable.DispatchScope(row['site_id'],row['workspace_id'],row['actor_id'],row['installation_id'],row['release_digest'])
    return store.set_state(env.cr,scope,ident,revision,'paused',authorize=lambda locked:_live(env,locked))


def resume_schedule(env,ident,revision):
    row=_owned(env,ident)
    scope=durable.DispatchScope(row['site_id'],row['workspace_id'],row['actor_id'],row['installation_id'],row['release_digest'])
    def authorized(locked):
        _live(env,locked)
        _saved(env,locked)
    return store.set_state(env.cr,scope,ident,revision,'active',authorize=authorized)


def cancel_outstanding(env,ident,revision):
    """Current owned schedule authority may stop old work without reviving it."""
    row=_owned(env,ident)
    scope=durable.DispatchScope(row['site_id'],row['workspace_id'],row['actor_id'],row['installation_id'],row['release_digest'])
    row=store._locked(env.cr,scope,ident,revision=revision)
    _live(env,row)
    if not row['outstanding_job_id']:return False
    env.cr.execute("""SELECT public_id FROM mp_job WHERE public_id=%s AND site_id=%s AND workspace_id=%s
        AND actor_id=%s AND installation_id=%s FOR UPDATE""",[row['outstanding_job_id'],scope.site_id,
            scope.workspace_id,scope.actor_id,scope.installation_id])
    if not env.cr.fetchone():raise PublicError('NOT_FOUND')
    # Cancellation never sends or settles an effect. The queue retains an
    # uncertain outcome if an external effect was already started.
    return durable.cancel_scheduled(env.cr,row['outstanding_job_id'],actor_id=scope.actor_id,workspace_id=scope.workspace_id)


def due(metadata_env,*,limit=100):
    release=current_release(metadata_env)
    metadata_env.cr.execute("SELECT timezone('UTC',clock_timestamp())")
    now=metadata_env.cr.fetchone()[0].replace(tzinfo=timezone.utc)
    return store.candidates(metadata_env.cr,release['site_id'],release['release_digest'],now,limit=limit)


def tick(metadata_env,ident):
    """One producer-owned transaction. Caller commits or retries a DB failure."""
    durable._uuid(ident)
    release=current_release(metadata_env)
    metadata_env.cr.execute("""SELECT to_jsonb(s),timezone('UTC',clock_timestamp()) FROM mp_job_schedule s
        WHERE public_id=%s AND site_id=%s AND release_digest=%s""",[ident,release['site_id'],release['release_digest']])
    found=metadata_env.cr.fetchone()
    if not found:return dict(outcome='unavailable',schedule_id=ident)
    row,now=found;now=now.replace(tzinfo=timezone.utc)
    scope=durable.DispatchScope(row['site_id'],row['workspace_id'],row['actor_id'],row['installation_id'],row['release_digest'])
    def submit(locked,timing,key):
        env,_,value=_saved(metadata_env,locked)
        return jobs.enqueue_scheduled(env,value['context']['alias'],locked['handler'],value['input'],key,
            schedule=timing,version=locked['handler_version'])
    try:
        return store.advance(metadata_env.cr,scope,ident,now,authorize=lambda locked:_saved(metadata_env,locked),submit=submit)
    except durable.DispatchPaused:raise
    except (AccessError,MissingError,ValidationError,PublicError,ContractError,durable.QueueError) as error:
        code=jobs._safe_code(error)
        if code not in {'FORBIDDEN','DEPENDENCY_UNAVAILABLE','CONFLICT','VALIDATION_FAILED'}:
            code='DEPENDENCY_UNAVAILABLE' if isinstance(error,MissingError) else 'CONFLICT'
        store.hold(metadata_env.cr,scope,ident,row['config_version'],code)
        return dict(outcome='held',schedule_id=ident,error_code=code)


def reconcile_release(metadata_env,*,previous_release,target_release):
    """Private lifecycle path; preserves intent and never reopens dispatch."""
    release=current_release(metadata_env)
    if release['release_digest']!=target_release:raise ContractError('Current recurring release required')
    cr=metadata_env.cr
    cr.execute('SELECT state FROM mp_dispatch_control WHERE site_id=%s AND release_digest=%s FOR UPDATE',
        [release['site_id'],target_release])
    if cr.fetchone()!=('paused',):raise durable.DispatchPaused('Recurring reconciliation requires closed dispatch')
    cr.execute('SELECT count(*) FROM mp_job_schedule')
    if cr.fetchone()[0]>100000:raise durable.QueueError('Recurring schedule reconciliation bound exceeded')
    cr.execute('SELECT to_jsonb(s) FROM mp_job_schedule s WHERE site_id=%s ORDER BY id FOR UPDATE',[release['site_id']])
    rows=cr.fetchall()
    states={}
    for (row,) in rows:
        if row['release_digest'] not in {previous_release,target_release}:raise ContractError('Unknown recurring release origin')
        state=row['state'];code=row['error_code']
        payload=row['payload'];input_digest=row['input_digest']
        try:
            candidate=dict(row,release_digest=target_release)
            rule=RecurrenceRule.from_wire(row['rule'])
            timing=durable.JobSchedule(rule.anchor_at,rule.anchor_at+timedelta(seconds=rule.validity_seconds),rule.attempt_seconds)
            envelope=dict(schema_version=2,input=payload['input'],context=payload['context'],schedule=timing.wire())
            actor,_=jobs._environment(metadata_env,dict(candidate,payload=envelope))
            definition=_definition(row['handler'],row['handler_version'])
            _,_,bound=jobs._authorize(actor,definition,payload['context']['alias'])
            before=payload['context']['binding'];after=bound.binding
            if ({key:value for key,value in before.items() if key!='generation'}!={key:value for key,value in after.items() if key!='generation'}
                    or after['generation']<before['generation']):raise PublicError('CONFLICT')
            proposed=copy.deepcopy(payload);proposed['context']['binding']=after
            _saved(metadata_env,dict(candidate,payload=proposed))
            payload=proposed
            _,_,input_digest=store._configuration(row['handler'],row['handler_version'],payload,rule)
        except (AccessError,MissingError,ValidationError,PublicError,ContractError,durable.QueueError) as error:
            state='held';code=jobs._safe_code(error)
        # A prior explicit hold or pause remains in force even when current
        # authority is sufficient. Only a native app edit/resume can clear it.
        cr.execute('UPDATE mp_job_schedule SET release_digest=%s,state=%s,error_code=%s,payload=%s::jsonb,input_digest=%s WHERE id=%s',
            [target_release,state,code,durable._json(payload)[0],input_digest,row['id']])
        states[state]=states.get(state,0)+1
    return states
