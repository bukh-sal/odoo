"""Bind the current image to upstream bytes, dependency metadata and kit notices."""
import ast
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path.cwd()
OUT = Path(__file__).parent
G7 = OUT.parent
KIT = ROOT / '.local/releases/r1-0.1.26'
PRIVATE = ROOT / '.local/g7-core26-provenance'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory


def load(path):
    return json.loads(path.read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


assert not PRIVATE.exists()
protect_directory(PRIVATE)
kit = load(KIT / 'kit-inventory.json')
images = load(KIT / 'images.json')
app = images['images']['application']['image_id']
assert app == 'sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415'
runtime = inspect_image(app)
assert runtime['inventory_digest'] == images['application_inventory_digest']
official = load(G7 / '20261104-source-notices-01/official-source.json')
assert all(runtime['inventory']['files'][name] == digest for name, digest in official['source_files'].items())
build = load(KIT / 'qualification/application-build.json')
assert all(sha((ROOT / name).read_bytes()) == digest for name, digest in build['source_sha256'].items())
base = inspect_image(images['images']['dependency_base']['image_id'])
assert runtime['python_metadata'] == base['python_metadata']
assert runtime['python_lock_digest'] == base['python_lock_digest']
assert runtime['inventory']['generated_patches'] == base['inventory']['generated_patches']

collector = G7 / '20261102-current-provenance-01/collect.py'
tree = ast.parse(collector.read_text(encoding='utf8'))
code = next(ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'code'
                                                    for target in node.targets))
name = 'mp-g7-core26-provenance'
command = ['docker', 'run', '--rm', '--name', name, '--label', 'mp.disposable=core26-provenance',
           '--log-driver', 'none', '--network', 'none', '--read-only', '--user', '10001:10001',
           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '512m',
           '--pids-limit', '128', '--entrypoint', '/venv/bin/python', app, '-B', '-c', code]
with (PRIVATE / 'collector.stdout').open('xb') as stdout, (PRIVATE / 'collector.stderr').open('xb') as stderr:
    subprocess.run(command, stdout=stdout, stderr=stderr, timeout=90, check=True)
current = load(PRIVATE / 'collector.stdout')
notices = current.pop('notices')
prior = load(G7 / '20261104-core23-provenance-01/application-index.json')
for key in ('python', 'os_packages', 'source_notices'):
    assert current[key] == prior[key]
assert len(current['python']) == 77 and len(current['os_packages']) == 113
old_native = {row['addon']: row for row in prior['native']}
new_native = {row['addon']: row for row in current['native']}
assert new_native.keys() == old_native.keys() and len(new_native) == 17
assert {addon for addon in old_native if old_native[addon] != new_native[addon]} == {'mp_core', 'mp_shell'}
for addon in new_native:
    assert {k: v for k, v in new_native[addon].items() if k != 'manifest_sha256'} == {
        k: v for k, v in old_native[addon].items() if k != 'manifest_sha256'}

bundle = load(G7 / '20261104-core22-provenance-01/notice-bundle.json')
notice_archive = KIT / 'notices/application.zip'
assert sha(notice_archive.read_bytes()) == bundle['archive_sha256']
with zipfile.ZipFile(notice_archive) as archive:
    assert set(archive.namelist()) == {row['path'] for row in bundle['files']}
    for row in bundle['files']:
        raw = archive.read(row['path'])
        assert len(raw) == row['bytes'] and sha(raw) == row['sha256']
    for path, item in notices.items():
        raw = base64.b64decode(item['base64'])
        assert sha(raw) == item['sha256'] and archive.read('runtime' + path) == raw
old_kit = load(ROOT / '.local/releases/r1-0.1.23/kit-inventory.json')
support_roles = ('worker', 'postgres', 'proxy')
assert all(kit['images'][role]['image_id'] == old_kit['images'][role]['image_id'] for role in support_roles)
notice_names = [name for name in kit['files'] if name.startswith('notices/')]
assert all(kit['files'][name] == old_kit['files'][name] for name in notice_names)
assert subprocess.run(['docker', 'inspect', '--type', 'container', name],
                      capture_output=True, timeout=30).returncode != 0
with (OUT / 'provenance.json').open('x', encoding='utf8') as handle:
    json.dump({
        'result': 'passed_current_core26_runtime_provenance_and_notices',
        'utc': datetime.now(timezone.utc).isoformat(), 'image': app,
        'inventory': runtime['inventory_digest'], 'recorded_build_inputs': len(build['source_sha256']),
        'upstream_and_generated_source_hashes': len(official['source_files']),
        'python_distributions': 77, 'os_packages': 113, 'native_addons': 17,
        'application_notice_entries': len(bundle['files']),
        'support_images_exact_to_qualified_kit': list(support_roles), 'notice_archives_exact': notice_names,
        'collector_sha256': sha(collector.read_bytes()), 'collector_removed': True,
    }, handle, indent=2)
    handle.write('\n')
print('Core26 source, packages and notice bytes verified')
