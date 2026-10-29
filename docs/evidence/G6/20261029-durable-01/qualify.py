"""Qualify F-01a primitives, explicitly short of complete JOB/EVT/SVC acceptance."""
from datetime import datetime,timezone
import base64,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from g6_fixture import LOCAL,load,save,guard
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.restore_executor import RestoreExecutor
from modular import configuration
from secret_scan import Scanner

state=load(LOCAL/'state.json');guard(state);assert state['phase']=='durable_primitives_verified'
probe=load(OUTPUT/'primitive-backend-01.json');audit=load(OUTPUT/'primitive-audit.json')
assert probe['result']==audit['result']=='passed' and probe['tests']==15 and not probe['failures'] and not probe['errors'] and probe['skipped']==0
assert load(OUTPUT/'private-model-HTTP-denials.json')['result']=='passed' and len(load(OUTPUT/'private-model-HTTP-denials.json')['cases'])==12
assert load(OUTPUT/'protected-audit.json')['result']=='passed'
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in audit['source_sha256'].items())
target=load(LOCAL/'operator/target.json');reader=DockerObserver(target)
child=json.loads(subprocess.check_output(['docker','inspect',probe['container']]))[0]
assert not child['State']['Running'] and child['State']['ExitCode']==0 and child['HostConfig']['LogConfig']['Type']=='none'
freeze=load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==87 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
old=ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in load(old/'known-values.json').items()}
for folder in [LOCAL,ROOT/'.local/g5-clean-recovery']:
    for p in folder.iterdir():
        if p.is_file() and (p.name.endswith('password') or p.name.endswith('secret') or p.name=='service-token'):
            value=p.read_bytes().strip()
            if len(value)>=16:values[folder.name+'/'+p.name]=value
private=RestoreExecutor(NativeExecutor(OperatorStore(LOCAL/'operator/control'),LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json')))._authority(state['active_db'])[1]
for user in private['users']:
    for field in ['password','totp_secret']:
        if user[field] and len(user[field])>=16:values['g6/native/'+str(user['id'])+'/'+field]=user[field].encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=[ROOT/n.decode() for n in names if n and (ROOT/n.decode()).is_file()]
findings=[f for p in paths for f in scanner.inspect_file(p,p.relative_to(ROOT).as_posix())]
logs=[p for p in (LOCAL/'logs').iterdir() if p.is_file()]
findings += [f for p in logs for f in scanner.inspect_file(p,'private-diagnostic/'+p.name)]
assert not findings,'Inspect redacted findings privately; no raw match output'
paths += [ROOT/'docs/architecture-decisions/0029-durable-jobs-and-outbox.md',ROOT/'tools/build_candidate.py',ROOT/'tools/g6_fixture.py',ROOT/'tools/g6_primitive_probe.py']
value=dict(result='passed',work_item='F-01a',utc=datetime.now(timezone.utc).isoformat(),source_commit_before_change=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],database=state['active_db'],core_native_version='19.0.0.1.7',real_native_PostgreSQL_tests=11,Linux_input_validation_tests=4,Windows_input_validation_tests=4,HTTP_native_CRUD_denials=12,frozen_files=87,six_G5_configurations_exact=True,four_G5_deployments_and_HTTP_fixture_audited=True,clean_G5_business_schema_exact=True,current_dispatch='paused generation4;9synthetic jobs/1outbox/11synthetic Notes retained',source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.relative_to(ROOT).parts[0] not in ['docs'] or p.suffix=='.py'},public_files_scanned=len(paths)-4,private_diagnostic_files=len(logs),known_credential_sources=len(values),credential_findings=0,checks=['primitive-backend-01.json','primitive-audit.json','private-model-HTTP-denials.json','protected-audit.json','core-provision-attempt.json'],limits=['This qualifies native durable primitives, not the complete JOB/EVT/SVC acceptance. Those11 G6 checks remain not_run until real authorized dispatch/subscriptions/worker/lifecycle/recovery are integrated.','Native handlers in this proof use real ordinary backing-user Notes CRUD. The production job registry/actor+grant reauthorization and event delivery are F-01b.','Lease expiry/reclaim and two real concurrent connections are exercised; no OS-worker-kill or external-service outage claim.','G5 restore still rejects job/outbox tables. Implement and qualify G6 drain/effect/credential reconciliation before representing this G6 environment as recoverable through that profile.','Only this suite\'s unfinished synthetic rows are held. All rows/business effects/uncertainty remain; no unknown data deletion or setup/native migration replay.','The initial seed database-prefix refusal committed no fixture data; zero-row reconciliation and separate provisioning-only continuation retained.'])
save('qualification.json',value);print(json.dumps(dict(result='passed',work_item='F-01a',PG_native=11,Linux_validation=4,Windows_validation=4,HTTP_denials=12,new_acceptance_passes=0)))
