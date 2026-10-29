"""Current host OS and redacted-channel source checks on Windows and Linux."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-operator-isolation'

def main():
 mode=sys.argv[1];assert mode in ['Windows','Linux'];dest=OUTPUT/('source-'+mode+'.json');assert not dest.exists();tests=['tests.test_operator_os','tests.test_feature_executor'];container=None
 if mode=='Windows':args=[sys.executable,'-X','utf8','-m','unittest',*tests,'-v']
 else:
  target=json.loads((ROOT/'.local/g5-httpsecurity/operator/target.json').read_text());container=target['project']+'-operator-source-linux-'+uuid4().hex[:8];args=['docker','run','--name',container,'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,nodev,size=128m,mode=1777','--workdir','/audit']
  for source in ['packages/platform_sdk','packages/contracts','tests','tools']:args+=['--mount','type=bind,source='+str(ROOT/source)+',target=/audit/'+source+',readonly']
  args+=['--entrypoint','/venv/bin/python',target['image_id'],'-B','-m','unittest',*tests,'-v'];(LOCAL/('source-'+mode+'-intent.json')).write_text(json.dumps(dict(container=container,image=target['image_id'])),encoding='utf8')
 r=subprocess.run(args,capture_output=True,timeout=300);(LOCAL/('source-'+mode+'.stdout')).write_bytes(r.stdout);(LOCAL/('source-'+mode+'.stderr')).write_bytes(r.stderr)
 import re
 found=re.search(rb'Ran (\d+) tests? in ([0-9.]+)s',r.stderr);assert r.returncode==0 and found,'Inspect exact retained diagnostic/intent before any continuation';paths=['tests/test_operator_os.py','tests/test_feature_executor.py']+['packages/platform_sdk/modular_platform/'+n for n in ['operator_os.py','operator_store.py','app_channel.py','contracts.py','plans.py']]
 report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),tests=int(found[1]),seconds=float(found[2]),skipped=0,container=container,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths});dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',mode=mode,tests=report['tests'],seconds=report['seconds'])))
if __name__=='__main__':main()
