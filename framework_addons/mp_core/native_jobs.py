"""Private human-origin native application jobs; no workspace impersonation.

Real installation and actor are selected from server-owned
metadata. Business handlers always receive the original non-sudo Environment.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tomllib
import zipfile
from uuid import uuid4

from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable
from modular_platform.contracts import ContractError, normalize_manifest, native_version
from modular_platform.native_scope import require_site_manifest

from . import job_dispatch as jobs


@dataclass(frozen=True)
class NativeBound:
    installation_id: int
    public_id: str
    plugin: str
    addon: str

    @property
    def binding(self):
        # Private Invocation routing fields, not a public service binding.
        return dict(workspace_id=None, provider_installation_id=self.public_id)


@lru_cache(maxsize=64)
def _image_package(plugin):
    root=Path('/opt/modular')
    inventory=json.loads((root/'distribution-inventory.json').read_bytes())
    pin=inventory.get('artifacts',{}).get(plugin)
    if (not isinstance(pin,dict) or pin.get('plugin_id')!=plugin
            or not isinstance(pin.get('file'),str) or Path(pin['file']).name!=pin['file']
            or '/' in pin['file'] or '\\' in pin['file']):
        raise AccessError('Native application artifact unavailable in this image')
    raw=(root/'artifacts'/pin['file']).read_bytes()
    if ('sha256:'+hashlib.sha256(raw).hexdigest()!=pin['digest']
            or inventory['files'].get('artifacts/'+pin['file'])!=pin['digest'][7:]):
        raise AccessError('Native application artifact differs from its image pin')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest=normalize_manifest(tomllib.loads(archive.read(plugin+'/plugin.toml').decode('utf8')))
    require_site_manifest(manifest)
    if (pin.get('addon')!=manifest['runtime']['addon_name'] or pin.get('version')!=manifest['plugin']['version']
            or pin['addon'] not in inventory['native_addons']):
        raise AccessError('Native application image mapping changed')
    return pin['digest'],manifest


def _actor(env, *, provision=False):
    if env.su or not env.uid:
        raise AccessError('Original non-sudo native actor required')
    env['res.users'].flush_model(['active','share'])
    env['mp.principal'].flush_model(['user_id','state','kind'])
    env.cr.execute('SELECT id FROM res_users WHERE id=%s AND active AND NOT share FOR SHARE', [env.uid])
    if not env.cr.fetchone():raise AccessError('Active internal native actor required')
    if provision:
        # Identity only: no role, workspace membership, credential or grant.
        env.cr.execute("""INSERT INTO mp_principal(name,public_id,user_id,kind,state,
            create_uid,write_uid,create_date,write_date)
            VALUES('Native application actor',%s,%s,'human','active',%s,%s,
                timezone('UTC',now()),timezone('UTC',now()))
            ON CONFLICT(user_id) DO NOTHING""",[str(uuid4()),env.uid,env.uid,env.uid])
    env.cr.execute("""SELECT id FROM mp_principal WHERE user_id=%s
        AND state='active' AND kind='human' FOR SHARE""",[env.uid])
    row=env.cr.fetchone()
    if not row:raise AccessError('Current human native principal required')
    return row[0]


def _installation(env,definition,expected=None,*,lock=True):
    env['mp.plugin.installation'].flush_model()
    env['ir.module.module'].flush_model(['name','state','latest_version'])
    env.cr.execute("""SELECT id,public_id,manifest,version,artifact_digest FROM mp_plugin_installation
        WHERE plugin_id=%s AND state='installed' AND runtime='native'"""+(' FOR SHARE' if lock else ''),[definition.plugin])
    row=env.cr.fetchone()
    if not row or (expected is not None and row[0]!=expected):
        raise AccessError('Native application installation unavailable')
    manifest=normalize_manifest(row[2])
    digest,image_manifest=_image_package(definition.plugin)
    if (manifest['plugin']['id']!=definition.plugin or manifest['plugin']['version']!=row[3]
            or manifest['runtime']['kind']!='native' or manifest['runtime']['addon_name']!=definition.addon
            or row[4]!=digest or manifest!=image_manifest):
        raise AccessError('Native application identity changed')
    env.cr.execute("""SELECT id FROM ir_module_module WHERE name=%s
        AND state='installed' AND latest_version=%s"""+(' FOR SHARE' if lock else ''),
        [definition.addon,native_version(manifest['plugin']['version'])])
    if not env.cr.fetchone():raise AccessError('Native application code/version unavailable')
    return NativeBound(row[0],row[1],definition.plugin,definition.addon)


def require_application(env,plugin,addon,*,lock=False):
    """Current native installation availability; ordinary reads remain read-only."""
    env.cr.execute('SELECT id FROM res_users WHERE id=%s AND active AND NOT share'+(' FOR SHARE' if lock else ''),[env.uid])
    if not env.cr.fetchone():raise AccessError('Active internal native application user required')
    return _installation(env,SimpleNamespace(plugin=plugin,addon=addon),lock=lock)


def enqueue_scheduled(env,ident,values,key,*,schedule,version=1):
    """Trusted native API: the caller cannot select a backing user or installation."""
    definition=jobs.DEFINITIONS.get((ident,version))
    if not definition or definition.authority!='native':
        raise AccessError('Registered native application job required')
    if not isinstance(schedule,durable.JobSchedule):raise ContractError('Explicit native schedule required')
    jobs._validate(definition.input_schema,values)
    # Whole operation rolls back if preflight fails, even when a caller catches it.
    with env.cr.savepoint():
        actor=_actor(env,provision=True)
        bound=_installation(env,definition)
        definition.authorize_resource(env,values,bound)
        release=current_release(env)
        trace=str(uuid4())
        payload=dict(schema_version=2,input=values,schedule=schedule.wire(),
                     context=dict(native_application=1,installation=bound.public_id,
                                  request_id=trace,trace_id=trace))
        scope=durable.NativeDispatchScope(release['site_id'],actor,bound.installation_id,release['release_digest'])
        return durable.enqueue(env.cr,scope,ident,version,payload,key,schedule=schedule,
            effect_mode=definition.effect_mode,max_attempts=definition.max_attempts,
            timeout_seconds=definition.timeout_seconds,retain_identity=True,
            deduplication=dict(input=values,installation=bound.public_id,handler=ident,version=version),
            on_new=lambda:jobs._validate(definition.prepared_schema,definition.prepare(env,values,bound)))


def _payload(row):
    payload=row['payload']
    if (row['workspace_id'] is not None or not isinstance(payload,dict)
            or set(payload)!={'schema_version','input','context','schedule'}
            or type(payload['schema_version']) is not int or payload['schema_version']!=2):
        raise ContractError('Native application job envelope required')
    durable.JobSchedule.from_wire(payload['schedule'])
    context=payload['context']
    if (not isinstance(context,dict) or set(context)!={'native_application','installation','request_id','trace_id'}
            or type(context['native_application']) is not int or context['native_application']!=1):
        raise ContractError('Native application job context required')
    for name in ('installation','request_id','trace_id'):durable._uuid(context[name])
    return payload


def authorized(metadata_env,row,definition,*,previous_release=None):
    payload=_payload(row);context=payload['context']
    metadata_env.cr.execute('SELECT user_id FROM mp_principal WHERE id=%s',[row['actor_id']])
    actor=metadata_env.cr.fetchone()
    if not actor:raise AccessError('Original native actor unavailable')
    env=api.Environment(metadata_env.cr,actor[0],{},su=False)
    if _actor(env)!=row['actor_id']:raise AccessError('Native job actor changed')
    bound=_installation(env,definition,expected=row['installation_id'])
    release=current_release(env)
    if previous_release is not None:
        # Only the closed host reconciliation transaction may inspect an old
        # claim under the target release. This never permits dispatch/apply:
        # their ordinary calls still require the current release on the row.
        env.cr.execute('SELECT release_digest,state FROM mp_dispatch_control WHERE site_id=%s FOR UPDATE',[release['site_id']])
        if env.cr.fetchone() not in ((previous_release,'paused'),(previous_release,'restoring')):
            raise AccessError('Native carry-forward requires the fenced source release')
    if (bound.public_id!=context['installation'] or release['site_id']!=row['site_id']
            or (previous_release or release['release_digest'])!=row['release_digest'] or row['effect_mode']!=definition.effect_mode):
        raise AccessError('Native job release/installation changed')
    jobs._validate(definition.input_schema,payload['input'])
    definition.authorize_resource(env,payload['input'],bound)
    return env,definition,payload,bound


def cancel(env,ident):
    """Invalidate a native occurrence under the current resource editor's authority.

    The editor may differ from the originating actor, who may now be revoked.
    The fixed registered definition authorizes the saved resource; callers cannot
    supply a scope, backing user, cancellation callback or permission snapshot.
    """
    durable._uuid(ident)
    with env.cr.savepoint():
        env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s FOR UPDATE',[ident])
        result=env.cr.fetchone()
        if not result:return False
        row=result[0];payload=_payload(row)
        definition=jobs.DEFINITIONS.get((row['handler'],row['handler_version']))
        if not definition or definition.authority!='native':raise AccessError('Native occurrence unavailable')
        _actor(env,provision=True)
        bound=_installation(env,definition,expected=row['installation_id'])
        release=current_release(env)
        if release['site_id']!=row['site_id'] or payload['context']['installation']!=bound.public_id:
            raise AccessError('Native occurrence site/installation changed')
        jobs._validate(definition.input_schema,payload['input'])
        definition.authorize_resource(env,payload['input'],bound)
        return durable.cancel_scheduled(env.cr,ident,actor_id=row['actor_id'],workspace_id=None)
