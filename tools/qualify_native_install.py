"""First managed install on the explicitly named disposable G5 core-only site.

Run once. Durable operation identity is saved before approval/apply so a crash
is reconciled, never turned into a second untracked native install attempt.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.catalog import Catalog
from modular_platform.artifacts import ArtifactValidator, TrustPolicy


def invoke(command, *, success=True, timeout=180):
    result = subprocess.run(command, capture_output=True, timeout=timeout, cwd=ROOT)
    if (result.returncode == 0) != success:
        # CLI errors are bounded/value-free; native diagnostic logs stay private.
        raise RuntimeError('Unexpected operator outcome: '+result.stderr.decode(errors='replace')[:700])
    return json.loads(result.stdout if success else result.stderr)


def write(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():
        raise ValueError('New G5 evidence directory required')
    local = ROOT/'.local/g5'
    marker = local/'managed-install.json'
    if marker.exists():
        raise RuntimeError('Managed install already nominated; read marker/store/children and reconcile without repeating')
    state = json.loads((local/'state.json').read_text())
    fixture = json.loads((local/'fixtures.json').read_text())
    target = ROOT/'.local/operator/targets/g5.json'
    configuration = json.loads(target.read_text())
    if state['project'] != configuration['project'] or state['profile'] != 'G5':
        raise RuntimeError('Explicit disposable G5 target required')
    output.mkdir(parents=True)
    trust_path = ROOT/'.local/operator/trust.json'
    trust = json.loads(trust_path.read_text())
    validator = ArtifactValidator(TrustPolicy(approved_digests=frozenset(trust['approved_digests']), generation=trust['generation']))
    catalog_root = ROOT/'.local/operator/catalog'
    snapshot = Catalog(catalog_root, validator, readonly=True).snapshot()
    observer = DockerObserver(configuration)
    before = observer.state(observer.read(), snapshot)['state']
    if before['installations']:
        raise RuntimeError('This first-install qualification requires the untouched core-only G5 site')
    artifact = next(item for item in before['release_lock']['plugins'] if item['plugin_id'] == 'org.example.notes')
    prefix = [sys.executable, 'tools/modular.py', '--config', str(trust_path)]
    bundle = invoke(prefix+['plugin', 'plan-current-install', '--deployment-config', str(target), '--store', str(catalog_root),
        '--site', fixture['site_id'], '--workspace', fixture['workspaces']['A']['public_id'],
        '--plugin', artifact['plugin_id'], '--version', artifact['version'], '--digest', artifact['digest']])
    operation = bundle['plan']['operation_id']
    write(output/'bundle.json', bundle)
    write(output/'state-before.json', before)
    write(marker, {'operation_id': operation, 'evidence': str(output.relative_to(ROOT)), 'plan_hash': bundle['plan_hash'], 'state': 'nominated'})
    control = ROOT/'.local/operator/control'
    operations = prefix+['operations', '--store', str(control)]
    registered = invoke(operations+['register', '--bundle', str(output/'bundle.json'), '--deployment-config', str(target), '--catalog', str(catalog_root)])
    write(output/'registered.json', registered)
    apply = prefix+['plugin', 'apply', operation, '--store', str(control), '--deployment-config', str(target), '--catalog', str(catalog_root)]
    denied = invoke(apply, success=False)
    assert denied['error'] == 'VALIDATION_FAILED' and 'without reconciliation' in denied['message']
    assert observer.state(observer.read(), snapshot)['state'] == before
    write(output/'unapproved-denied.json', {'result': denied, 'base_state_unchanged': True})
    if not args.apply:
        print(json.dumps({'state': 'prepared_only', 'operation_id': operation, 'plan_hash': bundle['plan_hash']}))
        return
    approved = invoke(operations+['approve', operation, '--plan-hash', bundle['plan_hash'], '--deployment-config', str(target),
        '--catalog', str(catalog_root), '--noninteractive', '--ack-trust', '--ack-permissions'])
    write(output/'approved.json', approved)
    print(json.dumps({'stage': 'approved', 'operation_id': operation, 'plan_hash': bundle['plan_hash']}), flush=True)
    completed = invoke(apply, timeout=600)
    assert completed['state'] == 'completed' and completed['mutation_started'] and completed['traffic_resumed']
    write(output/'completed.json', completed)
    configuration = json.loads(target.read_text())
    observer = DockerObserver(configuration)
    after = observer.state(observer.read(), snapshot)['state']
    assert after['release_digest'] == bundle['plan']['target_release_digest']
    assert len(after['installations']) == 1 and after['installations'][0]['feature_state'] == 'enabled'
    assert after['installations'][0]['workspace_id'] == fixture['workspaces']['A']['public_id']
    write(output/'state-after.json', after)
    replay = invoke(apply)
    assert replay == completed
    write(output/'completed-replay.json', {'result': 'passed', 'same_status_no_new_child': replay == completed})
    checkpoint = control/'checkpoints'/operation
    manifest = json.loads((checkpoint/'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256((checkpoint/name).read_bytes()).hexdigest() == expected
    with tarfile.open(checkpoint/'filestore.tar.gz') as archive:
        files = archive.getnames()
    listing = subprocess.run(['docker', 'exec', '-i', observer._container('db'), 'pg_restore', '--list'],
        input=(checkpoint/'database.dump').read_bytes(), capture_output=True, timeout=30)
    assert listing.returncode == 0
    write(output/'checkpoint-summary.json', {'result': 'passed', 'id': operation, 'manifest_digest': data_digest(manifest),
        'file_hashes': manifest['files'], 'database_archive_readable': True, 'filestore_entries': len(files),
        'old_image_id': manifest['configuration']['image_id'], 'secrets_in_evidence': False,
        'limits': ['Actual clean-target restore rehearsal and attachment reads remain pending.']})
    paths = [ROOT/'tools/modular.py', ROOT/'tools/qualify_native_install.py']
    paths += list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))
    write(output/'native-install.json', {'result': 'passed_subset', 'utc': datetime.now(timezone.utc).isoformat(),
        'operation_id': operation, 'plan_hash': bundle['plan_hash'], 'image_id': configuration['image_id'],
        'checks': ['Unapproved apply denied with no base-state change', 'Independent exact current-image reconstruction and OS approval',
            'Deployment/site process locks and stopped edge/workers', 'Coordinated DB/filestore checkpoint before durable mutation marker',
            'Controlled native install and exact site/workspace metadata/bindings', 'Internal HTTP/registry readiness before traffic',
            'New release lock generation published, completed journal outside DB', 'Same operation replay returns completed status without another install'],
        'limitations': ['Client epoch refresh, new-image upgrade/removal/uninstall, failure/crash/recovery/restore and UI queue/status integration remain pending G5.'],
        'source': {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})
    state['managed_install_operation'] = operation
    state['evidence_history'] = list(dict.fromkeys(state.get('evidence_history', [])+[state['evidence']]))
    state['evidence'] = str(output.relative_to(ROOT))
    state['stage'] = 'managed_notes_installed'
    (local/'state.json').write_text(json.dumps(state, indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id': operation, 'evidence': str(output.relative_to(ROOT)), 'plan_hash': bundle['plan_hash'], 'state': 'completed'}, indent=2)+'\n')
    print(json.dumps({'result': 'passed_subset', 'operation_id': operation, 'evidence': str(output.relative_to(ROOT))}))


if __name__ == '__main__': main()
