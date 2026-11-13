"""Bootstrap an empty, disposable development site from a current clean-core build.

Default plan performs file validation only. No kit guard, approval or runtime
inventory check is bypassed. Application admission/install remains separate.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'release'), str(ROOT / 'packages/platform_sdk'), str(ROOT / 'tools')]
from build_inputs import source_input_paths
from initialize_reference import Reference, write, configuration, Catalog
from modular_platform.operator_os import protect_directory, verify_private_directory
from modular_platform.operator_store import _write_new
from modular_platform.deployment import inspect_image
from modular_platform.projection import PLATFORM_VERSION, runtime_inputs

ADDONS = frozenset({'base', 'web', 'base_setup', 'auth_password_policy', 'bus', 'mp_compat', 'mp_identity', 'mp_core'})
HOST_SOURCES = ('tools/initialize_candidate.py', 'release/initialize_reference.py', 'release/reference_seed.py', 'deploy/runtime.lock.json')
FULL_ID = re.compile(r'sha256:[0-9a-f]{64}')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regular_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Bounded regular JSON file required')
    return json.loads(path.read_bytes())


def validate_record(path, *, root=ROOT):
    record = regular_json(path)
    if (record.get('state') != 'built' or record.get('result') != 'built_not_deployed'
            or record.get('deployment_changed') is not False or record.get('artifacts') != {}
            or not FULL_ID.fullmatch(record.get('image_id', ''))
            or not FULL_ID.fullmatch(record.get('inventory_digest', ''))
            or not re.fullmatch('[0-9a-f]{40}', record.get('git_base', ''))):
        raise ValueError('Successful immutable app-free candidate build record required')
    policy_name = record.get('distribution_policy')
    if (not isinstance(policy_name, str) or not re.fullmatch(r'deploy/distribution-r1(?:-[A-Za-z0-9_-]+)?\.json', policy_name)):
        raise ValueError('Operator-owned distribution policy required')
    policy = regular_json(root / policy_name)
    if (policy.get('runtime_surface') != 'clean' or policy.get('platform_sdk') is not True
            or policy.get('stock_webclient') is not True or set(policy.get('addons', [])) != ADDONS
            or len(policy['addons']) != len(ADDONS) or policy.get('server_wide_modules') != ['base', 'web']
            or policy.get('application_packages') or policy.get('reference_packages')):
        raise ValueError('Bootstrap requires the demonstrated eight-addon clean core without applications')
    expected = {name: digest(root / name) for name in source_input_paths(root, policy_name)}
    if not expected or record.get('source_sha256') != expected:
        raise ValueError('Candidate curated source set/hash changed; select or build a matching candidate')
    return record


def image_inputs(record, *, root=ROOT):
    runtime = regular_json(root / 'deploy/runtime.lock.json')
    def pinned(name):
        value = runtime[name]
        if not isinstance(value, str) or not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', value):
            raise ValueError('Locked immutable development dependency image required')
        return 'sha256:' + value.rsplit('@sha256:', 1)[1]
    return dict(images=dict(application=dict(image_id=record['image_id']),
        postgres=dict(image_id=pinned('postgres_image')), proxy=dict(image_id=pinned('reverse_proxy_image'))),
        application_inventory_digest=record['inventory_digest'])


def selected_subnets(runtime, edge):
    networks = [ipaddress.IPv4Network(value) for value in (runtime, edge)]
    if any(not net.is_private or not 16 <= net.prefixlen <= 28 for net in networks) or networks[0].overlaps(networks[1]):
        raise ValueError('Two nonoverlapping private IPv4 networks with prefixes16..28 required')
    return dict(runtime=str(networks[0]), edge=str(networks[1]))


def docker_absent(kind, name):
    noun = 'container' if kind == 'container' else kind
    result = subprocess.run(['docker', noun, 'inspect', name], capture_output=True, timeout=30)
    if result.returncode == 0:
        raise ValueError('Proposed exact resource already exists: ' + kind + ' ' + name)
    message = result.stderr.decode('utf-8', 'replace').strip()
    escaped = re.escape(name)
    patterns = [rf'(?:Error response from daemon: |Error: )?No such {noun}: {escaped}']
    if kind == 'container': patterns.append(rf'(?:Error response from daemon: |Error: )?No such object: {escaped}')
    if kind == 'network': patterns.append(rf'(?:Error response from daemon: |Error: )?network {escaped} not found')
    if kind == 'volume': patterns.append(rf'Error response from daemon: get {escaped}: no such volume')
    if not any(re.fullmatch(pattern, message, re.IGNORECASE) for pattern in patterns):
        raise ValueError('Docker metadata did not prove resource absence: ' + kind)


class CandidateSite(Reference):
    """Explicit candidate composition, separate from the sealed-kit constructor."""
    def __init__(self, workdir, context):
        self.work = Path(workdir).absolute()
        self.private = self.work / 'private'
        self.local = self.private / 'site'
        self.context = context
        self.record = validate_record(Path(context['build_record']))
        if (digest(context['build_record']) != context['build_record_sha256']
                or context['host_source_sha256'] != {p: digest(ROOT / p) for p in HOST_SOURCES}
                or image_inputs(self.record) != context['images']):
            raise ValueError('Bound bootstrap context or host source changed; inspect instead of replaying')
        self.args = SimpleNamespace(port=context['port'])

    def _intent(self, label, **details):
        if not re.fullmatch('[a-z0-9-]+', label): raise ValueError('Invalid durable phase label')
        directory = protect_directory(self.work / 'intents')
        try:
            _write_new(directory / (label + '.json'), dict(label=label, context_sha256=digest(self.work / 'context.json'),
                utc=datetime.now(timezone.utc).isoformat(), **details))
        except FileExistsError as error:
            raise RuntimeError('Step already attempted: ' + label + '; inspect status/logs, never delete its intent to retry') from error

    def _complete(self, phase):
        directory = protect_directory(self.work / 'completions')
        files = [self.local / 'state.json', self.local / 'operator/trust.json']
        if phase != 'prepare': files.append(self.local / 'fixtures.json')
        if phase == 'publish': files.append(self.local / 'operator/target.json')
        _write_new(directory / (phase + '.json'), dict(phase=phase,
            intent_sha256=digest(self.work / 'intents' / (phase + '.json')),
            files={str(p.relative_to(self.work)): digest(p) for p in files}))

    def _require_complete(self, phase):
        value = regular_json(self.work / 'completions' / (phase + '.json'))
        intent = regular_json(self.work / 'intents' / (phase + '.json'))
        if (value['phase'] != phase or value['intent_sha256'] != digest(self.work / 'intents' / (phase + '.json'))
                or intent['context_sha256'] != digest(self.work / 'context.json')
                or any(digest(self.work / name) != sha for name, sha in value['files'].items())):
            raise ValueError('Prior phase receipt or files changed; inspect actual state')

    def command(self, label, args, *, data=None, timeout=180):
        self._intent('command-' + label, argv_sha256=hashlib.sha256(json.dumps(args).encode()).hexdigest())
        return super().command(label, args, data=data, timeout=timeout)

    def phase(self, state, name):
        if name == 'creating_owned_networks': self._resource_gate(state)
        state['phase'] = name
        state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        write(self.local / 'state.json', state)

    def _resource_gate(self, state):
        nonce = state['project'].removeprefix('mp-r0-r1release')
        operation = state['bootstrap_id']
        if (not re.fullmatch('[0-9a-f]{12}', nonce) or state['database'] != 'mp_disposable_r0_r1_release_' + nonce
                or str(UUID(operation)) != operation
                or state['image_id'] != self.record['image_id'] or state['inventory_digest'] != self.record['inventory_digest']
                or state['port'] != self.context['port']):
            raise ValueError('Generated resource identity differs from bound development inputs')
        project = state['project']
        resources = dict(network=[project + '_runtime', project + '_edge'],
            volume=[project + '_' + n for n in ('appconfig', 'dbconfig', 'bootstrap', 'proxyconfig', 'filestore', 'pgdata')],
            container=[project + '-db-1', project + '-edge-1', project + '-core-init', project + '-core-provision',
                project + '-app-release-' + operation.replace('-', ''), project + '-op-' + operation + '-assets'])
        for kind, names in resources.items():
            for name in names: docker_absent(kind, name)
        with socket.socket() as probe: probe.bind(('127.0.0.1', self.context['port']))
        ids = subprocess.check_output(['docker', 'network', 'ls', '--quiet', '--no-trunc'], text=True, timeout=30).split()
        if ids:
            rows = json.loads(subprocess.check_output(['docker', 'network', 'inspect', *ids], timeout=30))
            if len(rows) != len(ids) or {r['Id'] for r in rows} != set(ids):
                raise ValueError('Incomplete global Docker network metadata')
            proposed = [ipaddress.IPv4Network(v) for v in self.context['subnets'].values()]
            for row in rows:
                for entry in row['IPAM']['Config'] or []:
                    if entry.get('Subnet'):
                        existing = ipaddress.ip_network(entry['Subnet'])
                        if existing.version == 4 and any(existing.overlaps(net) for net in proposed):
                            raise ValueError('Selected subnet overlaps an existing Docker network')
        state['resource_gate'] = dict(exact_resources=resources, subnets=self.context['subnets'], port=self.context['port'])

    def prepare_candidate(self):
        self._intent('prepare')
        protect_directory(self.private)
        runtime = inspect_image(self.record['image_id'])
        runtime_inputs(runtime, [])
        if (runtime['inventory_digest'] != self.record['inventory_digest']
                or runtime.get('platform_version') != PLATFORM_VERSION or runtime.get('published_release_protocol') != 1
                or runtime['inventory'].get('artifacts', {}) or set(runtime['inventory']['native_addons']) != ADDONS
                or any(runtime.get(k) for k in ('modified_files', 'missing_addon_files', 'unexpected_addon_files'))):
            raise ValueError('Actual image differs from the empty eight-addon candidate')
        trust = json.dumps(dict(schema_version=1, mode='curated', approved_digests=[], allow_unsigned_development=False, generation=1)).encode()
        self.prepare_resources(self.context['images'], self.record['git_base'], trust,
            subnets=self.context['subnets'], allow_noninteractive=self.context['allow_noninteractive_operations'])
        validator = configuration(self.local / 'operator/trust.json')
        if Catalog(self.private / 'catalog', validator).snapshot(): raise ValueError('Fresh catalog is not empty')
        if self.state()['phase'] != 'configured': raise ValueError('Preparation did not complete')
        self._complete('prepare')

    def initialize_candidate(self):
        self._require_complete('prepare')
        state = self.state()
        if state['phase'] != 'configured': raise ValueError('Initialization phase is not fresh')
        self._intent('initialize')
        self.initialize_core(state, 'web,auth_password_policy,mp_core')
        fixture = regular_json(self.local / 'fixtures.json')
        if (fixture['site_id'] != state['site_id'] or fixture.get('installed_plugins') != []
                or set(fixture['workspaces']) != {'A', 'B'} or set(fixture['users']) != {'operator', 'alice', 'bob', 'worker'}):
            raise ValueError('Development fixture differs from empty-core scope')
        query = "BEGIN READ ONLY; SELECT jsonb_build_object('modules',(SELECT jsonb_agg(name ORDER BY name) FROM ir_module_module WHERE state='installed'),'installations',(SELECT count(*) FROM mp_plugin_installation),'features',(SELECT count(*) FROM mp_workspace_plugin),'grants',(SELECT count(*) FROM mp_plugin_grant),'bindings',(SELECT count(*) FROM mp_service_binding)); ROLLBACK;"
        actual = json.loads(self.sql(state, 'verify-empty-core', query))
        if actual != dict(modules=sorted(ADDONS), installations=0, features=0, grants=0, bindings=0):
            raise ValueError('Initialized database differs from empty-core scope')
        self._complete('initialize')

    def publish_candidate(self):
        self._require_complete('initialize')
        state = self.state()
        if state['phase'] != 'core-provision': raise ValueError('Publication phase is not fresh')
        self._intent('publish')
        super().publish(state)
        target = regular_json(self.local / 'operator/target.json')
        if (not re.fullmatch('[0-9a-f]{64}', target.get('worker_id', ''))
                or target['image_id'] != self.record['image_id'] or target['deployment_id'] != state['deployment_id']
                or target['sites'] != [dict(site_id=state['site_id'], database=state['database'])]):
            raise ValueError('Fresh guarded worker target differs from prepared scope')
        self._complete('publish')


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument('action', nargs='?', choices=['plan', 'prepare', 'initialize', 'publish', 'status'], default='plan')
    value.add_argument('--workdir', type=Path, required=True)
    value.add_argument('--build-record', type=Path)
    value.add_argument('--port', type=int)
    value.add_argument('--runtime-subnet')
    value.add_argument('--edge-subnet')
    value.add_argument('--disposable-development-site', action='store_true')
    value.add_argument('--allow-noninteractive-operations', action='store_true')
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    work = args.workdir.absolute()
    if args.action in ('plan', 'prepare'):
        if work.exists() or work.is_symlink(): raise ValueError('Fresh workdir required; use status to inspect an attempted site')
        if args.build_record is None or args.port is None or not args.runtime_subnet or not args.edge_subnet:
            raise ValueError('Build record, loopback port and two private subnets required')
        if not 1024 <= args.port <= 65535: raise ValueError('Unprivileged loopback port required')
        record = validate_record(args.build_record)
        context = dict(schema_version=1, build_record=str(args.build_record.resolve()), build_record_sha256=digest(args.build_record),
            images=image_inputs(record), port=args.port, subnets=selected_subnets(args.runtime_subnet, args.edge_subnet),
            allow_noninteractive_operations=args.allow_noninteractive_operations,
            host_source_sha256={p: digest(ROOT / p) for p in HOST_SOURCES})
        if args.action == 'plan':
            result = dict(action='plan_only', workdir=str(work), image_id=record['image_id'], port=args.port,
                subnets=context['subnets'], default_core=sorted(ADDONS), installed_applications=0,
                development_fixture=True, allow_noninteractive_operations=args.allow_noninteractive_operations,
                next='Explicit prepare, initialize, publish; separate normal catalog/stage/approval for apps')
            print(json.dumps(result));return result
    else:
        if (args.build_record is not None or args.port is not None or args.runtime_subnet or args.edge_subnet
                or args.allow_noninteractive_operations):
            raise ValueError('Bootstrap inputs belong only to plan/prepare; later phases use the bound context')
        verify_private_directory(work)
        context = regular_json(work / 'context.json')
        if args.action == 'status':
            state_path = work / 'private/site/state.json'
            state = regular_json(state_path) if state_path.exists() else {}
            result = dict(action='status', workdir=str(work), phase=state.get('phase', 'context_prepared'),
                **{k: state[k] for k in ('project', 'database', 'url', 'image_id', 'inventory_digest') if k in state},
                attempted=[p.stem for p in sorted((work / 'intents').glob('*.json')) if not p.stem.startswith('command-')],
                completed=[p.stem for p in sorted((work / 'completions').glob('*.json'))],
                next='Inspect exact state/logs after any partial phase; never remove intent to replay')
            print(json.dumps(result));return result
    if not args.disposable_development_site:
        raise ValueError('Explicit --disposable-development-site required; no resources created')
    if args.action == 'prepare':
        protect_directory(work)
        _write_new(work / 'context.json', context)
    site = CandidateSite(work, context)
    getattr(site, args.action + '_candidate')()
    state = site.state()
    result = dict(action=args.action, phase=state['phase'], project=state['project'], database=state['database'],
        url=state['url'], image_id=state['image_id'], private_site=str(site.local),
        credentials_file=str(site.local / 'account-passwords.json'), next='Separate catalog/staging/review/approval before any application install')
    print(json.dumps(result));return result


if __name__ == '__main__':
    try: main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(json.dumps(dict(error='CANDIDATE_BOOTSTRAP_REFUSED', message=str(error),
            next='Inspect workdir status and private logs; do not repeat a partial phase'))) from None
