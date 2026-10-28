"""Build a unique, recorded candidate without replacing any running target."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or not re.fullmatch('[A-Za-z0-9_-]+',output.name):
        raise ValueError('Fresh named G5 evidence directory required')
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(output.name+'.json')
    if record_path.exists():raise RuntimeError('Build already attempted; inspect recorded state and builder before retrying')
    tag='modular-platform:stage-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    source={}
    for directory in ['platform_addons','plugins','packages/contracts','packages/platform_sdk','deploy','tools']:
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                source[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    source.update({name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['.dockerignore','LICENSE','COPYRIGHT']})
    output.mkdir(parents=True)
    command=['docker','build','-f','deploy/Dockerfile','--build-arg','DISTRIBUTION_POLICY=deploy/distribution-r1.json',
        '--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',tag,'.']
    record={'state':'building','tag':tag,'output':str(output.relative_to(ROOT)),'command':command,
        'git_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'source_sha256':source}
    _write_new(record_path,record)
    with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
        with (output/'build.log').open('xb') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        if result.returncode:raise RuntimeError('Candidate build failed; retained build record/log, no deployment action')
        image_id=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
        runtime=inspect_image(image_id)
    for name,digest in source.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Build inputs changed; inspect candidate without deploying it')
    report=record|{'state':'built','image_id':image_id,'utc':datetime.now(timezone.utc).isoformat(),
        'inventory_digest':runtime['inventory_digest'],'artifacts':runtime['inventory']['artifacts'],
        'deployment_changed':False,'result':'built_not_deployed'}
    (output/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n')
    record_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'built_not_deployed','tag':tag,'image_id':image_id,'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
