"""Affected host journal/review regressions, Linux equivalents and freeze."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
PATTERNS=['test_operator_store.py','test_recovery.py']
RUNNER="""import json,sys,unittest
sys.path[:0]=['tests','packages/platform_sdk']
suite=unittest.TestSuite()
for pattern in PATTERNS:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
result=unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped))))
sys.exit(not result.wasSuccessful())
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['host','linux','freeze']);args=parser.parse_args()
    dest=OUTPUT/('source-'+args.action+'.json');assert not dest.exists()
    source={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in [
        'packages/platform_sdk/modular_platform/operator_store.py','packages/platform_sdk/modular_platform/recovery_reviews.py',
        'packages/platform_sdk/modular_platform/unchanged_recovery.py','tools/modular.py','tests/test_unchanged_recovery.py']}
    if args.action=='freeze':command=[sys.executable,'-X','utf8','tools/check_contract_freeze.py']
    else:
        patterns=PATTERNS+(['test_unchanged_recovery.py'] if args.action=='linux' else [])
        code='PATTERNS='+repr(patterns)+'\n'+RUNNER
        command=[sys.executable,'-X','utf8','-c',code] if args.action=='host' else [
            'docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--memory','512m','--mount','type=bind,source='+str(ROOT)+',target=/workspace,readonly',
            '-w','/workspace','--entrypoint','/venv/bin/python',
            'sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea','-c',code]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
    (OUTPUT/('source-'+args.action+'.stdout.log')).write_bytes(result.stdout)
    (OUTPUT/('source-'+args.action+'.stderr.log')).write_bytes(result.stderr)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    report=dict(result='passed' if result.returncode==0 else 'failed',command=command,exit_code=result.returncode,source_sha256=source)
    if result.returncode==0:
        try:report['summary']=json.loads(result.stdout.decode('utf8').splitlines()[-1])
        except (ValueError,IndexError):pass
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(action=args.action,result=report['result'],summary=report.get('summary'))))
    if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
