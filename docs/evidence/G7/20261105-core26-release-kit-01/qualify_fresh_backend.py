"""Record the clean consumer backend result and retire its completed helpers."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).parent
PRIVATE = ROOT / '.local/release-kit-core26-rehearsal/private/reference'
PROJECT = 'mp-r0-r1release1c1f3b9c7a85'
DEPLOYMENT = '52bb1a77-589f-4863-9f59-b56331853c4d'
HELPERS = (
    'eac54535eda9', '64f5ef9eadd9', '319eb17a18ca', '64ffdc9b99ac',
    '38e607622875', '2ee71767f432', 'd6ba160c9e56', '040ad74388c0',
    '198e1db4a708', '2a77751c8994', '34f51a645d9d', '97f7b0eeec30',
    '14e7cc3aabd8', '2f8537fa0661', 'f1c2848b4a0a', '3159e7a6c222',
    'ad72bdf179f9', '13fa8259f716', 'f1089ce7c98c', '5d2811d012e6',
    '26ecf8bd1941', 'bc47ce4393e4', '52504c1f3f8d', '2a8cfbf6e37b',
    '5fa31ab6ef29', 'a3612feaabe2', 'afc31d0594b5', 'fb9ebaee7627',
    '572e95788391', 'f661c3cda584', '82296621490c', '18a56d40f74a',
)
sys.path.insert(0, str(ROOT / 'tools'))
from secret_scan import Scanner, save_report


def load(path):
    return json.loads(path.read_bytes())


def docker(*args):
    result = subprocess.run(['docker', *args], capture_output=True, timeout=60)
    assert result.returncode == 0, ('Docker command failed', args[0])
    return result


def inspect(*ids):
    return json.loads(docker('inspect', *ids).stdout)


state = load(PRIVATE / 'state.json')
reference = load(PRIVATE / 'reference-checks.json')
worker = load(PRIVATE / 'worker/job-qualified.json')
assert state['phase'] == 'kit_backend_worker_reference_qualified'
assert reference['phase'] == 'passed' and len(reference['checks']) == 5
job = worker['job']
assert (job['state'], job['attempts'], job['progress'], job['error_code']) == ('completed', 1, 100, None)
assert job['result']['statistics'] == {'lines': 1, 'words': 3, 'characters': 30}
assert (worker['notes'], worker['boards'], worker['publication_generation']) == (2, 1, 1)
attestation = worker['worker_attestation']
runtime_ids = ['5d56048c4399', 'd21123f1d0ee', '71823ac8ba40', attestation['container_id']]
running = inspect(*runtime_ids)
assert all(row['State']['Running'] for row in running)
network, = json.loads(docker('network', 'inspect', PROJECT + '_runtime').stdout)
assert network['Internal'] and network['Id'] == attestation['network_id']
assert set(network['Containers']) == {row['Id'] for row in running}
assert docker('port', running[1]['Id']).stdout.decode().strip() == '8069/tcp -> 127.0.0.1:18101'
assert running[0]['Image'] == 'sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415'
assert running[3]['Image'] == attestation['image_digest']
assert all(not row['HostConfig']['PortBindings'] for row in (running[0], running[2], running[3]))

known_path = ROOT / '.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json'
known = {name: base64.b64decode(value) for name, value in load(known_path).items()}
assert len(known) == 133
passwords = load(PRIVATE / 'account-passwords.json')
known.update({f'fresh-account-{i}': value.encode() for i, value in enumerate(passwords.values())})
known['fresh-worker-issuer'] = (PRIVATE / 'worker/issuer.pem').read_bytes()
scanner = Scanner((ROOT / '.local/g5-secret-scan/fingerprint-key').read_bytes(), known)

retained = PRIVATE / 'retired-helper-diagnostics'
retained.mkdir(exist_ok=True)
assert not any(retained.iterdir())
helpers = inspect(*HELPERS)
for row in helpers:
    name = row['Name'].lstrip('/')
    labels = row['Config']['Labels']
    assert name.startswith(PROJECT + '-')
    assert row['State']['Status'] == 'exited' and row['State']['ExitCode'] == 0
    assert row['Id'] not in {service['Id'] for service in running}
    assert (labels.get('com.modular.deployment') == DEPLOYMENT
            or labels.get('com.docker.compose.project') == PROJECT
            or labels.get('com.modular.disposable') == PROJECT)
    if row['HostConfig']['LogConfig']['Type'] == 'none':
        continue  # The executor captures attached streams in the private command logs.
    logs = docker('logs', row['Id'])
    (retained / (name + '.stdout')).write_bytes(logs.stdout)
    (retained / (name + '.stderr')).write_bytes(logs.stderr)

patterns = retained / 'patterns.regex'
scanner.write_patterns(patterns)
streams = sorted(path for path in PRIVATE.rglob('*') if path.suffix in {'.stdout', '.stderr'})
findings = scanner.scan_paths(streams, patterns, root=PRIVATE)
save_report(OUT / 'fresh-log-privacy.json', {
    'result': 'passed' if not findings else 'triage_required',
    'streams': len(streams), 'known_values': len(known), 'findings': findings,
    'scope': 'Command and retained Docker streams; credentials, state and checkpoints remain private.',
})
assert not findings
for row in helpers:
    current, = inspect(row['Id'])
    assert current['State']['Status'] == 'exited' and current['State']['ExitCode'] == 0
    docker('rm', row['Id'])
assert [row['Id'] for row in inspect(*runtime_ids)] == [row['Id'] for row in running]
save_report(OUT / 'fresh-backend.json', {
    'result': 'passed_clean_consumer_backend',
    'original_kit_manifest_sha256': 'b4ce8f9c2f14043d7f34872fd18f40638fed1b6ee4d899c83161022d0c7a6c3c',
    'project': PROJECT, 'application_image': running[0]['Image'],
    'fresh_reference_checks': reference['checks'],
    'worker_image': attestation['image_digest'], 'worker_publication': worker['publication_generation'],
    'original_actor_job': {'attempts': job['attempts'], 'state': job['state'],
                           'statistics': job['result']['statistics']},
    'notes': worker['notes'], 'boards': worker['boards'],
    'internal_runtime_network': True, 'published_endpoint': '127.0.0.1:18101',
    'removed_helpers': [{'id': row['Id'], 'name': row['Name'],
                         'log_driver': row['HostConfig']['LogConfig']['Type']} for row in helpers],
    'retained_runtime_ids': [row['Id'] for row in running],
    'private_result_sha256': {
        name: hashlib.sha256((PRIVATE / name).read_bytes()).hexdigest()
        for name in ('reference-checks.json', 'worker/job-qualified.json')
    },
    'scope': 'Backend HTTP and native descriptors, original-actor job and Docker topology. Fresh browser walkthrough deferred.',
})
print(json.dumps({'checks': len(reference['checks']), 'worker_attempts': job['attempts'],
                  'retired_helpers': len(helpers), 'streams': len(streams)}))
