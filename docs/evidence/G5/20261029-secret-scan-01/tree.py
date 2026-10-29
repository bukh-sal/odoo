"""Current tracked tree scan, including pinned upstream source and binary files."""
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from secret_scan import Scanner,save_report


def context():
    values=json.loads((LOCAL/'known-values.json').read_text(encoding='utf8'));return Scanner((LOCAL/'fingerprint-key').read_bytes(),{k:base64.b64decode(v) for k,v in values.items()})


def main():
    dest=OUTPUT/'tracked-tree.json';assert not dest.exists();scanner=context();names=[n.decode() for n in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).split(b'\0') if n];paths=[ROOT/n for n in names if (ROOT/n).is_file()];started=time.monotonic()
    print(json.dumps(dict(state='scanning_current_tracked_tree',files=len(paths))),flush=True)
    findings=scanner.scan_paths(paths,LOCAL/'patterns-v2.regex',root=ROOT)
    report=dict(result='scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),files=len(paths),bytes=sum(p.stat().st_size for p in paths),elapsed_seconds=round(time.monotonic()-started,3),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,source_sha256=hashlib.sha256((ROOT/'tools/secret_scan.py').read_bytes()).hexdigest(),limits=['Current tracked content only; Git history, image layers, packages/browser/logs are separate scans.','Generic signatures require exact fingerprint/file identity review, not automatic exclusion by directory.'])
    save_report(dest,report);print(json.dumps({k:report[k] for k in ['result','files','bytes','elapsed_seconds','known_secret_findings','generic_findings']}),flush=True)


if __name__=='__main__':main()
