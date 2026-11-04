"""Extend the older 121-value image proof for its two subsequent values."""
import base64,hashlib,io,json,sys,tarfile,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner
def load(path):return json.loads(path.read_bytes())
inventories=[];bindings=[]
for directory,receipt in [('g7-image-secret-audit-01','image-layers.json'),('g7-core23-secret-delta-01','image-delta.json')]:
 path=ROOT/'.local'/directory/'inventory.json';sha=hashlib.sha256(path.read_bytes()).hexdigest();proof=ROOT/'docs/evidence/G7'/('20261104-'+directory.removeprefix('g7-'))/receipt
 assert sha==load(proof)['inventory_sha256'];inventories.append(load(path));bindings.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha,proof=proof.relative_to(ROOT).as_posix()))
core={r['sha256'] for r in inventories[1]};wanted={r['sha256'] for r in inventories[0] if r['sha256'] not in core}
current={k:base64.b64decode(v) for k,v in load(ROOT/'.local/g7-core23-secret-delta-01/known-values.json').items()}
old={base64.b64decode(v) for v in load(ROOT/'.local/g7-image-secret-audit-01/known-values.json').values()};added={k:v for k,v in current.items() if v not in old};assert len(added)==2
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),added);scanner.generic={};seen={};findings=[];started=time.monotonic();last=started
def check(raw,label):
 global last
 sha=hashlib.sha256(raw).hexdigest()
 if sha in wanted and sha not in seen:
  findings.extend(scanner.inspect_bytes(raw,label));seen[sha]=len(raw)
 if time.monotonic()-last>25:print(json.dumps(dict(phase='legacy_image_two_value_delta',unique_contents=len(seen),findings=len(findings))),flush=True);last=time.monotonic()
with tarfile.open(ROOT/'.local/releases/r1-0.1.23/images.tar') as outer:
 for member in outer:
  if not member.isfile():continue
  raw=outer.extractfile(member).read()
  if member.name.startswith('blobs/sha256/'):
   assert hashlib.sha256(raw).hexdigest()==member.name.rsplit('/',1)[1]
   try:layer=tarfile.open(fileobj=io.BytesIO(raw),mode='r:*')
   except tarfile.ReadError:check(raw,'image-metadata/'+member.name)
   else:
    with layer:
     for row in layer:
      if row.isfile():check(layer.extractfile(row).read(),'image-layer/'+member.name+'/'+row.name)
  else:check(raw,'image-transport/'+member.name)
report=dict(result='passed_legacy_image_121_to123_value_extension' if not findings else 'legacy_image_value_findings_require_review',utc=datetime.now(timezone.utc).isoformat(),inventories_hash_bound=bindings,new_values=2,encoded_variants=len(scanner.patterns),unique_contents=len(seen),bytes=sum(seen.values()),checked_sha256=sorted(seen),findings=findings,elapsed_seconds=round(time.monotonic()-started,3),limits=['Only actual current kit members whose generic/121-value proof predates the two core23 values and whose hashes are absent from the 123-value core23 proof. Main kit audit supplies ten later values and generic scan for new contents.','Final qualification must reconcile the scanned hash set against the actual main expanded-member inventory; no pathname-only coverage.'])
with (OUT/'legacy-image-value-extension.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],unique_contents=len(seen),findings=len(findings))))
