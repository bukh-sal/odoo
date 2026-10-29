"""Bounded alternative after the Windows bind-mount launch never created a container."""
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from clean_recovery_fixture import LOCAL, load, save, write

state = load(LOCAL / 'state.json')
name = state['project'] + '-source-transfer-' + uuid4().hex[:8]
archive = io.BytesIO()
hashes = {}
with tarfile.open(fileobj=archive, mode='w:gz') as tar:
    for folder in ['packages/platform_sdk', 'packages/contracts', 'tests', 'tools']:
        for path in sorted((ROOT / folder).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            relative = path.relative_to(ROOT).as_posix()
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            tar.add(path, arcname=relative, recursive=False)
write(LOCAL / 'source-transfer-intent.json', dict(container=name, source_sha256=hashes))
code = '''import io,os,pathlib,sys,tarfile,subprocess
root=pathlib.Path('/tmp/audit');root.mkdir();os.chdir(root)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(root,filter='data')
sys.exit(subprocess.call(['/venv/bin/python','-B','-m','unittest','tests.test_native_auth_recovery','tests.test_restore_dispatch','tests.test_recovery','tests.test_unchanged_recovery','tests.test_maintenance_capture','-v']))
'''
args = ['docker', 'run', '--name', name, '--label', 'com.modular.disposable='+state['project'], '--log-driver', 'none', '-i', '--network', 'none', '--read-only', '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '512m', '--pids-limit', '128', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,mode=1777', '--entrypoint', '/venv/bin/python', state['image_id'], '-B', '-c', code]
result = subprocess.run(args, input=archive.getvalue(), capture_output=True, timeout=180)
(LOCAL/'logs/source-transfer.stdout').write_bytes(result.stdout)
(LOCAL/'logs/source-transfer.stderr').write_bytes(result.stderr)
found = re.search(rb'Ran (\d+) tests? in ([0-9.]+)s', result.stderr)
assert result.returncode == 0 and found, 'Inspect retained private diagnostics; no unchanged retry'
save('source-Linux.json', dict(result='passed', container=name, tests=int(found[1]), seconds=float(found[2]), source_sha256=hashes, isolation='UID10001, read-only root, network none, no host or private mounts; exact source transferred into disposable tmpfs'))
print(json.dumps(dict(result='passed', tests=int(found[1]))))
