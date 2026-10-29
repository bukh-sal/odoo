"""Affected executor fences and existing privileged-path regressions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
RUNNER="""import json,sys,unittest
sys.path[:0]=['tests','packages/platform_sdk']
suite=unittest.TestSuite()
for pattern in PATTERNS:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
if HOST:suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_operator_store.OperatorStoreTests.test_new_lock_owner_after_possible_commit_records_recovery_before_stale_state_check'))
r=unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))))
sys.exit(not r.wasSuccessful())
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['host','linux','freeze']);parser.add_argument('--attempt',type=int,choices=[1,2],default=1);args=parser.parse_args()
    stem='source-'+args.action+('2' if args.attempt==2 else '')
    dest=OUTPUT/(stem+'.json');assert not dest.exists()
    names=['packages/platform_sdk/modular_platform/native_executor.py','tests/test_executor_crash_fence.py',
           'packages/platform_sdk/modular_platform/operator_store.py','packages/platform_sdk/modular_platform/restore_executor.py',
           'packages/platform_sdk/modular_platform/recovery_reviews.py','packages/platform_sdk/modular_platform/unchanged_recovery.py','tools/modular.py']
    source={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    if args.action=='freeze':command=[sys.executable,'-X','utf8','tools/check_contract_freeze.py']
    else:
        patterns=['test_executor_crash_fence.py']
        if args.action=='linux':patterns+=['test_operator_store.py','test_recovery.py','test_unchanged_recovery.py','test_native_uninstall.py','test_artifact_removal.py','test_platform_deploy.py','test_core_upgrade.py']
        code='PATTERNS='+repr(patterns)+'\nHOST='+repr(args.action=='host')+'\n'+RUNNER
        command=[sys.executable,'-X','utf8','-c',code] if args.action=='host' else ['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','768m','--mount','type=bind,source='+str(ROOT)+',target=/workspace,readonly','-w','/workspace','--entrypoint','/venv/bin/python','sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea','-c',code]
    r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
    (OUTPUT/(stem+'.stdout.log')).write_bytes(r.stdout);(OUTPUT/(stem+'.stderr.log')).write_bytes(r.stderr)
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in source.items())
    report=dict(result='passed' if r.returncode==0 else 'failed',exit_code=r.returncode,command=command,source_sha256=source)
    if r.returncode==0:report['summary']=json.loads(r.stdout.decode('utf8').splitlines()[-1])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(action=args.action,result=report['result'],summary=report.get('summary'))))
    raise SystemExit(r.returncode)


if __name__=='__main__':main()
