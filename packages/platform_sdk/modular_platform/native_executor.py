"""Recoverable single-host executor for current-image native installation.

Independent OS approval and actual process locks precede all mutations. A
possible native commit leaves traffic stopped and recovery_required on error.
No application queue field chooses a command, volume, image or DB credential.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

from .approval_validation import IndependentValidator
from .catalog import Catalog
from .contracts import load_json
from .deployment import DockerObserver, _run
from .operator_os import OperatorError, OperationLocks, protect_directory
from .operator_store import _write_new
from .plans import data_digest


ARCHIVE_FILESTORE = """import pathlib,sys,tarfile
root=pathlib.Path(sys.argv[2] if len(sys.argv)>2 else '/var/lib/modular/filestore')/sys.argv[1]
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 if root.exists(): archive.add(root,arcname='filestore/'+sys.argv[1],recursive=True)
"""


def verify_native_state(bundle,state,previous,observation):
    if state['release_digest']!=bundle['plan']['target_release_digest']:
        raise OperatorError('Ready release differs from approved executable lock')
    expected={(item['installation_id'],item['workspace_id']):dict(item) for item in previous['installations']}
    for target in bundle['operation_lock']['targets']:
        key=target['installation_id'],target['workspace_id']
        if target['action']=='install':
            if key in expected:raise OperatorError('Install target already exists in checkpoint')
            expected[key]={name:value for name,value in target.items() if name!='action'}|{
                'state':'installed','feature_state':'enabled','metadata_state':'installed'}
        elif key not in expected:raise OperatorError('Upgrade target is absent from checkpoint')
    actual={(item['installation_id'],item['workspace_id']):item for item in state['installations']}
    if actual!=expected or state['bindings']!=bundle['operation_lock']['bindings']:
        raise OperatorError('Ready metadata/bindings or preserved availability differ from approved targets')
    grants={(site['site_id'],row['workspace_id'],row['installation_id'],row['capability']):row
        for site in observation['sites'] for row in site['grants']}
    for change in bundle['plan']['permission_changes']:
        target=next(item for item in bundle['operation_lock']['targets'] if item['plugin_id']==change['plugin_id'] and item['workspace_id']==change['workspace_id'])
        actual=grants.get((target['site_id'],target['workspace_id'],target['installation_id'],change['capability']))
        if not actual or actual['state']!=('approved' if change['action']=='grant' else 'revoked') or actual['policy_version']!=bundle['plan']['policy_version']:
            raise OperatorError('Ready permission metadata differs from exact approved changes')


class NativeExecutor:
    staged_execution=False
    def __init__(self, store, target_path, catalog_root, validator):
        self.store, self.target_path = store, Path(target_path)
        self.config = load_json(self.target_path.read_bytes())
        self.observer = DockerObserver(self.config)
        self.catalog_root, self.validator = catalog_root, validator

    def _validate(self, *, quiesced=False):
        from .release_staging import StageStore
        stages=StageStore(self.store,self.config,Catalog(self.catalog_root,self.validator,readonly=True))
        return IndependentValidator(self.config, self.catalog_root, self.validator, quiesced=quiesced,stage_store=stages)

    def _execution_image(self,bundle):
        return bundle['operation_lock'].get('staged_image',{}).get('target_image_id',self.config['image_id'])

    def _replace_workers(self,app,bundle,directory):
        target=dict(self.config,image_id=self._execution_image(bundle),
            generation=bundle['operation_lock']['release']['generation'],release_created_at=bundle['plan']['created_at'])
        from .workers import ensure
        inventory=bundle['operation_lock'].get('staged_image',{}).get('inventory_digest')
        if not inventory:
            inventory=self.observer.read(quiesced=True)['runtime']['inventory_digest']
        app=ensure(target,target['image_id'],bundle['plan']['operation_id'],inventory_digest=inventory)
        target['worker_id']=app
        _write_new(directory/'worker-replacement.json',{'container_id':app,'configuration':target,'previous_image_id':self.config['image_id']})
        _run(['docker','start',app])
        return app,target

    def mirror_progress(self, operation):
        # App progress is a best-effort mirror. A broken/untrusted application
        # must not hide or invalidate a successful independent journal result.
        try:
            if not self.store.application_request(operation):return
            from .app_channel import publish_status
            observer=DockerObserver(load_json(self.target_path.read_bytes()))
            publish_status(self.store,observer,Catalog(self.catalog_root,self.validator,readonly=True),operation)
        except Exception:
            pass  # Existing UI observation becomes stale; local show still works.

    def _inspect(self, container):
        return load_json(_run(['docker', 'inspect', container]))[0]

    def _topology(self):
        if len(self.config['sites']) != 1:
            raise OperatorError('This executor requires the qualified single-site profile')
        app = self.observer._container('app')
        database = self.observer._container('db')
        edge = self.observer._container('edge')
        app_info, db_info = self._inspect(app), self._inspect(database)
        project = self.config['project']
        expected = {'/var/lib/modular': project+'_filestore', '/run/secrets': project+'_appconfig'}
        if (app_info['Image'] != self.config['image_id']
                or {mount['Destination']: mount.get('Name') for mount in app_info['Mounts']} != expected
                or not app_info['HostConfig']['ReadonlyRootfs']
                or set(app_info['NetworkSettings']['Networks']) != {project+'_runtime'}
                or not db_info['State']['Running']):
            raise OperatorError('Unexpected executor deployment topology')
        return app, database, edge

    def _child(self, operation, suffix, *, writable=False, network=True,image_id=None):
        project = self.config['project']
        name = project+'-op-'+operation+'-'+suffix
        arguments = ['docker', 'run', '--name', name, '--label', 'com.modular.operation='+operation,
            '--label', 'com.modular.deployment='+self.config['deployment_id'], '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp',
            '--memory', '1536m', '--cpus', '2', '--network', project+'_runtime' if network else 'none',
            '--mount', 'type=volume,source='+project+'_appconfig,target=/run/secrets,readonly',
            '--mount', 'type=volume,source='+project+'_filestore,target=/var/lib/modular'+('' if writable else ',readonly'),
            '--entrypoint', '/venv/bin/python', image_id or self.config['image_id']]
        return arguments, name

    def _private_command(self, arguments, path, *, input=None, timeout=300):
        # Preserve private diagnostics for recovery. Native log text never goes
        # into app status, stdout or a tracked evidence bundle.
        with path.open('xb') as stream, path.with_name(path.name+'.stderr.log').open('xb') as errors:
            result = subprocess.run(arguments, input=input, stdout=stream, stderr=errors, timeout=timeout)
            stream.flush()
            os.fsync(stream.fileno())
        if result.returncode:
            raise OperatorError('Controlled maintenance child failed; private diagnostics retained')

    def _checkpoint(self, operation, bundle, database, directory):
        root = protect_directory(self.store.root/'checkpoints')
        checkpoint = protect_directory(root/operation)
        site = self.config['sites'][0]
        self._private_command(['docker', 'exec', database, 'pg_dump', '-U', 'postgres', '--no-owner', '-Fc', site['database']],
                              checkpoint/'database.dump')
        arguments, name = self._child(operation, 'checkpoint', network=False)
        self._private_command(arguments+['-c', ARCHIVE_FILESTORE,site['database']], checkpoint/'filestore.tar.gz')
        previous = {'schema_version': 1, 'operation_id': operation, 'plan_hash': bundle['plan_hash'],
            'configuration': self.config, 'previous_release': self.observer.state(self.observer.read(quiesced=True),
                Catalog(self.catalog_root, self.validator, readonly=True).snapshot())['state'],
            'files': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in checkpoint.iterdir() if path.is_file()},
            'app_config_volume': self.config['project']+'_appconfig',
            'secret_recovery': 'Retain separately secured appconfig/dbconfig volumes; values intentionally excluded.',
            'external_dispatch': 'Disabled: no external runtime or jobs installed in this profile.',
            'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        _write_new(checkpoint/'manifest.json', previous)
        # Keep a stable local tag as well as its immutable image identity.
        _run(['docker', 'tag', self.config['image_id'], 'modular-platform:retained-'+operation])
        _write_new(directory/'checkpoint.json', {'id': operation, 'manifest_digest': data_digest(previous)})
        return operation

    def apply(self, operation):
        bundle = self.store.bundle(operation)
        if 'staged_image' in bundle['operation_lock'] and not self.staged_execution:
            raise OperatorError('Staged native execution must use the new-image executor adapter; current-image mutation denied')
        if bundle['plan']['operation_type'] not in (('install','upgrade') if self.staged_execution else ('install',)):
            raise OperatorError('Native execution requires a supported install/upgrade plan')
        plan = bundle['plan']
        with OperationLocks(self.store.root/'locks', plan['deployment_id'], plan['site_ids']) as locks:
            if self.store.status(operation)['state'] == 'completed':
                self.mirror_progress(operation)
                return self.store.status(operation)
            self.store.reserve(operation, locks, self._validate())
            self.mirror_progress(operation)
            stages = protect_directory(self.store.root/'stages')
            directory = stages/operation
            if directory.exists():
                # Reconcile a crashed/pre-mutation attempt; never silently
                # overwrite diagnostics or infer that a child also stopped.
                raise OperatorError('Existing execution stage requires explicit reconciliation')
            directory = protect_directory(directory)
            failure = 'STAGING_FAILED'
            try:
                self._validate()(bundle)
                app, database, edge = self._topology()
                _write_new(directory/'bundle.json', bundle)
                _write_new(directory/'configuration.json', self.config)
                self.store.advance(operation, locks, 'staged')
                self.mirror_progress(operation)
                failure = 'DRAIN_FAILED'
                locks.check()
                _run(['docker', 'stop', '--time', '20', edge])
                self.store.advance(operation, locks, 'maintenance')
                _run(['docker', 'stop', '--time', '30', app])
                info = self._inspect(app)
                if info['State']['Running'] or info['State']['ExitCode'] != 0:
                    raise OperatorError('Worker drain did not finish gracefully; reconcile uncertain requests')
                active = _run(['docker', 'exec', database, 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'postgres', '-c',
                    "SELECT count(*) FROM pg_stat_activity WHERE datname='"+self.config['sites'][0]['database']+"' AND usename<>'postgres'"]).decode().strip()
                if active != '0':
                    raise OperatorError('Unexpected database clients prevent a consistent checkpoint')
                self.store.advance(operation, locks, 'drained')
                failure = 'BACKUP_FAILED'
                checkpoint = self._checkpoint(operation, bundle, database, directory)
                self.store.advance(operation, locks, 'checkpointed', backup_id=checkpoint)
                failure = 'MUTATION_FAILED'
                self.store.before_mutation(operation, locks, self._validate(quiesced=True))
                snapshot = Catalog(self.catalog_root, self.validator, readonly=True).snapshot()
                plugins = {item['manifest']['plugin']['id']: item for item in snapshot
                    if any(entry['plugin_id'] == item['manifest']['plugin']['id'] and entry['digest'] == item['digest']
                           for entry in bundle['operation_lock']['release']['plugins'])}
                image=self._execution_image(bundle)
                installs=sorted({plugins[item['plugin_id']]['manifest']['runtime']['addon_name'] for item in bundle['operation_lock']['targets'] if item['action']=='install'})
                upgrades=sorted({plugins[item['plugin_id']]['manifest']['runtime']['addon_name'] for item in bundle['operation_lock']['targets'] if item['action']=='upgrade'})
                arguments, child = self._child(operation, 'native', writable=True,image_id=image)
                flags=(['-i',','.join(installs)] if installs else [])+(['-u',','.join(upgrades)] if upgrades else [])
                self._private_command(arguments+['odoo-bin', '-c', '/run/secrets/odoo_config', '-d', self.config['sites'][0]['database'],
                    *flags, '--stop-after-init', '--no-http', '--workers=0', '--max-cron-threads=0', '--without-demo'], directory/'native.log')
                locks.check()
                payload = {'site_id': self.config['sites'][0]['site_id'], 'deployment_id': self.config['deployment_id'],
                    'operation_id': operation, 'generation': bundle['operation_lock']['release']['generation'],
                    'release_digest': plan['target_release_digest'], 'targets': bundle['operation_lock']['targets'],
                    'plugins': plugins, 'bindings': bundle['operation_lock']['bindings'],
                    'permission_changes':bundle['plan']['permission_changes'],'database':self.config['sites'][0]['database'],
                    'policy_version':plan['policy_version'],
                    'previous_plugins':{item['plugin_id']:item for item in load_json((self.store.root/'checkpoints'/checkpoint/'manifest.json').read_bytes())['previous_release']['release_lock']['plugins']}}
                arguments, child = self._child(operation, 'metadata',image_id=image)
                arguments.insert(2, '-i')
                self._private_command(arguments+['-c', Path(__file__).with_name('install_metadata.py').read_text()], directory/'metadata.log', input=json.dumps(payload).encode())
                self.store.advance(operation, locks, 'migrated')
                failure = 'READINESS_FAILED'
                app,target=self._replace_workers(app,bundle,directory)
                self.store.advance(operation, locks, 'workers_replaced')
                from .workers import wait_ready
                wait_ready(app)
                observation = DockerObserver(target).read()
                state = DockerObserver(target).state(observation, snapshot)['state']
                previous=load_json((self.store.root/'checkpoints'/checkpoint/'manifest.json').read_bytes())['previous_release']
                verify_native_state(bundle,state,previous,observation)
                self.store.advance(operation, locks, 'ready')
                temporary = self.target_path.with_name(self.target_path.name+'.'+operation+'.tmp')
                _write_new(temporary, target)
                os.replace(temporary, self.target_path)
                self.store.advance(operation, locks, 'release_published')
                # Persist the conservative "traffic may have opened" fence
                # BEFORE the external command; a crash after it starts must
                # never permit an automatic destructive restore.
                self.store.advance(operation, locks, 'traffic_resumed')
                _run(['docker', 'start', edge])
                _write_new(directory/'result.json', {'state': 'completed', 'release_digest': state['release_digest'],
                    'limits': ['Client epoch refresh and general new-image staging are pending G5 qualification.']})
                self.store.advance(operation, locks, 'completed')
                self.mirror_progress(operation)
                return self.store.status(operation)
            except BaseException:
                # Keep traffic in maintenance on any uncertain state; never
                # infer database rollback from a process exit or Python error.
                self.store.fail(operation, locks, code=failure)
                raise


class StagedNativeExecutor(NativeExecutor):
    """Same journal/checkpoint protocol, with independently pinned replacement."""
    staged_execution=True

    def apply(self,operation):
        bundle=self.store.bundle(operation)
        if 'staged_image' not in bundle['operation_lock']:
            raise OperatorError('Staged executor requires an exact independent image descriptor')
        return super().apply(operation)
