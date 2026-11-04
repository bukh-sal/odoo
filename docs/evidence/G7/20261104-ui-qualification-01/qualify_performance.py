"""Read-only preservation and privacy qualification of the completed browser run."""
import base64,hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-ui-qualification-01'
def load(p):return json.loads(p.read_bytes())
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
def write(p,v):
 with p.open('x',encoding='utf8') as stream:json.dump(v,stream,indent=2);stream.write('\n')
record=load(PRIVATE/'browser-input.json');before=load(PRIVATE/'tables-before.json');result=load(PRIVATE/'performance-result.json');process=load(PRIVATE/'process.json')
assert process['state']=='stopped' and process['exit']==dict(code=0,signal=None)
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
after=json.loads(call(['docker','exec',record['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database'],'-c',query]));assert before==after
runtimes=load(PRIVATE/'runtimes-before.json');actual=json.loads(call(['docker','inspect',*[r['Id'] for r in runtimes]]))
for old,new in zip(runtimes,actual):
 assert new['State']['Running']
 for key in ['Id','Image','Mounts','NetworkSettings']:assert old[key]==new[key],key
 assert old['State']['StartedAt']==new['State']['StartedAt']
# Inspect only our exact owned profile's process identity; never stop personal Edge.
command="$mpOwned="+"'"+record['profile'].replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
owned=call(['powershell','-NoProfile','-Command',command]).strip();assert owned in (b'',b'[]',b'null'), 'Owned browser still running'
assert len(result['shellSamples'])==4 and all(s['under3000ms'] and s['login_to_interactive_Odoo_commands_ms']<3000 for s in result['shellSamples'])
assert result['cycles']==100 and result['warmup_cycles']==5 and all(result['memory_checks'].values())
assert result['runtime_exception_count']==0 and not result['app_foreign_requests'] and not result['foreign_websockets'] and result['outbound_control_observed_and_refused']
first,last=result['memorySamples'][0],result['memorySamples'][-1]
assert last['heap_used_bytes']-first['heap_used_bytes']==95568 and first['documents']==last['documents']==33 and first['nodes']==last['nodes']==2630 and first['jsEventListeners']==last['jsEventListeners']==151
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
publish=['performance-result.json','network-sanitized.json','browser-version.json','native-shell.png','after100-settings.png']
sources=list(OUT.glob('*.py'))+list(OUT.glob('*.mjs'))+[OUT/'prepared.json',ROOT/'docs/architecture-decisions/0055-headless-qualification-measurements.md']
paths=[PRIVATE/name for name in publish]+sources+[PRIVATE/'edge-performance.log',PRIVATE/'performance-progress.json',PRIVATE/'process.json']
findings=[f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings, 'Privacy findings require explicit review'
for name in publish:shutil.copyfile(PRIVATE/name,OUT/name)
qualification=dict(result='passed_current_shell_and100mount_dispose_targets',utc=datetime.now(timezone.utc).isoformat(),work_item='G-01c4',spec_sections=['24.1'],image=record['image_id'],inventory=record['inventory_digest'],generation=4,realm=record['base'],browser=load(PRIVATE/'browser-version.json'),shell_samples=result['shellSamples'],memory_samples=result['memorySamples'],retained_heap_growth_bytes=95568,all100Canvas_roots_disposed=True,all17_business_authority_job_event_tables_exact=True,all4_runtime_process_image_mount_network_identities_exact=True,owned_browser_stopped_exit0_no_profile_process_remaining=True,personal_browser_used=False,Docker_assets_added=0,privacy=dict(known_values=len(values),files=len(paths),findings=0),evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+[OUT/name for name in publish]},limits=['Subresults only: no additional performance point until R0/heartbeat/revocation/diagnostics/readiness mapping closes.','Network interception positive control passed and no app foreign requests observed during these paths; complete section27 classification is separate.','ID08 and UI09 were not exercised by this measurement.','Numeric post-GC metrics and reviewed screenshots only. Protected profile/session and whole-table snapshots remain private.','Finite local100cycle observation; no universal leak guarantee or WCAG/production claim.'])
write(OUT/'performance-qualification.json',qualification)
print(json.dumps(dict(result=qualification['result'],tables_exact=len(before),runtime_identities_exact=len(actual),heap_growth_bytes=95568,privacy_findings=0)))
