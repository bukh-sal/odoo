"""Private human-origin native application jobs; no workspace impersonation.

Draft AT-01 adapter. Real installation and actor are selected from server-owned
metadata. Business handlers always receive the original non-sudo Environment.
"""
from dataclasses import dataclass
from uuid import uuid4

from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable
from modular_platform.contracts import ContractError, normalize_manifest, native_version

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


def _installation(env,definition,expected=None):
    env['mp.plugin.installation'].flush_model()
    env['ir.module.module'].flush_model(['name','state','latest_version'])
    env.cr.execute("""SELECT id,public_id,manifest,version FROM mp_plugin_installation
        WHERE plugin_id=%s AND state='installed' AND runtime='native' FOR SHARE""",[definition.plugin])
    row=env.cr.fetchone()
    if not row or (expected is not None and row[0]!=expected):
        raise AccessError('Native application installation unavailable')
    manifest=normalize_manifest(row[2])
    if (manifest['plugin']['id']!=definition.plugin or manifest['plugin']['version']!=row[3]
            or manifest['runtime']['kind']!='native' or manifest['runtime']['addon_name']!=definition.addon
            or 'site' not in manifest['activation']['scopes']):
        raise AccessError('Native application identity changed')
    env.cr.execute("""SELECT id FROM ir_module_module WHERE name=%s
        AND state='installed' AND latest_version=%s FOR SHARE""",
        [definition.addon,native_version(manifest['plugin']['version'])])
    if not env.cr.fetchone():raise AccessError('Native application code/version unavailable')
    return NativeBound(row[0],row[1],definition.plugin,definition.addon)


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


def authorized(metadata_env,row,definition):
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
    metadata_env.cr.execute('SELECT user_id FROM mp_principal WHERE id=%s',[row['actor_id']])
    actor=metadata_env.cr.fetchone()
    if not actor:raise AccessError('Original native actor unavailable')
    env=api.Environment(metadata_env.cr,actor[0],{},su=False)
    if _actor(env)!=row['actor_id']:raise AccessError('Native job actor changed')
    bound=_installation(env,definition,expected=row['installation_id'])
    release=current_release(env)
    if (bound.public_id!=context['installation'] or release['site_id']!=row['site_id']
            or release['release_digest']!=row['release_digest'] or row['effect_mode']!=definition.effect_mode):
        raise AccessError('Native job release/installation changed')
    jobs._validate(definition.input_schema,payload['input'])
    definition.authorize_resource(env,payload['input'],bound)
    return env,definition,payload,bound
