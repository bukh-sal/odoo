"""Registered native jobs reuse current actor/scope/bound-service authorization.

Only trusted native adapters call this module. It exposes no RPC methods and
does not turn serialized context or registered Python into a sandbox.
"""
from dataclasses import dataclass, replace
import copy
import hashlib
import json
from uuid import uuid4
import psycopg2

from jsonschema import Draft202012Validator
from odoo import api
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.mp_identity.scopes import current_scope, resolve_scope
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable
from modular_platform.contracts import ContractError, FORMAT_CHECKER, validate

from .controllers import PublicError
from .dispatch import CallFrame, authorize_bound, authorize_origin


@dataclass(frozen=True)
class JobDefinition:
    ident: str
    version: int
    plugin: str
    service: str
    api_version: str
    method: str
    input_schema: dict
    prepared_schema: dict
    computed_schema: dict
    output_schema: dict
    authorize_resource: object
    prepare: object
    compute: object
    apply: object
    effect_mode: str = 'idempotent'
    max_attempts: int = 5
    timeout_seconds: int = 120


DEFINITIONS = {}


def register(definition):
    if not isinstance(definition,JobDefinition) or not definition.ident.startswith(definition.plugin+':'):
        raise ValueError('Namespaced native job definition required')
    durable._name(definition.ident);durable._bounded(definition.version,1,1000)
    if definition.effect_mode not in {'idempotent','reconcile'}:
        raise ValueError('Explicit job effect policy required')
    for schema in [definition.input_schema,definition.prepared_schema,definition.computed_schema,definition.output_schema]:
        Draft202012Validator.check_schema(schema)
    if not all(callable(fn) for fn in [definition.authorize_resource,definition.prepare,definition.compute,definition.apply]):
        raise ValueError('Explicit native job handlers required')
    key=definition.ident,definition.version
    if key in DEFINITIONS:raise ValueError('Duplicate native job definition')
    DEFINITIONS[key]=definition


def _validate(schema,value):
    if not Draft202012Validator(schema,format_checker=FORMAT_CHECKER).is_valid(value):
        raise ContractError('Invalid registered job data')
    durable._json(value)
    return value


def _locked_scope(env):
    scope=current_scope(env)
    # Lock only current authority rows, not business data. A concurrent committed
    # revocation triggers the native transaction retry instead of stale access.
    env.cr.execute("""SELECT p.id FROM mp_principal p JOIN res_users u ON u.id=p.user_id
        JOIN mp_membership m ON m.principal_id=p.id JOIN mp_workspace w ON w.id=m.workspace_id
        WHERE p.id=%s AND p.user_id=%s AND w.id=%s AND p.state='active' AND u.active
          AND m.state='active' AND w.state='active' FOR SHARE OF p,u,m,w""",
        [scope.principal_id,env.uid,scope.workspace_id])
    if not env.cr.fetchone():raise AccessError('Current job authority unavailable')
    scope=resolve_scope(env,scope.workspace_public_id,previous=scope)
    if scope.principal_kind=='service':
        if not scope.credential_id or not scope.authenticated_installation_id:
            raise AccessError('Scoped technical credential required')
        env.cr.execute("""SELECT 1 FROM res_groups_users_rel r JOIN ir_model_data d ON d.res_id=r.gid
            AND d.model='res.groups' AND d.module='base' AND d.name IN ('group_system','group_erp_manager') WHERE r.uid=%s""",[env.uid])
        if env.uid==1 or env.cr.fetchone():raise AccessError('Technical administrator mapping forbidden')
        env.cr.execute("SELECT id FROM mp_service_credential WHERE id=%s AND state='active' FOR SHARE",[scope.credential_id])
        if not env.cr.fetchone():raise AccessError('Technical credential unavailable')
    return scope


def _authorize(env,definition,alias):
    scope=_locked_scope(env)
    frame=env.context.get('_mp_call_frame')
    release=current_release(env)
    if not isinstance(frame,CallFrame) or frame.site_id!=release['site_id']:
        raise AccessError('Server-selected job site required')
    bound=authorize_bound(env,alias,definition.method)
    if (bound.provider_plugin,bound.binding['service_id'],bound.binding['api_version'])!=(definition.plugin,definition.service,definition.api_version):
        raise PublicError('CONFLICT')
    # An authenticated technical origin never gains a consumer/provider's
    # broader grants by traversing a supported native call chain.
    authorize_origin(env,scope,bound)
    return scope,release,bound


