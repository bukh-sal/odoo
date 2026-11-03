"""Bind executed fixture/SDK bytes to the audited image and scan new diagnostics."""
import base64,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-request-faults-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner
def load(path):return json.loads(path.read_bytes())
report=load(OUT/'qualification.json');assert report['result']=='passed_current_API03_API05_request_outcomes'
inventory=load(ROOT/'.local/g7-image-secret-audit-01/inventory.json')
fixture='opt/modular/fixtures/v1/mp_r1_fault/controllers.py'
matches=[r for r in inventory if r['location'].endswith('/'+fixture)]
assert len(matches)==1 and matches[0]['sha256']==report['native_fault_source_sha256']
runtime=load(ROOT/'.local/g7-core22-provenance-01/runtime-observation.json')
assert runtime['inventory']['files']['addons/mp_shell/static/src/host.js']==report['SDK_source_sha256']
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/g7-image-secret-audit-01/known-values.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[p for p in PRIVATE.iterdir() if p.is_file() and p.suffix in ['.stdout','.stderr']]
paths.extend(p for p in (ROOT/'.local/g7-fresh-release-01/target21/logs').iterdir() if p.is_file() and p.name.startswith('request-fault-') and p.suffix in ['.stdout','.stderr'])
findings=[f for path in paths for f in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())]
assert not findings,'Inspect redacted findings, do not echo raw credentials'
state=load(PRIVATE/'state.json');assert state['state']=='backend_qualified_helpers_retired'
for name in [state['secondary'],state['edge']]:
 absent=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=20);assert absent.returncode and b'no such' in absent.stderr.lower()
record=dict(result='passed_executed_source_binding_and_new_diagnostic_secret_scan',image_id=report['image_id'],fault_source_matches_audited_physical_image_member=matches[0],SDK_source_matches_declared_immutable_image_inventory=True,private_log_files=len(paths),known_values=len(values),known_or_generic_findings=0,helpers_absent=True,normal_primary_fault_surface_absent=report['cleanup']['main_fault_environment_mount_absent'],limits=['Existing exact secret corpus plus structural rules on this new diagnostic scope; complete earlier SEC03 proof retained separately.','Fixture emits marker immediately before fixed os._exit(86); observed lost HTTP response and durable result replay qualify crash behavior. Worker exit-code constant is source-bound, not a separately captured process wait status.','No additional request, fixture replay, deployment or schema change.'])
with (OUT/'source-and-log-attestation.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],diagnostic_files=len(paths),known_or_generic_findings=0)))
