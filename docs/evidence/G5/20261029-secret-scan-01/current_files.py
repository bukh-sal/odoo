"""Scan only new/changed current files; earlier full-tree/history scans retained."""
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan';sys.path[:0]=[str(ROOT/'tools'),str(OUTPUT)]
from tree import context
from secret_scan import save_report

def main():
 dest=OUTPUT/'current-files.json';assert not dest.exists();scanner=context();raw=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=ROOT);names=sorted(set(n.decode() for n in raw.split(b'\0') if n));paths=[ROOT/n for n in names if (ROOT/n).is_file()];findings=scanner.scan_paths(paths,LOCAL/'patterns-v2.regex',root=ROOT);files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
 report=dict(result='scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),files=files,bytes=sum(p.stat().st_size for p in paths),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,limits=['Complements full tracked tree/history/image/package/log scans; status/prose/output records excluded from runtime code identity.'])
 save_report(dest,report);print(json.dumps(dict(files=len(files),known_secret_findings=report['known_secret_findings'],generic_findings=report['generic_findings'],findings=findings)))
if __name__=='__main__':main()
