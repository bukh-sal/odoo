"""Bind native-interaction adapter regressions and frozen contracts to source."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--image',default='modular-platform:r1');args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 evidence required')
    output.mkdir(parents=True);checks=[]
    commands=[['node','--test','tests/test_native_interactions.mjs'],[sys.executable,'tools/check_contract_freeze.py'],
        ['node','node_modules/typescript/lib/tsc.js','--noEmit'],['node','--test','tests/test_canvas_lifecycle.mjs'],
        ['node','--test','tests/test_client_release.mjs'],[sys.executable,'-m','unittest','discover','-s','tests','-p','test_client_release.py','-v']]
    for index,command in enumerate(commands):
        result=subprocess.run(command,cwd=ROOT/'packages/host_sdk' if index==2 else ROOT,capture_output=True,timeout=90)
        record={'command':command,'exit_code':result.returncode,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}
        (output/('check-'+str(index)+'.json')).write_text(json.dumps(record,indent=2)+'\n');checks.append(record)
    for name in ['host.js','native_interactions.js','client_release.js']:
        raw=(ROOT/'platform_addons/mp_shell/static/src'/name).read_bytes()
        result=subprocess.run(['node','--check','--input-type=module'],input=raw,capture_output=True,timeout=20)
        checks.append({'source':name,'exit_code':result.returncode,'stderr':result.stderr.decode(errors='replace')})
    bundle=io.BytesIO()
    with tarfile.open(fileobj=bundle,mode='w') as archive:
        for directory in ['packages/platform_sdk','packages/contracts','platform_addons/mp_identity']:
            for path in (ROOT/directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:archive.add(path,arcname=path.relative_to(ROOT).as_posix(),recursive=False)
        archive.add(ROOT/'tests/test_client_release.py',arcname='tests/test_client_release.py')
    runner="""import os,sys,tarfile,unittest
os.mkdir('/tmp/client-release',0o700)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:archive.extractall('/tmp/client-release',filter='data')
os.chdir('/tmp/client-release')
suite=unittest.defaultTestLoader.discover('tests',pattern='test_client_release.py')
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
"""
    command=['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--pids-limit','64','--user','10001:10001','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777','--entrypoint','/venv/bin/python',args.image,'-c',runner]
    result=subprocess.run(command,input=bundle.getvalue(),capture_output=True,timeout=90)
    linux={'command':command,'exit_code':result.returncode,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}
    (output/'client-release-linux.json').write_text(json.dumps(linux,indent=2)+'\n');checks.append(linux)
    paths=[path for path in (ROOT/'platform_addons/mp_shell').rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    paths+=[Path(__file__),ROOT/'tests/test_native_interactions.mjs',ROOT/'tests/test_canvas_lifecycle.mjs',ROOT/'tests/test_client_release.mjs',ROOT/'tests/test_client_release.py',ROOT/'tools/r1_probe.py',
        ROOT/'packages/platform_sdk/modular_platform/client_release.py',ROOT/'packages/platform_sdk/modular_platform/contracts.py',ROOT/'packages/platform_sdk/modular_platform/plans.py',ROOT/'packages/contracts/v1/client-release.schema.json',ROOT/'packages/contracts/examples/v1/client-release.json',ROOT/'docs/contracts/freeze-v1.json',ROOT/'platform_addons/mp_identity/release.py',ROOT/'platform_addons/mp_identity/models/ir_http.py',ROOT/'platform_addons/mp_identity/scopes.py',ROOT/'platform_addons/mp_identity/__manifest__.py',ROOT/'platform_addons/mp_core/controllers.py',ROOT/'platform_addons/mp_core/__manifest__.py',
        ROOT/'platform_addons/mp_example_canvas/static/src/page.js',ROOT/'platform_addons/mp_example_canvas/static/src/adapter.js']
    report={'result':'passed' if all(row['exit_code']==0 for row in checks) else 'failed','utc':datetime.now(timezone.utc).isoformat(),
        'git_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'linux_image_id':subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}']).decode().strip(),
        'node':subprocess.check_output(['node','--version']).decode().strip(),'checks':checks,
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limits':['Mock services test mount/authority/Promise adapters; actual native rendering/focus/Escape/hotkeys/CRUD require browser qualification.',
            'Release identity/adapter functions and client latch are source-only here; actual gateway/native/browser/core maintenance and recovery qualification remain separate checks.']}
    (output/'ui-reuse-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'result':report['result'],'evidence':str(output)}))
    return report['result']!='passed'


if __name__=='__main__':raise SystemExit(main())
