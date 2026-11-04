"""Scan new reachable Git blobs and check new secret variants in prior/current bytes."""
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-privacy-delta-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from secret_scan import Scanner
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
prior_dir=ROOT/'docs/evidence/G7/20261104-image-secret-audit-01'
prior=json.loads((prior_dir/'qualification.json').read_bytes());base=prior['source_head']
head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
assert subprocess.run(['git','diff','--quiet','HEAD','--'],capture_output=True).returncode==0
assert subprocess.run(['git','merge-base','--is-ancestor',base,head],capture_output=True).returncode==0
values={k:base64.b64decode(v) for k,v in json.loads((ROOT/'.local/g7-core23-secret-delta-01/known-values.json').read_bytes()).items()}
old_values={k:base64.b64decode(v) for k,v in json.loads((ROOT/'.local/g7-image-secret-audit-01/known-values.json').read_bytes()).items()}
assert len(values)==123 and len(old_values)==121 and set(old_values.values())<=set(values.values())
added={k:v for k,v in values.items() if v not in set(old_values.values())};assert len(added)==2
key=(ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes()
scanner=Scanner(key,values);new_only=Scanner(key,added);new_only.generic={}
def tree(revision):
 rows={}
 for entry in subprocess.check_output(['git','ls-tree','-rz','--full-tree',revision]).split(b'\0'):
  if not entry:continue
  meta,name=entry.split(b'\t',1);mode,kind,oid=meta.decode().split()
  if kind=='blob':rows[name.decode()]=oid
 return rows
old_tree=tree(base);current=tree(head)
prior_oids=set(old_tree.values())
paths=[ROOT/name for name in current if (ROOT/name).is_file()]
assert len(paths)==len(current)
pattern=PRIVATE/'new-values.regex'
# Hex-escaped byte regex preserves UTF16/base64/hex variants without raw/NUL
# pattern-file bytes or source disclosure.
pattern.write_bytes(b'|'.join(b''.join(('\\x%02x'%byte).encode() for byte in value) for value in new_only.patterns)+b'\n')
started=time.monotonic()
print(json.dumps(dict(state='checking_new_secret_variants_current_tree',files=len(paths))),flush=True)
findings=new_only.scan_paths(paths,pattern,root=ROOT)
objects={}
for line in subprocess.check_output(['git','rev-list','--objects',base+'..'+head]).decode().splitlines():
 parts=line.split(' ',1)
 if len(parts)==2:objects.setdefault(parts[0],parts[1])
checked=subprocess.check_output(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],input=''.join(k+'\n' for k in objects).encode())
delta=[]
for line in checked.decode().splitlines():
 oid,kind,size=line.split()
 if kind=='blob':delta.append(dict(oid=oid,path=objects[oid],size=int(size)))
old_history=json.loads((ROOT/'.local/g7-image-secret-audit-01/history-inventory.json').read_bytes())
old_history_oids={r['oid'] for r in old_history}
old_extra=[dict(oid=r['oid'],path=r['path'],size=r['size']) for r in old_history if r['oid'] not in {d['oid'] for d in delta}]
assert set(current.values())<=prior_oids|{r['oid'] for r in delta}
process=subprocess.Popen(['git','cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
cache=PRIVATE/'finding-bytes';cache.mkdir();new_findings=[];old_new_value_hits=[]
try:
 for i,row in enumerate(delta+old_extra):
  oid=row['oid'];process.stdin.write((oid+'\n').encode());process.stdin.flush()
  assert process.stdout.readline().decode().split()==[oid,'blob',str(row['size'])]
  raw=process.stdout.read(row['size']);assert len(raw)==row['size'] and process.stdout.read(1)==b'\n'
  row['sha256']=hashlib.sha256(raw).hexdigest()
  scan=scanner if i<len(delta) else new_only
  hits=scan.inspect_bytes(raw,'git-history/'+row['path'])
  if hits:
   (cache/oid).write_bytes(raw)
   target=new_findings if i<len(delta) else old_new_value_hits
   target.extend(dict(hit,file_sha256=row['sha256'],git_blob=oid) for hit in hits)
 process.stdin.close();assert process.wait(timeout=30)==0
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=10)
findings+=new_findings+old_new_value_hits
(PRIVATE/'history-inventory.json').write_text(json.dumps(dict(delta=delta,prior_implementation_new_value_check=old_extra),indent=2)+'\n',encoding='utf8')
report=dict(result='repository_delta_scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),source_head=head,prior_qualified_head=base,
 known_values=123,new_value_variants=len(new_only.patterns),current_tracked_files=len(current),
 identical_prior_tree_members=sum(oid in prior_oids for oid in current.values()),new_history_blobs=len(delta),new_history_bytes=sum(r['size'] for r in delta),
 prior_implementation_blobs_checked_for_new_values=len(old_extra),all_current_tree_and_prior_implementation_checked_for_new_value_variants=True,
 findings=findings,elapsed_seconds=round(time.monotonic()-started,3),
 limits=['Prior generic/121-value current-tree and full implementation history proof is reused only through its exact qualified commit/blob identities. New reachable blobs are scanned with all123 values/generic rules, including deleted/replaced versions.',
 'All current tracked bytes and prior implementation history blobs are also checked for both newly generated values and all scanner-supported encodings. Pinned upstream historical ancestry outside implementation remains outside this release-history scope.',
 'Current untracked audit files and later commits/diagnostics/served assets are separate. No Git rewrite or publication.'])
with (OUT/'repository-delta.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(state=report['result'],new_blobs=len(delta),old_blobs=len(old_extra),findings=len(findings),seconds=report['elapsed_seconds'])),flush=True)
