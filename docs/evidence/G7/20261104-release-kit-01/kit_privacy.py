"""Inspect actual kit/archive members; reuse prior privacy only by exact bytes."""
import base64,gzip,hashlib,io,json,re,subprocess,sys,tarfile,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-privacy-01';KIT=ROOT/'.local/releases/r1-0.1.23'
sys.dont_write_bytecode=True;sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from secret_scan import Scanner
from verify import verify
from modular_platform.operator_os import protect_directory
def load(p):return json.loads(p.read_bytes())
assert not PRIVATE.exists();protect_directory(PRIVATE);protect_directory(PRIVATE/'finding-bytes')
manifest=verify(KIT);head=manifest['source_commit'];base=load(ROOT/'docs/evidence/G7/20261104-release-privacy-delta-01/qualification.json')['source_head']
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()}
old={k:base64.b64decode(v) for k,v in load(ROOT/'.local/g7-core23-secret-delta-01/known-values.json').items()}
added={k:v for k,v in values.items() if v not in set(old.values())};assert len(values)==133 and len(added)==10
key=(ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes();full=Scanner(key,values);delta=Scanner(key,added);delta.generic={}
trusted=set()
for name,receipt in [('g7-core23-secret-delta-01','image-delta.json'),('g7-image-secret-audit-01','image-layers.json')]:
 path=ROOT/'.local'/name/'inventory.json';proof=ROOT/'docs/evidence/G7'/('20261104-'+name.removeprefix('g7-'))/receipt
 assert hashlib.sha256(path.read_bytes()).hexdigest()==load(proof)['inventory_sha256']
 trusted.update(row['sha256'] for row in load(path))
base_oids=set()
for row in subprocess.check_output(['git','ls-tree','-rz','--full-tree',base]).split(b'\0'):
 if row:
  meta,_=row.split(b'\t',1);_,kind,oid=meta.decode().split()
  if kind=='blob':base_oids.add(oid)
seen={};inventory=[];findings=[];counts={};started=time.monotonic();last=started
def phase(name):print(json.dumps(dict(phase=name,members=len(inventory),unique_contents=len(seen),findings=len(findings))),flush=True)
def scan(raw,location,*,prior=False):
 global last
 sha=hashlib.sha256(raw).hexdigest();counts[location.split('/',1)[0]]=counts.get(location.split('/',1)[0],0)+1
 if sha in seen:mode='same_current_bytes_reused'
 else:
  reuse=prior or sha in trusted;scanner=delta if reuse else full;mode='prior_exact_generic_proof_plus_actual_new10' if reuse else 'actual_full_generic_133_values'
  hits=scanner.inspect_bytes(raw,location)
  for hit in hits:hit['file_sha256']=sha;findings.append(hit)
  if hits:
   path=PRIVATE/'finding-bytes'/sha
   if not path.exists():path.write_bytes(raw)
  seen[sha]=dict(bytes=len(raw),mode=mode,findings=len(hits))
 inventory.append(dict(location=location,bytes=len(raw),sha256=sha,mode=mode))
 if time.monotonic()-last>25:phase('scanning');last=time.monotonic()
 return sha
def zip_members(raw,label,*,source=False):
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  if source:assert archive.comment.decode()==head
  names=set()
  for row in archive.infolist():
   if row.is_dir():continue
   assert row.filename not in names;names.add(row.filename)
   data=archive.read(row)
   prior=False
   if source:
    assert not row.filename.startswith(('.local/','.git/')) and '..' not in Path(row.filename).parts
    oid=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();prior=oid in base_oids
   scan(data,label+'/'+row.filename,prior=prior)
def tar_members(raw,label):
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as archive:
  for row in archive:
   if row.isfile():scan(archive.extractfile(row).read(),label+'/'+row.name)
   elif row.issym() or row.islnk():scan(row.linkname.encode(),label+'/link-target/'+row.name)
phase('actual_top_level_transport_bytes')
patterns=PRIVATE/'all-values.regex';full.write_patterns(patterns)
top=[KIT/name for name in [*manifest['files'],'kit-inventory.json','SHA256SUMS']]
top_findings=full.scan_paths(top,patterns,root=KIT)
for hit in top_findings:
 hit['file_sha256']=hashlib.sha256((KIT/hit['location']).read_bytes()).hexdigest();hit['location']='transport/'+hit['location'];findings.append(hit)
phase('source_and_distribution_components')
for name in manifest['files']:
 if name=='images.tar':continue
 raw=(KIT/name).read_bytes()
 if name.endswith(('.zip','.whl','.mplug')):zip_members(raw,'component/'+name,source=name=='source.zip')
 elif name.endswith(('.tar.gz','.tgz')):tar_members(raw,'component/'+name)
 else:scan(raw,'component/'+name)
phase('actual_OCI_image_layer_members')
with tarfile.open(KIT/'images.tar') as archive:
 index=json.load(archive.extractfile('index.json'))
 assert {row['digest'] for row in index['manifests']}=={row['image_id'] for row in manifest['images'].values()}
 for row in archive:
  if not row.isfile():continue
  raw=archive.extractfile(row).read()
  if row.name.startswith('blobs/sha256/'):
   assert hashlib.sha256(raw).hexdigest()==row.name.rsplit('/',1)[1]
   try:layer=tarfile.open(fileobj=io.BytesIO(raw),mode='r:*')
   except tarfile.ReadError:scan(raw,'image-metadata/'+row.name)
   else:
    with layer:
     for member in layer:
      if member.isfile():scan(layer.extractfile(member).read(),'image-layer/'+row.name+'/'+member.name)
      elif member.issym() or member.islnk():scan(member.linkname.encode(),'image-link/'+row.name+'/'+member.name)
  else:scan(raw,'image-transport/'+row.name)
phase('new_reachable_history_blobs')
objects={}
for line in subprocess.check_output(['git','rev-list','--objects',base+'..'+head]).decode().splitlines():
 parts=line.split(' ',1)
 if len(parts)==2:objects.setdefault(parts[0],parts[1])
rows=subprocess.check_output(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],input=''.join(k+'\n' for k in objects).encode())
history_rows=[];known_oids=set()
for line in rows.decode().splitlines():
 oid,kind,size=line.split()
 if kind=='blob':history_rows.append((oid,int(size),'git-history/'+objects[oid],oid in base_oids));known_oids.add(oid)
