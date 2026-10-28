"""Qualify the current additive G2 revision and affected data-only consumers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def run(command):
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=90)
    return {'command':command,'exit_code':result.returncode,
            'stdout':result.stdout.decode('utf-8',errors='replace'),'stderr':result.stderr.decode('utf-8',errors='replace')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G2') or output.exists():raise ValueError('Fresh G2 evidence directory required')
    output.mkdir(parents=True)
    records={}
    for name,pattern in [('contracts','test_*contracts.py'),('archives','test_artifacts.py'),('resolution','test_resolution.py'),('plans','test_plans.py'),('planning-cli','test_planning_cli.py')]:
        records[name]=run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern,'-v'])
    node=shutil.which('node');npm=shutil.which('npm')
    if not node or not npm:raise RuntimeError('Qualified local Node/npm toolchain required')
    npm_cli=Path(npm).parent/'node_modules/npm/bin/npm-cli.js'
    if not npm_cli.is_file():raise RuntimeError('Cannot locate the installed npm CLI entrypoint')
    records['typescript']=run([node,str(npm_cli),'--prefix','packages/host_sdk','run','check'])
    records['freeze']=run([sys.executable,'tools/check_contract_freeze.py'])
    for name,record in records.items():(output/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    inventory=ROOT/'docs/contracts/freeze-v1.json';freeze=json.loads(inventory.read_text())
    result='passed' if all(record['exit_code']==0 for record in records.values()) else 'failed'
    gate={'gate':'G2','result':result,'utc':datetime.now(timezone.utc).isoformat(),'contract_major':freeze['contract_major'],'revision':freeze['revision'],
        'frozen_files':len(freeze['files']),'inventory_sha256':hashlib.sha256(inventory.read_bytes()).hexdigest(),
        'records':[name+'.json' for name in records],'tests':'See per-command records for actual counts; contracts, affected archive/resolver/plan/CLI consumers, TypeScript and current freeze.',
        'change':'ADR0016 revision9 operator-only core_upgrade enum/example; old valid fixtures/golden plan bytes retained; app request excludes operation.',
        'runtime_qualification':'No existing live image/handler changed. G5 actual core maintenance/recovery and UI07 remain required separately.',
        'prerequisite':'docs/evidence/G1/20261028t003753z/gate-G1.json','git_base':run(['git','rev-parse','HEAD'])['stdout'].strip()}
    (output/'gate-G2.json').write_text(json.dumps(gate,indent=2)+'\n')
    print(json.dumps({'result':result,'revision':freeze['revision'],'files':len(freeze['files']),'evidence':str(output)}))
    return 0 if result=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
