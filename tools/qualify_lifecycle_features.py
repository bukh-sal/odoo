"""Once-only real manager/native setup and feature operations on G5 lifecycle.

No main/retained manager data is changed. Every mutating operation has its own
recorded request/hash and independent review/approval; never blindly replay.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/g5-lifecycle'
OUTPUT = ROOT / 'docs/evidence/G5/20261029-lifecycle-01'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.contracts import validate
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import OperationLocks
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle, data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.release_staging import StageStore
from modular import configuration
from qualify_manager_upgrade_operation import snapshot, sql, files
import r1_probe

FEATURES = {
    'suspend-notes-A': ('suspend', 'org.example.notes', True, {'org.example.notes', 'org.example.canvas', 'org.example.notes_labels'}),
    'enable-canvas-A': ('enable', 'org.example.canvas', True, {'org.example.notes', 'org.example.canvas'}),
    'enable-labels-A': ('enable', 'org.example.notes_labels', False, {'org.example.notes_labels'}),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'apply'])
    parser.add_argument('--case', choices=['install-canvas', 'install-labels', *FEATURES], required=True)
    parser.add_argument('--resume-preparation', action='store_true')
    parser.add_argument('--browser-operation', help='Exact already prepared/requested fixture UI operation; never prepare a duplicate')
    args = parser.parse_args()
    target = LOCAL / 'operator/target.json'
    state = json.loads((LOCAL / 'state.json').read_text(encoding='utf-8'))
    config = json.loads(target.read_text(encoding='utf-8'))
    assert state['disposable'] and state['project'] == config['project'] == 'mp-r0-r1lifef99acae9d906'
    assert config['sites'][0]['database'] == state['active_db'] == 'mp_disposable_r0_r1_g5_life_f99acae9d906'
    assert config['image_id'] == 'sha256:154d74a9d63337cb64607affb78104462a5eb9ab97afe8cd9a5ede48b65b8c5a'
    install = args.case.startswith('install-')
    fixture = json.loads((LOCAL / 'fixtures.json').read_text(encoding='utf-8'))
    r1_probe.r1.r0.LOCAL = LOCAL
    trust = ROOT / '.local/operator/trust.json'
    catalog_root = ROOT / '.local/operator/catalog'
    validator = configuration(trust)
    catalog = Catalog(catalog_root, validator, readonly=True)
    control = LOCAL / 'operator/control'
    store = OperatorStore(control)
    reader = DockerObserver(config)
    observation = reader.read()
    document = reader.state(observation, catalog.snapshot())
    before = document['state']
    output = OUTPUT / args.case
    marker = LOCAL / (args.case + '.json')
    prefix = [sys.executable, 'tools/modular.py', '--config', str(trust)]
    options = ['--deployment-config', str(target), '--catalog', str(catalog_root)]
    ops = prefix + ['operations', '--store', str(control)]
    def guard():
        assert hashlib.sha256((ROOT / '.local/operator/targets/g5.json').read_bytes()).hexdigest() == state['main_target_sha256']
    def invoke(argv):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=600)
        if result.returncode:
            raise RuntimeError('Lifecycle CLI failed; reconcile marker/journal before another attempt: ' + result.stderr.decode(errors='replace')[:400])
        return json.loads(result.stdout)
    def write(name, value):
        with (output / name).open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(value, indent=2) + '\n')
    guard()
    if args.action == 'prepare':
        if args.resume_preparation:
            record = json.loads(marker.read_text(encoding='utf-8'))
            assert args.case == 'install-canvas' and record['state'] == 'preparing' and 'operation_id' not in record
            assert record['base_state_digest'] == data_digest(before) and (output / 'prepare-failure.txt').is_file()
            assert sql(reader, 'SELECT count(*) FROM mp_operation_request;').strip() == b'0'
            assert before == json.loads((output / 'state-before.json').read_text(encoding='utf-8'))
        else:
            assert not marker.exists() and not output.exists()
            output.mkdir()
            record = {'state': 'preparing', 'case': args.case, 'base_state_digest': data_digest(before), 'generation': config['generation']}
        def phase(value):
            record.update(state=value, utc=datetime.now(timezone.utc).isoformat())
            marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        phase('preparing')
        if not args.resume_preparation:
            write('state-before.json', before)
            write('business-before.json', snapshot(reader))
            write('files-before.json', files(reader))
        if install:
            plugin = 'org.example.canvas' if args.case == 'install-canvas' else 'org.example.notes_labels'
            artifact = next(item for item in catalog.snapshot() if item['manifest']['plugin']['id'] == plugin
                and item['digest'] == observation['runtime']['inventory']['artifacts'][plugin]['digest'])
            if not args.resume_preparation:
                write('staged-image.json', invoke(prefix + ['plugin', 'stage-image', '--image-id', config['image_id'], '--store', str(control)] + options))
            stages = StageStore(store, config, catalog)
            if not args.resume_preparation:
                with OperationLocks(store.root / 'locks', config['deployment_id'], [site['site_id'] for site in config['sites']]):
                    publish_profile(reader, catalog, staged=stages.load())
            else:
                assert stages.load()[0] == json.loads((output / 'staged-image.json').read_text(encoding='utf-8'))
            nomination = {'schema_version': 1, 'operation': 'prepare', 'operation_type': 'install', 'site_id': state['site_id'], 'plugin_id': plugin,
                'artifact_version': artifact['manifest']['plugin']['version'], 'artifact_digest': artifact['digest'],
                'workspace_ids': [fixture['workspaces'][key]['public_id'] for key in ['A', 'B']], 'cascade': True}
            expected_plugins = {'org.example.notes', 'org.example.canvas'} if args.case == 'install-canvas' else {'org.example.notes_labels'}
            expected_count = len(expected_plugins) * 2
        else:
            action, plugin, cascade, expected_plugins = FEATURES[args.case]
            artifact = next(item for item in before['release_lock']['plugins'] if item['plugin_id'] == plugin)
            nomination = {'schema_version': 1, 'operation': 'prepare', 'operation_type': action, 'site_id': state['site_id'], 'plugin_id': plugin,
                'workspace_ids': [fixture['workspaces']['A']['public_id']], 'cascade': cascade}
            expected_count = len(expected_plugins)
        validate('operations-request', nomination)
        operator = r1_probe.Client(state, fixture, 'operator')
        headers = {'X-CSRFToken': operator.csrf}
        if args.case == 'suspend-notes-A' and not args.browser_operation:
            status, rejected = operator.request('/api/v1/operations/prepare', nomination | {'cascade': False}, headers=headers)
            assert status == 400 and rejected['error']['code'] == 'VALIDATION_FAILED'
            write('dependent-cascade-rejected.json', rejected)
        if args.browser_operation:
            assert not install
            op = args.browser_operation
            status, value = operator.request('/api/v1/operations/status/' + op)
            assert status == 200 and value['data']['state'] == 'awaiting_operator_approval'
            prepared = None
            record.update(operation_id=op, plan_hash=value['data']['plan_hash'])
        else:
            status, prepared = operator.request('/api/v1/operations/prepare', nomination, headers=headers)
            assert status == 200, ('Prepare failed', status, prepared)
            validate('operations-view', prepared['data'])
            op = prepared['data']['operation_id']
            record.update(operation_id=op, plan_hash=prepared['data']['plan_hash'])
        phase('prepared_application_request')
        write('nomination.json', nomination)
        if prepared:
            write('prepared-view.json', prepared['data'])
        status, bundle = operator.request('/api/v1/operations/bundle/' + op)
        assert status == 200
        bundle = bundle['data']
        check_bundle(bundle, before)
        assert len(bundle['operation_lock']['targets']) == expected_count
        assert {t['plugin_id'] for t in bundle['operation_lock']['targets']} == expected_plugins
        assert all(t['action'] == nomination['operation_type'] for t in bundle['operation_lock']['targets'])
        if not install:
            assert all(t['workspace_id'] == fixture['workspaces']['A']['public_id'] for t in bundle['operation_lock']['targets'])
            assert not bundle['plan']['backup']['required'] and not bundle['plan']['destructive'] and bundle['plan']['target_release_digest'] == before['release_digest']
        else:
            assert bundle['plan']['backup']['required'] and len(bundle['plan']['permission_changes']) == 2
        write('bundle.json', bundle)
        if args.browser_operation:
            status, submitted = operator.request('/api/v1/operations/status/' + op)
        else:
            request_nomination = {'schema_version': 1, 'operation': 'request', 'operation_id': op,
                'plan_hash': bundle['plan_hash'], 'request_id': str(uuid4())}
            validate('operations-request', request_nomination)
            status, submitted = operator.request('/api/v1/operations/request', request_nomination, headers=headers)
        assert status == 200 and submitted['data']['state'] == 'awaiting_operator_approval'
        write('request-status.json', submitted['data'])
        phase('importing')
        write('registered.json', invoke(ops + ['import-request', op] + options))
        write('independent-review.json', store.review(op, NativeExecutor(store, target, catalog_root, validator)._validate()))
        assert before == reader.state(reader.read(), catalog.snapshot())['state']
        phase('independently_reviewed_not_approved')
        guard()
        print(json.dumps({'state': record['state'], 'case': args.case, 'operation_id': op, 'plan_hash': record['plan_hash'], 'targets': expected_count}), flush=True)
        return
    record = json.loads(marker.read_text(encoding='utf-8'))
    assert record['state'] == 'independently_reviewed_not_approved' and record['base_state_digest'] == data_digest(before)
    bundle = json.loads((output / 'bundle.json').read_text(encoding='utf-8'))
    assert snapshot(reader) == json.loads((output / 'business-before.json').read_text(encoding='utf-8'))
    op = record['operation_id']
    def phase(value):
        record.update(state=value, utc=datetime.now(timezone.utc).isoformat())
        marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    flags = ['--ack-trust', '--ack-permissions'] if install else ['--ack-trust']
    write('approved.json', invoke(ops + ['approve', op, '--plan-hash', record['plan_hash'], '--noninteractive'] + flags + options))
    phase('applying')
    print(json.dumps({'stage': 'approved_applying', 'case': args.case, 'operation_id': op}), flush=True)
    completed = invoke(prefix + ['plugin', 'apply', op, '--store', str(control)] + options)
    write('completed.json', completed)
    assert completed['state'] == 'completed' and (not install or completed['traffic_resumed'])
    phase('completed_needs_verification')
    current = json.loads(target.read_text(encoding='utf-8'))
    observer = DockerObserver(current)
    after = observer.state(observer.read(), catalog.snapshot())['state']
    if install:
        assert current['generation'] == config['generation'] + 1 and current['image_id'] == config['image_id']
        assert len(after['installations']) == (4 if args.case == 'install-canvas' else 6)
        assert all(row['state'] == row['metadata_state'] == 'installed' and row['feature_state'] == 'enabled' for row in after['installations'])
        child = json.loads(subprocess.check_output(['docker', 'inspect', state['project'] + '-op-' + op + '-native']))[0]
        assert child['State']['ExitCode'] == 0 and '-i' in child['Config']['Cmd'] and '-u' not in child['Config']['Cmd']
        write('native-child.json', {'image_id': child['Image'], 'arguments': child['Config']['Cmd'], 'exit_code': 0})
        state.update(generation=current['generation'], image_id=current['image_id'], worker_id=current['worker_id'], phase=args.case + '_completed')
        (LOCAL / 'state.json').write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        for key, space in fixture['workspaces'].items():
            consumer = next(i['installation_id'] for i in after['installations'] if i['plugin_id'] == 'org.example.notes' and i['workspace_id'] == space['public_id'])
            fixture.setdefault('bindings', {})[key] = next(b for b in after['bindings'] if b['consumer_installation_id'] == consumer and b['workspace_id'] == space['public_id'] and b['alias'] == 'documents')
        (LOCAL / 'fixtures.json').write_text(json.dumps(fixture, indent=2) + '\n', encoding='utf-8')
    else:
        assert current == config and after['release_digest'] == before['release_digest'] and after['bindings'] == before['bindings']
        previous_business = json.loads((output / 'business-before.json').read_text(encoding='utf-8'))
        now = snapshot(observer)
        assert {k: v for k, v in now.items() if k != 'features'} == {k: v for k, v in previous_business.items() if k != 'features'}
        intended = {(t['installation_id'], t['workspace_id']): t['action'] for t in bundle['operation_lock']['targets']}
        expected = [dict(row, feature_state=('enabled' if intended[(row['installation_id'], row['workspace_id'])] == 'enable' else 'suspended')) if (row['installation_id'], row['workspace_id']) in intended else row for row in before['installations']]
        assert after['installations'] == expected
    old_files = json.loads((output / 'files-before.json').read_text(encoding='utf-8'))
    current_files = files(observer)
    assert all(current_files.get(name) == digest for name, digest in old_files.items())
    write('state-after.json', after)
    write('business-after.json', snapshot(observer))
    phase('completed_verified')
    guard()
    write('result.json', {'result': 'passed_exact_' + args.case, 'utc': record['utc'], 'operation_id': op,
        'plan_hash': record['plan_hash'], 'generation': current['generation'], 'retained_files': len(old_files),
        'main_target_unchanged': True, 'limits': ['Feature gate/API/UI/retention qualification recorded separately; native uninstall/artifact removal remain G5-X05.']})
    print(json.dumps({'result': 'completed_verified', 'case': args.case, 'operation_id': op, 'generation': current['generation']}), flush=True)


if __name__ == '__main__':
    main()
