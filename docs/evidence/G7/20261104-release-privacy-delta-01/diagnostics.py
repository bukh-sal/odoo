"""Audit the actual retained log corpus; prior aggregate lacks per-file reuse hashes."""
import base64,hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-privacy-delta-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in json.loads((ROOT/'.local/g7-core23-secret-delta-01/known-values.json').read_bytes()).items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
patterns=PRIVATE/'all-values.regex';scanner.write_patterns(patterns)
paths=[]
for directory in (ROOT/'.local').iterdir():
 if not directory.is_dir() or directory.name=='g7-image-secret-audit-01' or not directory.name.startswith(('g6-','g7-')):continue
 for parent,dirs,files in os.walk(directory):
  dirs[:]=[d for d in dirs if d not in ['profile','node_modules','filestore','data','pgdata','history-blobs','image-files','finding-files','finding-bytes','served-assets']]
  paths.extend(Path(parent)/name for name in files if name.endswith(('.stdout','.stderr','.log')))
print(json.dumps(dict(state='scanning_actual_retained_diagnostics',files=len(paths))),flush=True)
findings=scanner.scan_paths(paths,patterns,root=ROOT)
for finding in findings:finding['file_sha256']=hashlib.sha256((ROOT/finding['location']).read_bytes()).hexdigest()
inventory=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
(PRIVATE/'diagnostic-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf8')
report=dict(result='retained_diagnostics_scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),files=len(paths),bytes=sum(r['bytes'] for r in inventory),known_values=123,
 inventory_sha256=hashlib.sha256((PRIVATE/'diagnostic-inventory.json').read_bytes()).hexdigest(),findings=findings,
 limits=['Actual current G6/G7 stdout/stderr/log corpus, not configured secret stores/checkpoints/DB/filestore/browser sessions or source archives.',
 'Prior5922-file aggregate has no reusable per-file hashes; full current corpus checked once with123 values instead of assuming mtime proves unchanged bytes. New per-file private hashes permit future exact reuse.',
 'The old audit directory remains separately protected with its retained positive findings and secret transport relocation; it is not silently reclassified clean.'])
with (OUT/'diagnostics.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(files=len(paths),findings=len(findings))),flush=True)