old_history=load(ROOT/'.local/g7-release-privacy-delta-01/history-inventory.json')
for row in old_history['delta']+old_history['prior_implementation_new_value_check']:
 if row['oid'] not in known_oids:
  history_rows.append((row['oid'],row['size'],'git-history-prior/'+row['path'],True));known_oids.add(row['oid'])
process=subprocess.Popen(['git','cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 for oid,size,label,prior in history_rows:
  process.stdin.write((oid+'\n').encode());process.stdin.flush();assert process.stdout.readline().decode().split()==[oid,'blob',str(size)]
  raw=process.stdout.read(size);assert len(raw)==size and process.stdout.read(1)==b'\n';scan(raw,label,prior=prior)
 process.stdin.close();assert process.wait(timeout=30)==0
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=10)
(PRIVATE/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf8')
(PRIVATE/'content-results.json').write_text(json.dumps(seen,indent=2)+'\n',encoding='utf8')
(PRIVATE/'findings.json').write_text(json.dumps(findings,indent=2)+'\n',encoding='utf8')
report=dict(result='actual_complete_kit_members_scanned_triage_required' if findings else 'passed_actual_complete_kit_members_and_history_privacy',utc=datetime.now(timezone.utc).isoformat(),source_commit=head,prior_source_commit=base,kit_manifest_sha256=hashlib.sha256((KIT/'kit-inventory.json').read_bytes()).hexdigest(),known_values=len(values),new_known_values=len(added),top_level_files=len(top),expanded_members=len(inventory),unique_contents=len(seen),member_categories=counts,findings=findings,inventory_sha256=hashlib.sha256((PRIVATE/'inventory.json').read_bytes()).hexdigest(),elapsed_seconds=round(time.monotonic()-started,3),
 limits=['Actual top-level bytes plus expanded regular source/plugin/notice/wheel/Windows Python/Node/OCI layer members, link targets and new reachable Git history. No archive code executes and nothing is extracted to archive-selected paths.',
 'Prior source123/image121-or123 proof reused only for exact qualified source Git blobs or image member SHA256; every reused unique byte sequence is checked for all ten newly generated values/encodings. Older-image two-value extension must reconcile before final qualification. Other unique bytes receive full generic/133-value inspection.',
 'Known benign static findings require exact per-file/offset/fingerprint review; this collector never suppresses them.',
 'Earlier implementation-history generic/123-value proof retains its existing qualification; all its recorded blobs also receive the new10-value check. Pinned upstream historical ancestry outside the original implementation-history scope remains excluded.',
 'This does not close browser network/accessibility/performance or final G7.'])
with (OUT/'kit-expanded-privacy.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
phase(report['result'])
