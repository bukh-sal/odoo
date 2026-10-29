"""Close G5 only when its complete acceptance/exit map has current passing evidence."""
from datetime import datetime,timezone
import collections,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
status=(ROOT/'docs/implementation-status.md').read_text();ledger=status.split('## Acceptance ledger',1)[1]
rows=[]
for line in ledger.splitlines():
    if re.match(r'^\| [A-Z]+-\d+ \|',line):
        ident,phase,result,observation,evidence=[c.strip() for c in line.split('|')[1:-1]]
        rows.append(dict(id=ident,phase=phase,result=result,evidence=evidence))
g5=[r for r in rows if r['phase']=='E/G5'];assert len(g5)==45 and all(r['result']=='passed' for r in g5)
counts=collections.Counter(r['result'] for r in rows);assert counts==dict(passed=86,not_run=13,excluded_R2=5)
assert load(OUTPUT/'qualification.json')['result']=='passed'
clean=ROOT/'docs/evidence/G5/20261029-clean-recovery-01';assert load(clean/'qualification.json')['result']=='passed' and load(clean/'minimal-Canvas-fixture.json')['result']=='passed'
frozen=load(ROOT/'docs/contracts/freeze-v1.json');assert len(frozen['files'])==87 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['files'].items())
runtime=load(ROOT/'.local/g5-provenance/runtime-observation.json')
build=load(OUTPUT/'build-provenance.json')
for p,h in build['host_operator_source'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
assert '## G5 exit criteria: complete' in status and 'G5-X10 | Minimal Canvas reference setup | passed' in status
for field in ['native_auth_policy','native_auth_digest']:
    operation=load(ROOT/'.local/g5-clean-recovery/fault-operation.json')['operation_id'];assert field in load(ROOT/'.local/g5-clean-recovery/operator/control/recoveries'/operation/'result.json')
state=load(ROOT/'.local/g5-clean-recovery/state.json')
for path,h in state['protected_configurations'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
static=load(OUTPUT/'runtime-license-index.json')['container'];info=json.loads(subprocess.check_output(['docker','inspect',static]))[0];assert not info['State']['Running'] and info['State']['ExitCode']==0 and info['HostConfig']['LogConfig']['Type']=='none'
paths=[ROOT/'planning/modular_platform_spec.md',ROOT/'upstream.lock',ROOT/'deploy/host-toolchain.lock.json',ROOT/'docs/contracts/freeze-v1.json']
value=dict(gate='G5',result='passed',utc=datetime.now(timezone.utc).isoformat(),source_commit_before_provenance=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),source_binding='Unchanged b43f6e2f executable host/SDK source; exact runtime image/inventory, immutable prior integration evidence and new provenance source/lock hashes. Status/work-log/evidence bytes excluded from executable identity.',image_id=build['image_id'],inventory_digest=runtime['inventory_digest'],frozen_files=87,acceptance=g5,acceptance_passed=45,reference_fixture='X10 passed: clean-recovery-01/minimal-Canvas-fixture.json',exit_criteria={f'G5-X{n:02}':'passed' for n in range(1,11)},overall_R1_acceptance=dict(passed=86,not_run=13,excluded_R2=5),weighted_progress_percent=80,next_gate='G6',next_work_item='F-01 durable jobs/outbox/scoped external service',source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},qualification_records=['../20261029-clean-recovery-01/qualification.json','qualification.json','../20261029-operator-isolation-01/qualification.json','../20261029-approval-security-01/qualification.json','../20261029-dispatch-fence-01/qualification.json','../20261029-worker-fence-01/qualification.json'],limits=['This passes G5, not G7 or the R1 goal. G6 actual adapters must extend and requalify restored effects, worker compatibility and scoped identities.','G7 must run the complete current final-release acceptance and reproduce install/recovery/provenance/security/network/accessibility/performance.','Canvas remains minimal and standard CRUD remains native Odoo. No publication, production deployment or destruction of unknown data.'])
dest=OUTPUT/'gate-G5.json';assert not dest.exists();dest.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(dict(gate='G5',result='passed',acceptance='45/45',R1='86/99',progress_percent=80,next='G6')))
