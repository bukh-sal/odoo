"""Bounded changed lifecycle consumers, separate from installed acceptance."""
import json
from pathlib import Path
import re
import subprocess
import sys

root=Path.cwd();out=Path(__file__).parent
patterns=['test_lifecycle_contracts.py','test_lifecycle_impact.py','test_uninstall_planning.py',
          'test_native_uninstall.py','test_lifecycle_planning.py','test_reference_recovery.py',
          'test_reference_reregistration.py','test_restore_dispatch.py','test_native_dispatch_resume.py']
records=[]
for pattern in patterns:
    command=[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',pattern,'-v']
    result=subprocess.run(command,capture_output=True,timeout=90)
    stdout=result.stdout.decode('utf8');stderr=result.stderr.decode('utf8')
    counts=re.findall(r'Ran (\d+) tests?',stderr)
    assert len(counts)==1 and int(counts[0])>0,(pattern,result.returncode)
    record=dict(command=command,exit_code=result.returncode,stdout=stdout,stderr=stderr,tests=int(counts[0]))
    (out/(pattern+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    records.append(dict(pattern=pattern,exit_code=result.returncode,tests=int(counts[0])))
report=dict(result='passed' if all(r['exit_code']==0 for r in records) else 'failed',
            tests=sum(r['tests'] for r in records),records=records,
            limits=['Host source and guard checks only; installed native uninstall/fault/restore still required.'])
(out/'source-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report));raise SystemExit(report['result']!='passed')
