"""Detached reference computation; fresh native authority surrounds remote I/O.

No model, environment, database credential or issuer key crosses the worker API.
Only registered native job handlers call this module; no public arbitrary dispatch.
"""
import copy
from odoo import api
from odoo.modules.registry import Registry
from odoo.exceptions import AccessError
from modular_platform import durable
from modular_platform.contracts import validate
from modular_platform.worker_authority import PublishedWorkerAuthority, AuthorityUnavailable
from modular_platform.worker_dispatch import WorkerClient, WorkerDispatchError
from . import job_dispatch as jobs
from .controllers import PublicError
from .external_authority import authorize_analysis

AUTHORITY_ROOT='/run/worker-authority'


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
            provider_env=bound.model.env
            frame=provider_env.context['_mp_call_frame']
            cr.execute("""SELECT p.public_id,p.manifest->'external_service'->>'endpoint_config'
                FROM mp_service_binding b JOIN mp_plugin_installation c ON c.id=b.consumer_id
                JOIN mp_plugin_installation p ON p.public_id=b.descriptor->>'provider_installation_id'
                WHERE c.public_id=%s AND b.workspace_id=%s AND b.alias=%s AND b.state='active'""",
                [frame.provider_installation_id,row['workspace_id'],alias])
            target=cr.fetchone()
            if not target:raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE')
            cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id'")
            deployment=cr.fetchone()
            if not deployment:raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE')
            authority=PublishedWorkerAuthority(authority_root,deployment_id=deployment[0],site_id=row['site_id'])
            snapshot=authority.select(installation_id=target[0],workspace_id=frame.workspace_id,endpoint_config=target[1])
            authorize_analysis(provider_env,alias,snapshot.endpoint)
            return authority,snapshot
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
    authority,snapshot=_snapshot(registry,provenance,prepared,context,alias,authority_root)
    def current_endpoint():
        _,current=_snapshot(registry,provenance,prepared,context,alias,authority_root)
        if current!=snapshot:raise WorkerDispatchError('FORBIDDEN')
        return current.endpoint
    client=WorkerClient(current_endpoint,lambda ref:authority.issuer(snapshot,ref),snapshot.egress,
        **{key:snapshot.endpoint[key] for key in ['site_id','workspace_id','installation_id']})
    value=client.analyze(copy.deepcopy(prepared['input']),request_id=context['request_id'],operation_id=context['job_id'])
    return value['data']
