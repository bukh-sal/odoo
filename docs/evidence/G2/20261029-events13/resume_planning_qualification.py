"""Correct only diagnosed CLI fixtures; reuse exact passing source records."""
import hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=Path(__file__).resolve().parent
first=BASE/'qualification';out=BASE/'qualification-planning-fix';assert not out.exists();out.mkdir()
load=lambda p:json.loads(p.read_text())
gate=load(first/'gate-G2.json');assert gate['result']=='failed'
freeze=load(ROOT/'docs/contracts/freeze-v1.json');assert freeze['revision']==13 and len(freeze['files'])==94
assert hashlib.sha256((ROOT/'docs/contracts/freeze-v1.json').read_bytes()).hexdigest()==gate['inventory_sha256']
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
records=[];reused=[]
for name in gate['records']:
    old=load(first/name)
    if name=='planning-cli.json':
        assert old['exit_code']==1 and 'Plugin dependency conflict' in old['stderr']
        command=[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_planning_cli.py','-v']
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=90)
        record=dict(command=command,exit_code=result.returncode,stdout=result.stdout.decode('utf8'),stderr=result.stderr.decode('utf8'))
        (out/name).write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');records.append(record)
    else:
        assert old['exit_code']==0
        raw=(first/name).read_bytes();(out/name).write_bytes(raw);records.append(old)
        reused.append(dict(record=name,source=(first/name).relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest(),reason='Passing source/schema/type consumer unchanged; no rerun after CLI-only fixture correction.'))
counts={name:([int(v) for v in re.findall(r'Ran (\d+) tests?',record['stderr'])] or [None])[-1] for name,record in zip(gate['records'],records)}
gate.update(result='passed' if all(r['exit_code']==0 for r in records) else 'failed',utc=datetime.now(timezone.utc).isoformat(),reused_records='reused-records.json',test_counts=counts,fixture_correction='Actual reference archives now require platform0.1.8. Old planning CLI positive fixtures still declared0.1.0. Construct a consistent already-compatible empty core and preserve an explicit legacy-platform refusal/immutable-catalog test; no resolver/runtime policy weakened.',corrected_test_source_sha256=hashlib.sha256((ROOT/'tests/test_planning_cli.py').read_bytes()).hexdigest(),prior_failed_gate=(first/'gate-G2.json').relative_to(ROOT).as_posix())
(out/'reused-records.json').write_text(json.dumps(reused,indent=2)+'\n',encoding='utf8');(out/'gate-G2.json').write_text(json.dumps(gate,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=gate['result'],revision=13,files=94,test_counts=counts)))
raise SystemExit(0 if gate['result']=='passed' else 1)
