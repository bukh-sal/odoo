"""Read-only CLI/source/evidence cross-check; never replay qualified failures."""
import hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-01'
def load(p):return json.loads(p.read_bytes())
python=ROOT/'.local/release-kit-rehearsal/operator/Scripts/python.exe'
source=ROOT/'.local/release-kit-rehearsal/source'
trust=ROOT/'.local/release-kit-rehearsal/private/reference/operator/trust.json'
commands=[['plugin',name] for name in ['validate','apply','stage-image','plan-staged','plan-external','recover']]
commands+=[['catalog',name] for name in ['add','quarantine']]
commands+=[['operations',name] for name in ['register','import-request','approve','show']]
commands+=[['worker',name] for name in ['prepare','publish','run-job-once']]
rows=[]
for i,args in enumerate(commands):
 stdout=PRIVATE/('runbook-help-'+str(i)+'.stdout');stderr=PRIVATE/('runbook-help-'+str(i)+'.stderr')
 if stdout.exists():
  # All fifteen commands already passed before the first evidence-path read
  # failed. Preserve/reuse those actual streams, not new command attempts.
  raw=stdout.read_bytes();assert b'usage:' in raw and stderr.read_bytes()==b''
 else:
  result=subprocess.run([str(python),'-I',str(source/'tools/modular.py'),'--config',str(trust),*args,'--help'],capture_output=True,timeout=20)
  for path,data in [(stdout,result.stdout),(stderr,result.stderr)]:
   with path.open('xb') as stream:stream.write(data)
  assert result.returncode==0 and b'usage:' in result.stdout;raw=result.stdout
 rows.append(dict(command=' '.join(args),exit_code=0,usage_sha256=hashlib.sha256(raw).hexdigest()))
cases=[
 ('Fresh deployment',['full-bootstrap-qualified.json','application-bootstrap.json','worker-integration.json']),
 ('Plugin install and permission approval',['worker-integration.json']),
 ('Schema upgrade',['../20261104-core23-maintenance-01/completed.json','../20261104-core23-maintenance-01/preservation.json','../20261104-core23-maintenance-01/http.json']),
 ('Failed startup',['../../G5/20261029-premutation-fault-01/resume-qualification.json']),
 ('Failed migration',['../20261104-native-uninstall-recovery-01/qualification.json']),
 ('Worker outage',['../../G6/20261102-headless-ui-01/qualification.json']),
 ('Expired/revoked credentials',['../20261104-native-uninstall-recovery-01/qualification.json','../20261103-worker-security-transition-01/qualification.json']),
 ('Backup and restoration',['../20261104-native-uninstall-recovery-01/qualification.json']),
 ('Compromised native plugin',['../20261104-operator-isolation-01/qualification.json']),
 ('Artifact/catalog trust failure',['../../G5/20261028T0508474407833Z/archive-catalog.json']),
 ('Upstream patch/security update',['../20261104-core23-repro-01/qualification.json']),
 ('Data export/destructive removal',['../20261104-native-uninstall-recovery-01/qualification.json'])]
ledger=(ROOT/'docs/implementation-status.md').read_text();evidence=[]
for number,(name,paths) in enumerate(cases,1):
 documents=[]
 for relative in paths:
  path=(OUT/relative).resolve();value=load(path)
  documents.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reported_result=value.get('result',value.get('state','structured_evidence'))))
 evidence.append(dict(number=number,case=name,retained_qualification=documents))
runbook=ROOT/'docs/operator-runbooks.md';text=runbook.read_text();assert len(re.findall(r'^## \d+\.',text,re.M))==12
for _,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',text):
 if '://' not in target:assert (runbook.parent/target.split('#')[0]).is_file()
report=dict(result='passed_runbook_CLI_link_and_retained_functional_evidence_crosscheck',utc=datetime.now(timezone.utc).isoformat(),runbook_sha256=hashlib.sha256(runbook.read_bytes()).hexdigest(),cli_help_checks=rows,cases=evidence,
 boundaries=['Help confirms command syntax, never runtime approval or recovery success. Actual fresh install/job/full bootstrap and retained failure/recovery evidence are separately hash-bound.',
 'Retained qualifications keep their original source/environment/profile limits; this cross-check does not rerun them or relabel historical evidence as a new fresh-realm fault.',
 'Compromise containment/data-exfiltration response and security update decisions are operator procedures; no malware exercise, generic external undo, scheduled backup command or production authorization is claimed.',
 'Full kit expanded privacy and final section28 operator/browser/performance review remain required.'])
with (OUT/'runbook-cross-check.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],cli_help_checks=len(rows),cases=len(evidence))))
