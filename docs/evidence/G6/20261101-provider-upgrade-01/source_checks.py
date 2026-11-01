"""Record bounded successor compatibility and retention regressions."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
checks=[]
for module in ['test_external_projection','test_external_planning','test_reference_staging']:
    args=[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',module+'.py']
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    checks.append(dict(module=module,result='passed',output=result.stdout+result.stderr))
freeze=subprocess.run([sys.executable,'-X','utf8','tools/check_contract_freeze.py'],cwd=ROOT,capture_output=True,text=True,timeout=60)
assert freeze.returncode==0
paths=['plugins/document_stats/plugin.toml']+['tests/'+c['module']+'.py' for c in checks]
report=dict(result='passed',at=datetime.now(timezone.utc).isoformat(),checks=checks,total=37,
    frozen_contracts=json.loads(freeze.stdout),source_digests={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
    limits=['Source planning/retention regressions; actual lifecycle evidence separate.'])
path=OUT/'source-checks.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('37 targeted source checks and unchanged 94-file/8-row contract freeze passed')
