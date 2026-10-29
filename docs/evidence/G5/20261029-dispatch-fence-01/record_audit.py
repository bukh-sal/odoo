"""Final bounded recording validation; no runtime or database actions."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'record-audit.json';assert not dest.exists()
    private=[]
    for folder,names in [(ROOT/'.local/g5-dispatch',['bootstrap-password','postgres-password','app-db-password','database-master-password']),(ROOT/'.local/g5-lifecycle',['bootstrap-password']),(ROOT/'.local/g5',['bootstrap-password']),(ROOT/'.local/g5-manager-upgrade',['bootstrap-password'])]:
        for name in names:
            p=folder/name
            if p.exists():private.append(p.read_text(encoding='utf8').strip().encode())
    count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not v or v not in raw for v in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    source=load(OUTPUT/'source-boundary.json')['source_sha256'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    for name in ['qualification.json','final-audit.json','source-host2.json','source-linux.json']:assert load(OUTPUT/name)['result']=='passed'
    freeze=load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==87 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
    status=(ROOT/'docs/implementation-status.md').read_text(encoding='utf8').split('## Acceptance ledger',1)[1]
    results=re.findall(r'^\| [A-Z]+-\d+ \| [^|]+ \| (passed|not_run|invalidated|failed|excluded_R2) \|',status,re.M);assert results.count('passed')==77 and results.count('not_run')==22 and results.count('excluded_R2')==5
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),public_files_checked=count,known_private_values_checked=len(private),current_source_hashes_verified=len(source),frozen_files=87,acceptance_passed=77,acceptance_not_run=22,R2_excluded=5,limits=['Bounded evidence recording scan; not SEC03 release qualification.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(value))


if __name__=='__main__':main()
