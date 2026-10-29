"""Record current security source checks without echoing private diagnostics."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent

def main():
 dest=OUTPUT/'source-Windows.json';assert not dest.exists();start=time.monotonic();cmd=[sys.executable,'-X','utf8','-m','unittest','tests.test_approval_fences','tests.test_operator_store','tests.test_plans','tests.test_contracts','-v'];r=subprocess.run(cmd,capture_output=True,timeout=900);(ROOT/'.local/g5-approval-security/source-tests.stdout').write_bytes(r.stdout);(ROOT/'.local/g5-approval-security/source-tests.stderr').write_bytes(r.stderr)
 import re
 found=re.search(rb'Ran (\d+) tests? in ([0-9.]+)s',r.stderr);assert found and r.returncode==0,'Inspect private test diagnostics; do not replay unchanged failures';paths=['tests/test_approval_fences.py','tests/test_operator_store.py','tests/test_plans.py','tests/test_contracts.py']+['packages/platform_sdk/modular_platform/'+n for n in ['operator_store.py','operator_os.py','approval_validation.py','plans.py','contracts.py','native_executor.py','feature_executor.py','projection.py']]+['tools/modular.py']
 report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),tests=int(found[1]),elapsed_seconds=round(time.monotonic()-start,3),skipped=0,command=cmd[1:],source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths});dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',tests=report['tests'],elapsed_seconds=report['elapsed_seconds'])))
if __name__=='__main__':main()
