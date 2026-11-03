"""Scan current tracked bytes and every implementation-introduced Git blob."""
import base64,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner,save_report
BASE='5c7defb49e020fec8b6bb82403a2f54eb79e92e1'
values={k:base64.b64decode(v) for k,v in json.loads((PRIVATE/'known-values.json').read_bytes()).items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
patterns=PRIVATE/'patterns.regex';scanner.write_patterns(patterns)
head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
names=[n.decode() for n in subprocess.check_output(['git','ls-files','-z']).split(b'\0') if n]
paths=[ROOT/name for name in names if (ROOT/name).is_file()];started=time.monotonic()
print(json.dumps(dict(state='scanning_current_tree',files=len(paths))),flush=True)
findings=scanner.scan_paths(paths,patterns,root=ROOT)
for finding in findings:finding['file_sha256']=hashlib.sha256((ROOT/finding['location']).read_bytes()).hexdigest()
save_report(OUT/'tracked-tree.json',dict(result='scanned_triage_required',source_head=head,files=len(paths),bytes=sum(p.stat().st_size for p in paths),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,scope='All tracked bytes at captured HEAD; untracked audit evidence separately scanned before commit.'))
print(json.dumps(dict(state='current_tree_complete',findings=len(findings))),flush=True)
objects=subprocess.check_output(['git','rev-list','--objects',BASE+'..'+head]).splitlines()
records={}
for line in objects:
 parts=line.decode().split(' ',1)
 if len(parts)==2:records.setdefault(parts[0],parts[1])
checked=subprocess.run(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],input=''.join(k+'\n' for k in records).encode(),capture_output=True,check=True).stdout
inventory=[]
for line in checked.decode().splitlines():
 oid,kind,size=line.split()
 if kind=='blob':inventory.append(dict(oid=oid,path=records[oid],size=int(size)))
cache=PRIVATE/'history-blobs';cache.mkdir();mapping={r['oid']:r for r in inventory}
process=subprocess.Popen(['git','cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 for row in inventory:
  oid=row['oid'];process.stdin.write((oid+'\n').encode());process.stdin.flush()
  assert process.stdout.readline().decode().split()==[oid,'blob',str(row['size'])]
  raw=process.stdout.read(row['size']);assert len(raw)==row['size'] and process.stdout.read(1)==b'\n'
  (cache/oid).write_bytes(raw)
 process.stdin.close();assert process.wait(timeout=30)==0
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=10)
print(json.dumps(dict(state='scanning_all_implementation_history',blobs=len(inventory))),flush=True)
findings=scanner.scan_paths([cache/r['oid'] for r in inventory],patterns,root=cache)
for finding in findings:
 row=mapping[finding['location']];finding.update(git_blob=row['oid'],location=scanner.redact_location('git-history/'+row['path']),file_sha256=hashlib.sha256((cache/row['oid']).read_bytes()).hexdigest())
(PRIVATE/'history-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
save_report(OUT/'implementation-history.json',dict(result='scanned_triage_required',source_head=head,upstream_base=BASE,implementation_commits=int(subprocess.check_output(['git','rev-list','--count',BASE+'..'+head])),blobs=len(inventory),bytes=sum(r['size'] for r in inventory),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,elapsed_seconds=round(time.monotonic()-started,3),limits=['All blobs introduced after exact pinned upstream through captured HEAD, including replaced/deleted versions; upstream current source scanned separately.','No Git rewrite/publication; raw blob cache remains private pending exact identity triage and cleanup.']))
print(json.dumps(dict(state='repository_and_history_scanned',history_findings=len(findings),seconds=round(time.monotonic()-started,3))),flush=True)
