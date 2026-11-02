"""Qualify shared restart semantics and the actual manager preview boundary."""
import hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
patterns=['test_manager_external.py','test_current_install_cli.py','test_manager_planning.py','test_manager_views.py','test_manager_routes.py',
    'test_external_planning.py','test_external_projection.py','test_reference_staging.py','test_plans.py','test_metadata_executor.py',
    'test_native_feature_executor.py','test_operation_contracts.py']
records=[];total=0
for pattern in patterns:
    command=[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',pattern]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=90)
    found=re.search(r'Ran (\d+) tests?',result.stderr);assert found,'No tests for '+pattern
    total+=int(found.group(1));records.append(dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
for command in [['node','--test','tests/test_manager_inspection.mjs'],[sys.executable,'-X','utf8','tools/check_contract_freeze.py']]:
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=90)
    records.append(dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
paths=['packages/platform_sdk/modular_platform/'+n+'.py' for n in ['contracts','plans','projection','manager_planning','manager_views','external_planning','operation_views']]
paths+=['platform_addons/mp_core/__manifest__.py','platform_addons/mp_core/operations.py','tests/test_manager_external.py','tests/test_operation_contracts.py','docs/contracts/freeze-v1.json']
report=dict(result='passed' if all(r['exit_code']==0 for r in records) else 'failed',utc=datetime.now(timezone.utc).isoformat(),python_tests=total,
    records=records,source_digests={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},no_docker_assets_created=True,
    limits=['Source qualification only; installed core14 browser counterexample remains until coherent core15 activation.'])
p=OUT/'source.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=report['result'],python_tests=total,evidence=str(p))))
sys.exit(0 if report['result']=='passed' else 1)
