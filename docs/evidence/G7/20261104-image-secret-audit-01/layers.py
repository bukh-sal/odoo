"""Scan all regular layer members and image metadata; retain only finding bytes."""
import hashlib,json,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner,save_report
import base64
assert PRIVATE.is_dir() and not (PRIVATE/'images.tar').exists()
values={k:base64.b64decode(v) for k,v in json.loads((PRIVATE/'known-values.json').read_bytes()).items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
target=json.loads((ROOT/'.local/g7-fresh-release-01/target21/operator/target.json').read_bytes())
lock=json.loads((ROOT/'deploy/runtime.lock.json').read_bytes())
worker=json.loads((ROOT/'services/document_stats/image.lock.json').read_bytes())
images=sorted({target['image_id'],worker['image_id'],lock['postgres_image'],lock['reverse_proxy_image']})
assert len(images)==4 and target['generation']==5
archive=PRIVATE/'images.tar';cache=PRIVATE/'finding-files';cache.mkdir()
started=time.monotonic();print(json.dumps(dict(state='exporting_four_selected_release_images')),flush=True)
r=subprocess.run(['docker','image','save','--output',str(archive),*images],capture_output=True,timeout=600)
(PRIVATE/'save.stderr').write_bytes(r.stderr);assert r.returncode==0,'Inspect export process/file; no blind retry'
print(json.dumps(dict(state='export_complete_scanning',bytes=archive.stat().st_size)),flush=True)
temporary=PRIVATE/'current-member';inventory=[];findings=[];layers=[]
def scan(stream,size,location):
 assert size<=512*1024*1024,'Unexpected large member requires explicit review'
 digest=hashlib.sha256();remaining=size
 with temporary.open('xb') as output:
  while remaining:
   raw=stream.read(min(4*1024*1024,remaining));assert raw
   output.write(raw);digest.update(raw);remaining-=len(raw)
 row=dict(location=location,size=size,sha256=digest.hexdigest());inventory.append(row)
 hits=scanner.inspect_file(temporary,scanner.redact_location(location))
 if hits:
  destination=cache/row['sha256']
  if not destination.exists():temporary.replace(destination)
  else:temporary.unlink()
  findings.extend(dict(**hit,file_sha256=row['sha256']) for hit in hits)
 else:temporary.unlink()
with tarfile.open(archive,'r:*') as outer:
 for member in outer:
  if not member.isfile():continue
  stream=outer.extractfile(member);head=stream.read(512);stream.seek(0)
  layer=member.name.endswith('/layer.tar') or member.name.startswith('blobs/') and (head[:2]==b'\x1f\x8b' or head[257:262]==b'ustar')
  if layer:
   layers.append(member.name)
   with tarfile.open(fileobj=stream,mode='r|*') as inner:
    for entry in inner:
     if entry.isfile():scan(inner.extractfile(entry),entry.size,'image-layer/'+member.name+'/'+entry.name)
   print(json.dumps(dict(state='layer_scanned',layers=len(layers),files=len(inventory),findings=len(findings))),flush=True)
  else:scan(stream,member.size,'image-metadata/'+member.name)
(PRIVATE/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
result=dict(result='scanned_current_images_triage_required',images=images,known_values=len(values),unique_layers=len(layers),files=len(inventory),bytes=sum(r['size'] for r in inventory),export_bytes=archive.stat().st_size,elapsed_seconds=round(time.monotonic()-started,3),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,inventory_sha256=hashlib.sha256((PRIVATE/'inventory.json').read_bytes()).hexdigest(),limits=['Every exported regular file in every unique layer, including files hidden/deleted by later layers, plus image configuration/history metadata.','No extracted names become filesystem paths; one bounded temporary member is removed after scanning; only exact finding bytes are retained privately.','ZIP payloads, current logs, served browser assets and Git source/history require separate scans. No SEC03 pass until findings reviewed.'])
save_report(OUT/'image-layers.json',result)
print(json.dumps({k:result[k] for k in ['result','unique_layers','files','known_secret_findings','generic_findings','elapsed_seconds']}),flush=True)
