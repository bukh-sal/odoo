"""Scan retained G6/G7 command/executor streams, excluding secret stores."""
import base64,hashlib,json,os,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner,save_report
values={k:base64.b64decode(v) for k,v in json.loads((PRIVATE/'known-values.json').read_bytes()).items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[]
for directory in (ROOT/'.local').iterdir():
 if not directory.is_dir() or directory==PRIVATE or not directory.name.startswith(('g6-','g7-')):continue
 for parent,dirs,files in os.walk(directory):
  dirs[:]=[d for d in dirs if d not in ['profile','node_modules','filestore','data','pgdata','history-blobs','image-files','finding-files','served-assets']]
  for name in files:
   if name.endswith(('.stdout','.stderr','.log')):paths.append(Path(parent)/name)
patterns=PRIVATE/'patterns.regex';assert patterns.is_file()
print(json.dumps(dict(state='scanning_retained_command_logs',files=len(paths))),flush=True)
findings=scanner.scan_paths(paths,patterns,root=ROOT)
for finding in findings:finding['file_sha256']=hashlib.sha256((ROOT/finding['location']).read_bytes()).hexdigest()
report=dict(result='scanned_retained_logs_triage_required',files=len(paths),bytes=sum(p.stat().st_size for p in paths),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,limits=['Retained G6/G7 stdout/stderr/log command streams, including operational diagnostics; configured credentials, issuer stores, backups/DB/filestore and dynamic browser bootstrap stores are private secret stores, not release logs.','G5 log scans/remediation retain their own exact historical evidence; no prior log record is silently overwritten.'])
save_report(OUT/'retained-command-logs-after.json',report)
print(json.dumps({k:report[k] for k in ['result','files','known_secret_findings','generic_findings']}),flush=True)

