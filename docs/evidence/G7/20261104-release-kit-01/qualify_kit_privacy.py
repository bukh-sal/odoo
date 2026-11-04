"""Reconcile exact prior proofs, current findings, nested contents and source tree."""
import collections,hashlib,json,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-privacy-01';KIT=ROOT/'.local/releases/r1-0.1.23'
sys.path[:0]=[str(ROOT/'release')];from verify import verify
def load(p):return json.loads(p.read_bytes())
manifest=verify(KIT);main=load(OUT/'kit-expanded-privacy.json');nested=load(OUT/'kit-nested-privacy.json');triage=load(OUT/'kit-static-triage.json');extension=load(OUT/'legacy-image-value-extension.json')
assert main['source_commit']==nested['source_commit']==manifest['source_commit']
assert main['kit_manifest_sha256']==hashlib.sha256((KIT/'kit-inventory.json').read_bytes()).hexdigest()
inventory=load(PRIVATE/'inventory.json');nested_inventory=load(PRIVATE/'nested-inventory.json')
assert hashlib.sha256((PRIVATE/'inventory.json').read_bytes()).hexdigest()==main['inventory_sha256']
assert hashlib.sha256((PRIVATE/'nested-inventory.json').read_bytes()).hexdigest()==nested['inventory_sha256']
assert len(inventory)==main['expanded_members'] and len(nested_inventory)==nested['expanded_member_instances']
assert not nested['findings'] and not extension['findings'] and triage['known_generated_findings']==0 and triage['unreviewed_findings']==0
identity=lambda f:(f['location'],f['file_sha256'],f['offset'],f['rule'],f['fingerprint'])
assert {identity(f) for f in main['findings']}=={identity(f) for f in triage['reviewed']} and len(triage['reviewed'])==8
hashsets=[]
for row in extension['inventories_hash_bound']:
 path=ROOT/row['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']==load(ROOT/row['proof'])['inventory_sha256'];hashsets.append({r['sha256'] for r in load(path)})
legacy=hashsets[0]-hashsets[1];actual_hashes={r['sha256'] for r in inventory}
legacy_reused=legacy&actual_hashes
assert legacy_reused<=set(extension['checked_sha256']),'A121-value-only reused content lacks its two-value extension'
# The collector's legacy-mode label123 is supported here by either the actual
# core23 proof or this explicit121-to123 extension, then its actual new10 scan.
old_history=load(ROOT/'.local/g7-release-privacy-delta-01/history-inventory.json')
expected=collections.Counter((r['path'],r['sha256'],r['size']) for r in old_history['delta']+old_history['prior_implementation_new_value_check'])
actual=collections.Counter((r['location'].removeprefix('git-history-prior/'),r['sha256'],r['bytes']) for r in inventory if r['location'].startswith('git-history-prior/'))
assert actual==expected and sum(actual.values())==6288
tree={}
for row in subprocess.check_output(['git','ls-tree','-rz','--full-tree',manifest['source_commit']]).split(b'\0'):
 if row:
  meta,name=row.split(b'\t',1);mode,kind,oid=meta.decode().split();assert kind=='blob' and mode in ['100644','100755'];tree[name.decode()]=oid
observed=set()
with zipfile.ZipFile(KIT/'source.zip') as archive:
 assert archive.comment.decode()==manifest['source_commit']
 for row in archive.infolist():
  if row.is_dir():continue
  raw=archive.read(row);oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  assert oid==tree[row.filename];observed.add(row.filename)
assert observed==set(tree)
main_hashes=set(load(PRIVATE/'content-results.json'));nested_hashes={r['sha256'] for r in nested_inventory};new_nested=nested_hashes-main_hashes
fully_scanned={r['sha256'] for r in nested_inventory if r['mode']=='full_generic_133_values'};assert new_nested<=fully_scanned
proofs=['kit-expanded-privacy.json','kit-nested-privacy.json','kit-static-triage.json','legacy-image-value-extension.json','full-bootstrap-qualified.json','application-bootstrap.json','worker-integration.json','runbook-cross-check.json','image-transport-load.json']
report=dict(result='passed_current_local_kit_privacy_source_identity_and_installation_binding',utc=datetime.now(timezone.utc).isoformat(),source_commit=manifest['source_commit'],kit_manifest_sha256=main['kit_manifest_sha256'],kit_components=len(manifest['files']),known_values=133,
 main_member_history_instances=len(inventory),nested_member_instances=len(nested_inventory),main_unique_contents=len(main_hashes),new_unique_nested_contents=len(new_nested),combined_unique_contents=len(main_hashes|nested_hashes),source_files_exact_to_Git=len(tree),prior_implementation_history_blobs_new10_checked=6288,
 older_image_contents_with_two_additional_values_checked=len(extension['checked_sha256']),actual_reused_older_image_hashes_covered=len(legacy_reused),known_generated_findings=0,reviewed_exact_static_findings=8,unreviewed_findings=0,
 proof_sha256={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in proofs},
 qualified_scope=['Actual kit50components/expandedZIP,TAR,gzip members, allOCI layers/config/history, source/current+priorimplementationGit history and nested recognized containers; no archive execution or selected-path extraction.',
 'Exact private inventory hashes match committed prior image proofs. Its121-value-only hashes are explicitly extended for two values, then the main audit supplies the ten later values. Prior source123 proof reused only by Git blob identity.',
 'All eight generic matches are exact upstream documentation examples/compiled-source equivalents; no detector rule or vendor document was removed. Nested new-content count is derived from actual hash sets, not the collector mutable mode summary.',
 'Actual fresh native/reference/worker original-actor job, corrected empty-workdir offline bootstrap and twelve-case CLI/evidence runbook cross-check are separately bound.'],
 limits=['Finite detector/encoding/archive-format scope; no universal secret/vulnerability guarantee, arbitrary encrypted/media decoding or hostile-native sandbox.',
 'Pinned upstream ancestry outside original implementation-history scope remains excluded. Authenticated dynamic session transport and actual private site/configuration/control/issuer stores remain private, outside this public-input artifact.',
 'Kit remains draft pending browser network/identity/accessibility/performance and final G7/section28 handoff. No production/commercial distribution or blank-second-Docker-daemon qualification.'])
with (OUT/'kit-qualified.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps({k:report[k] for k in ['result','source_files_exact_to_Git','combined_unique_contents','new_unique_nested_contents','actual_reused_older_image_hashes_covered','reviewed_exact_static_findings','known_generated_findings']}))
