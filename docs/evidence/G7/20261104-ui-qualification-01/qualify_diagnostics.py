"""Bind actual UI09 findings/preservation; never turn source edits into a UI pass."""
import base64,hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-ui-qualification-01'
def load(p):return json.loads(p.read_bytes())
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
record=load(PRIVATE/'browser-input.json');before=load(PRIVATE/'tables-before.json');runs=[PRIVATE/('ui09-0'+str(n)) for n in [1,2,3]]
first,second,third=[load(p/'observations.json') for p in runs]
assert len(first['observations'])==11 and len(second['observations'])==5 and third['appearance_restored']
assert all(not row['background_button_focused'] for row in third['background_focus_attempts'])
assert not any(run['foreign_requests'] for run in [first,second,third]) and not any(run['runtime_exceptions'] for run in [first,second,third])
for p in runs:
 process=load(p/'process.json');assert process['state']=='stopped' and process['exit']==dict(code=0,signal=None)
command="$mpOwned="+"'"+record['profile'].replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
assert call(['powershell','-NoProfile','-Command',command]).strip() in (b'',b'[]',b'null')
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
after=json.loads(call(['docker','exec',record['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database'],'-c',query]));assert before==after
old=load(PRIVATE/'runtimes-before.json');actual=json.loads(call(['docker','inspect',*[r['Id'] for r in old]]))
for a,b in zip(old,actual):assert b['State']['Running'] and a['Id']==b['Id'] and a['Image']==b['Image'] and a['State']['StartedAt']==b['State']['StartedAt'] and a['Mounts']==b['Mounts'] and a['NetworkSettings']==b['NetworkSettings']
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
sources=[OUT/name for name in ['accessibility01.mjs','accessibility02.mjs','accessibility03.mjs','browser_runtime.mjs','browser_runtime02.mjs','source24_checks.py','source24-checks.json','qualify_diagnostics.py']]
sources+=[ROOT/p for p in load(OUT/'source24-checks.json')['source_sha256']]+[ROOT/'docs/architecture-decisions/0057-shell-accessibility-correction.md']
streams=[p for folder in [*runs,PRIVATE/'source24-checks'] for p in folder.iterdir() if p.is_file() and p.suffix in ['.json','.png','.log','.stdout','.stderr']]
findings=[f for p in sources+streams for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings,'Privacy findings require review'
# Publish a reduced focus description rather than BODY.innerText from a helper.
redacted=[]
def sanitize(value,location=''):
 if isinstance(value,dict):
  result={k:sanitize(v,location+'/'+k) for k,v in value.items()}
  if result.get('tag')=='BODY' and 'name' in result:result['name']='(document body; no app control focused)';redacted.append(location+'/name')
  return result
 if isinstance(value,list):return [sanitize(v,location+'/'+str(i)) for i,v in enumerate(value)]
 return value
published=[];raw_bindings={}
for run in runs:
 destination=OUT/run.name;destination.mkdir(exist_ok=False)
 for name in ['observations.json','network.json']:
  src=run/name;value=sanitize(load(src),run.name+'/'+name);(destination/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');published.append(destination/name);raw_bindings[str(src.relative_to(ROOT))]=hashlib.sha256(src.read_bytes()).hexdigest()
for run,name in [(runs[0],'Arabic-settings.png'),(runs[0],'theme-light-native.png'),(runs[0],'theme-dark-native.png'),(runs[0],'narrow-settings.png'),(runs[0],'two_hundred_percent_equivalent-settings.png'),(runs[1],'Labels-keyboard.png'),(runs[1],'Odoo-confirm-keyboard.png'),(runs[1],'Canvas-keyboard.png'),(runs[2],'dark-labels.png'),(runs[2],'dark-Odoo-confirm.png')]:
 destination=OUT/run.name/name;shutil.copyfile(run/name,destination);published.append(destination)
assert not [f for p in published for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))]
report=dict(result='verified_UI09_diagnostics_with_required_defects_not_pass',utc=datetime.now(timezone.utc).isoformat(),acceptance='UI-09',acceptance_result='failed',image=record['image_id'],inventory=record['inventory_digest'],generation=4,required_defects=[dict(id='UI09-C01',behavior='Light subtitle4.38contrast below4.5normal text'),dict(id='UI09-C02',behavior='Dark Members h3 and native confirmation h4 inherit black on dark surface'),dict(id='UI09-L01',behavior='HTML language unset for English/Arabic shell; Arabic Settings labels/help remain English'),dict(id='UI09-F01',behavior='Native text fields/Labels textarea have no explicit shell focus outline; native close glyph obscured by generic background shorthand')],resolved_harness_observations=['Enter character event was missing; actual corrected keyboard Labels and Odoo confirmation open/Escape/restore checks completed.','Canvas reload requires explicit Unsaved board confirmation. Corrected keyboard lane change, local84character mixed input and two discarded reloads completed; no Save.','Native main is main.o_content; command search is its input combobox with accessible name Commands.','Native HTML dialog may report BODY between controls; attempted focus of inert background app button fails. UA modal boundary and Escape/initiator restore retained; no replacement trap.'],remaining_scope=['Normal immutable core24/Shell11 candidate/admission/independent review/upgrade and actual installed UI09 requalification.','Contrast all headings/dialogs, field focus, native close image, document/Settings language/RTL/narrow/equivalent200%reflow after correction.','Reconcile physical browser-chrome zoom/screen-reader scope and standard SDK locale-formatting evidence rather than claiming them from emulation alone.','Canvas move loses local selection focus but keyboard move/reload work; final scope review must distinguish required behavior from optional reference polish.','Final source-kit/privacy/release/section28 handoff.'],all17_business_authority_job_event_tables_exact=True,all4_runtime_process_image_mount_network_identities_exact=True,three_owned_browsers_exited0_no_profile_process_remaining=True,no_business_Save_Delete_Labels_submission=True,new_profiles_or_Docker_assets=0,privacy=dict(known_values=len(values),files=len(sources+streams),findings=0,controlled_fixture_screenshots_visually_reviewed=True,redacted_BODY_focus_descriptions=redacted),private_actual_response_sha256=raw_bindings,evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in published+sources},limits=['Failed/current14de observations; source24 fixes have only host checks, no installed candidate/runtime pass.','Finite read-only DOM/AX/style/keyboard/network observations and visual review, not a full WCAG compliance certification.','Raw session/profile, whole-table preservation snapshots and actual controlled-fixture helper streams stay private. Public BODY focus text reduced; no authentication headers/bodies/cookies captured.'])
with (OUT/'ui09-diagnostics.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],acceptance_result='failed',required_defect_groups=len(report['required_defects']),tables_exact=17,runtimes_exact=4,privacy_findings=0)))
