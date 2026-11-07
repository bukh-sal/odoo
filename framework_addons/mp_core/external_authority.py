"""Current native authority for the fixed R1 external analysis provider.

The endpoint argument MUST come from the independently published host authority
file, never an artifact, browser or stored job payload. This adapter verifies
native scope/binding/grants; it does not attest images or grant executor approval.
No remote call or business effect occurs in this transaction.
"""
import copy
from dataclasses import dataclass
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.release import current_release
from modular_platform.contracts import validate, validate_binding
from .controllers import PublicError
from .dispatch import CallFrame, authorize_origin


@dataclass(frozen=True)
class ExternalPermission:
    permission: str = 'org.example.document_stats:analysis.run'
    action: str = 'read'


@dataclass(frozen=True)
class ExternalAuthorization:
    binding: dict
    provider_plugin: str
    endpoint: dict
    spec: ExternalPermission = ExternalPermission()


def authorize_analysis(env, alias, approved_endpoint):
    from .job_dispatch import _locked_scope
    endpoint=copy.deepcopy(approved_endpoint);validate('endpoint',endpoint)
    scope=_locked_scope(env);frame=env.context.get('_mp_call_frame');release=current_release(env)
    if not isinstance(frame,CallFrame) or (frame.principal_id,frame.workspace_id,frame.site_id)!=(scope.principal_public_id,scope.workspace_public_id,release['site_id']):
        raise AccessError('Registered current external-service actor required')
    if len(frame.chain)>=8:raise PublicError('CONFLICT')
    if scope.allowed_actions is not None and 'read' not in scope.allowed_actions:
        raise AccessError('Technical read action required')
    # Keep pending supported policy mutations consistent with the SQL reads.
    # This flushes metadata only, without a commit or business ACL elevation.
    for model,fields in [
        ('mp.plugin.installation',['public_id','plugin_id','manifest','runtime','state']),
        ('mp.service.binding',['public_id','consumer_id','workspace_id','alias','descriptor','state']),
        ('mp.plugin.grant',['installation_id','workspace_id','capability','state']),
    ]:env[model].flush_model(fields)
    env.cr.execute("""SELECT b.descriptor,c.plugin_id,c.manifest,c.state,p.plugin_id,p.manifest,p.state,p.runtime
        FROM mp_service_binding b JOIN mp_plugin_installation c ON c.id=b.consumer_id
        JOIN mp_plugin_installation p ON p.public_id=b.descriptor->>'provider_installation_id'
        WHERE c.public_id=%s AND b.workspace_id=%s AND b.alias=%s AND b.state='active'
        FOR SHARE OF b,c,p""",[frame.provider_installation_id,scope.workspace_id,alias])
    row=env.cr.fetchone()
    if not row:raise PublicError('DEPENDENCY_UNAVAILABLE')
    binding,consumer,cmanifest,cstate,provider,pmanifest,pstate,runtime=row
    if cstate!='installed' or pstate!='installed':raise PublicError('PLUGIN_SUSPENDED')
    if consumer!=frame.provider_plugin_id or binding['site_id']!=frame.site_id:
        raise AccessError('External binding actor chain mismatch')
    if provider!='org.example.document_stats' or runtime!='external_service' or pmanifest['runtime']['kind']!='external_service':
        raise PublicError('DEPENDENCY_UNAVAILABLE')
    for plugin in [consumer,provider]:
        env.cr.execute("SELECT availability FROM mp_workspace_plugin WHERE workspace_id=%s AND plugin_id=%s FOR SHARE",[scope.workspace_id,plugin])
        feature=env.cr.fetchone()
        if not feature or feature[0]!='enabled':raise PublicError('PLUGIN_SUSPENDED')
    requirement=next((v for v in cmanifest['services']['requires'] if v['alias']==alias),None)
    declaration=next((v for v in pmanifest['services']['provides'] if (v['id'],v['api_version'])==(binding['service_id'],binding['api_version'])),None)
    if not requirement or not declaration or 'analyze' not in declaration['methods']:
        raise PublicError('DEPENDENCY_UNAVAILABLE')
    validate_binding(binding,requirement,{**declaration,'plugin_id':provider,'installation_id':binding['provider_installation_id']})
    if (binding['service_id'],binding['api_version'],binding['contract_major'])!=('org.example.document_stats.analysis','1.0',1):
        raise PublicError('CONFLICT')
    permission=ExternalPermission()
    if consumer!=provider:
        env.cr.execute("""SELECT 1 FROM mp_plugin_grant g JOIN mp_plugin_installation i ON i.id=g.installation_id
            WHERE i.public_id=%s AND g.workspace_id=%s AND g.capability=%s AND g.state='approved' FOR SHARE OF g,i""",
            [frame.provider_installation_id,scope.workspace_id,permission.permission])
        if not env.cr.fetchone():raise AccessError('Current approved analysis grant required')
    if (provider,binding['service_id'],'analyze') in frame.chain:raise PublicError('CONFLICT')
    expected=dict(installation_id=binding['provider_installation_id'],site_id=release['site_id'],workspace_id=scope.workspace_public_id,
                  endpoint_config=pmanifest['external_service']['endpoint_config'],api_version='1.0',state='enabled',
                  expected_image_digest=pmanifest['external_service']['expected_image'].split('@',1)[1])
    if any(endpoint[key]!=value for key,value in expected.items()) or 'analyze' not in endpoint['allowed_methods']:
        raise AccessError('Current independently approved endpoint mismatch')
    result=ExternalAuthorization(copy.deepcopy(binding),provider,endpoint)
    authorize_origin(env,scope,result)
    return result
