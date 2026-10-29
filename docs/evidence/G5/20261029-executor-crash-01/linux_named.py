"""Inspectable retained unit container; avoids ambiguous Docker attach waits."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUTPUT));from source import RUNNER


def main():
    name='mp-g5-executor-crash-checks-02';marker=ROOT/'.local/g5-lifecycle/executor-checks02.json';dest=OUTPUT/'source-linux2.json'
    assert not marker.exists() and not dest.exists()
    absent=subprocess.run(['docker','inspect',name],capture_output=True);assert absent.returncode!=0
    patterns=['test_executor_crash_fence.py','test_operator_store.py','test_recovery.py','test_unchanged_recovery.py','test_native_uninstall.py','test_artifact_removal.py','test_platform_deploy.py','test_core_upgrade.py']
    code='PATTERNS='+repr(patterns)+'\nHOST=False\n'+RUNNER
    runner=OUTPUT/'linux-runner02.py';assert not runner.exists();runner.write_text(code,encoding='utf8')
    source=json.loads((OUTPUT/'source-host2.json').read_text(encoding='utf8'))['source_sha256'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    record=dict(state='creating',name=name,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    command=['docker','create','--name',name,'--label','com.modular.qualification=G5-executor-crash','--network','none','--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--mount','type=bind,source='+str(ROOT)+',target=/workspace,readonly','-w','/workspace','--entrypoint','/venv/bin/python','sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea','/workspace/docs/evidence/G5/20261029-executor-crash-01/linux-runner02.py']
    created=subprocess.run(command,capture_output=True,timeout=60);assert created.returncode==0,created.stderr.decode('utf8',errors='replace')
    record.update(state='created',container_id=created.stdout.decode().strip());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    subprocess.run(['docker','start',name],capture_output=True,check=True,timeout=30)
    record['state']='running';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record),flush=True)
    deadline=time.monotonic()+300
    while True:
        info=json.loads(subprocess.check_output(['docker','inspect',name],timeout=15))[0]
        if not info['State']['Running']:break
        if time.monotonic()>deadline:raise RuntimeError('Named unit container still running; inspect exact ID/logs before any action')
        time.sleep(0.5)
    logs=subprocess.run(['docker','logs',name],capture_output=True,timeout=30)
    (OUTPUT/'source-linux2.stdout.log').write_bytes(logs.stdout);(OUTPUT/'source-linux2.stderr.log').write_bytes(logs.stderr)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    report=dict(result='passed' if info['State']['ExitCode']==0 else 'failed',container_id=info['Id'],exit_code=info['State']['ExitCode'],oom_killed=info['State']['OOMKilled'],command=command,source_sha256=source)
    if info['State']['ExitCode']==0:report['summary']=json.loads(logs.stdout.decode('utf8').splitlines()[-1])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');record['state']=report['result'];marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(report.get('summary',report)),flush=True)
    raise SystemExit(info['State']['ExitCode'])


if __name__=='__main__':main()
