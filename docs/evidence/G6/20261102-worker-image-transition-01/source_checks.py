"""Bounded host/source checks. Does not deploy or qualify SVC05."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
modules=['test_worker_transition','test_reference_reregistration','test_reference_recovery','test_reference_staging',
    'test_external_projection','test_external_planning','test_metadata_executor','test_restore_dispatch',
    'test_native_dispatch_resume','test_worker_dispatch']
files=['packages/platform_sdk/modular_platform/'+n+'.py' for n in ['worker_transition','reference_dispatch','reference_recovery',
    'metadata_executor','dispatch_lifecycle','projection']]+['platform_addons/mp_core/__manifest__.py']
files+=['tests/'+n+'.py' for n in modules]
source={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
command=[sys.executable,'-X','utf8','-m','unittest','-q',*modules]
import os
environment=dict(os.environ,PYTHONPATH=str(ROOT/'tests')+os.pathsep+str(ROOT/'packages/platform_sdk'))
with (OUT/'tests.log').open('xb') as log:
    result=subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=120)
freeze=subprocess.run([sys.executable,'-X','utf8','tools/check_contract_freeze.py'],cwd=ROOT,capture_output=True,timeout=30)
(OUT/'freeze.log').write_bytes(freeze.stdout+freeze.stderr)
record=dict(utc=datetime.now(timezone.utc).isoformat(),git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    source_sha256=source,modules=modules,tests_exit_code=result.returncode,freeze_exit_code=freeze.returncode,
    result='passed_source_only' if result.returncode==freeze.returncode==0 else 'failed',deployment_changed=False,
    limits='Independent IO substituted; actual immutable image rollout, distinct worker upgrade/recovery remain required. No SVC05 credit.')
(OUT/'source-checks.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['result','tests_exit_code','freeze_exit_code','deployment_changed']}))
raise SystemExit(result.returncode or freeze.returncode)
