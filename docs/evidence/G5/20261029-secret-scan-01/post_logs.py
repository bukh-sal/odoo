"""Fresh remaining daemon streams after exact private-retention remediation."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan';sys.path[:0]=[str(ROOT/'tools'),str(OUTPUT)]
from tree import context
from secret_scan import save_report

def main():
 dest=OUTPUT/'post-remediation-logs.json';assert not dest.exists();scanner=context();scope=json.loads((LOCAL/'scope.json').read_text());assert json.loads((OUTPUT/'legacy-payload-log-remediation.json').read_text())['containers']==53;cache=LOCAL/'current-container-logs';cache.mkdir();started=time.monotonic();findings=[];records=[]
 for raw in subprocess.check_output(['docker','ps','-a','--format','{{json .}}']).splitlines():
  row=json.loads(raw);labels=dict(v.split('=',1) for v in row['Labels'].split(',') if '=' in v);project=labels.get('com.docker.compose.project');name=row['Names']
  if project not in scope['projects'] and not any(name.startswith(p+'-') for p in scope['projects']):continue
  info=json.loads(subprocess.check_output(['docker','inspect',row['ID']]))[0];driver=info['HostConfig']['LogConfig']['Type'];r=subprocess.run(['docker','logs',row['ID']],capture_output=True,timeout=60)
  if driver=='none':assert not r.stdout;records.append(dict(id=info['Id'],name=name,driver=driver,stdout_bytes=0,logging_disabled=True));continue
  assert r.returncode==0;data=r.stdout+b'\n'+r.stderr;path=cache/row['ID'];path.write_bytes(data);findings+=scanner.inspect_file(path,'container-log/'+name);records.append(dict(id=info['Id'],name=name,driver=driver,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 paths=[ROOT/p for p in scope['private_logs'] if (ROOT/p).is_file()];findings+=scanner.scan_paths(paths,LOCAL/'patterns-v2.regex',root=ROOT)
 report=dict(result='passed' if not findings else 'failed_triage_required',utc=datetime.now(timezone.utc).isoformat(),container_logs=len(records),private_log_files=len(paths),records=records,findings=findings,known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),elapsed_seconds=round(time.monotonic()-started,3),limits=['Private config/credential/backup/audit archives remain expected secret stores; raw prior leaked diagnostics are retained only there.','No universal redaction/sandbox claim for arbitrary trusted plugin code; re-scan logs for each new release.'])
 save_report(dest,report);print(json.dumps({k:report[k] for k in ['result','container_logs','private_log_files','known_secret_findings','generic_findings','elapsed_seconds']}))
if __name__=='__main__':main()
