"""Bind current runtime, kit, gate evidence and the actual CLI without mutation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path.cwd()
OUT = Path(__file__).parent
DOCS = ROOT / 'docs'
EVIDENCE = DOCS / 'evidence'
KIT = ROOT / '.local/releases/r1-0.1.26'
CORE = EVIDENCE / 'G7/20261105-core26-release-kit-01'
DEV = EVIDENCE / 'G7/20261105-core26-developer-install-01'
WORK = ROOT / '.local/release-kit-core26-rehearsal'
REFERENCE = WORK / 'private/reference'
TRUST = ROOT / '.local/g7-core26-developer-install/upgrade/trust.json'
ORIGINAL = ROOT / '.local/release-kit-rehearsal/private/reference'
sys.path.insert(0, str(ROOT / 'release'))
from verify import verify

REGRESSION_REFRESH = sys.argv[1:] == ['--after-regression-refresh']
assert REGRESSION_REFRESH or not sys.argv[1:]
REPORT = 'backend-audit-regression.json' if REGRESSION_REFRESH else 'backend-audit.json'


def load(path):
    return json.loads(path.read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=90)
    assert result.returncode == 0, ('Read-only audit command failed', args[0])
    return result.stdout


assert Path(sys.executable).resolve() == (WORK / 'operator/Scripts/python.exe').resolve()
spec = (ROOT / 'planning/modular_platform_spec.md').read_text(encoding='utf8')
matrix = spec.split('## 23.2 Acceptance matrix', 1)[1].split('## 23.3', 1)[0]
status = (DOCS / 'implementation-status.md').read_text(encoding='utf8')
ledger = status.split('## Acceptance ledger', 1)[1]
expected = re.findall(r'^\| ([A-Z]+-\d+) \| [^|]+ \| ([^|]+) \|$', matrix, re.M)
observed = re.findall(r'^\| ([A-Z]+-\d+) \| [^|]+ \| ([^|]+) \|', ledger, re.M)
assert len(expected) == len(observed) == len(dict(observed)) == 104
assert dict((key, 'excluded_R2' if scope.startswith('R2') else 'passed') for key, scope in expected) == {
    key: result.strip() for key, result in observed
}
gate_paths = [
    'G0/20261027t234238z/gate-G0.json', 'G1/20261028t003753z/gate-G1.json',
    'G2/20261104-native-uninstall18/gate-G2.json', 'G3/20261028t011619z/gate-G3.json',
    'G4/20261028T161000Z-reuse-requalification/gate-G4.json',
    'G5/20261029-provenance-01/gate-G5.json', 'G6/20261102-headless-ui-01/gate-G6.json',
]
gates = {}
for number, relative in enumerate(gate_paths):
    path = EVIDENCE / relative
    record = load(path)
    assert record['gate'] == f'G{number}'
    assert (record.get('result') or record.get('state') or record.get('decision')) == 'passed'
    gates[relative] = sha(path.read_bytes())

manifest = verify(KIT)
manifest_sha = sha((KIT / 'kit-inventory.json').read_bytes())
privacy = load(CORE / ('privacy-delta-regression.json' if REGRESSION_REFRESH else 'privacy-delta-final.json'))
assert manifest_sha == privacy['kit_manifest_sha256']
assert manifest['source_commit'] == privacy['source_commit'] and not privacy['findings']
assert len(manifest['files']) == 52
assert run('git', 'branch', '--show-current').decode().strip() == 'platform/r1'
assert not run('git', 'diff', '--name-only', manifest['source_commit'], '--',
               'deploy', 'platform_addons', 'plugins', 'packages', 'tests', 'tools', 'services', 'release')
build = load(EVIDENCE / 'G7/20261105-core26-ui09-image-01/candidate-build.json')
repro = load(EVIDENCE / 'G7/20261105-core26-repro-01/qualification.json')
images = load(KIT / 'images.json')
assert build['image_id'] == repro['reference_image'] == images['images']['application']['image_id']
assert build['inventory_digest'] == repro['inventory_digest'] == images['application_inventory_digest']
assert repro['dependency_base'] == images['images']['dependency_base']['image_id']
assert all(repro['comparisons'].values())
with zipfile.ZipFile(KIT / 'source.zip') as source:
    assert source.comment.decode() == manifest['source_commit']
    for name, digest in build['source_sha256'].items():
        assert sha(source.read(name)) == sha((ROOT / name).read_bytes()) == digest
    frozen = 'docs/contracts/freeze-v1.json'
    assert sha(source.read(frozen)) == sha((ROOT / frozen).read_bytes())
    assert sha(source.read(frozen)) == load(EVIDENCE / gate_paths[2])['inventory_sha256']
    assert sha(source.read('release/initialize_reference.py')) == load(CORE / 'catalog-preflight.json')['initializer_sha256']
    assert source.read('tools/operation_progress.py') == (ROOT / 'tools/operation_progress.py').read_bytes()
assert len(build['source_sha256']) == 377
freeze = json.loads(run(sys.executable, '-I', str(ROOT / 'tools/check_contract_freeze.py')))
assert freeze == {'result': 'passed', 'contract_major': 1, 'files': 106, 'rows': 8}

upgrade = load(DEV / 'backend-verification.json')
assert upgrade['result'] == 'passed_installed_developer_examples_backend'
targets = {}
for label, ref, expected_image in [('release', ORIGINAL, build['image_id']),
                                  ('developer', REFERENCE, upgrade['app_image'])]:
    target = load(ref / 'operator/target.json')
    assert target['image_id'] == expected_image
    runtime = run('docker', 'inspect', target['worker_id'], '--format', '{{.Image}} {{.State.Running}}')
    assert runtime.decode().strip() == expected_image + ' true'
    worker = load(ref / 'worker/job-qualified.json')['worker_attestation']['container_id']
    runtime = run('docker', 'inspect', worker, '--format', '{{.Image}} {{.State.Running}}')
    assert runtime.decode().strip() == images['images']['worker']['image_id'] + ' true'
    targets[label] = {'image': expected_image, 'generation': target['generation'], 'separate_worker_running': True}
assert targets['developer']['generation'] == upgrade['app_generation'] == 5
assert targets['release']['generation'] == 7

cli = [sys.executable, '-I', str(WORK / 'source/tools/modular.py'), '--config', str(TRUST)]
operation = upgrade['operation_id']
journal = json.loads(run(*cli, 'operations', '--store', str(REFERENCE / 'operator/control'), 'show', operation))
assert journal['state'] == 'completed' and journal['operation_id'] == operation
assert journal['executor_observation']['state'] == 'returned'
runbooks = DOCS / 'operator-runbooks.md'
assert re.findall(r'^## (\d+)\.', runbooks.read_text(encoding='utf8'), re.M) == [str(i) for i in range(1, 13)]
command_checks = {}
old = EVIDENCE / 'G7/20261104-release-kit-01/runbook-cross-check.json'
for row in load(old)['cli_help_checks']:
    command = row['command']
    usage = run(*cli, *command.split(), '--help')
    assert b'usage:' in usage and row['exit_code'] == 0
    command_checks[command] = sha(usage)

recovery = EVIDENCE / 'G7/20261103-fresh-release-01/dependency-recovery'
fault = load(recovery / 'qualification-corrected.json')
assert fault['result'] == 'passed_actual_dependency_changing_postcommit_fault_fresh_restore_and_separate_resume'
for name, digest in fault['records'].items():
    assert sha((recovery / name).read_bytes()) == digest
assert fault['failed_database_retained'] != fault['fresh_database']
assert fault['baseline_image'] != fault['failed_target_image'] and fault['tables_present'] == 17
assert fault['original_working_deployment_unchanged']
matches = [name for name, digest in fault['unchanged_host_lifecycle_source_sha256'].items()
           if sha((ROOT / name).read_bytes()) == digest]
changed = sorted(set(fault['unchanged_host_lifecycle_source_sha256']) - set(matches))
assert changed == ['packages/platform_sdk/modular_platform/native_executor.py']
binding = load(CORE / 'retained-recovery-binding.json')
assert sha((ROOT / changed[0]).read_bytes()) == binding['matching_source_sha256'][changed[0]]
assert binding['current_core26_image'] == build['image_id']

handoff = DOCS / 'r1-handoff.md'
links = re.findall(r'\]\(([^)]+)\)', handoff.read_text(encoding='utf8'))
local_links = [link for link in links if '://' not in link]
assert all((DOCS / link).is_file() or link == OUT.relative_to(DOCS).as_posix() + '/' + REPORT
           for link in local_links)
assert set(links) - set(local_links) == {
    load(ref / 'state.json')['url'] for ref in (ORIGINAL, REFERENCE)
}
report = {
    'result': 'passed_current_backend_and_retained_evidence_crosscheck',
    'scope': 'Read-only backend and evidence audit. Fresh browser rendering and G7 closure remain pending.',
    'branch': 'platform/r1', 'git_head_before_audit_receipts': run('git', 'rev-parse', 'HEAD').decode().strip(),
    'acceptance_ids_match_specification': Counter(result.strip() for _, result in observed),
    'gate_receipt_sha256': gates, 'contract_freeze': freeze,
    'kit_manifest_sha256': manifest_sha, 'kit_source_commit': manifest['source_commit'],
    'verified_kit_components': len(manifest['files']), 'build_source_inputs_exact': len(build['source_sha256']),
    'live_targets': targets, 'operation': operation, 'independent_journal_completed': True,
    'runbooks': 12, 'runbook_command_usage_sha256': command_checks, 'handoff_links_checked': len(links),
    'historical_failed_upgrade': {
        'operation_id': fault['operation_id'], 'verified_receipts': len(fault['records']),
        'current_matching_host_modules': sorted(matches), 'later_native_executor_binding': changed,
        'scope': 'Actual dependency-changing fixture fault on core20 to core21. Later core23 recovery covers the changed executor, and core26 receipts bind its current bytes.',
    },
}
with (OUT / REPORT).open('x', encoding='utf8') as handle:
    json.dump(report, handle, indent=2)
    handle.write('\n')
print(json.dumps({'acceptance': report['acceptance_ids_match_specification'], 'kit': 52, 'runbooks': 12,
                  'historical_fault_receipts': len(fault['records']), 'cli_checks': len(command_checks)}))
