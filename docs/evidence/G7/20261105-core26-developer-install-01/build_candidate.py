"""Build the two versioned developer examples without changing the release tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path.cwd()
OUT = Path(__file__).parent
PRIVATE = ROOT / '.local/g7-core26-developer-install'
CONTEXT = PRIVATE / 'source'
PACKAGING = ROOT / '.local/g7-core26-developer-packaging'
RELEASE = OUT.parent / '20261105-core26-release-kit-01'
PYTHON = ROOT / '.local/release-kit-core26-rehearsal/operator/Scripts/python.exe'
SOURCE = '38ca47098c68c8bd0ea0fe8839386d2052560ac5'
BASE = 'sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert Path(sys.executable).resolve() == PYTHON.resolve()
policy_correction = sys.argv[1:] == ['--resume-with-release-policy']
resume = policy_correction or sys.argv[1:] == ['--resume-before-build']
assert resume or not sys.argv[1:]
if not resume:
    assert not PRIVATE.exists()
    protect_directory(PRIVATE)
    CONTEXT.mkdir()
    archive = PRIVATE / 'build-context.zip'
    inputs = [
        '.dockerignore', 'LICENSE', 'COPYRIGHT', 'requirements.txt', 'odoo-bin',
        'odoo', 'addons/web', 'addons/base_setup', 'addons/auth_totp', 'addons/auth_passkey',
        'addons/auth_password_policy', 'addons/base_import', 'addons/bus', 'addons/web_tour',
        'tools', 'platform_addons', 'plugins', 'packages/contracts', 'packages/platform_sdk',
        'deploy', 'tests/fixtures',
    ]
    subprocess.run(['git', 'archive', '--format=zip', '--output', str(archive), SOURCE, '--', *inputs],
                   check=True, timeout=180)
    with zipfile.ZipFile(archive) as source:
        assert source.comment.decode() == SOURCE
        source.extractall(CONTEXT)
    archive.unlink()


changes = {
    'plugins/notes_labels/plugin.toml',
    'platform_addons/mp_example_notes_labels/__manifest__.py',
    'plugins/canvas/plugin.toml',
    'platform_addons/mp_example_canvas/__manifest__.py',
    'platform_addons/mp_example_canvas/static/src/page.js',
}
previous = load(OUT.parent / '20261105-core26-ui09-image-01/candidate-build.json')
assert previous['image_id'] == BASE
assert all(sha(CONTEXT / name) == (sha(PACKAGING / 'source' / name) if resume and name in changes else digest)
           for name, digest in previous['source_sha256'].items())
if not resume:
    for path in changes:
        assert sha(PACKAGING / 'source' / path) != sha(CONTEXT / path)
        shutil.copyfile(PACKAGING / 'source' / path, CONTEXT / path)
expected = load(RELEASE / 'developer-packaging.json')['examples']
for example in expected:
    name = example['example']
    artifact = PRIVATE / (name + '.mplug')
    if not resume:
        subprocess.run([str(PYTHON), '-I', str(CONTEXT / 'tools/package_reference.py'),
                        '--source', str(CONTEXT), '--example', name, '--output', str(artifact)],
                       check=True, timeout=30)
    assert 'sha256:' + sha(artifact) == example['digest']
    assert artifact.read_bytes() == (PACKAGING / 'artifacts' / f"{name}-{example['version']}.mplug").read_bytes()

# A private detached Git pointer lets the ordinary helper record the true base
# without staging the five overlay files or changing the release checkout.
git_dir = PRIVATE / 'git'
if not resume:
    subprocess.run(['git', 'init', '--bare', '--quiet', str(git_dir)], check=True, timeout=30)
object_dir = subprocess.check_output(
    ['git', 'rev-parse', '--path-format=absolute', '--git-path', 'objects'], cwd=ROOT, text=True).strip()
env = os.environ | {'GIT_DIR': str(git_dir), 'GIT_WORK_TREE': str(CONTEXT),
                    'GIT_ALTERNATE_OBJECT_DIRECTORIES': object_dir}
if not resume:
    subprocess.run(['git', 'update-ref', '--no-deref', 'HEAD', SOURCE], env=env, cwd=CONTEXT, check=True, timeout=30)
elif not policy_correction:
    failed = load(CONTEXT / '.local/operator/builds/developer-examples-01.json')
    assert failed['state'] == 'building'
    assert not any((CONTEXT / 'docs/evidence/G7/developer-examples-01').iterdir())
    assert 'verify_private_directory(self.directory)' in (PRIVATE / 'build-driver.log').read_text()
    assert subprocess.run(['docker', 'image', 'inspect', failed['tag']], capture_output=True, timeout=30).returncode != 0
    assert subprocess.run(['docker', 'image', 'inspect', 'modular-platform:dependency-base-developer-examples-01'],
                          capture_output=True, timeout=30).returncode != 0
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], env=env, cwd=CONTEXT, text=True).strip() == SOURCE
protect_directory(CONTEXT / '.local/operator/control/locks')

if policy_correction:
    refused = load(OUT / 'candidate-omitted-connector.json')
    assert refused['distribution_policy'] != previous['distribution_policy']
    assert set(previous['artifacts']) - set(refused['artifacts']) == {'org.example.notes_stats'}
    assert 'Solved release differs from the independently staged executable image' in (
        PRIVATE / 'upgrade/plan.stderr').read_text()
    assert not (PRIVATE / 'upgrade/register.stdout').exists()
attempt = '03' if policy_correction else '02' if resume else '01'
candidate = CONTEXT / 'docs/evidence/G7' / ('developer-examples-' + attempt)
with (PRIVATE / ('build-driver-' + attempt + '.log') if resume else PRIVATE / 'build-driver.log').open('xb') as log:
    subprocess.run([str(PYTHON), '-I', str(CONTEXT / 'tools/build_candidate.py'),
                    '--gate', 'G7', '--output', str(candidate), '--dependency-base-image', BASE,
                    '--policy', previous['distribution_policy']],
                   cwd=CONTEXT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1050)
result = load(candidate / 'candidate-build.json')
assert result['result'] == 'built_not_deployed'
assert result['dependency_base_image'] == BASE and result['git_base'] == SOURCE
assert set(previous['source_sha256']) == set(result['source_sha256'])
assert {name for name, value in result['source_sha256'].items()
        if previous['source_sha256'][name] != value} == changes
for example in expected:
    plugin = 'org.example.' + example['example']
    assert result['artifacts'][plugin]['digest'] == example['digest']
assert result['distribution_policy'] == previous['distribution_policy']
assert set(result['artifacts']) == set(previous['artifacts'])
assert all(result['artifacts'][plugin] == previous['artifacts'][plugin]
           for plugin in ('org.example.notes', 'org.example.notes_stats'))
result['isolated_source_snapshot'] = SOURCE
result['isolated_changed_inputs'] = sorted(changes)
result['independently_reproduced_example_artifacts'] = expected
with (OUT / 'candidate-build.json').open('x', encoding='utf8') as handle:
    json.dump(result, handle, indent=2)
    handle.write('\n')
print(json.dumps({'result': result['result'], 'image': result['image_id'], 'tag': result['tag']}))
