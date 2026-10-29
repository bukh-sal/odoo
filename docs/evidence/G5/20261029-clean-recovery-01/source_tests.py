"""Affected recovery/source checks, recorded once per OS at this source boundary."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,re
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-clean-recovery'

def main():
 mode=sys.argv[1];assert mode in ['Windows','Linux'];dest=OUTPUT/('source-'+mode+'.json');assert not dest.exists();tests=['tests.test_native_auth_recovery','tests.test_restore_dispatch','tests.test_recovery','tests.test_unchanged_recovery','tests.test_maintenance_capture'];container=None
 if mode=='Windows':args=[sys.executable,'-X','utf8','-m','unittest',*tests,'tests.test_secret_scan','-v']
 else:
  state=json.loads((LOCAL/'state.json').read_text());container=state['project']+'-recovery-source-linux-'+uuid4().hex[:8];args=['docker','run','--name',container,'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,nodev,size=128m,mode=1777','--workdir','/audit']
  for source in ['packages/platform_sdk','packages/contracts','tests','tools']:args+=['--mount','type=bind,source='+str(ROOT/source)+',target=/audit/'+source+',readonly']
  args+=['--entrypoint','/venv/bin/python',state['image_id'],'-B','-m','unittest',*tests,'-v'];(LOCAL/'source-Linux-intent.json').write_text(json.dumps(dict(container=container,image=state['image_id'])),encoding='utf8')
 r=subprocess.run(args,capture_output=True,timeout=600);(LOCAL/'logs'/('source-'+mode+'.stdout')).write_bytes(r.stdout);(LOCAL/'logs'/('source-'+mode+'.stderr')).write_bytes(r.stderr);found=re.search(rb'Ran (\d+) tests? in ([0-9.]+)s',r.stderr);assert r.returncode==0 and found,'Inspect private test diagnostics and retained container; do not replay unchanged failures';paths=['tests/test_native_auth_recovery.py','tests/test_restore_dispatch.py','tests/test_recovery.py','tests/test_unchanged_recovery.py','tests/test_maintenance_capture.py','packages/platform_sdk/modular_platform/native_auth_recovery.py','packages/platform_sdk/modular_platform/restore_executor.py','packages/platform_sdk/modular_platform/recovery_reviews.py','packages/platform_sdk/modular_platform/native_executor.py','packages/platform_sdk/modular_platform/operator_store.py','tools/modular.py'];result=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),tests=int(found[1]),seconds=float(found[2]),skipped=0,container=container,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths});dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',OS=mode,tests=result['tests'],seconds=result['seconds'])))
if __name__=='__main__':main()
