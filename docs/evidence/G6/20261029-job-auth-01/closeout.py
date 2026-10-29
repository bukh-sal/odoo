"""Check updated ledger/docs/source/privacy before the local checkpoint."""
import base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_job_fixture as j
j.select_profile('runner');f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state)
from modular_platform.native_executor import NativeExecutor
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.operator_store import OperatorStore
from modular import configuration
from secret_scan import Scanner
proof=f.load(OUT/'qualification.json');assert proof['result']=='passed'
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in proof['source_sha256'].items())
status=(ROOT/'docs/implementation-status.md').read_text();ledger=status.split('## Acceptance ledger\n')[1]
rows=[line.split('|') for line in ledger.splitlines() if line.startswith('| ') and len(line.split('|'))>5]
counts={key:sum(parts[3].strip()==key for parts in rows) for key in ['passed','not_run','excluded_R2','failed','invalidated']}
assert counts==dict(passed=88,not_run=11,excluded_R2=5,failed=0,invalidated=0),counts
assert hashlib.sha256((ROOT/'planning/modular_platform_spec.md').read_bytes()).hexdigest()=='c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201'
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==87
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in freeze['files'].items())
old=ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in f.load(old/'known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
 for p in folder.iterdir():
  if p.is_file() and (p.name.endswith('password') or p.name.endswith('secret') or p.name=='service-token'):
   value=p.read_bytes().strip()
   if len(value)>=16:values[folder.name+'/'+p.name]=value
 authority=RestoreExecutor(NativeExecutor(OperatorStore(folder/'operator/control'),folder/'operator/target.json',folder/'operator/catalog',configuration(folder/'operator/trust.json')))._authority(f.load(folder/'state.json')['active_db'])[1]
 for user in authority['users']:
  for field in ['password','totp_secret']:
   if user[field] and len(user[field])>=16:values[folder.name+'/native/'+str(user['id'])+'/'+field]=user[field].encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=[ROOT/n.decode() for n in names if n and (ROOT/n.decode()).is_file()]
findings=[finding for path in paths for finding in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())]
assert not findings,'Inspect redacted findings privately'
f.guard(state);record=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),acceptance_counts=counts,rough_gate_progress_percent=83,specification_unchanged=True,frozen_files=87,runtime_sources_match_qualification=True,protected_configurations=8,known_credential_sources=len(values),public_files_scanned=len(paths),credential_findings=0,goal='active; F-01b2 next, G6/G7 incomplete')
assert not (OUT/'closeout.json').exists();f.write(OUT/'closeout.json',record);print(json.dumps(record))
