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
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
from build_inputs import source_input_paths

CLEAN_NODE_IMAGE='node:24.22.2-bookworm-slim@sha256:c0a93797ee78814ae6d32fcca2561fdbbe423149c3f5389aad32d86e9fd85bd4'
CLEAN_NODE_VERSION='v24.22.2'
CLEAN_RTLCSS_VERSION='rtlcss version: 4.3.0'
CLEAN_DOCKER_TARGET='clean-runtime'


def _clean_inputs(root):
    runtime_lock=json.loads((root/'deploy/runtime.lock.json').read_bytes())
    python_image=runtime_lock['python_image'];snapshot=runtime_lock['debian_snapshot']
    if not isinstance(python_image,str) or not re.fullmatch(r'python:[^@\s]+@sha256:[0-9a-f]{64}',python_image):
        raise ValueError('Exact pinned clean Python image required')
    dockerfile=(root/'deploy/Dockerfile').read_text(encoding='utf8')
    required=(f'ARG PYTHON_IMAGE={python_image}',f'ARG RTL_NODE_IMAGE={CLEAN_NODE_IMAGE}',
        'FROM ${RTL_NODE_IMAGE} AS rtl-compiler','FROM ${PYTHON_IMAGE} AS clean-runtime',
        'COPY --from=builder /release /opt/modular','COPY --from=rtl-compiler /opt/stock-rtl /opt/stock-rtl',
        'COPY deploy/stock-rtl/package.json deploy/stock-rtl/package-lock.json')
    if any(value not in dockerfile for value in required):
        raise ValueError('Clean Dockerfile is missing its pinned RTL/clean-runtime closure')
    lock=root/'deploy/stock-rtl/package-lock.json';package=root/'deploy/stock-rtl/package.json';wrapper=root/'deploy/stock-rtl/rtlcss'
    if not lock.is_file() or not package.is_file() or not wrapper.is_file():
        raise ValueError('Pinned RTL package inputs are missing')
    return {
        'build_mode':'clean','docker_target':CLEAN_DOCKER_TARGET,'rtl_node_image':CLEAN_NODE_IMAGE,
        'python_image':python_image,'python_version':runtime_lock['python'],'debian_snapshot':snapshot,
        'dockerfile_sha256':'sha256:'+hashlib.sha256((root/'deploy/Dockerfile').read_bytes()).hexdigest(),
        'runtime_requirements_sha256':'sha256:'+hashlib.sha256((root/'deploy/requirements-r1.lock').read_bytes()).hexdigest(),
        'rtl_node_version':CLEAN_NODE_VERSION,'rtlcss_version':CLEAN_RTLCSS_VERSION,
        'rtl_package_lock_sha256':'sha256:'+hashlib.sha256(lock.read_bytes()).hexdigest(),
        'rtl_package_sha256':'sha256:'+hashlib.sha256(package.read_bytes()).hexdigest(),
        'rtl_wrapper_sha256':'sha256:'+hashlib.sha256(wrapper.read_bytes()).hexdigest()}


