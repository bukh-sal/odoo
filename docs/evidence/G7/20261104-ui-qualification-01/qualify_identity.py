"""Qualify actual current ID08 and native form network subresults."""
import base64,hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-ui-qualification-01';RUN=PRIVATE/'identity02'
def load(p):return json.loads(p.read_bytes())
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
record=load(PRIVATE/'browser-input.json');before=load(PRIVATE/'tables-before.json');result=load(RUN/'identity-result.json');process=load(RUN/'process-identity.json')
assert result['image']==record['image_id'] and result['generation']==4 and result['same_authenticated_Alice_session'] and result['A_administrator_B_viewer']
assert all(result['initial_native_lists'].values()) and all(result['after_actual_late_response'].values()) and result['actual_backend_response_held_status']==200
assert result['late_request_cancellation_observed'] and result['late_response_release']=='already_canceled_by_disposal'
assert result['native_forms']['A']['editable'] and not result['native_forms']['B']['editable']
assert not result['app_foreign_requests'] and not result['foreign_websockets'] and result['runtime_exception_count']==0 and result['positive_foreign_control_observed']
assert process['state']=='stopped' and process['exit']==dict(code=0,signal=None)
command="$mpOwned="+"'"+record['profile'].replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
assert call(['powershell','-NoProfile','-Command',command]).strip() in (b'',b'[]',b'null')
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
after=json.loads(call(['docker','exec',record['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database'],'-c',query]));assert before==after
old=load(PRIVATE/'runtimes-before.json');actual=json.loads(call(['docker','inspect',*[r['Id'] for r in old]]))
for a,b in zip(old,actual):
 assert b['State']['Running'] and a['Id']==b['Id'] and a['Image']==b['Image'] and a['State']['StartedAt']==b['State']['StartedAt'] and a['Mounts']==b['Mounts'] and a['NetworkSettings']==b['NetworkSettings']
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
publish=['identity-result.json','identity-network.json','identity-tab-A-list.png','identity-tab-B-list.png','identity-tab-A-form.png','identity-tab-B-form.png']
paths=[RUN/name for name in publish]+[p for p in OUT.iterdir() if p.is_file() and (p.name.startswith('identity') or p.name=='qualify_identity.py')]+[RUN/'edge-identity.log',RUN/'process-identity.json',PRIVATE/'identity-failure.json',PRIVATE/'edge-identity.log',PRIVATE/'process-identity.json']
findings=[f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings
for name in publish:shutil.copyfile(RUN/name,OUT/name)
qualification=dict(result='passed_current_ID08_native_two_tab_workspace_role_cache_and_late_response_isolation',utc=datetime.now(timezone.utc).isoformat(),acceptance=['ID-08'],image=record['image_id'],inventory=record['inventory_digest'],generation=4,same_actor_tabs_A_administrator_B_viewer=True,native_lists_and_forms_default=True,actual_late_backend_reply_canceled_by_disposal_no_cross_tab_contamination=True,all17_business_authority_job_event_tables_exact=True,all4_runtime_process_image_mount_network_identities_exact=True,owned_browser_exit0_no_profile_process_remaining=True,app_foreign_requests=0,foreign_websockets=0,runtime_exceptions=0,positive_foreign_control_observed=True,privacy=dict(known_values=len(values),files=len(paths),findings=0,controlled_fixture_screenshots_visually_reviewed=True),new_profiles_or_Docker_assets=0,evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/name for name in publish]+[OUT/'identity.mjs',OUT/'identity02.mjs',OUT/'identity-attempt01.json']},limits=['Actual HTTP200 native read response was held and canceled on route disposal; its body was not inspected or replaced. Separate actual native lists/forms prove successful own-workspace reads and role separation.','Initial harness timeout/hidden-tab screenshot preserved. Corrected run foregrounds tabs and releases after actual route selection, then checks native lists/forms.','No Note/board/Labels edit. UI09 and full native Labels/RTL/release closure remain required.','Protected profile/session and whole-table snapshots remain private; finite byte scanner plus visual screenshot review is not a universal secret detector.'])
with (OUT/'identity-qualification.json').open('x',encoding='utf8') as f:json.dump(qualification,f,indent=2);f.write('\n')
print(json.dumps(dict(result=qualification['result'],acceptance='ID-08',tables_exact=17,runtimes_exact=4,privacy_findings=0)))
