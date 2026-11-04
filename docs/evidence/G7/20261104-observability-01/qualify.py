"""Close the finite performance/diagnostic slice; keep release/UI gates separate."""
import base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-observability-02'
def load(p):return json.loads(p.read_bytes())
def write(name,value):
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.write('\n')
progress=load(OUT/'progress-qualification.json');review=load(OUT/'source-bound-review.json');ui=load(OUT.parent/'20261104-ui-qualification-01/performance-qualification.json');reads=load(OUT.parent/'20261104-performance-current-01/read-qualification.json')
assert progress['all_owned_processes_exited'] and progress['stale_detected_after_kill_seconds']<25 and progress['concurrent_process_refused']
assert len(review['current_live_source_sha256'])==21 and len(review['retained_G6_whole_file_exact'])==10
assert reads['image']==ui['image']==review['image'] and reads['total_errors']==0
for p,h in progress['source_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
result=subprocess.run([sys.executable,'-X','utf8','tools/check_contract_freeze.py'],capture_output=True,timeout=30)
(PRIVATE/'freeze.stdout').write_bytes(result.stdout);(PRIVATE/'freeze.stderr').write_bytes(result.stderr);assert result.returncode==0
freeze=json.loads(result.stdout);assert freeze['result']=='passed' and freeze['files']==106 and freeze['rows']==8
# Read-only final preservation around all diagnostics; no lifecycle replay.
record=load(ROOT/'.local/g7-ui-qualification-01/browser-input.json');before=load(ROOT/'.local/g7-ui-qualification-01/tables-before.json')
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
after=json.loads(subprocess.check_output(['docker','exec',record['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database'],'-c',query],stderr=subprocess.PIPE,timeout=30));assert before==after
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[p for p in OUT.iterdir() if p.is_file()]+[ROOT/p for p in progress['source_sha256']]+[ROOT/'docs/performance.md',ROOT/'docs/operator-runbooks.md',ROOT/'docs/architecture-decisions/0056-independent-executor-observation.md']
paths+=[p for directory in [PRIVATE,ROOT/'.local/g7-observability-01'] for p in directory.iterdir() if p.is_file() and p.suffix in ('.stdout','.stderr')]
findings=[f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings,'Privacy findings need review'
qualification=dict(result='passed_remaining_performance_and_operational_observation_slice',utc=datetime.now(timezone.utc).isoformat(),work_item='G-01c4',spec_sections=['24.1','24.2','24.3'],image=review['image'],native_Odoo_views_default=True,performance_points_total=2,additional_weighted_point=1,all17_current_business_authority_job_event_tables_exact=True,contract_freeze=freeze,actual_affected_unit_tests=19,privacy=dict(known_values=len(values),files=len(paths),findings=0),evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_relative_to(OUT) or p.suffix=='.md'},scope=['Current10k/20session reads, current shell timing/100disposal cycles, current source bounds and diagnostic equivalents combined.','Actual independent CLI observation/process-death qualification, source-bound G6 lease/worker failure/revocation proof and current native failure/fresh restore evidence.'],limits=['No full G7/ID08/UI09/OPS03 claim. Security/network/operator-source-kit closure and final audit remain.','Heartbeat is observation, not work advancement or rollback. Direct SDK callers and legacy operations have no new wrapper pulse.','Scheduler-dependent lease expiry, native code/OS/daemon limitations and R0 comparison limits remain explicit in source-bound-review.json/docs/performance.md.','No new Docker asset or product data mutation. First probe launcher-PID and second read-only JSON-field refusal preserved; no native/lifecycle replay.'])
write('qualification.json',qualification);print(json.dumps(dict(result=qualification['result'],weighted_point=1,tests=19,freeze_files=106,privacy_findings=0)))
