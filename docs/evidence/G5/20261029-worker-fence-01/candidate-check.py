"""Evaluate reviewed candidate bootstrap against actual DBs, read-only only."""
import hashlib,json,subprocess
from pathlib import Path
from observe import ROOT,OUTPUT,LOCAL,PROBE
load=lambda p:json.loads(p.read_text(encoding='utf8'))
config=load(LOCAL/'operator/target.json');baseline=load(OUTPUT/'read-only-baseline.json');dest=OUTPUT/'candidate-read-only.json';assert not dest.exists()
source=(ROOT/'packages/platform_sdk/modular_platform/worker_start.py').read_bytes()
probe=PROBE.replace("bootstrap=runpy.run_path(str(guard),run_name='read_only_guard_qualification')", "bootstrap={'__name__':'operator_reviewed_candidate_guard'};exec(compile(sys.stdin.read(),'<reviewed candidate guard>','exec'),bootstrap)")
reports=[]
for index,case in enumerate(baseline['guard_cases']):
 r=subprocess.run(['docker','exec','-i',config['worker_id'],'/venv/bin/python','-c',probe,case['database']],input=source,capture_output=True,timeout=90)
 if r.returncode:
  (LOCAL/'worker-fence-candidate.stderr').write_bytes(r.stderr);raise RuntimeError('Inspect candidate read-only diagnostics')
 value=json.loads(r.stdout);assert value['result']==('accepted' if index==0 else 'rejected')
 if index:assert 'differs from native registration' in value['reason']
 reports.append(value)
assert (ROOT/'packages/platform_sdk/modular_platform/worker_start.py').read_bytes()==source
report=dict(result='passed',candidate_source_sha256=hashlib.sha256(source).hexdigest(),cases=reports,limits=['Operator-supplied candidate source in read-only validation process; not immutable default-entrypoint or deployment qualification.'])
dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
