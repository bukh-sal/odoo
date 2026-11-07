"""Detached reference computation; fresh native authority surrounds remote I/O.

No model, environment, database credential or issuer key crosses the worker API.
Only registered native job handlers call this module; no public arbitrary dispatch.
"""
import copy
from dataclasses import asdict
from odoo import api
from odoo.modules.registry import Registry
from odoo.exceptions import AccessError
from modular_platform import durable
from modular_platform.plans import data_digest
from modular_platform.worker_authority import PublishedWorkerAuthority, AuthorityUnavailable
from modular_platform.worker_dispatch import WorkerClient, WorkerDispatchError
from . import job_dispatch as jobs
from .controllers import PublicError
from .external_authority import authorize_analysis
from .dispatch import CallFrame

AUTHORITY_ROOT='/run/worker-authority'


def authorization_snapshot(provider_env,alias='stats',*,authority_root=AUTHORITY_ROOT):
    """Current native permission and independent publication in caller's tx.

    Final application already owns its job claim lock. Reuse its freshly
    authorized actor environment rather than opening another cursor that would
    block on that same claim. No remote I/O, signing or transaction commit here.
    """
    scope=jobs._locked_scope(provider_env)
    frame=provider_env.context.get('_mp_call_frame')
    if not isinstance(frame,CallFrame):raise AccessError('Server-selected external-service frame required')
    for model,fields in [('mp.service.binding',['consumer_id','workspace_id','alias','descriptor','state']),
                         ('mp.plugin.installation',['public_id','manifest'])]:
        provider_env[model].flush_model(fields)
    cr=provider_env.cr
    cr.execute("""SELECT p.public_id,p.manifest->'external_service'->>'endpoint_config'
        FROM mp_service_binding b JOIN mp_plugin_installation c ON c.id=b.consumer_id
        JOIN mp_plugin_installation p ON p.public_id=b.descriptor->>'provider_installation_id'
        WHERE c.public_id=%s AND b.workspace_id=%s AND b.alias=%s AND b.state='active'""",
        [frame.provider_installation_id,scope.workspace_id,alias])
    target=cr.fetchone()
    if not target:raise PublicError('DEPENDENCY_UNAVAILABLE')
    cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id'")
    deployment=cr.fetchone()
    if not deployment:raise PublicError('DEPENDENCY_UNAVAILABLE')
    try:
        authority=PublishedWorkerAuthority(authority_root,deployment_id=deployment[0],site_id=frame.site_id)
        selection=dict(installation_id=target[0],workspace_id=scope.workspace_public_id,endpoint_config=target[1])
        snapshot=authority.select(**selection)
        authorized=authorize_analysis(provider_env,alias,snapshot.endpoint)
        if authority.select(**selection)!=snapshot:raise WorkerDispatchError('FORBIDDEN')
    except AuthorityUnavailable:raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE') from None
    fingerprint=data_digest(dict(worker=asdict(snapshot),binding=authorized.binding,provider_plugin=authorized.provider_plugin))
    return authority,snapshot,fingerprint


def _snapshot(registry, provenance, prepared, context, alias, authority_root):
    claim=durable.Claim(**provenance['claim'])
    if claim.job_id!=context['job_id']:raise WorkerDispatchError('FORBIDDEN')
    with registry.cursor() as cr:
        try:
            metadata=api.Environment(cr,1,{})
            row=durable._lock(cr,claim)
            if (row['handler'],row['handler_version'],jobs._fingerprint(row))!=(provenance['handler'],provenance['version'],provenance['fingerprint']):
                raise WorkerDispatchError('FORBIDDEN')
            env,definition,payload,bound=jobs._authorized_job(metadata,row)
            # Re-read original-actor resource/revision, not a stale prepared body.
            current=jobs._validate(definition.prepared_schema,definition.prepare(env,payload['input'],bound))
            if current!=prepared:raise WorkerDispatchError('CONFLICT')
            return authorization_snapshot(bound.model.env,alias,authority_root=authority_root)
        except WorkerDispatchError:raise
        except AccessError:raise WorkerDispatchError('FORBIDDEN') from None
        except PublicError as error:raise WorkerDispatchError(error.code) from None
        except (durable.ClaimLost,durable.DispatchPaused):raise WorkerDispatchError('CANCELLED') from None
        except AuthorityUnavailable:raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE') from None
        finally:
            # No authority locks/cursor or uncommitted writes cross remote I/O.
            cr.rollback()


def analyze(prepared, context, *, alias='stats', authority_root=AUTHORITY_ROOT):
    provenance=context.get('_native_job')
    if not isinstance(provenance,dict) or set(provenance)!={'database','handler','version','fingerprint','claim'} or not provenance['database']:
        raise WorkerDispatchError('FORBIDDEN')
    if not isinstance(prepared,dict) or set(prepared)!={'input'}:raise WorkerDispatchError('VALIDATION_FAILED')
    # Registry name comes from the server-created Invocation, not job input.
    registry=Registry(provenance['database'])
    authority,snapshot,fingerprint=_snapshot(registry,provenance,prepared,context,alias,authority_root)
    def current_endpoint():
        _,current,digest=_snapshot(registry,provenance,prepared,context,alias,authority_root)
        if current!=snapshot or digest!=fingerprint:raise WorkerDispatchError('FORBIDDEN')
        return current.endpoint
    client=WorkerClient(current_endpoint,lambda ref:authority.issuer(snapshot,ref),snapshot.egress,
        **{key:snapshot.endpoint[key] for key in ['site_id','workspace_id','installation_id']})
    value=client.analyze(copy.deepcopy(prepared['input']),request_id=context['request_id'],operation_id=context['job_id'])
    return dict(statistics=value['data'],authority_digest=fingerprint)
