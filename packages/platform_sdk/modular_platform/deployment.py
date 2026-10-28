"""Independent read-only observation of the qualified single-host Docker profile.

This adapter uses operator-selected container labels and PostgreSQL READ ONLY
transactions. It never imports installed plugin code or invokes the native ORM.
Production target authorization and executor mutations are separate concerns.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from uuid import UUID

from .contracts import load_json, normalize_manifest, validate
from .plans import data_digest, release_lock
from .resolution import PlanningError, resolve_release


OBSERVE_SQL = """
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '5s';
SELECT jsonb_build_object(
 'site_id',(SELECT value FROM ir_config_parameter WHERE key='mp.site_id'),
 'installations',COALESCE((SELECT jsonb_agg(jsonb_build_object('installation_id',public_id,'plugin_id',plugin_id,'version',version,'digest',artifact_digest,'runtime',runtime,'metadata_state',state,'manifest',manifest) ORDER BY public_id) FROM mp_plugin_installation),'[]'::jsonb),
 'features',COALESCE((SELECT jsonb_agg(jsonb_build_object('installation_id',i.public_id,'plugin_id',f.plugin_id,'workspace_id',w.public_id,'feature_state',f.availability) ORDER BY i.public_id,w.public_id) FROM mp_workspace_plugin f JOIN mp_plugin_installation i ON i.id=f.installation_id JOIN mp_workspace w ON w.id=f.workspace_id),'[]'::jsonb),
 'workspaces',COALESCE((SELECT jsonb_agg(jsonb_build_object('workspace_id',public_id,'state',state,'policy_generation',policy_generation) ORDER BY public_id) FROM mp_workspace),'[]'::jsonb),
 'memberships',COALESCE((SELECT jsonb_agg(jsonb_build_object('principal_id',p.public_id,'workspace_id',w.public_id,'role',m.role,'state',m.state,'principal_state',p.state) ORDER BY p.public_id,w.public_id) FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id JOIN mp_workspace w ON w.id=m.workspace_id),'[]'::jsonb),
 'bindings',COALESCE((SELECT jsonb_agg(jsonb_build_object('descriptor',descriptor,'state',state) ORDER BY public_id) FROM mp_service_binding),'[]'::jsonb),
 'grants',COALESCE((SELECT jsonb_agg(jsonb_build_object('installation_id',i.public_id,'workspace_id',w.public_id,'capability',g.capability,'state',g.state,'policy_version',g.policy_version) ORDER BY i.public_id,w.public_id,g.capability) FROM mp_plugin_grant g JOIN mp_plugin_installation i ON i.id=g.installation_id JOIN mp_workspace w ON w.id=g.workspace_id),'[]'::jsonb),
 'native_modules',COALESCE((SELECT jsonb_agg(jsonb_build_object('addon',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module WHERE state IN ('installed','to install','to upgrade','to remove')),'[]'::jsonb)
);
ROLLBACK;
"""

# Read static tool/distribution metadata only. Source files are hashed, never
# imported. Tokens/config/filestore/database connection material is not read.
OBSERVE_RUNTIME = """import hashlib,importlib.metadata,json,pathlib,platform,sys
from packaging.markers import default_environment
from packaging.tags import sys_tags
root=pathlib.Path('/opt/modular')
inventory=json.loads((root/'distribution-inventory.json').read_text())
bad=[name for name,digest in inventory['files'].items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest]
expected={name for name in inventory['files'] if name.startswith(('addons/','odoo/addons/'))}
actual={path.relative_to(root).as_posix() for folder in ('addons','odoo/addons') for path in (root/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc'}
runtime_lock=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest()
wheels=[]
for distribution in importlib.metadata.distributions():
    source={str(entry):hashlib.sha256(pathlib.Path(distribution.locate_file(entry)).read_bytes()).hexdigest() for entry in (distribution.files or []) if str(entry).endswith(('.py','.so','.dist-info/METADATA')) and pathlib.Path(distribution.locate_file(entry)).is_file()}
    digest='sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    wheels.append({'name':distribution.metadata['Name'],'version':distribution.version,'kind':'runtime_distribution','requires_python':distribution.metadata.get('Requires-Python',''),'requires_dist':distribution.requires or [],'digest':digest})
print(json.dumps({'inventory':inventory,'inventory_digest':'sha256:'+hashlib.sha256((root/'distribution-inventory.json').read_bytes()).hexdigest(),'python_lock_digest':'sha256:'+runtime_lock,'python':platform.python_version(),'architecture':platform.machine(),'markers':default_environment(),'accepted_wheel_tags':[str(tag) for tag in sys_tags()],'python_metadata':sorted(wheels,key=lambda item:item['name'].lower()),'modified_files':bad,'unexpected_addon_files':sorted(actual-expected),'missing_addon_files':sorted(expected-actual)}))
"""


def _run(arguments, *, input=None):
    completed = subprocess.run(arguments, input=input, capture_output=True, timeout=60)
    if completed.returncode:
        # Native diagnostics may contain configuration; do not echo raw stderr.
        raise PlanningError('Independent Docker observation failed; command exit ' + str(completed.returncode))
    if len(completed.stdout) > 16 * 1024 * 1024:
        raise PlanningError('Observed metadata size limit')
    return completed.stdout


class DockerObserver:
    def __init__(self, configuration):
        required = {'schema_version', 'deployment_id', 'project', 'sites', 'image_id',
                    'generation', 'policy_version', 'operator_authorization_generation', 'release_created_at'}
        if not isinstance(configuration, dict) or set(configuration) != required or configuration['schema_version'] != 1:
            raise PlanningError('Exact independently owned deployment configuration required')
        self.config = configuration
        if not re.fullmatch('mp-r0-r1[a-z0-9]+', configuration['project']):
            raise PlanningError('This adapter currently targets only named disposable R1 projects')
        if str(UUID(configuration['deployment_id'])) != configuration['deployment_id'] or not re.fullmatch('sha256:[0-9a-f]{64}', configuration['image_id']):
            raise PlanningError('Pinned deployment/image identity required')
        if not configuration['sites']:
            raise PlanningError('Every sharing site must be explicitly configured')
        for site in configuration['sites']:
            if set(site) != {'site_id', 'database'} or str(UUID(site['site_id'])) != site['site_id'] or not re.fullmatch('mp_disposable_r0_r1_[a-z0-9_]+', site['database']):
                raise PlanningError('Explicit disposable site/database identity required')

    def _container(self, service):
        raw = _run(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + self.config['project'],
                    '--filter', 'label=com.docker.compose.service=' + service]).decode().split()
        if len(raw) != 1 or not re.fullmatch('[0-9a-f]{12,64}', raw[0]):
            raise PlanningError('Exactly one running container per observed service required')
        return raw[0]

    def read(self):
        app, database = self._container('app'), self._container('db')
        identity = load_json(_run(['docker', 'inspect', '--format', '{{json .Image}}', app]))
        if identity != self.config['image_id']:
            raise PlanningError('Running application image differs from operator pin')
        runtime = load_json(_run(['docker', 'exec', app, '/venv/bin/python', '-c', OBSERVE_RUNTIME]))
        if runtime['modified_files'] or runtime['unexpected_addon_files'] or runtime['missing_addon_files']:
            raise PlanningError('Running executable source differs from the curated release inventory')
        sites = []
        for target in self.config['sites']:
            raw = _run(['docker', 'exec', '-i', database, 'psql', '-X', '-qAt', '-U', 'postgres',
                        '-v', 'ON_ERROR_STOP=1', '-d', target['database']], input=OBSERVE_SQL.encode())
            site = load_json(raw)
            if site['site_id'] != target['site_id']:
                raise PlanningError('Observed site identity differs from operator target')
            if any(item['state'] != 'installed' for item in site['native_modules']):
                raise PlanningError('Native registry has a pending/uncertain module operation')
            sites.append(site)
        return {'image_id': identity, 'runtime': runtime, 'sites': sites}

    def state(self, observation, catalog):
        from .projection import project_deployment
        return project_deployment(self.config, observation, catalog)
