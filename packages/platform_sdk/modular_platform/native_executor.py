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
from .contracts import CONTRACTS, load_json
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
    feature_states={(r['installation_id'],r['workspace_id']):r['availability'] for r in bundle['operation_lock'].get('feature_states',[])}
    for target in bundle['operation_lock']['targets']:
        key=target['installation_id'],target['workspace_id']
        if target['action']=='install':
            if key in expected and (expected[key]['state']!='not_installed' or expected[key]['metadata_state']!='removed'):
                raise OperatorError('Install target already exists in checkpoint')
            expected[key]={name:value for name,value in target.items() if name!='action'}|{
                'state':'installed','feature_state':feature_states.get(key,'enabled'),'metadata_state':'installed'}
        elif target['action']=='uninstall':
            if key not in expected:raise OperatorError('Uninstall target is absent from checkpoint')
            expected[key].update(state='not_installed',feature_state='suspended',metadata_state='removed')
        elif target['action']=='remove':
            if key in expected and (expected[key]['state']!='not_installed' or expected[key]['metadata_state']!='removed' or expected[key]['feature_state']!='suspended'):
                raise OperatorError('Source removal requires inert retained installation metadata')
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
    if bundle['plan'].get('operation_type') in ('uninstall','remove'):
        affected={t['installation_id'] for t in bundle['operation_lock']['targets']}
        if any(row['state']=='approved' for site in observation['sites'] for row in site['grants'] if row['installation_id'] in affected):
            raise OperatorError('Ready uninstall retained an affected approved grant')
    if feature_states and any(row['state']=='approved' and feature_states.get((row['installation_id'],row['workspace_id']))=='suspended'
            for site in observation['sites'] for row in site['grants']):
        raise OperatorError('Ready reinstall revived a grant in a suspended retained scope')


def native_maintenance_flags(bundle,plugins):
    """Commands derive only from the independently reconstructed operation lock."""
    operation=bundle['plan']['operation_type'];lock=bundle['operation_lock']
    installs=sorted({plugins[item['plugin_id']]['manifest']['runtime']['addon_name'] for item in lock['targets'] if item['action']=='install'})
    upgrades=sorted({plugins[item['plugin_id']]['manifest']['runtime']['addon_name'] for item in lock['targets'] if item['action']=='upgrade'})
    if operation=='uninstall':
        if (installs or upgrades or any(t['action']!='uninstall' for t in lock['targets']) or not lock.get('native_uninstall_impact')
                or {'native_core_changes','platform_source_diff','staged_image'}.intersection(lock)):
            raise OperatorError('Native uninstall requires its exact independently approved impact and fixed child')
        if not bundle['plan']['destructive'] or not bundle['plan']['backup']['required']:
            raise OperatorError('Native uninstall requires destructive acknowledgement and checkpoint')
        return None  # The explicit fixed child is selected below, never a CLI -i/-u.
    if operation=='remove':
        if (installs or upgrades or any(t['action']!='remove' for t in lock['targets'])
                or not lock.get('platform_source_diff') or 'staged_image' not in lock
                or any(row['target_sha256'] is not None for row in lock['platform_source_diff'])
                or 'native_core_changes' in lock or bundle['plan']['permission_changes'] or bundle['plan']['trust_changes']
                or not bundle['plan']['backup']['required']):
            raise OperatorError('Source removal requires exact staged subtraction and checkpoint without native maintenance')
        return None
    if operation in ('deploy','core_upgrade'):
        if installs or upgrades or not lock.get('platform_source_diff') or any(item['action']!='deploy' for item in lock['targets']):
            raise OperatorError('Platform maintenance cannot combine plugin migrations')
        if operation=='deploy':
            if 'native_core_changes' in lock:raise OperatorError('Static deploy cannot invoke native core maintenance')
            return None
        from .release_staging import CORE_ADDONS
        changes=lock.get('native_core_changes',[])
        upgrades=[item['addon'] for item in changes]
        if (not upgrades or len(upgrades)!=len(set(upgrades)) or not set(upgrades)<=CORE_ADDONS
                or not bundle['plan']['destructive'] or not bundle['plan']['backup']['required']):
            raise OperatorError('Exact versioned core maintenance/checkpoint acknowledgement required')
    elif 'native_core_changes' in lock:
        raise OperatorError('Native core maintenance requires its explicit operation')
    return (['-i',','.join(installs)] if installs else [])+(['-u',','.join(upgrades)] if upgrades else [])


def require_native_uninstall_runtime(runtime):
    """Reject old/different maintenance readers before reserving or draining."""
    files = runtime['inventory']['files']
    paths = {'packages/platform_sdk/modular_platform/' + name: Path(__file__).with_name(name)
             for name in ('lifecycle_impact.py', 'native_uninstall.py', 'uninstall_metadata.py')}
    paths['packages/contracts/v1/lifecycle-impact.schema.json'] = CONTRACTS / 'lifecycle-impact.schema.json'
    if any(files.get(name) != hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()):
        raise OperatorError('Native uninstall requires an independently staged compatible maintenance image before any drain or mutation')


