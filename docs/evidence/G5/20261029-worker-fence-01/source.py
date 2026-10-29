"""Capture the affected worker/bootstrap source qualification."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
names=['packages/platform_sdk/modular_platform/worker_start.py','packages/platform_sdk/modular_platform/workers.py','packages/platform_sdk/modular_platform/native_executor.py','tools/start_worker.py','tests/test_worker_installations.py','tests/test_workers.py','tests/test_start_worker.py']
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
 code='PATTERNS='+repr(['test_worker_installations.py','test_workers.py','test_start_worker.py'])+'\n'+RUNNER
 command=[sys.executable,'-X','utf8','-c',code]
 r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120)
 (OUTPUT/'source-host.stdout.log').write_bytes(r.stdout);(OUTPUT/'source-host.stderr.log').write_bytes(r.stderr)
 assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in source.items())
 report=dict(result='passed' if r.returncode==0 else 'failed',command=command,exit_code=r.returncode,source_sha256=source)
 if r.returncode==0:report['summary']=json.loads(r.stdout.decode('utf8').splitlines()[-1])
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report.get('summary',dict(result='failed'))));raise SystemExit(r.returncode)