def enqueue_bound(env,alias,ident,values,key,*,version=1,request_id=None,trace_id=None):
    durable._bounded(version,1,1000)
    definition=DEFINITIONS.get((ident,version))
    if not definition:raise PublicError('NOT_FOUND')
    _validate(definition.input_schema,values)
    scope,release,bound=_authorize(env,definition,alias)
    # Resource preflight is read-only and runs as the originating backing user.
    _validate(definition.prepared_schema,definition.prepare(env,values,bound))
    request_id=request_id or str(uuid4());trace_id=trace_id or request_id
    durable._uuid(request_id);durable._uuid(trace_id)
    context=dict(binding=bound.binding,alias=alias,request_id=request_id,trace_id=trace_id,
        credential_id=scope.credential_id,authenticated_installation_id=scope.authenticated_installation_id,
        allowed_actions=sorted(scope.allowed_actions) if scope.allowed_actions is not None else None)
    payload=dict(schema_version=1,input=values,context=context)
    env.cr.execute('SELECT id FROM mp_plugin_installation WHERE public_id=%s',[bound.binding['consumer_installation_id']])
    consumer=env.cr.fetchone()
    if not consumer:raise PublicError('DEPENDENCY_UNAVAILABLE')
    storage=durable.DispatchScope(release['site_id'],scope.workspace_id,scope.principal_id,consumer[0],release['release_digest'])
    return durable.enqueue(env.cr,storage,ident,version,payload,key,effect_mode=definition.effect_mode,
        max_attempts=definition.max_attempts,timeout_seconds=definition.timeout_seconds,
        deduplication=dict(input=values,binding=bound.binding,handler=ident,version=version))


def _envelope(row):
    value=row['payload']
    if not isinstance(value,dict) or set(value)!={'schema_version','input','context'} or type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ContractError('Unsupported native job envelope')
    context=value['context']
    keys={'binding','alias','request_id','trace_id','credential_id','authenticated_installation_id','allowed_actions'}
    if not isinstance(context,dict) or set(context)!=keys:
        raise ContractError('Invalid private job context')
    validate('binding',context['binding']);durable._uuid(context['request_id']);durable._uuid(context['trace_id'])
    if context['alias']!=context['binding']['alias']:raise ContractError('Job alias mismatch')
    actions=context['allowed_actions'];credential=context['credential_id'];installation=context['authenticated_installation_id']
    if credential is None:
        if actions is not None or installation is not None:raise ContractError('Invalid human job credential context')
    else:
        durable._bounded(credential,1,2**31-1);durable._uuid(installation)
        if not isinstance(actions,list) or not actions or len(set(actions))!=len(actions) or not set(actions)<={'read','create','write','unlink'}:
            raise ContractError('Invalid technical job scope')
    durable._json(value)
    return value


def _environment(metadata_env,row):
    payload=_envelope(row);context=payload['context'];binding=context['binding']
    cr=metadata_env.cr
    # This metadata lookup uses the immutable stored actor FK, never a backing
    # user/role/site supplied in the serialized job input.
    cr.execute("""SELECT p.user_id,p.public_id,p.kind,w.public_id,i.public_id,i.plugin_id
        FROM mp_principal p JOIN mp_workspace w ON w.id=%s JOIN mp_plugin_installation i ON i.id=%s
        WHERE p.id=%s""",[row['workspace_id'],row['installation_id'],row['actor_id']])
    identity=cr.fetchone()
    if not identity:raise AccessError('Job identity unavailable')
    user,principal,kind,workspace,consumer,plugin=identity
    env=api.Environment(cr,user,{})
    scope=resolve_scope(env,workspace)
    if kind=='service':
        if context['credential_id'] is None:raise AccessError('Technical job credential missing')
        scope=replace(scope,credential_id=context['credential_id'],allowed_actions=frozenset(context['allowed_actions']))
        scope=resolve_scope(env,workspace,previous=scope)
    elif context['credential_id'] is not None:
        raise AccessError('Job principal kind changed')
    if scope.authenticated_installation_id!=context['authenticated_installation_id']:
        raise AccessError('Job technical origin changed')
    if (binding['consumer_installation_id'],binding['workspace_id'],binding['site_id'])!=(consumer,workspace,row['site_id']):
        raise AccessError('Job binding scope mismatch')
    frame=CallFrame(principal,workspace,row['site_id'],consumer,plugin,())
    trace=dict(job_id=row['public_id'],request_id=context['request_id'],trace_id=context['trace_id'])
    return env(context={'_mp_scope':scope,'_mp_call_frame':frame,'_mp_job_context':trace}),payload


def _authorized_job(metadata_env,row):
    definition=DEFINITIONS.get((row['handler'],row['handler_version']))
    if not definition:raise PublicError('DEPENDENCY_UNAVAILABLE')
    env,payload=_environment(metadata_env,row)
    _validate(definition.input_schema,payload['input'])
    scope,release,bound=_authorize(env,definition,payload['context']['alias'])
    if release['site_id']!=row['site_id'] or release['release_digest']!=row['release_digest'] or bound.binding!=payload['context']['binding']:
        raise PublicError('CONFLICT')
    if row['effect_mode']!=definition.effect_mode:raise ContractError('Job effect policy mismatch')
    definition.authorize_resource(env,payload['input'],bound)
    return env,definition,payload,bound


