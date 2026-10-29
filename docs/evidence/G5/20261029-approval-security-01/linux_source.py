"""Current readonly source on actual Linux/POSIX identity, no live mounts."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-approval-security'

def main():
 dest=OUTPUT/'source-Linux.json';assert not dest.exists();target=json.loads((ROOT/'.local/g5-httpsecurity/operator/target.json').read_text());name=target['project']+'-approval-source-linux-'+uuid4().hex[:8];args=['docker','run','--name',name,'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,nodev,size=128m,mode=1777','--workdir','/audit']
 for source,destination in [('packages/platform_sdk','/audit/packages/platform_sdk'),('packages/contracts','/audit/packages/contracts'),('tests','/audit/tests'),('tools','/audit/tools')]:args+=['--mount','type=bind,source='+str(ROOT/source)+',target='+destination+',readonly']
 args+=['--entrypoint','/venv/bin/python',target['image_id'],'-B','-m','unittest','tests.test_approval_fences','tests.test_operator_store','tests.test_plans','-v'];(LOCAL/(name+'-intent.json')).write_text(json.dumps(dict(container=name,image=target['image_id'],read_only_source=True)),encoding='utf8');r=subprocess.run(args,capture_output=True,timeout=300);(LOCAL/'source-linux-final.stdout').write_bytes(r.stdout);(LOCAL/'source-linux-final.stderr').write_bytes(r.stderr)
 import re
 found=re.search(rb'Ran (\d+) tests? in ([0-9.]+)s',r.stderr);assert r.returncode==0 and found,'Inspect exact retained Linux container and private output, no automatic replay';info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['State']['Running'] and info['State']['ExitCode']==0 and info['Config']['User']=='10001:10001' and info['HostConfig']['LogConfig']['Type']=='none' and info['HostConfig']['NetworkMode']=='none' and all(not m['RW'] for m in info['Mounts'] if m['Type']=='bind')
 paths=['tests/test_approval_fences.py','tests/test_operator_store.py','tests/test_plans.py']+['packages/platform_sdk/modular_platform/'+n for n in ['operator_store.py','operator_os.py','approval_validation.py','plans.py','contracts.py','native_executor.py','feature_executor.py','projection.py']];result=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),tests=int(found[1]),skipped=0,seconds=float(found[2]),container_id=info['Id'],image_id=target['image_id'],actual_UID=10001,no_network_private_or_live_mounts=True,all_source_mounts_readonly=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths});dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',linux_tests=result['tests'],seconds=result['seconds'],container=name)))
if __name__=='__main__':main()
