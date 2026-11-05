"""Check the owned core26 delta before staging a lifecycle operation."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path(__file__).parent
sys.path[:0] = [str(ROOT / 'packages/platform_sdk'), str(ROOT / 'tools')]
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_core_upgrade, core_python_changes
from secret_scan import Scanner


def load(path):
    return json.loads(path.read_bytes())


build = load(OUT / 'candidate-build.json')
base = build['dependency_base_image']
assert base == 'sha256:8658390b780b937bf59c0dbe5932210e13358545c1a4df6872ccbf5b96eda5b8'
before = inspect_image(base)
after = inspect_image(build['image_id'])
source, native = validate_core_upgrade(before, after, {
    'base_image_id': base, 'target_image_id': build['image_id'],
})
expected = {
    'addons/mp_core/__manifest__.py',
    'addons/mp_shell/__manifest__.py',
    'addons/mp_shell/static/src/host.js',
    'addons/mp_shell/static/src/operations.js',
    'packages/platform_sdk/modular_platform/projection.py',
}
assert {row['path'] for row in source} == expected
assert native == [
    {'addon': 'mp_core', 'previous_version': '19.0.0.1.25', 'target_version': '19.0.0.1.26', 'migrations': []},
    {'addon': 'mp_shell', 'previous_version': '19.0.0.1.12', 'target_version': '19.0.0.1.13', 'migrations': []},
]
for field in ('python_metadata', 'python_lock_digest', 'python', 'architecture', 'markers'):
    assert before[field] == after[field]
assert len(after['python_metadata']) == 77 and not core_python_changes(before, after)
assert not any(after[field] for field in ('modified_files', 'unexpected_addon_files', 'missing_addon_files'))
for field in ('artifacts', 'policy'):
    assert before['inventory'][field] == after['inventory'][field]
for name, digest in build['source_sha256'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
assert subprocess.run(['docker', 'image', 'inspect', 'modular-platform:dependency-base-' + OUT.name],
                      capture_output=True, timeout=30).returncode != 0

known = load(ROOT / '.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json')
scanner = Scanner((ROOT / '.local/g5-secret-scan/fingerprint-key').read_bytes(),
                  {key: base64.b64decode(value) for key, value in known.items()})
paths = [OUT / 'build.log', OUT / 'candidate-build.json', Path(__file__)]
paths += list((OUT.parent / '20261105-ui09-live-region-01').glob('*'))
assert not [finding for file in paths for finding in scanner.inspect_file(file, str(file.relative_to(ROOT)))]
result = {
    'result': 'passed_static_core26_shell13_admission', 'image_id': build['image_id'],
    'inventory_digest': after['inventory_digest'], 'base_image_id': base,
    'source_changes': source, 'native_changes': native, 'python_distributions': 77,
    'dependency_environment_exact': True, 'packaged_artifacts_and_policy_exact': True,
    'all_build_source_hashes_exact': True, 'dependency_alias_removed': True,
    'privacy': {'known_values': len(known), 'findings': 0},
}
with (OUT / 'candidate-admission.json').open('x', encoding='utf8') as handle:
    json.dump(result, handle, indent=2)
    handle.write('\n')
print(json.dumps({key: result[key] for key in ('result', 'image_id', 'inventory_digest')}))
