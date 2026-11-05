"""Retain private diagnostics before retiring this rehearsal's completed helpers."""
import base64
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).parent
PRIVATE = ROOT / '.local/g7-core26-developer-install/upgrade'
REFERENCE = ROOT / '.local/release-kit-core26-rehearsal/private/reference'
sys.path.insert(0, str(ROOT / 'tools'))
from secret_scan import Scanner, save_report


def load(path):
    return json.loads(path.read_bytes())


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, check=True, timeout=60)


assert load(OUT / 'backend-verification.json')['result'] == 'passed_installed_developer_examples_backend'
previous = load(PRIVATE / 'target-before.json')
current = load(REFERENCE / 'operator/target.json')
operation = load(OUT / 'apply.json')['operation_id']
project = previous['project']
assert current['project'] == project == 'mp-r0-r1release1c1f3b9c7a85'
worker = load(REFERENCE / 'worker/job-qualified.json')['worker_attestation']['container_id']
active = json.loads(docker('inspect', current['worker_id'], project + '-edge-1', project + '-db-1', worker).stdout)
assert all(row['State']['Running'] for row in active)
active_ids = {row['Id'] for row in active}
observed_ids = docker('ps', '-aq', '--no-trunc', '--filter', 'name=' + project).stdout.decode().splitlines()
helpers = [row for row in json.loads(docker('inspect', *observed_ids).stdout) if row['Id'] not in active_ids]
stages = set()
for row in helpers:
    assert row['State']['Status'] == 'exited' and row['State']['ExitCode'] == 0
    labels, name = row['Config']['Labels'], row['Name'].lstrip('/')
    if row['Id'] == previous['worker_id']:
        assert labels['com.docker.compose.project'] == project
        assert labels['com.docker.compose.service'] == 'app'
    else:
        assert labels['com.modular.deployment'] == current['deployment_id']
        assert name.startswith(project + '-op-' + labels['com.modular.operation'] + '-')
        if labels['com.modular.operation'] == operation:
            stages.add(name.removeprefix(project + '-op-' + operation + '-'))
        else:
            assert name.endswith('-dispatch-observe')
assert stages == {'checkpoint', 'native', 'metadata', 'assets', 'dispatch-fence', 'dispatch-reconcile', 'dispatch-enable'}

retained = PRIVATE / 'retired-helper-diagnostics'
retained.mkdir()
for row in helpers:
    if row['HostConfig']['LogConfig']['Type'] != 'none':
        logs = docker('logs', row['Id'])
        (retained / (row['Id'] + '.stdout')).write_bytes(logs.stdout)
        (retained / (row['Id'] + '.stderr')).write_bytes(logs.stderr)
prior = ROOT / '.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json'
known = {name: base64.b64decode(value) for name, value in load(prior).items()}
passwords = load(REFERENCE / 'account-passwords.json')
known.update({f'fresh-account-{i}': value.encode() for i, value in enumerate(passwords.values())})
known['fresh-worker-issuer'] = (REFERENCE / 'worker/issuer.pem').read_bytes()
scanner = Scanner((ROOT / '.local/g5-secret-scan/fingerprint-key').read_bytes(), known)
patterns = PRIVATE / 'diagnostic-patterns.regex'
scanner.write_patterns(patterns)
streams = sorted(p for p in PRIVATE.rglob('*') if p.suffix in {'.stdout', '.stderr'})
findings = scanner.scan_paths(streams, patterns, root=PRIVATE)
assert not findings, 'Inspect bounded redacted scanner findings privately before retirement'
for row in helpers:
    new, = json.loads(docker('inspect', row['Id']).stdout)
    assert new['State']['Status'] == 'exited' and new['State']['ExitCode'] == 0
    docker('rm', row['Id'])
assert all(row['State']['Running'] for row in json.loads(docker('inspect', *sorted(active_ids)).stdout))
save_report(OUT / 'helper-retirement.json', {
    'result': 'passed', 'operation_id': operation, 'known_values': len(known), 'streams': len(streams),
    'findings': findings, 'removed_container_ids': [row['Id'] for row in helpers],
    'retained_running_ids': sorted(active_ids),
})
print(json.dumps({'retired': len(helpers), 'streams_scanned': len(streams), 'findings': len(findings)}))
