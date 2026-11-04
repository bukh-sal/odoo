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
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--gate',choices=['G5','G6','G7'],default='G5',help='Owning implementation gate for recorded build evidence')
    parser.add_argument('--policy',type=Path,default=Path('deploy/distribution-r1.json'),help='Operator-owned R1 distribution policy under deploy/; never an application-selected path')
    parser.add_argument('--dependency-base-image',help='Exact sha256 image for code-only maintenance; preserves its Python/OS environment, independently rechecked after build')
    args=parser.parse_args()
    dependency_base=None
    if args.dependency_base_image:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',args.dependency_base_image):
            raise ValueError('Immutable independently selected dependency base required')
        dependency_base=inspect_image(args.dependency_base_image)
        if (dependency_base['python_lock_digest']!='sha256:'+hashlib.sha256((ROOT/'deploy/requirements-r1.lock').read_bytes()).hexdigest()
                or any(dependency_base[name] for name in ['modified_files','missing_addon_files','unexpected_addon_files'])):
            raise ValueError('Code-only maintenance requires exact unchanged dependency lock and inventoried base')
    policy=(ROOT/args.policy).resolve()
    if (not policy.is_relative_to(ROOT/'deploy') or not policy.is_file()
            or not re.fullmatch(r'distribution-r1(?:-[A-Za-z0-9_-]+)?\.json',policy.name)):
        raise ValueError('Existing operator-owned deploy/distribution-r1*.json policy required')
    policy_name=policy.relative_to(ROOT).as_posix()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence'/args.gate) or output.exists() or not re.fullmatch('[A-Za-z0-9_-]+',output.name):
        raise ValueError('Fresh named evidence directory under the owning gate required')
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(output.name+'.json')
    if record_path.exists():raise RuntimeError('Build already attempted; inspect recorded state and builder before retrying')
    tag='modular-platform:stage-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    dependency_tag='modular-platform:dependency-base-'+output.name if dependency_base else None
    source={}
    for directory in ['platform_addons','plugins','packages/contracts','packages/platform_sdk','deploy','tools']:
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                source[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    source.update({name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['.dockerignore','LICENSE','COPYRIGHT']})
    output.mkdir(parents=True)
    dockerfile='deploy/Dockerfile.core-maintenance' if dependency_base else 'deploy/Dockerfile'
    command=['docker','build','-f',dockerfile,'--build-arg','DISTRIBUTION_POLICY='+policy_name,
        '--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',tag,'.']
    if dependency_base:
        # Dockerfile FROM treats a bare sha256 image ID as a repository name.
        # Bind one owned temporary alias, verify it, and remove only that alias.
        command[2:2]=['--build-arg','DEPENDENCY_BASE_IMAGE='+dependency_tag]
    record={'state':'building','tag':tag,'output':str(output.relative_to(ROOT)),'command':command,'distribution_policy':policy_name,
        'git_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'source_sha256':source,
        'dependency_base_image':args.dependency_base_image}
    _write_new(record_path,record)
    with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
        if dependency_tag:
            prior=subprocess.run(['docker','image','inspect',dependency_tag],capture_output=True,timeout=30)
            if prior.returncode==0:raise RuntimeError('Dependency alias already exists; reconcile the original build record')
            subprocess.run(['docker','tag',args.dependency_base_image,dependency_tag],check=True,timeout=30)
            actual=subprocess.check_output(['docker','image','inspect',dependency_tag,'--format','{{.Id}}']).decode().strip()
            if actual!=args.dependency_base_image:raise RuntimeError('Dependency alias does not match the exact selected image')
        try:
            with (output/'build.log').open('xb') as log:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        finally:
            if dependency_tag:
                actual=subprocess.check_output(['docker','image','inspect',dependency_tag,'--format','{{.Id}}']).decode().strip()
                if actual!=args.dependency_base_image:raise RuntimeError('Dependency alias changed; refuse cleanup')
                subprocess.run(['docker','image','rm',dependency_tag],check=True,capture_output=True,timeout=30)
        if result.returncode:raise RuntimeError('Candidate build failed; retained build record/log, no deployment action')
        image_id=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
        runtime=inspect_image(image_id)
        if dependency_base and any(runtime[key]!=dependency_base[key] for key in
                ['python','architecture','markers','python_lock_digest','python_metadata']):
            raise RuntimeError('Code-only maintenance changed the selected dependency environment; candidate is not admissible')
    for name,digest in source.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Build inputs changed; inspect candidate without deploying it')
    report=record|{'state':'built','image_id':image_id,'utc':datetime.now(timezone.utc).isoformat(),
        'inventory_digest':runtime['inventory_digest'],'artifacts':runtime['inventory']['artifacts'],
        'deployment_changed':False,'result':'built_not_deployed'}
    (output/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n')
    record_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'built_not_deployed','tag':tag,'image_id':image_id,'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
