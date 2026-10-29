"""Actor-preserving supported provider chains; trusted native code is not confined."""
from dataclasses import dataclass
import json

from jsonschema import Draft202012Validator
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import current_scope
from modular_platform.contracts import CONTRACTS, ContractError, FORMAT_CHECKER, validate_binding

from .registry import SERVICES


@dataclass(frozen=True)
class CallFrame:
    principal_id: str
    workspace_id: str
    site_id: str
    provider_installation_id: str
    provider_plugin_id: str
    chain: tuple


@dataclass(frozen=True)
class BoundCall:
    """Private, transaction-local authorization result; never serialize it."""
    model: object
    spec: object
    binding: dict
    provider_plugin: str

    def invoke(self, values):
        from .controllers import PublicError
        schema=json.loads((CONTRACTS/self.spec.schema_file).read_text())['$defs'][self.spec.input_schema]
        if not Draft202012Validator(schema,format_checker=FORMAT_CHECKER).is_valid(values):
            raise ContractError('Invalid provider input')
        self.model._mp_guard(self.spec.action)
        value=getattr(self.model,self.spec.handler)(values)
        if not Draft202012Validator(self.spec.output_schema,format_checker=FORMAT_CHECKER).is_valid(value):
            raise PublicError('INTERNAL_ERROR')
        return value


def authorize_bound(env,alias,method):
    """Shared synchronous/job authorization, without invoking the service."""
    from .controllers import PublicError
    frame=env.context.get('_mp_call_frame');scope=current_scope(env)
    if not isinstance(frame,CallFrame) or (frame.principal_id,frame.workspace_id)!=(scope.principal_public_id,scope.workspace_public_id):
        raise AccessError('Registered actor frame required')
    if len(frame.chain)>=8:raise PublicError('CONFLICT')
    env.cr.execute("""SELECT b.descriptor,c.plugin_id,c.manifest,c.state,p.plugin_id,p.manifest,p.state
        FROM mp_service_binding b JOIN mp_plugin_installation c ON c.id=b.consumer_id
        JOIN mp_plugin_installation p ON p.public_id=b.descriptor->>'provider_installation_id'
        WHERE c.public_id=%s AND b.workspace_id=%s AND b.alias=%s AND b.state='active'
        FOR SHARE OF b,c,p""",[frame.provider_installation_id,scope.workspace_id,alias])
    row=env.cr.fetchone()
    if not row:raise PublicError('DEPENDENCY_UNAVAILABLE')
    binding,consumer,cmanifest,cstate,provider,pmanifest,pstate=row
    if cstate!='installed' or pstate!='installed':raise PublicError('PLUGIN_SUSPENDED')
    if consumer!=frame.provider_plugin_id or binding['site_id']!=frame.site_id:raise AccessError('Provider chain identity mismatch')
    for plugin in [consumer,provider]:
        env.cr.execute("SELECT availability FROM mp_workspace_plugin WHERE workspace_id=%s AND plugin_id=%s FOR SHARE",[scope.workspace_id,plugin])
        feature=env.cr.fetchone()
        if not feature or feature[0]!='enabled':raise PublicError('PLUGIN_SUSPENDED')
    requirement=next((r for r in cmanifest['services']['requires'] if r['alias']==alias),None)
    declaration=next((p for p in pmanifest['services']['provides'] if p['id']==binding['service_id'] and p['api_version']==binding['api_version']),None)
    if not requirement or not declaration:raise PublicError('DEPENDENCY_UNAVAILABLE')
    validate_binding(binding,requirement,{**declaration,'plugin_id':provider,'installation_id':binding['provider_installation_id']})
    spec=SERVICES.get((binding['service_id'],binding['api_version'],provider),{}).get(method)
    if not spec or method not in declaration['methods']:raise PublicError('NOT_FOUND')
    if consumer!=provider:
        env.cr.execute("SELECT 1 FROM mp_plugin_grant g JOIN mp_plugin_installation i ON i.id=g.installation_id WHERE i.public_id=%s AND g.workspace_id=%s AND g.capability=%s AND g.state='approved' FOR SHARE OF g,i",[frame.provider_installation_id,scope.workspace_id,spec.permission])
        if not env.cr.fetchone():raise AccessError('Current integration grant required')
    target=(provider,binding['service_id'],method)
    if target in frame.chain:raise PublicError('CONFLICT')
    child=CallFrame(frame.principal_id,frame.workspace_id,frame.site_id,binding['provider_installation_id'],provider,frame.chain+(target,))
    model=env[spec.model].with_context(_mp_call_frame=child)
    model._mp_guard(spec.action)
    return BoundCall(model,spec,binding,provider)


def call_bound(env,alias,method,values):
    return authorize_bound(env,alias,method).invoke(values)
