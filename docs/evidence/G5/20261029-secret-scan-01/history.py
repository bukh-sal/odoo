"""Scan every blob introduced by implementation commits, preserving Git itself."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(OUTPUT)]
from secret_scan import save_report
from tree import context


def main():
    dest=OUTPUT/'implementation-history.json';assert not dest.exists();inventory=json.loads((LOCAL/'history-inventory.json').read_text(encoding='utf8'));cache=LOCAL/'history-blobs';cache.mkdir();paths=[];mapping={};started=time.monotonic()
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for record in inventory:
            oid=record['oid'];assert re.fullmatch('[0-9a-f]{40}',oid);process.stdin.write((oid+'\n').encode());process.stdin.flush();header=process.stdout.readline().decode().split();assert header==[oid,'blob',str(record['size'])]
            raw=process.stdout.read(record['size']);assert len(raw)==record['size'] and process.stdout.read(1)==b'\n';p=cache/oid;p.write_bytes(raw);paths.append(p);mapping[oid]=record
        process.stdin.close();assert process.wait(timeout=30)==0
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
    print(json.dumps(dict(state='scanning_implementation_history',blobs=len(paths))),flush=True)
    scanner=context();findings=scanner.scan_paths(paths,LOCAL/'patterns-v2.regex',root=cache)
    for finding in findings:
        record=mapping[finding['location']];finding.update(git_blob=record['oid'],location=scanner.redact_location('git-history/'+record['path']))
    count=int(subprocess.check_output(['git','rev-list','--count','5c7defb49e020fec8b6bb82403a2f54eb79e92e1..HEAD'],cwd=ROOT))
    value=dict(result='scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),implementation_commits=count,blobs=len(paths),bytes=sum(r['size'] for r in inventory),elapsed_seconds=round(time.monotonic()-started,3),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,limits=['All blob objects introduced after the exact pinned upstream baseline through current HEAD. Pinned upstream current tree is separately scanned; older official upstream ancestor history is not represented as project credential history.','No Git rewrite/delete/publication; raw object audit cache remains private.'])
    save_report(dest,value);print(json.dumps({k:value[k] for k in ['result','implementation_commits','blobs','elapsed_seconds','known_secret_findings','generic_findings']}),flush=True)


if __name__=='__main__':main()