def _fingerprint(row):
    value={k:row[k] for k in ['public_id','site_id','workspace_id','actor_id','installation_id','handler','handler_version','release_digest','payload','effect_mode','idempotency_key']}
    return hashlib.sha256(durable._json(value)[0].encode()).hexdigest()


@dataclass(frozen=True)
class Invocation:
    claim: durable.Claim
    handler: str
    version: int
    fingerprint: str
    prepared: dict
    context: dict


def _safe_code(error):
    if isinstance(error,PublicError) and error.code in {'NOT_FOUND','DEPENDENCY_UNAVAILABLE','PLUGIN_SUSPENDED','CONFLICT','DEADLINE_EXCEEDED'}:return error.code
    if isinstance(error,AccessError):return 'FORBIDDEN'
    if isinstance(error,MissingError):return 'NOT_FOUND'
    if isinstance(error,(ValidationError,ContractError,durable.QueueError,ValueError,TypeError)):return 'VALIDATION_FAILED'
    return 'INTERNAL_ERROR'


def prepare_one(metadata_env,owner,*,lease_seconds=30):
    """Claim and authorize in a short caller-owned transaction; never compute."""
    release=current_release(metadata_env)
    handlers=sorted({ident for ident,version in DEFINITIONS})
    if not handlers:return None
    claim=durable.claim(metadata_env.cr,release['site_id'],release['release_digest'],owner,handlers,lease_seconds=lease_seconds)
    if claim is None:return None
    row=durable._lock(metadata_env.cr,claim)
    try:
        with metadata_env.cr.savepoint():
            env,definition,payload,bound=_authorized_job(metadata_env,row)
            prepared=_validate(definition.prepared_schema,definition.prepare(env,payload['input'],bound))
            context=dict(job_id=claim.job_id,site_id=row['site_id'],workspace_id=bound.binding['workspace_id'],
                provider_installation_id=bound.binding['provider_installation_id'],request_id=payload['context']['request_id'],trace_id=payload['context']['trace_id'])
            return Invocation(claim,definition.ident,definition.version,_fingerprint(row),copy.deepcopy(prepared),context)
    except (psycopg2.OperationalError,psycopg2.IntegrityError):
        raise
    except Exception as error:
        code=_safe_code(error);state=durable.fail(metadata_env.cr,claim,code,retryable=False)
        return dict(job_id=claim.job_id,state=state,error_code=code)


def compute(invocation):
    definition=DEFINITIONS[(invocation.handler,invocation.version)]
    return _validate(definition.computed_schema,definition.compute(copy.deepcopy(invocation.prepared),copy.deepcopy(invocation.context)))


def finish_one(metadata_env,invocation,computed):
    """Fresh authorization, native business application and job outcome commit together."""
    def work(row):
        if _fingerprint(row)!=invocation.fingerprint:raise PublicError('CONFLICT')
        env,definition,payload,bound=_authorized_job(metadata_env,row)
        _validate(definition.prepared_schema,invocation.prepared)
        _validate(definition.computed_schema,computed)
        value=_validate(definition.output_schema,definition.apply(env,payload['input'],invocation.prepared,computed,bound))
        env.flush_all()
        return value
    try:
        return durable.run_fenced(metadata_env.cr,invocation.claim,work)
    except (durable.ClaimLost,durable.DispatchPaused):
        raise
    except (psycopg2.OperationalError,psycopg2.IntegrityError):
        raise
    except Exception as error:
        code=_safe_code(error);state=durable.fail(metadata_env.cr,invocation.claim,code,retryable=False)
        return dict(job_id=invocation.claim.job_id,state=state,error_code=code)


def status(env,ident):
    """Private adapter: only the current originating actor may see an outcome."""
    durable._uuid(ident);scope=_locked_scope(env)
    env.cr.execute("SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s AND actor_id=%s AND workspace_id=%s",[ident,scope.principal_id,scope.workspace_id])
    row=env.cr.fetchone()
    if not row:raise PublicError('NOT_FOUND')
    record=row[0];_,definition,_,_=_authorized_job(env,record)
    result=record['result']
    if result is not None:_validate(definition.output_schema,result)
    allowed={'NOT_FOUND','DEPENDENCY_UNAVAILABLE','PLUGIN_SUSPENDED','CONFLICT','DEADLINE_EXCEEDED','FORBIDDEN','VALIDATION_FAILED','INTERNAL_ERROR','LEASE_EXPIRED',None}
    code=record['error_code'] if record['error_code'] in allowed else 'INTERNAL_ERROR'
    return dict(id=ident,state=record['state'],progress=record['progress'],attempts=record['attempts'],error_code=code,result=result)
