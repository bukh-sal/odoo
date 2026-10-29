"""Run public sources in a no-bind temporary filesystem; retain exact logs."""
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUTPUT));from source import RUNNER


def main():
    name='mp-g5-dispatch-fence-checks-01';dest=OUTPUT/'source-linux.json';assert not dest.exists()
    assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0
    source=json.loads((OUTPUT/'source-boundary-input.json').read_text(encoding='utf8'))['source_sha256'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    patterns=['test_restore_dispatch.py','test_recovery.py','test_unchanged_recovery.py','test_operator_store.py','test_workers.py','test_executor_crash_fence.py']
    code='PATTERNS='+repr(patterns)+'\nHOST=False\n'+RUNNER
    buffer=io.BytesIO();copied={}
    with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
        for folder in ['packages','tests','platform_addons','plugins','deploy','tools']:
            for p in sorted((ROOT/folder).rglob('*')):
                if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
                assert not p.is_symlink();raw=p.read_bytes();relative=p.relative_to(ROOT).as_posix();copied[relative]=hashlib.sha256(raw).hexdigest()
                entry=tarfile.TarInfo(relative);entry.size=len(raw);entry.mode=0o444;archive.addfile(entry,io.BytesIO(raw))
        for filename in ['LICENSE','COPYRIGHT']:
            raw=(ROOT/filename).read_bytes();entry=tarfile.TarInfo(filename);entry.size=len(raw);entry.mode=0o444;archive.addfile(entry,io.BytesIO(raw))
        raw=code.encode();entry=tarfile.TarInfo('linux-runner.py');entry.size=len(raw);entry.mode=0o444;archive.addfile(entry,io.BytesIO(raw))
    image=json.loads((ROOT/'.local/g5-lifecycle/operator/target.json').read_text(encoding='utf8'))['image_id']
    command=['docker','create','--name',name,'--label','com.modular.qualification=G5-dispatch-fence','--network','none','--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--entrypoint','/venv/bin/python',image,'-c','import time;time.sleep(600)']
    created=subprocess.run(command,capture_output=True,timeout=30);assert created.returncode==0,created.stderr.decode('utf8',errors='replace')
    cid=created.stdout.decode().strip();subprocess.run(['docker','start',name],capture_output=True,check=True,timeout=30)
    print(json.dumps(dict(state='running_isolated_no_bind_unit_container',container_id=cid)),flush=True)
    unpack="import pathlib,sys,tarfile;root=pathlib.Path('/tmp/qualification');root.mkdir();tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall(root,filter='data')"
    subprocess.run(['docker','exec','-i',name,'/venv/bin/python','-c',unpack],input=buffer.getvalue(),capture_output=True,check=True,timeout=30)
    r=subprocess.run(['docker','exec','-w','/tmp/qualification',name,'/venv/bin/python','linux-runner.py'],capture_output=True,timeout=180)
    (OUTPUT/'source-linux.stdout.log').write_bytes(r.stdout);(OUTPUT/'source-linux.stderr.log').write_bytes(r.stderr)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    subprocess.run(['docker','stop','--time','2',name],capture_output=True,check=True,timeout=15)
    report=dict(result='passed' if r.returncode==0 else 'failed',container_id=cid,exit_code=r.returncode,command=command,public_source_copy_sha256=copied,source_sha256=source,private_or_live_mounts=False,archive_bytes=len(buffer.getvalue()),utc=datetime.now(timezone.utc).isoformat())
    if r.returncode==0:report['summary']=json.loads(r.stdout.decode('utf8').splitlines()[-1])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=report['result'],summary=report.get('summary'))),flush=True);raise SystemExit(r.returncode)


if __name__=='__main__':main()
