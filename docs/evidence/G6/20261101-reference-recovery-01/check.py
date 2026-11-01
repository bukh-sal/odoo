"""Bounded host-source recovery regressions; no Docker/SQL mutation evidence."""
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
SUITES=['test_reference_recovery','test_restore_dispatch','test_restore_continuation',
        'test_native_dispatch_resume','test_metadata_executor','test_core_upgrade','test_executor_crash_fence']
sources=['reference_recovery.py','reference_dispatch.py','restore_executor.py','restore_continuation.py',
         'unchanged_recovery.py','native_executor.py','metadata_executor.py','dispatch_operator.py']
destination=Path(__file__).parent/'qualification.json'
if destination.exists():raise SystemExit('Preserve existing evidence; use a new attempt destination')
results=[]
for name in SUITES:
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName(name))
    results.append(dict(suite=name,tests=result.testsRun,successful=result.wasSuccessful(),transcript=output.getvalue()))
report=dict(utc=datetime.now(timezone.utc).isoformat(),result='passed' if all(r['successful'] for r in results) else 'failed',
    tests=sum(r['tests'] for r in results),suites=results,
    sources={name:hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform'/name).read_bytes()).hexdigest() for name in sources},
    cli_sha256=hashlib.sha256((ROOT/'tools/modular.py').read_bytes()).hexdigest(),
    scope='Host source only; recovery Docker/SQL/checkpoint effects substituted. Real OS journals have separate retained evidence.',
    installed=False,actual_metadata_recovery=False,new_docker_assets=0,
    acceptance_credit=False,limits=['Known reference immutable worker image only; changed-image transition is not qualified.',
        'No real checkpoint, fresh database restore, runtime launch, endpoint publication or remote IO in these suites.',
        'Unknown effects, live technical credentials, API keys, unknown release metadata and stale queue state remain refused.'])
destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=report['result'],tests=report['tests'],suites=len(results))))
raise SystemExit(0 if report['result']=='passed' else 1)
