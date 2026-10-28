"""Bind native-interaction adapter regressions and frozen contracts to source."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 evidence required')
    output.mkdir(parents=True);checks=[]
    commands=[['node','--test','tests/test_native_interactions.mjs'],[sys.executable,'tools/check_contract_freeze.py'],
        ['node','node_modules/typescript/lib/tsc.js','--noEmit']]
    for index,command in enumerate(commands):
        result=subprocess.run(command,cwd=ROOT/'packages/host_sdk' if index==2 else ROOT,capture_output=True,timeout=90)
        record={'command':command,'exit_code':result.returncode,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}
        (output/('check-'+str(index)+'.json')).write_text(json.dumps(record,indent=2)+'\n');checks.append(record)
    for name in ['host.js','native_interactions.js']:
        raw=(ROOT/'platform_addons/mp_shell/static/src'/name).read_bytes()
        result=subprocess.run(['node','--check','--input-type=module'],input=raw,capture_output=True,timeout=20)
        checks.append({'source':name,'exit_code':result.returncode,'stderr':result.stderr.decode(errors='replace')})
    paths=[path for path in (ROOT/'platform_addons/mp_shell').rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    paths+=[Path(__file__),ROOT/'tests/test_native_interactions.mjs']
    report={'result':'passed' if all(row['exit_code']==0 for row in checks) else 'failed','utc':datetime.now(timezone.utc).isoformat(),
        'git_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'node':subprocess.check_output(['node','--version']).decode().strip(),'checks':checks,
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limits':['Mock services test mount/authority/Promise adapters; actual native rendering/focus/Escape/hotkeys/CRUD require browser qualification.',
            'Native list/form hosting, action/router pilot and client release fencing remain separate checks.']}
    (output/'ui-reuse-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'result':report['result'],'evidence':str(output)}))
    return report['result']!='passed'


if __name__=='__main__':raise SystemExit(main())