def require_native_reinstall_runtime(runtime):
    files=runtime['inventory']['files']
    names=('lifecycle_planning.py','projection.py','install_metadata.py','planning_cli.py','plans.py')
    if any(files.get('packages/platform_sdk/modular_platform/'+name)!=hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names):
        raise OperatorError('Retained-scope reinstall requires a compatible independently staged maintenance image')


def require_native_removal_runtime(runtime):
    names=('artifact_removal.py','remove_metadata.py','projection.py','planning_cli.py','plans.py')
    files=runtime['inventory']['files']
    if any(files.get('packages/platform_sdk/modular_platform/'+name)!=hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names):
        raise OperatorError('Source removal requires an independently staged compatible publication image before any drain or mutation')


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
            generation=bundle['operation_lock']['release']['generation'],release_created_at=bundle['plan']['created_at'],
            published_release=bundle['operation_lock']['release'])
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
        # Maintenance stdout can carry configuration or binary checkpoints. Keep
        # attached output for the private operator capture, never a daemon log.
        arguments = ['docker', 'run', '--log-driver', 'none', '--name', name, '--label', 'com.modular.operation='+operation,
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

    def _prepare_assets(self, operation, target, state, observation, directory, *, suffix='assets'):
        arguments, child = self._child(operation, suffix, writable=True, image_id=target['image_id'])
        arguments.insert(2, '-i')
        asset_target = {'database': target['sites'][0]['database'],
            'site_id': target['sites'][0]['site_id'], 'deployment_id': target['deployment_id'],
            'generation': target['generation'], 'release_digest': state['release_digest'],
            'inventory_digest': observation['runtime']['inventory_digest']}
        self._private_command(arguments+['-c', Path(__file__).with_name('prepare_assets.py').read_text()],
            directory/'assets.json', input=json.dumps(asset_target).encode())

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
        dispatch=directory/'dispatch-fence/fence.json'
        if dispatch.exists() and load_json(dispatch.read_bytes())['result'] is not None:
            from .dispatch_operator import DispatchMaintenance
            actual=DispatchMaintenance(self).inspect()
            if actual!=load_json(dispatch.read_bytes())['result']['after']:
                raise OperatorError('Dispatch changed after drain; checkpoint cannot be declared coordinated')
            previous['dispatch_profile']=actual
            previous['external_dispatch']='Native queue/receipt profile fenced; remote effects are excluded by this profile.'
        _write_new(checkpoint/'manifest.json', previous)
        # Keep a stable local tag as well as its immutable image identity.
        _run(['docker', 'tag', self.config['image_id'], 'modular-platform:retained-'+operation])
        _write_new(directory/'checkpoint.json', {'id': operation, 'manifest_digest': data_digest(previous)})
        return operation

    def apply(self, operation):
        bundle = self.store.bundle(operation)
        if 'staged_image' in bundle['operation_lock'] and not self.staged_execution:
            raise OperatorError('Staged native execution must use the new-image executor adapter; current-image mutation denied')
        if bundle['plan']['operation_type'] not in (('install','upgrade','deploy','core_upgrade','remove') if self.staged_execution else ('install','uninstall')):
            raise OperatorError('Native execution requires a supported install/upgrade plan')
        plan = bundle['plan']
        with OperationLocks(self.store.root/'locks', plan['deployment_id'], plan['site_ids']) as locks:
            journal = self.store.status(operation)
            if journal['state'] == 'completed':
                self.mirror_progress(operation)
                return self.store.status(operation)
            if journal['mutation_started']:
                # A dead executor can leave the app stopped or the candidate
                # stale. Fence its possible commit BEFORE requiring either.
                def no_replay(_):
                    raise OperatorError('Possible native mutation requires explicit reconciliation before revalidation')
                self.store.reserve(operation, locks, no_replay)
                raise OperatorError('Started native operation requires explicit reconciliation')
            if plan['operation_type']=='remove':
                from .release_staging import StageStore
                stages=StageStore(self.store,self.config,Catalog(self.catalog_root,self.validator,readonly=True))
                _,record=stages.load(bundle['operation_lock']['staged_image'])
                require_native_removal_runtime(record['runtime'])
            if not self.staged_execution:
                runtime=self.observer.read()['runtime']
                if runtime.get('published_release_protocol')!=1:
                    raise OperatorError('Native installation requires an image with the published-release profile reader; stage a compatible candidate')
                if plan['operation_type']=='uninstall':require_native_uninstall_runtime(runtime)
                if plan['operation_type']=='install' and 'feature_states' in bundle['operation_lock']:require_native_reinstall_runtime(runtime)
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
                from .dispatch_operator import DispatchMaintenance
                dispatch=DispatchMaintenance(self)
                if dispatch.present():dispatch.require_runtime(self.observer.read()['runtime'])
                _write_new(directory/'bundle.json', bundle)
                _write_new(directory/'configuration.json', self.config)
                self.store.advance(operation, locks, 'staged')
                self.mirror_progress(operation)
                failure = 'DRAIN_FAILED'
                locks.check()
                _run(['docker', 'stop', '--time', '20', edge])
                self.store.advance(operation, locks, 'maintenance')
                dispatch_fence=None
                if dispatch.present():
                    dispatch_fence=dispatch.run('fence',operation,directory/'dispatch-fence',release_digest=plan['base_release_digest'])
                    dispatch.require_native(dispatch_fence['after'],closed=True)
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
                flags=native_maintenance_flags(bundle,plugins)
                if plan['operation_type']=='uninstall':
                    arguments, child = self._child(operation, 'native', writable=True, image_id=image)
                    arguments.insert(2,'-i')
                    native_payload=dict(database=self.config['sites'][0]['database'],site_id=self.config['sites'][0]['site_id'],
                        deployment_id=self.config['deployment_id'],operation_id=operation,plan_hash=bundle['plan_hash'],
                        impact=bundle['operation_lock']['native_uninstall_impact'],plugins=plugins,
                        inventory_digest=bundle['operation_lock']['release']['core_inventory_digest'])
                    self._private_command(arguments+['-c',Path(__file__).with_name('native_uninstall.py').read_text(encoding='utf8')],
                                          directory/'native.log',input=json.dumps(native_payload).encode())
                    effects=[]
                    for line in (directory/'native.log').read_text(encoding='utf8').splitlines():
                        try:value=load_json(line)
                        except ValueError:continue
                        if isinstance(value,dict) and value.get('kind')=='native_uninstall_effects':effects.append(value)
                    if len(effects)!=1 or effects[0]['operation_id']!=operation or effects[0]['plan_hash']!=bundle['plan_hash']:
                        raise OperatorError('Native uninstall effect observation is missing or mismatched; reconcile actual state')
                    _write_new(directory/'native-effects.json',effects[0])
                elif flags is None:
                    reason='Reviewed source removal; native schema already absent' if plan['operation_type']=='remove' else 'Reviewed platform-only image deployment; no native maintenance'
                    _write_new(directory/'native-skipped.json',{'reason':reason})
                else:
                    arguments, child = self._child(operation, 'native', writable=True,image_id=image)
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
                if 'feature_states' in bundle['operation_lock']:payload['feature_states']=bundle['operation_lock']['feature_states']
                arguments, child = self._child(operation, 'metadata',image_id=image)
                arguments.insert(2, '-i')
                metadata_script={'uninstall':'uninstall_metadata.py','remove':'remove_metadata.py'}.get(plan['operation_type'],'install_metadata.py')
                self._private_command(arguments+['-c', Path(__file__).with_name(metadata_script).read_text(encoding='utf8')], directory/'metadata.log', input=json.dumps(payload).encode())
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
                # Build public target assets under the approved image while
                # traffic is still closed. An asset failure after native commit
                # is recovery_required, never a falsely successful release.
                self._prepare_assets(operation, target, state, observation, directory)
                from .profile_channel import publish_profile
                _write_new(directory/'profile-publication.json',publish_profile(DockerObserver(target),
                    Catalog(self.catalog_root,self.validator,readonly=True)))
                dispatch_ready=None
                if dispatch.present(configuration=target):
                    prior_dispatch=plan['base_release_digest']
                    if dispatch_fence is None:
                        # First scheduler introduction: no supported dispatch
                        # existed in the base, so fence the exact new profile
                        # before classifying any migration-created work.
                        initial=dispatch.run('fence',operation,directory/'dispatch-initial',configuration=target,release_digest=plan['target_release_digest'])
                        dispatch.require_native(initial['after'],closed=True)
                        prior_dispatch=plan['target_release_digest']
                    reconciled=dispatch.reconcile_jobs(operation,directory/'dispatch-reconcile',configuration=target,
                        previous_release=prior_dispatch,release_digest=plan['target_release_digest'],inventory_digest=observation['runtime']['inventory_digest'])
                    if not reconciled['resume_allowed']:raise OperatorError('Uncertain job effects require independent reconciliation before dispatch or traffic')
                    dispatch_ready=dispatch.require_native(dispatch.inspect(configuration=target),closed=True)
                    _write_new(directory/'dispatch-ready.json',dispatch_ready)
                self.store.advance(operation, locks, 'ready')
                temporary = self.target_path.with_name(self.target_path.name+'.'+operation+'.tmp')
                _write_new(temporary, target)
                os.replace(temporary, self.target_path)
                self.store.advance(operation, locks, 'release_published')
                # Persist the conservative "traffic may have opened" fence
                # BEFORE the external command; a crash after it starts must
                # never permit an automatic destructive restore.
                self.store.advance(operation, locks, 'traffic_resumed')
                if dispatch_ready is not None:
                    self.store._authorize_plan(plan)
                    dispatch.run('enable',operation,directory/'dispatch-enable',configuration=target,
                        release_digest=plan['target_release_digest'],expected_digest=dispatch_ready['state_digest'])
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
