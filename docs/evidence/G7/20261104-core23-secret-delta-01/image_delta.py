"""Inspect every current app layer; reuse only previously audited identical bytes."""
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core23-secret-delta-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner
prior_dir=ROOT/'docs/evidence/G7/20261104-image-secret-audit-01'
prior=json.loads((prior_dir/'image-layers.json').read_bytes())
prior_inventory_path=ROOT/'.local/g7-image-secret-audit-01/inventory.json'
assert hashlib.sha256(prior_inventory_path.read_bytes()).hexdigest()==prior['inventory_sha256']
old_inventory=json.loads(prior_inventory_path.read_bytes());known_hashes={r['sha256'] for r in old_inventory}
assert json.loads((prior_dir/'qualification.json').read_bytes())['unreviewed_findings']==0
old_values={k:base64.b64decode(v) for k,v in json.loads((ROOT/'.local/g7-image-secret-audit-01/known-values.json').read_bytes()).items()}
values={k:base64.b64decode(v) for k,v in json.loads((PRIVATE/'known-values.json').read_bytes()).items()}
assert len(old_values)==121 and len(values)==123
assert set(old_values.values())<=set(values.values())
added_values=set(values.values())-set(old_values.values())
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
image='sha256:14de369e46f20616e76847cbcacbcb66d5bb791808b950aaf97bc607d31d6b93'
meta=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]
base='sha256:ae8bb33d618305d2d2b000e94e98bf9180e7e8c550e566d0dce0f5c97a2dd73a'
base_meta=json.loads(subprocess.check_output(['docker','image','inspect',base]))[0]
assert base in prior['images']
assert meta['RootFS']['Layers'][:len(base_meta['RootFS']['Layers'])]==base_meta['RootFS']['Layers']
archive=PRIVATE/'application-image.tar';assert not archive.exists()
started=time.monotonic()
print(json.dumps(dict(state='exporting_current_app_no_new_image_or_container')),flush=True)
r=subprocess.run(['docker','image','save','--output',str(archive),image],capture_output=True,timeout=180)
(PRIVATE/'save.stderr').write_bytes(r.stderr);assert r.returncode==0
rows=[];findings=[];layers=[];reused=0;fresh=0;additional_hits=0
cache=PRIVATE/'finding-files';cache.mkdir()
def scan(stream,size,location):
 global reused,fresh,additional_hits
 assert size<=512*1024*1024
 raw=stream.read(size);assert len(raw)==size
 digest=hashlib.sha256(raw).hexdigest()
 row=dict(location=location,size=size,sha256=digest,reused_prior_generic_scan=digest in known_hashes)
 rows.append(row)
 # Even byte-identical members are checked against every newly generated value.
 if any(secret in raw for secret in added_values):additional_hits+=1
 if digest in known_hashes:reused+=1;return
 fresh+=1
 hits=scanner.inspect_bytes(raw,location)
 if hits:
  target=cache/digest
  if not target.exists():target.write_bytes(raw)
  findings.extend(dict(hit,file_sha256=digest) for hit in hits)
with tarfile.open(archive,'r:*') as outer:
 for member in outer:
  if not member.isfile():continue
  stream=outer.extractfile(member);head=stream.read(512);stream.seek(0)
  is_layer=member.name.endswith('/layer.tar') or member.name.startswith('blobs/') and (head[:2]==b'\x1f\x8b' or head[257:262]==b'ustar')
  if is_layer:
   layers.append(member.name)
   with tarfile.open(fileobj=stream,mode='r|*') as inner:
    for entry in inner:
     if entry.isfile():scan(inner.extractfile(entry),entry.size,'image-layer/'+member.name+'/'+entry.name)
   print(json.dumps(dict(state='layer_complete',layers=len(layers),members=len(rows),fresh=fresh)),flush=True)
  else:scan(stream,member.size,'image-metadata/'+member.name)
(PRIVATE/'inventory.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
report=dict(result='current_app_layer_delta_scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),image=image,
 base_image=base,base_layers_identical=True,prior_qualification='../20261104-image-secret-audit-01/qualification.json',
 known_values=len(values),new_unique_values=len(added_values),layers=len(layers),regular_members=len(rows),
 bytes=sum(r['size'] for r in rows),reused_identical_member_scans=reused,new_byte_sequences_scanned=fresh,
 newly_generated_value_hits=additional_hits,findings=findings,export_bytes=archive.stat().st_size,
 inventory_sha256=hashlib.sha256((PRIVATE/'inventory.json').read_bytes()).hexdigest(),elapsed_seconds=round(time.monotonic()-started,3),
 limits=['Every current app exported regular member/history/config is hashed; prior generic/121-secret scan is reused only for byte-identical members with existing final triage. Two new secret values are checked against every member.',
 'Unchanged worker/PostgreSQL/proxy layers retain prior exact-image qualification. Git history/current diagnostics/archives/assets require separately scoped evidence.',
 'No image build, container, volume, network, running configuration or database mutation. Export is retained privately until result/any findings are reviewed.'])
with (OUT/'image-delta.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:report[k] for k in ['result','regular_members','new_byte_sequences_scanned','newly_generated_value_hits','elapsed_seconds']}),flush=True)
print(json.dumps(dict(generic_or_known_findings=len(findings))),flush=True)
