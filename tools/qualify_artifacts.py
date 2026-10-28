"""Record G5 archive/catalog qualification on Windows and isolated Linux."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, input=None):
    process = subprocess.run(command, cwd=ROOT, input=input, capture_output=True, timeout=180)
    return {'command': command, 'exit_code': process.returncode,
            'stdout': process.stdout.decode('utf-8', errors='replace'),
            'stderr': process.stderr.decode('utf-8', errors='replace')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', default='modular-platform:r1')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'docs/evidence/G5') or output.exists():
        raise ValueError('Output must be a fresh G5 evidence directory')
    output.mkdir(parents=True)
    selected = {ROOT / name for name in ['LICENSE', 'COPYRIGHT', 'tools/reference_package.py',
        'tools/modular.py', 'tools/qualify_artifacts.py', 'tests/test_artifacts.py']}
    for folder in ['packages/platform_sdk', 'packages/contracts', 'plugins',
                   'platform_addons/mp_example_notes', 'platform_addons/mp_example_notes_labels',
                   'platform_addons/mp_example_canvas']:
        selected.update(path for path in (ROOT / folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    source = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(selected)}
    host = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_artifacts.py', '-v'])
    (output / 'host-tests.json').write_text(json.dumps(host, indent=2) + '\n')
    frozen = run([sys.executable, 'tools/check_contract_freeze.py'])
    (output / 'contract-freeze.json').write_text(json.dumps(frozen, indent=2) + '\n')
    tar_input = io.BytesIO()
    with tarfile.open(fileobj=tar_input, mode='w') as archive:
        for path in sorted(selected):
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    runner = '''import os,sys,tarfile,subprocess
os.mkdir('/tmp/qualification',0o700)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
    archive.extractall('/tmp/qualification',filter='data')
os.chdir('/tmp/qualification')
print('QUALIFICATION_PYTHON='+sys.version,flush=True)
raise SystemExit(subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_artifacts.py','-v']).returncode)
'''
    container = run(['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
        '--memory', '512m', '--cpus', '2', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777',
        '--entrypoint', '/venv/bin/python', args.image, '-c', runner], input=tar_input.getvalue())
    (output / 'linux-tests.json').write_text(json.dumps(container, indent=2) + '\n')
    image = run(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'])
    summary = {'item': 'E-01a', 'gate': 'G5', 'result': 'passed' if all(item['exit_code'] == 0 for item in (host, frozen, container, image)) else 'failed',
        'utc': datetime.now(timezone.utc).isoformat(), 'host': {'system': platform.system(), 'python': platform.python_version()},
        'image': args.image, 'image_id': image['stdout'].strip(),
        'git_base': run(['git', 'rev-parse', 'HEAD'])['stdout'].strip(),
        'source_sha256': source, 'records': ['host-tests.json', 'linux-tests.json', 'contract-freeze.json'],
        'acceptance': ['PKG-01', 'PKG-02', 'PKG-03', 'PKG-04', 'PKG-05'],
        'limits': ['No signature verification claim; exact-digest curated approval only.',
                   'Secret and remote-script lint is supplementary; trusted code is not sandboxed.',
                   'Release inventory startup, solver, executor, OS approval separation and lifecycle remain E-01b/c/d.',
                   'Linux test uses pinned existing image dependencies with current source streamed to disposable tmpfs; it is not a release build.']}
    (output / 'archive-catalog.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'result': summary['result'], 'evidence': str(output), 'host_exit': host['exit_code'], 'linux_exit': container['exit_code']}))
    return 0 if summary['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
