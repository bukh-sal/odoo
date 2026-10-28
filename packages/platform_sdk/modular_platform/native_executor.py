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
import time

from .approval_validation import IndependentValidator
from .catalog import Catalog
from .contracts import load_json
from .deployment import DockerObserver, _run
from .operator_os import OperatorError, OperationLocks, protect_directory
from .operator_store import _write_new
from .plans import data_digest


ARCHIVE_FILESTORE = """import pathlib,sys,tarfile
root=pathlib.Path('/var/lib/modular/filestore')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 if root.exists(): archive.add(root,arcname='filestore',recursive=True)
"""


class NativeExecutor:
    def __init__(self, store, target_path, catalog_root, validator):
        self.store, self.target_path = store, Path(target_path)
        self.config = load_json(self.target_path.read_bytes())
        self.observer = DockerObserver(self.config)
        self.catalog_root, self.validator = catalog_root, validator

    def _validate(self, *, quiesced=False):
        return IndependentValidator(self.config, self.catalog_root, self.validator, quiesced=quiesced)

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

    def _child(self, operation, suffix, *, writable=False, network=True):
        project = self.config['project']
        name = project+'-op-'+operation+'-'+suffix
        arguments = ['docker', 'run', '--name', name, '--label', 'com.modular.operation='+operation,
            '--label', 'com.modular.deployment='+self.config['deployment_id'], '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp',
            '--memory', '1536m', '--cpus', '2', '--network', project+'_runtime' if network else 'none',
            '--mount', 'type=volume,source='+project+'_appconfig,target=/run/secrets,readonly',
            '--mount', 'type=volume,source='+project+'_filestore,target=/var/lib/modular'+('' if writable else ',readonly'),
            '--entrypoint', '/venv/bin/python', self.config['image_id']]
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
        self._private_command(arguments+['-c', ARCHIVE_FILESTORE], checkpoint/'filestore.tar.gz')
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
        if bundle['plan']['operation_type'] != 'install':
            raise OperatorError('This executor currently accepts current-image native installation only')
        plan = bundle['plan']
        with OperationLocks(self.store.root/'locks', plan['deployment_id'], plan['site_ids']) as locks:
            if self.store.status(operation)['state'] == 'completed':
                return self.store.status(operation)
            self.store.reserve(operation, locks, self._validate())
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
                addons = sorted({plugins[item['plugin_id']]['manifest']['runtime']['addon_name'] for item in bundle['operation_lock']['targets']})
                arguments, child = self._child(operation, 'native', writable=True)
                self._private_command(arguments+['odoo-bin', '-c', '/run/secrets/odoo_config', '-d', self.config['sites'][0]['database'],
                    '-i', ','.join(addons), '--stop-after-init', '--no-http', '--workers=0', '--max-cron-threads=0', '--without-demo'], directory/'native.log')
                locks.check()
                payload = {'site_id': self.config['sites'][0]['site_id'], 'deployment_id': self.config['deployment_id'],
                    'operation_id': operation, 'generation': bundle['operation_lock']['release']['generation'],
                    'release_digest': plan['target_release_digest'], 'targets': bundle['operation_lock']['targets'],
                    'plugins': plugins, 'bindings': bundle['operation_lock']['bindings']}
                arguments, child = self._child(operation, 'metadata')
                arguments.insert(2, '-i')
                self._private_command(arguments+['-c', Path(__file__).with_name('install_metadata.py').read_text()], directory/'metadata.log', input=json.dumps(payload).encode())
                self.store.advance(operation, locks, 'migrated')
                failure = 'READINESS_FAILED'
                _run(['docker', 'start', app])
                self.store.advance(operation, locks, 'workers_replaced')
                target = dict(self.config, generation=bundle['operation_lock']['release']['generation'], release_created_at=plan['created_at'])
                deadline = time.monotonic()+90
                while True:
                    try:
                        probe = "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8069/web/login',timeout=5); assert r.status==200"
                        _run(['docker', 'exec', app, '/venv/bin/python', '-c', probe])
                        break
                    except (ValueError, OSError):
                        if time.monotonic() >= deadline:
                            raise OperatorError('Registry readiness deadline exceeded')
                        time.sleep(1)
                observation = DockerObserver(target).read()
                state = DockerObserver(target).state(observation, snapshot)['state']
                if state['release_digest'] != plan['target_release_digest']:
                    raise OperatorError('Ready release differs from approved executable lock')
                expected = {(item['installation_id'], item['workspace_id']) for item in bundle['operation_lock']['targets']}
                actual = {(item['installation_id'], item['workspace_id']) for item in state['installations']
                          if item['state']=='installed' and item['feature_state']=='enabled'}
                if not expected <= actual or state['bindings'] != bundle['operation_lock']['bindings']:
                    raise OperatorError('Ready native metadata/bindings differ from exact targets')
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
                return self.store.status(operation)
            except BaseException:
                # Keep traffic in maintenance on any uncertain state; never
                # infer database rollback from a process exit or Python error.
                self.store.fail(operation, locks, code=failure)
                raise
