"""Expand recognized nested ZIP/TAR/gzip containers without executing/extracting."""
import base64,gzip,hashlib,io,json,sys,tarfile,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-privacy-01';KIT=ROOT/'.local/releases/r1-0.1.23'
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
def load(p):return json.loads(p.read_bytes())
assert load(OUT/'kit-expanded-privacy.json')['source_commit']==load(KIT/'kit-inventory.json')['source_commit']
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
prior=load(PRIVATE/'content-results.json');seen={};archives={};inventory=[];findings=[];started=time.monotonic();last=started
def scan(raw,label):
 sha=hashlib.sha256(raw).hexdigest()
 if sha in seen:mode='same_nested_content_reused'
 elif sha in prior:mode='main_current_content_proof_reused'
 else:
  mode='full_generic_133_values';hits=scanner.inspect_bytes(raw,label)
  for hit in hits:hit['file_sha256']=sha;findings.append(hit)
  if hits:
   target=PRIVATE/'finding-bytes'/sha
   if not target.exists():target.write_bytes(raw)
 seen.setdefault(sha,mode);inventory.append(dict(location=label,sha256=sha,bytes=len(raw),mode=mode))
def walk(raw,label,depth=0):
 global last
 assert depth<=8,'Inspect actual nested-depth limit rather than skip content'
 sha=hashlib.sha256(raw).hexdigest()
 if sha in archives:return
 if zipfile.is_zipfile(io.BytesIO(raw)):
  archives[sha]=dict(location=label,format='ZIP',depth=depth)
  with zipfile.ZipFile(io.BytesIO(raw)) as archive:
   # The verified complete Community Git source expands to1.19GB. Only that
   # exact root component gets a2GiB budget; other ZIPs retain1GiB.
   limit=2*1024**3 if depth==0 and label=='nested/source.zip' and sha==manifest['files']['source.zip']['sha256'] else 1024**3
   assert len(archive.infolist())<=100000 and sum(r.file_size for r in archive.infolist())<=limit
   for row in archive.infolist():
    if row.is_dir():continue
    assert not row.flag_bits&1,'Encrypted archive requires explicit review'
    data=archive.read(row);child=label+'/'+row.filename
    if depth>=1:scan(data,child)
    walk(data,child,depth+1)
 elif raw.startswith(b'\x1f\x8b'):
  with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:data=stream.read(1024**3+1)
  assert len(data)<=1024**3
  try:archive=tarfile.open(fileobj=io.BytesIO(data),mode='r:')
  except tarfile.ReadError:
   archives[sha]=dict(location=label,format='gzip',depth=depth);scan(data,label+'/gzip-content');walk(data,label+'/gzip-content',depth+1)
  else:tar_walk(archive,sha,label,depth)
 elif len(raw)>=512 and raw[257:262]==b'ustar':
  tar_walk(tarfile.open(fileobj=io.BytesIO(raw),mode='r:'),sha,label,depth)
 if time.monotonic()-last>25:print(json.dumps(dict(phase='nested_containers',containers=len(archives),members=len(inventory),findings=len(findings))),flush=True);last=time.monotonic()
def tar_walk(archive,sha,label,depth):
 archives[sha]=dict(location=label,format='TAR',depth=depth)
 with archive:
  for row in archive:
   if row.isfile():
    assert row.size<=1024**3;data=archive.extractfile(row).read();child=label+'/'+row.name
    if depth>=1:scan(data,child)
    walk(data,child,depth+1)
   elif (row.issym() or row.islnk()) and depth>=1:scan(row.linkname.encode(),label+'/link-target/'+row.name)
manifest=load(KIT/'kit-inventory.json')
for name in manifest['files']:
 if name.endswith(('.zip','.tar','.tar.gz','.whl','.mplug')):walk((KIT/name).read_bytes(),'nested/'+name)
 if name in ['images.tar','source.zip','toolchain/python-windows.tar.gz','toolchain/node-windows.zip']:
  (PRIVATE/'nested-progress02.json').write_text(json.dumps(dict(completed_through=name,archives=archives,seen=seen,inventory=inventory,findings=findings),indent=2)+'\n',encoding='utf8')
with (PRIVATE/'nested-inventory.json').open('x',encoding='utf8') as stream:json.dump(inventory,stream,indent=2);stream.write('\n')
report=dict(result='nested_members_scanned_triage_required' if findings else 'passed_recognized_nested_archive_members',utc=datetime.now(timezone.utc).isoformat(),source_commit=manifest['source_commit'],containers=list(archives.values()),expanded_member_instances=len(inventory),unique_contents=len(seen),new_full_scanned_contents=sum(v=='full_generic_133_values' for v in seen.values()),known_values=len(values),findings=findings,inventory_sha256=hashlib.sha256((PRIVATE/'nested-inventory.json').read_bytes()).hexdigest(),elapsed_seconds=round(time.monotonic()-started,3),limits=['Recognized ZIP containers include wheels and Office ZIP formats regardless of suffix; TAR and gzip are recursively expanded. No archive entry is extracted to a filesystem path or executed.','Main current proof reuse is exact SHA256 and needs its final static triage plus the older-image two-value extension.','Depth8/100000ZIPentries/1GiBcontainer-or-member limits fail rather than silently exclude; exact checksum-bound root Community source ZIP has reviewed2GiB budget for actual1.19GB footprint. This is not a universal decoder of encrypted/media/other container formats.'])
with (OUT/'kit-nested-privacy.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],containers=len(archives),members=len(inventory),new_contents=report['new_full_scanned_contents'],findings=len(findings))))
