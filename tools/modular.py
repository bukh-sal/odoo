"""Local operator CLI. No network approval authority or plugin imports.

Run with the repository's locked Python environment. The operator config and
catalog belong outside any application-writable mount; G5 executor setup owns
the independently tested OS separation, not this argument parser.
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import fields
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.artifacts import ArchiveLimits, ArtifactError, ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.contracts import ContractError, load_json


class ConfigurationBoundValidator(ArtifactValidator):
    """A running operation cannot keep using a changed private trust policy."""
    def bind_configuration(self,path,raw):
        self.configuration_path=Path(path).resolve()
        self.configuration_size=len(raw);self.configuration_digest=hashlib.sha256(raw).digest()
        return self

    def _check_configuration(self):
        if (self.configuration_path.stat().st_size!=self.configuration_size
                or hashlib.sha256(self.configuration_path.read_bytes()).digest()!=self.configuration_digest):
            raise ArtifactError('Independent trust configuration changed; reload actual state and prepare/review again')

    def verify(self,source,*,expected_digest=None):
        self._check_configuration()
        result=super().verify(source,expected_digest=expected_digest)
        self._check_configuration()
        return result


def configuration(path):
    raw = Path(path).read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ArtifactError('Operator configuration size limit')
    config = load_json(raw)
    required = {'schema_version', 'mode', 'approved_digests', 'allow_unsigned_development', 'generation'}
    if (not isinstance(config, dict) or not required <= config.keys() or not config.keys() <= required | {'limits'}
            or type(config['schema_version']) is not int or config['schema_version'] != 1
            or config['mode'] not in ('curated', 'development')
            or type(config['allow_unsigned_development']) is not bool
            or type(config['generation']) is not int or config['generation'] < 1
            or not isinstance(config['approved_digests'], list)
            or not all(isinstance(value, str) and re.fullmatch('sha256:[0-9a-f]{64}', value) for value in config['approved_digests'])):
        raise ArtifactError('Invalid independently owned operator configuration')
    limits = config.get('limits', {})
    if not isinstance(limits, dict) or not limits.keys() <= {item.name for item in fields(ArchiveLimits)}:
        raise ArtifactError('Unknown archive limits configuration')
    policy = TrustPolicy(config['mode'], frozenset(config['approved_digests']), config['allow_unsigned_development'], config['generation'])
    return ConfigurationBoundValidator(policy, ArchiveLimits(**limits)).bind_configuration(path,raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path, help='Independent operator-owned JSON configuration')
    groups = parser.add_subparsers(dest='group', required=True)
    plugin = groups.add_parser('plugin').add_subparsers(dest='action', required=True)
    validate = plugin.add_parser('validate')
    validate.add_argument('artifact', type=Path)
    validate.add_argument('--digest', required=True)
    plan = plugin.add_parser('plan')
    plan.add_argument('--input', required=True, type=Path, help='Untrusted declarative proposal; grants no execution authority')
    plan.add_argument('--store', required=True, type=Path, help='Existing operator catalog, opened read only')
    current = plugin.add_parser('plan-current-install', help='Nominate native packages already present in the verified image')
    current.add_argument('--deployment-config', required=True, type=Path)
    current.add_argument('--store', required=True, type=Path)
    current.add_argument('--site', required=True)
    current.add_argument('--workspace', required=True, action='append')
    current.add_argument('--plugin', required=True)
    current.add_argument('--version', required=True)
    current.add_argument('--digest', required=True)
    apply = plugin.add_parser('apply', help='Execute one independently registered/approved exact plan')
    apply.add_argument('operation_id')
    apply.add_argument('--store', required=True, type=Path, help='Independent OS-owned control store')
    apply.add_argument('--deployment-config', required=True, type=Path)
    apply.add_argument('--catalog', required=True, type=Path)
    for action in ('stage-image','plan-staged','plan-external'):
        staged=plugin.add_parser(action)
        staged.add_argument('--store',required=True,type=Path,help='Independent OS-owned control store')
        staged.add_argument('--deployment-config',required=True,type=Path)
        staged.add_argument('--catalog',required=True,type=Path)
        if action=='stage-image':staged.add_argument('--image-id',required=True)
        else:staged.add_argument('--input',required=True,type=Path,help='Exact scoped target nomination; grants no approval')
    recover = plugin.add_parser('recover', help='Review/restore a checkpoint to a fresh disposable database, then separately resume')
    recover.add_argument('recovery_action', choices=['prepare-restore','restore','prepare-resume','resume','revoke-review','prepare-unchanged-resume','resume-unchanged'])
    recover.add_argument('operation_id')
    recover.add_argument('--store', required=True, type=Path)
    recover.add_argument('--deployment-config', required=True, type=Path)
    recover.add_argument('--catalog', required=True, type=Path)
    recover.add_argument('--decision', type=Path)
    recover.add_argument('--decision-hash')
    recover.add_argument('--noninteractive', action='store_true')
    catalog = groups.add_parser('catalog')
    catalog.add_argument('--store', required=True, type=Path)
    catalog_actions = catalog.add_subparsers(dest='action', required=True)
    add = catalog_actions.add_parser('add')
    add.add_argument('artifact', type=Path)
    add.add_argument('--digest', required=True)
    catalog_actions.add_parser('list')
    quarantine = catalog_actions.add_parser('quarantine')
    quarantine.add_argument('digest')
    operations = groups.add_parser('operations')
    operations.add_argument('--store', required=True, type=Path, help='Independent OS-owned control store')
    operation_actions = operations.add_subparsers(dest='action', required=True)
    initialize = operation_actions.add_parser('init-store')
    initialize.add_argument('--deployment-config', required=True, type=Path)
    initialize.add_argument('--allow-noninteractive-disposable', action='store_true')
    register = operation_actions.add_parser('register')
    register.add_argument('--bundle', required=True, type=Path)
    register.add_argument('--deployment-config', required=True, type=Path)
    register.add_argument('--catalog', required=True, type=Path)
    for action in ('import-request','mirror-status'):
        channel=operation_actions.add_parser(action)
        channel.add_argument('operation_id')
        channel.add_argument('--deployment-config',required=True,type=Path)
        channel.add_argument('--catalog',required=True,type=Path)
    approve = operation_actions.add_parser('approve')
    approve.add_argument('operation_id')
    approve.add_argument('--plan-hash', required=True)
    approve.add_argument('--deployment-config', required=True, type=Path)
    approve.add_argument('--catalog', required=True, type=Path)
    approve.add_argument('--noninteractive', action='store_true')
    for name in ('destructive', 'trust', 'permissions'):
        approve.add_argument('--ack-' + name, action='store_true')
    operation_actions.add_parser('show').add_argument('operation_id')
    adopt=operation_actions.add_parser('adopt-release')
    adopt.add_argument('operation_id')
    adopt.add_argument('--deployment-config',required=True,type=Path)
    adopt.add_argument('--catalog',required=True,type=Path)
    operation_actions.add_parser('revoke-approval').add_argument('operation_id')
    worker=groups.add_parser('worker',help='Independent local worker authority; never launches an external runtime')
    worker.add_argument('--store',required=True,type=Path)
    worker.add_argument('--deployment-config',required=True,type=Path)
    worker.add_argument('--worker-config',required=True,type=Path)
    worker_actions=worker.add_subparsers(dest='action',required=True)
    keys=worker_actions.add_parser('provision-keys')
    keys.add_argument('--private-reference',required=True);keys.add_argument('--public-reference',required=True)
    keys.add_argument('--private-key',required=True,type=Path);keys.add_argument('--public-key',required=True,type=Path)
    prepare_worker=worker_actions.add_parser('prepare')
    prepare_worker.add_argument('--endpoint',required=True,type=Path);prepare_worker.add_argument('--key-id',required=True)
    worker_actions.add_parser('prepare-bootstrap')
    worker_actions.add_parser('review').add_argument('operation_id')
    publish_worker=worker_actions.add_parser('publish');publish_worker.add_argument('operation_id')
    publish_worker.add_argument('--plan-hash',required=True);publish_worker.add_argument('--noninteractive',action='store_true')
    worker_actions.add_parser('run-job-once')
    args = parser.parse_args(argv)
    try:
        validator = configuration(args.config)
        if args.group=='worker':
            import subprocess
            from modular_platform.operator_store import OperatorStore
            from modular_platform.operator_os import OperatorError
            from modular_platform.worker_operator import WorkerOperator,private_json
            operator=WorkerOperator(OperatorStore(args.store),args.deployment_config,args.worker_config)
            try:
                if args.action=='provision-keys':
                    result=operator.provision(args.private_reference,args.public_reference,args.private_key,args.public_key)
                elif args.action=='prepare':
                    result=operator.publisher.prepare(private_json(args.endpoint),args.key_id,operator.observer)
                elif args.action=='prepare-bootstrap':result=operator.publisher.prepare_bootstrap()
                elif args.action=='review':result=operator.review(args.operation_id)
                elif args.action=='publish':
                    review=operator.review(args.operation_id)
                    if not args.noninteractive:
                        if not sys.stdin.isatty():raise OperatorError('Noninteractive publication requires explicit flag and OS-owned policy')
                        if input('Type the exact reviewed worker plan hash to publish: ').strip()!=args.plan_hash:
                            raise OperatorError('Exact reviewed plan hash confirmation required')
                    result=operator.publish(review,args.plan_hash,args.noninteractive)
                else:result=operator.run_once()
            except subprocess.SubprocessError:
                raise OperatorError('Independent worker Docker operation failed; inspect retained intent and private diagnostics before retry') from None
        elif args.group == 'operations':
            from modular_platform.operator_store import OperatorStore
            from modular_platform.deployment import DockerObserver
            from modular_platform.approval_validation import IndependentValidator
            from modular_platform.operator_os import OperatorError
            from modular_platform.worker_operator import operator_observer
            if args.action == 'init-store':
                target = load_json(args.deployment_config.read_bytes())
                DockerObserver(target)
                store = OperatorStore.initialize(args.store,
                    {target['deployment_id']: [site['site_id'] for site in target['sites']]},
                    allow_noninteractive=args.allow_noninteractive_disposable)
                result = {'state': 'initialized', 'authorization_generation': store.policy['authorization_generation']}
            else:
                store = OperatorStore(args.store)
                if args.action in ('register', 'approve','import-request'):
                    from modular_platform.release_staging import StageStore
                    deployment=load_json(args.deployment_config.read_bytes())
                    stage_store=StageStore(store,deployment,Catalog(args.catalog,validator,readonly=True))
                    independent=operator_observer(store,args.deployment_config)
                    revalidate = IndependentValidator(deployment,args.catalog,validator,stage_store=stage_store,
                        external_reader=independent.external_reader)
                if args.action=='adopt-release':
                    from modular_platform.release_adoption import adopt_release
                    result=adopt_release(store,args.deployment_config,args.catalog,validator,args.operation_id)
                elif args.action in ('import-request','mirror-status'):
                    from modular_platform.app_channel import read_request,publish_status
                    observer=operator_observer(store,args.deployment_config)
                    if args.action=='import-request':
                        nomination=read_request(observer,args.operation_id)
                        operation=store.register(nomination['bundle'],revalidate)
                        store.attach_application_request(operation,nomination)
                        result=store.status(operation)
                        try:publish_status(store,observer,Catalog(args.catalog,validator,readonly=True),operation)
                        except Exception:pass
                    else:
                        result=publish_status(store,observer,Catalog(args.catalog,validator,readonly=True),args.operation_id)
                elif args.action == 'register':
                    raw = args.bundle.read_bytes()
                    if len(raw) > 16 * 1024 * 1024:
                        raise OperatorError('Operation bundle size limit')
                    result = store.status(store.register(load_json(raw), revalidate))
                elif args.action == 'approve':
                    review = store.review(args.operation_id, revalidate)
                    if not args.noninteractive:
                        if not sys.stdin.isatty():
                            raise OperatorError('Use an explicitly configured noninteractive policy and exact hash, or an interactive terminal')
                        print(json.dumps(review, indent=2))
                        if input('Type the exact reviewed plan hash to approve: ').strip() != args.plan_hash:
                            raise OperatorError('Interactive exact-hash confirmation did not match')
                    store.approve(args.operation_id, exact_hash=args.plan_hash,
                        acknowledgments={'destructive': args.ack_destructive, 'trust_expansion': args.ack_trust,
                                         'permission_expansion': args.ack_permissions},
                        revalidate=revalidate, noninteractive=args.noninteractive)
                    result = store.status(args.operation_id)
                    result['review'] = review
                    if store.application_request(args.operation_id):
                        from modular_platform.native_executor import NativeExecutor
                        NativeExecutor(store,args.deployment_config,args.catalog,validator).mirror_progress(args.operation_id)
                elif args.action == 'revoke-approval':
                    store.revoke(args.operation_id)
                    result = store.status(args.operation_id)
                else:
                    result = store.status(args.operation_id)
        elif args.group == 'plugin' and args.action == 'plan-external':
            from datetime import datetime,timezone
            from uuid import uuid4
            from modular_platform.operator_store import OperatorStore
            from modular_platform.worker_operator import operator_observer
            from modular_platform.external_planning import prepare_external_metadata
            raw=args.input.read_bytes()
            if len(raw)>1024*1024:raise ArtifactError('Metadata nomination size limit')
            nomination=load_json(raw)
            required={'operation_type','targets'}
            if not isinstance(nomination,dict) or not required<=nomination.keys() or not nomination.keys()<=required|{'selections','feature_states'}:
                raise ArtifactError('Exact metadata-only nomination fields required')
            store=OperatorStore(args.store);observer=operator_observer(store,args.deployment_config)
            observation=observer.read();snapshot=Catalog(args.catalog,validator,readonly=True).snapshot()
            if 'external_state' not in observation:raise ArtifactError('Independent worker configuration required')
            result=prepare_external_metadata(observer.state(observation,snapshot),observation['sites'],snapshot,
                **nomination,external_state=observation['external_state'],operation_id=str(uuid4()),
                created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        elif args.group == 'plugin' and args.action in ('stage-image','plan-staged'):
            from datetime import datetime,timezone
            from uuid import uuid4
            from modular_platform.operator_store import OperatorStore
            from modular_platform.deployment import DockerObserver
            from modular_platform.release_staging import StageStore,prepare_staged_plan
            store=OperatorStore(args.store);deployment=load_json(args.deployment_config.read_bytes())
            catalog=Catalog(args.catalog,validator,readonly=True);stages=StageStore(store,deployment,catalog)
            if args.action=='stage-image':result=stages.stage(args.image_id)
            else:
                raw=args.input.read_bytes()
                if len(raw)>2*1024*1024:raise ArtifactError('Staged nomination size limit')
                nomination=load_json(raw)
                if set(nomination)!={'operation_type','targets'}:raise ArtifactError('Exact native operation/targets nomination required')
                descriptor,record=stages.load();observer=DockerObserver(deployment);observation=observer.read();snapshot=catalog.snapshot()
                result=prepare_staged_plan(observer.state(observation,snapshot),observation['sites'],snapshot,record['runtime'],descriptor,
                    targets=nomination['targets'],operation_type=nomination['operation_type'],operation_id=str(uuid4()),
                    created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=observation['runtime'])
        elif args.group == 'plugin' and args.action == 'recover':
            from modular_platform.operator_store import OperatorStore
            from modular_platform.native_executor import NativeExecutor
            from modular_platform.restore_executor import RestoreExecutor
            from modular_platform.operator_os import OperatorError
            from modular_platform.plans import data_digest
            recovery = RestoreExecutor(NativeExecutor(OperatorStore(args.store),args.deployment_config,args.catalog,validator))
            if args.recovery_action in ('prepare-unchanged-resume','resume-unchanged'):
                from modular_platform.unchanged_recovery import UnchangedReleaseRecovery
                recovery=UnchangedReleaseRecovery(recovery.native)
            if args.recovery_action.startswith('prepare-'):
                decision = recovery.prepare_resume(args.operation_id) if args.recovery_action=='prepare-resume' else recovery.prepare(args.operation_id)
                result = {'decision':decision,'decision_hash':data_digest(decision)}
            else:
                if not args.decision or not args.decision_hash:
                    raise OperatorError('A separately reviewed recovery decision and exact hash are required')
                decision = load_json(args.decision.read_bytes())
                if decision['operation_id']!=args.operation_id:
                    raise OperatorError('Recovery operation identity mismatch')
                if not args.noninteractive:
                    if not sys.stdin.isatty():raise OperatorError('Interactive recovery requires a terminal')
                    print(json.dumps(decision,indent=2))
                    if input('Type the exact reviewed recovery hash: ').strip()!=args.decision_hash:
                        raise OperatorError('Recovery hash confirmation mismatch')
                if args.recovery_action=='revoke-review':
                    result=recovery.revoke_review(decision,exact_hash=args.decision_hash)
                else:
                    method = recovery.execute if args.recovery_action=='restore' else recovery.resume
                    result = method(decision,exact_hash=args.decision_hash,noninteractive=args.noninteractive)
        elif args.group == 'plugin' and args.action == 'apply':
            from modular_platform.operator_store import OperatorStore
            from modular_platform.native_executor import NativeExecutor
            store=OperatorStore(args.store)
            bundle=store.bundle(args.operation_id)
            metadata=bool(bundle['plan']['artifacts']) and all(a['runtime']=='external_service' for a in bundle['plan']['artifacts'])
            if metadata:
                from modular_platform.metadata_executor import ReferenceMetadataExecutor
                executor=ReferenceMetadataExecutor(store,args.deployment_config,args.catalog,validator)
            else:executor=NativeExecutor(store,args.deployment_config,args.catalog,validator)
            if not metadata and 'staged_image' in bundle['operation_lock']:
                from modular_platform.native_executor import StagedNativeExecutor
                executor=StagedNativeExecutor(store,args.deployment_config,args.catalog,validator)
            if not metadata and bundle['plan']['operation_type'] in ('suspend','enable'):
                from modular_platform.feature_executor import FeatureExecutor
                executor=FeatureExecutor(executor)
            result=executor.apply(args.operation_id)
        elif args.group == 'plugin' and args.action == 'plan-current-install':
            from datetime import datetime, timezone
            from uuid import uuid4
            from modular_platform.deployment import DockerObserver
            from modular_platform.lifecycle_planning import prepare_current_image_install
            observer = DockerObserver(load_json(args.deployment_config.read_bytes()))
            snapshot = Catalog(args.store, validator, readonly=True).snapshot()
            observation = observer.read()
            result = prepare_current_image_install(observer.state(observation, snapshot), observation['sites'], snapshot,
                site_id=args.site, workspace_ids=args.workspace, plugin_id=args.plugin, version=args.version,
                artifact_digest=args.digest, operation_id=str(uuid4()),
                created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        elif args.group == 'plugin' and args.action == 'plan':
            from modular_platform.planning_cli import prepare_document
            raw = args.input.read_bytes()
            if len(raw) > 16 * 1024 * 1024:
                raise ArtifactError('Plan input size limit')
            result = prepare_document(load_json(raw), Catalog(args.store, validator, readonly=True).snapshot())
        elif args.group == 'plugin':
            result = validator.verify(args.artifact, expected_digest=args.digest).descriptor()
        else:
            store = Catalog(args.store, validator)
            if args.action == 'add':
                result = store.add(args.artifact, expected_digest=args.digest)
            elif args.action == 'list':
                result = store.snapshot()
            else:
                store.quarantine(args.digest)
                result = {'digest': args.digest, 'state': 'quarantined'}
        for item in result if isinstance(result, list) else [result]:
            trust_entries = [item.get('trust', {})]
            trust_entries.extend(plugin['trust'] for plugin in item.get('operation_lock', {}).get('release', {}).get('plugins', []))
            for trust in trust_entries:
                for warning in trust.get('warnings', []):
                    print(warning, file=sys.stderr)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
        return 0
    except (ContractError, OSError, TypeError, ValueError, KeyError, sqlite3.Error) as error:
        # Validation messages are deliberately value-free. OS errors may contain
        # sensitive local paths, so only expose their type to the CLI consumer.
        message = str(error) if isinstance(error, ContractError) else type(error).__name__
        print(json.dumps({'error': 'VALIDATION_FAILED', 'message': message}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
