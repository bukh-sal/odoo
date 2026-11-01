"""Source-only staged native/external retention regression checkpoint."""
import hashlib,io,json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
destination=Path(__file__).with_name('qualification.json')
if destination.exists():raise SystemExit('Preserve evidence; use a new attempt destination')
names=['test_reference_staging','test_release_staging','test_manager_planning','test_core_upgrade',
       'test_platform_deploy','test_artifact_removal','test_reinstall_planning','test_plans']
results=[]
for name in names:
    output=io.StringIO();result=unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromName(name))
    results.append(dict(suite=name,tests=result.testsRun,passed=result.wasSuccessful(),transcript=output.getvalue()))
files=['release_staging.py','manager_planning.py','artifact_removal.py','profile_channel.py','plans.py','lifecycle_planning.py']
report=dict(utc=datetime.now(timezone.utc).isoformat(),result='passed' if all(r['passed'] for r in results) else 'failed',
    tests=sum(r['tests'] for r in results),suites=results,
    sources={name:hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform'/name).read_bytes()).hexdigest() for name in files},
    cli_sha256=hashlib.sha256((ROOT/'tools/modular.py').read_bytes()).hexdigest(),
    scope='Pure source planning, immutable artifact assembly/validation and temporary OS approval fixtures only.',
    actual_staged_deployment=False,actual_external_registration=False,installed=False,new_docker_assets=0,acceptance_credit=False)
destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['result','tests']}))
raise SystemExit(report['result']!='passed')
