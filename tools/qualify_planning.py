"""Bind pure G5 solver/plan/CLI evidence to source and locked resolver metadata."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ['test_artifacts.py', 'test_resolution.py', 'test_plans.py', 'test_planning_cli.py']


def run(command, *, input=None):
    result = subprocess.run(command, input=input, capture_output=True, cwd=ROOT, timeout=300)
    return {'command': command, 'exit_code': result.returncode,
            'stdout': result.stdout.decode('utf-8', errors='replace'), 'stderr': result.stderr.decode('utf-8', errors='replace')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--image', default='modular-platform:r1')
    parser.add_argument('--operator', action='store_true', help='Include independent OS/store primitives')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'docs/evidence/G5') or output.exists():
        raise ValueError('Fresh G5 evidence directory required')
    output.mkdir(parents=True)
    patterns = PATTERNS + (['test_operator_os.py', 'test_operator_store.py'] if args.operator else [])
    host = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'])
    (output / 'host-tests.json').write_text(json.dumps(host, indent=2) + '\n')
    selected = {ROOT / name for name in ['LICENSE', 'COPYRIGHT', 'tools/reference_package.py', 'tools/modular.py',
        'tools/qualify_planning.py', 'tools/observe_r1.py', 'tools/qualify_live_planning.py', 'tools/qualify_operator_live.py',
        'deploy/requirements-operator.in', 'deploy/requirements-operator.lock'] + ['tests/' + name for name in patterns]}
    for folder in ['packages/platform_sdk', 'packages/contracts', 'plugins',
                   'platform_addons/mp_example_notes', 'platform_addons/mp_example_notes_labels', 'platform_addons/mp_example_canvas']:
        selected.update(path for path in (ROOT / folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    source = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(selected)}
    dependency = importlib.metadata.distribution('resolvelib')
    if dependency.version != '1.2.1':
        raise ValueError('Install the exact reviewed requirements-operator.lock')
    dependencies = {}
    for entry in dependency.files:
        if '__pycache__' in entry.parts:
            continue
        if not entry.parts[0].startswith(('resolvelib/', 'resolvelib-')) and entry.parts[0] != 'resolvelib':
            raise ValueError('Unexpected installed resolver path')
        path = Path(dependency.locate_file(entry))
        raw = path.read_bytes()
        if entry.hash:
            if entry.hash.mode != 'sha256' or base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode() != entry.hash.value:
                raise ValueError('Installed resolver file differs from wheel RECORD')
        elif entry.name != 'RECORD':
            raise ValueError('Unhashed resolver distribution file')
        dependencies[str(entry).replace('\\', '/')] = raw
    tar_input = io.BytesIO()
    with tarfile.open(fileobj=tar_input, mode='w') as archive:
        for path in sorted(selected):
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
        for name, raw in sorted(dependencies.items()):
            info = tarfile.TarInfo('operator_dependencies/' + name)
            info.mode = 0o444
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    runner = '''import os,sys,tarfile,unittest
os.mkdir('/tmp/qualification',0o700)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
    archive.extractall('/tmp/qualification',filter='data')
os.chdir('/tmp/qualification')
os.environ['PYTHONPATH']='/tmp/qualification/operator_dependencies:/opt/modular/packages/platform_sdk'
sys.path.insert(0,'/tmp/qualification/operator_dependencies')
print('QUALIFICATION_PYTHON='+sys.version,flush=True)
suite=unittest.TestSuite()
for pattern in PATTERN_INPUT:
    suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
'''
    runner = runner.replace('PATTERN_INPUT', repr(patterns))
    linux = run(['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
        '--memory', '512m', '--cpus', '2', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777',
        '--entrypoint', '/venv/bin/python', args.image, '-c', runner], input=tar_input.getvalue())
    (output / 'linux-tests.json').write_text(json.dumps(linux, indent=2) + '\n')
    frozen = run([sys.executable, 'tools/check_contract_freeze.py'])
    (output / 'contract-freeze.json').write_text(json.dumps(frozen, indent=2) + '\n')
    result = 'passed' if all(item['exit_code'] == 0 for item in (host, linux, frozen)) else 'failed'
    report = {'item': 'E-01c-primitives' if args.operator else 'E-01b-core', 'gate': 'G5', 'result': result, 'utc': datetime.now(timezone.utc).isoformat(),
        'host': {'system': platform.system(), 'python': platform.python_version()},
        'git_base': run(['git', 'rev-parse', 'HEAD'])['stdout'].strip(),
        'image_id': run(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'])['stdout'].strip(),
        'source_sha256': source, 'resolver_version': dependency.version,
        'resolver_files_sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(dependencies.items())},
        'records': ['host-tests.json', 'linux-tests.json', 'contract-freeze.json'],
        'limitations': ['Pure resolver/lock/plan and real CLI qualified, not an executor or G5 exit.',
            'No new deployment/site mutation or production release build.',
            'Linux test streams the locally hash-locked resolver including license, verified against wheel RECORD, into private tmpfs.',
            'UI queue, independent snapshot/approval, process locks, journal, native execution and recovery remain pending.',
            'Dependency decisions use static metadata; no network/build/import of plugin code during planning.']}
    (output / 'planning-core.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'result': result, 'evidence': str(output), 'host_exit': host['exit_code'], 'linux_exit': linux['exit_code']}))
    return 0 if result == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