def _verify_clean_rtl(image_id,root):
    node=subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','/usr/local/bin/node',
        image_id,'--version'],timeout=30).strip()
    rtl=subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','/usr/local/bin/rtlcss',
        image_id,'--version'],timeout=30).strip()
    if node!=CLEAN_NODE_VERSION.encode() or rtl!=CLEAN_RTLCSS_VERSION.encode():
        raise RuntimeError('Clean candidate RTL compiler versions differ from the pinned closure')
    lock=json.loads((root/'deploy/stock-rtl/package-lock.json').read_bytes())
    expected=set(lock['packages'])-{''}
    found=subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','find',
        image_id,'/opt/stock-rtl/node_modules','-type','f','-iname','license*'],timeout=30).decode().splitlines()
    actual={Path(name).relative_to('/opt/stock-rtl').as_posix().rsplit('/',1)[0] for name in found}
    if actual!=expected:raise RuntimeError('Clean candidate stock RTL notice closure differs from its package lock')
    return {'node_version':node.decode(),'rtlcss_version':rtl.decode(),'notice_packages':len(actual)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--gate',choices=['G5','G6','G7'],default='G5',help='Owning implementation gate for recorded build evidence')
    parser.add_argument('--policy',type=Path,default=Path('deploy/distribution-r1-core.json'),help='Operator-owned R1 distribution policy under deploy/; never an application-selected path')
    parser.add_argument('--dependency-base-image',help='Exact sha256 image for code-only maintenance; preserves its Python/OS environment, independently rechecked after build')
    parser.add_argument('--reproduction', action='store_true', help='Rebuild from the exact dependency image without build cache or RUN network access')
    parser.add_argument('--recompile-dependencies', action='store_true', help='Clean candidate only: reexecute the fixed builder stage without pruning shared cache; locked dependency network access remains enabled')
    args=parser.parse_args()
    policy=(ROOT/args.policy).resolve()
    if (not policy.is_relative_to(ROOT/'deploy') or not policy.is_file()
            or not re.fullmatch(r'distribution-r1(?:-[A-Za-z0-9_-]+)?\.json',policy.name)):
        raise ValueError('Existing operator-owned deploy/distribution-r1*.json policy required')
    policy_name=policy.relative_to(ROOT).as_posix()
    policy_data=json.loads(policy.read_bytes());surface=policy_data.get('runtime_surface')
    if surface not in (None,'clean'):raise ValueError('Unsupported distribution runtime surface')
    clean=surface=='clean'
    if clean and policy_data.get('platform_sdk') is not True:
        raise ValueError('Clean runtime requires the guarded platform SDK')
    if clean and (args.dependency_base_image or args.reproduction):
        raise ValueError('Clean runtime rejects dependency-base and reproduction modes before any build/output')
    if args.recompile_dependencies and (not clean or args.dependency_base_image or args.reproduction):
        raise ValueError('Dependency recompilation requires only the normal clean candidate route')
    if args.reproduction and not args.dependency_base_image:
        parser.error('--reproduction requires --dependency-base-image')
    dependency_base=None
    if args.dependency_base_image:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',args.dependency_base_image):
            raise ValueError('Immutable independently selected dependency base required')
        dependency_base=inspect_image(args.dependency_base_image)
        if (dependency_base['python_lock_digest']!='sha256:'+hashlib.sha256((ROOT/'deploy/requirements-r1.lock').read_bytes()).hexdigest()
                or any(dependency_base[name] for name in ['modified_files','missing_addon_files','unexpected_addon_files'])):
            raise ValueError('Code-only maintenance requires exact unchanged dependency lock and inventoried base')
    clean_inputs=_clean_inputs(ROOT) if clean else None
    if json.loads(policy.read_bytes()).get('stock_webclient') and not clean:
        if not dependency_base:
            raise ValueError('Stock WebClient requires the pinned RTL dependency image from Dockerfile.stock-rtl')
        version = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--read-only',
            '--entrypoint', '/usr/local/bin/rtlcss', args.dependency_base_image, '--version'], timeout=30)
        if version.strip() != b'rtlcss version: 4.3.0':
            raise ValueError('Selected stock WebClient dependency image has the wrong RTL compiler')
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence'/args.gate) or output.exists() or not re.fullmatch('[A-Za-z0-9_-]+',output.name):
        raise ValueError('Fresh named evidence directory under the owning gate required')
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(output.name+'.json')
    if record_path.exists():raise RuntimeError('Build already attempted; inspect recorded state and builder before retrying')
    tag='modular-platform:stage-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    dependency_tag='modular-platform:dependency-base-'+output.name if dependency_base else None
    source={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in source_input_paths(ROOT, policy_name)}
    output.mkdir(parents=True)
    dockerfile='deploy/Dockerfile.core-maintenance' if dependency_base else 'deploy/Dockerfile'
    command=['docker','build','-f',dockerfile]
    if clean:command+=['--target',CLEAN_DOCKER_TARGET,'--build-arg','RTL_NODE_IMAGE='+CLEAN_NODE_IMAGE,
        '--build-arg','PYTHON_IMAGE='+clean_inputs['python_image'],'--build-arg','DEBIAN_SNAPSHOT='+clean_inputs['debian_snapshot']]
    command+=['--build-arg','DISTRIBUTION_POLICY='+policy_name,'--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock',
        '--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',tag,'.']
    if dependency_base:
        # Dockerfile FROM treats a bare sha256 image ID as a repository name.
        # Bind one owned temporary alias, verify it, and remove only that alias.
        command[2:2]=['--build-arg','DEPENDENCY_BASE_IMAGE='+dependency_tag]
    if args.reproduction:
        command[2:2]=['--no-cache', '--network=none']
    if args.recompile_dependencies:
        command[2:2]=['--no-cache-filter','builder']
    record={'state':'building','tag':tag,'output':str(output.relative_to(ROOT)),'command':command,'distribution_policy':policy_name,
        'git_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'source_sha256':source,
        'dependency_base_image':args.dependency_base_image}
    record['build_cache_policy']='recompile_builder_stage' if args.recompile_dependencies else ('maintenance_no_cache_no_network' if args.reproduction else 'normal_cache')
    if clean:record.update(clean_inputs)
    _write_new(record_path,record)
    control=protect_directory(ROOT/'.local/operator/control')
    locks=protect_directory(control/'locks')
    with ProcessLock(locks,'candidate-build'):
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
        clean_verification=None
        if clean:
            try:
                if any(runtime.get(name) for name in ['modified_files','missing_addon_files','unexpected_addon_files']):
                    raise RuntimeError('Clean candidate differs from its runtime inventory')
                clean_verification=_verify_clean_rtl(image_id,ROOT)
            except Exception as error:
                failure=record|{'state':'verification_failed','phase':'clean_postbuild_verification',
                    'image_id':image_id,'deployment_changed':False,'error_type':type(error).__name__}
                record_path.write_text(json.dumps(failure,indent=2)+'\n',encoding='utf8')
                (output/'candidate-verification-failed.json').write_text(json.dumps(failure,indent=2)+'\n',encoding='utf8')
                raise
    for name,digest in source.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Build inputs changed; inspect candidate without deploying it')
    report=record|{'state':'built','image_id':image_id,'utc':datetime.now(timezone.utc).isoformat(),
        'inventory_digest':runtime['inventory_digest'],'artifacts':runtime['inventory'].get('artifacts',{}),
        'deployment_changed':False,'result':'built_not_deployed'}
    if clean:report['clean_verification']=clean_verification
    (output/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n')
    record_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'built_not_deployed','tag':tag,'image_id':image_id,'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
