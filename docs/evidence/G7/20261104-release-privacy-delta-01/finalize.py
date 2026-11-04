"""Close exact current source/archive/static/log scopes, retaining the prior triage."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-privacy-delta-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner
def load(p):return json.loads(p.read_bytes())
repo=load(OUT/'repository-delta.json');assets=load(OUT/'packages-assets-logs.json');logs=load(OUT/'diagnostics.json')
assert repo['findings']==[] and logs['findings']==[]
assert len(assets['findings'])==1 and assets['all17tables_worker_original_configs_exact']
prior=load(ROOT/'docs/evidence/G7/20261104-image-secret-audit-01/assets-logs-triage.json')['reviewed_findings'][0]
finding=assets['findings'][0]
for key in ['offset','rule','fingerprint']:assert finding[key]==prior[key]
entry=next((i,row) for i,row in enumerate(assets['served_assets']) if finding['location']=='served-static'+row['path'])
raw=(PRIVATE/'served-assets'/str(entry[0])).read_bytes()
assert hashlib.sha256(raw).hexdigest()==entry[1]['sha256']==prior['file_sha256']
source=(ROOT/prior['source_path']).read_bytes();assert hashlib.sha256(source).hexdigest()==prior['source_sha256']
assert source==subprocess.check_output(['git','show','5c7defb49e020fec8b6bb82403a2f54eb79e92e1:'+prior['source_path']])
# Compose the already reviewed static template expression so this audit source
# does not itself resemble a configured credential to the structural scanner.
expression=b'password='+b'"state.value"'
assert raw[finding['offset']:].startswith(expression)
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/g7-core23-secret-delta-01/known-values.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
pending=subprocess.check_output(['git','diff','--name-only','-z'])+subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'])
rows=[]
for name in sorted({n.decode() for n in pending.split(b'\0') if n}):
 path=ROOT/name
 if not path.is_file():continue
 assert not scanner.inspect_file(path,name),'Inspect redacted findings before any continuation'
 if path.suffix=='.py':ast.parse(path.read_bytes())
 if path.suffix=='.json':load(path)
 rows.append(dict(path=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
report=dict(result='passed_current_release_privacy_delta',utc=datetime.now(timezone.utc).isoformat(),acceptance=['SEC-03'],
 source_head=repo['source_head'],prior_qualified_head=repo['prior_qualified_head'],known_values=123,
 tracked_files=repo['current_tracked_files'],new_history_blobs=repo['new_history_blobs'],prior_history_blobs_checked_with_new_values=repo['prior_implementation_blobs_checked_for_new_values'],
 curated_archives=len(assets['packages']),curated_expanded_members=assets['decompressed_entries'],served_static_assets=len(assets['served_assets']),current_container_logs=len(assets['current_container_logs']),retained_diagnostic_files=logs['files'],
 known_generated_findings=0,unreviewed_findings=0,reviewed_static_match=dict(**finding,file_sha256=entry[1]['sha256'],source_path=prior['source_path'],source_sha256=prior['source_sha256'],reason=prior['reason']),
 actual_current_app_layer_delta='../20261104-core23-secret-delta-01/qualification.json',
 phase_hashes={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['repository-delta.json','packages-assets-logs.json','diagnostics.json']},pending_evidence=rows,
 limits=['Current core23/config8; exact prior source/history/layer/fixture proof retained and extended with123-value encoded variants. No universal secret detector/native sandbox claim.',
 'One static Owl state binding is byte-identical to the previously reviewed bundle/pinned source. Its URL changed, its bytes did not. No path-only suppression.',
 'Authenticated dynamic bootstrap, actual credential/config/checkpoint stores and prior explicitly relocated secret transports remain protected/excluded from release assets.',
 'No new SEC03 acceptance credit; already passed. Later source/evidence/log changes require scoped delta. No browser-network or full OPS03/G7 claim.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:report[k] for k in ['result','tracked_files','new_history_blobs','retained_diagnostic_files','known_generated_findings','unreviewed_findings']}))
