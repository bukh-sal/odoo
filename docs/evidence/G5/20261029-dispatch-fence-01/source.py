"""Capture the affected worker/bootstrap source qualification."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
names=['packages/platform_sdk/modular_platform/restore_executor.py','tests/test_restore_dispatch.py','packages/platform_sdk/modular_platform/operator_store.py','packages/platform_sdk/modular_platform/native_executor.py','packages/platform_sdk/modular_platform/recovery_reviews.py','packages/platform_sdk/modular_platform/unchanged_recovery.py','tools/modular.py','tests/test_recovery.py']
source={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
RUNNER="""import json,sys,unittest
sys.path[:0]=['tests','tools','packages/platform_sdk']
suite=unittest.TestSuite()
for pattern in PATTERNS:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
r=unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))))
sys.exit(not r.wasSuccessful())
"""
if __name__=='__main__':
 dest=OUTPUT/'source-host.json';assert not dest.exists()
 code='PATTERNS='+repr(['test_restore_dispatch.py','test_recovery.py','test_unchanged_recovery.py','test_operator_store.py'])+'\n'+RUNNER
 command=[sys.executable,'-X','utf8','-c',code]
 r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300)
 (OUTPUT/'source-host.stdout.log').write_bytes(r.stdout);(OUTPUT/'source-host.stderr.log').write_bytes(r.stderr)
 assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in source.items())
 report=dict(result='passed' if r.returncode==0 else 'failed',command=command,exit_code=r.returncode,source_sha256=source)
 if r.returncode==0:report['summary']=json.loads(r.stdout.decode('utf8').splitlines()[-1])
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report.get('summary',dict(result='failed'))));raise SystemExit(r.returncode)
