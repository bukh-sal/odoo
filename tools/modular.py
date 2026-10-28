"""Local operator CLI. No network approval authority or plugin imports.

Run with the repository's locked Python environment. The operator config and
catalog belong outside any application-writable mount; G5 executor setup owns
the independently tested OS separation, not this argument parser.
"""
from __future__ import annotations

import argparse
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
    return ArtifactValidator(policy, ArchiveLimits(**limits))


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
    approve = operation_actions.add_parser('approve')
    approve.add_argument('operation_id')
    approve.add_argument('--plan-hash', required=True)
    approve.add_argument('--deployment-config', required=True, type=Path)
    approve.add_argument('--catalog', required=True, type=Path)
    approve.add_argument('--noninteractive', action='store_true')
    for name in ('destructive', 'trust', 'permissions'):
        approve.add_argument('--ack-' + name, action='store_true')
    operation_actions.add_parser('show').add_argument('operation_id')
    operation_actions.add_parser('revoke-approval').add_argument('operation_id')
    args = parser.parse_args(argv)
    try:
        validator = configuration(args.config)
        if args.group == 'operations':
            from modular_platform.operator_store import OperatorStore
            from modular_platform.deployment import DockerObserver
            from modular_platform.approval_validation import IndependentValidator
            from modular_platform.operator_os import OperatorError
            if args.action == 'init-store':
                target = load_json(args.deployment_config.read_bytes())
                DockerObserver(target)
                store = OperatorStore.initialize(args.store,
                    {target['deployment_id']: [site['site_id'] for site in target['sites']]},
                    allow_noninteractive=args.allow_noninteractive_disposable)
                result = {'state': 'initialized', 'authorization_generation': store.policy['authorization_generation']}
            else:
                store = OperatorStore(args.store)
                if args.action in ('register', 'approve'):
                    revalidate = IndependentValidator(load_json(args.deployment_config.read_bytes()), args.catalog, validator)
                if args.action == 'register':
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
                elif args.action == 'revoke-approval':
                    store.revoke(args.operation_id)
                    result = store.status(args.operation_id)
                else:
                    result = store.status(args.operation_id)
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
