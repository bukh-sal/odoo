"""Build-only replacement of one verified native application on pinned core49.

Runs as data assembly, never imports application code or changes installed state.
The caller supplies an isolated image filesystem (or a test-owned temporary root).
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import sys


def apply_layer(root, inputs, request):
    from modular_platform.artifacts import ArtifactValidator,TrustPolicy
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    from package_materialization import materialize_archive
    from package_composition import validate_composition,validate_dependencies

    keys={'schema_version','foundation_image_id','foundation_inventory_digest','application_digest','application_file'}
    if (not isinstance(request,dict) or set(request)!=keys or type(request['schema_version']) is not int
            or request['schema_version']!=1 or request['application_file']!='application.mplug'
            or any(not isinstance(request[k],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',request[k])
                   for k in ('foundation_image_id','foundation_inventory_digest','application_digest'))):
        raise ValueError('Exact pinned application layer input v1 required')
    root=Path(root).resolve();inputs=Path(inputs).resolve()
    original_raw=(root/'distribution-inventory.json').read_bytes()
    original=json.loads(original_raw)
    if 'sha256:'+hashlib.sha256(original_raw).hexdigest()!=request['foundation_inventory_digest']:
        raise ValueError('Foundation inventory differs from operator-selected pin')

    def verify_file(name,expected):
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Inventoried foundation source drift: '+name)
    for name,value in original['files'].items():verify_file(name,value)
    core=ast.literal_eval((root/'addons/mp_core/__manifest__.py').read_text(encoding='utf-8'))
    if core.get('version')!='19.0.0.1.49':raise ValueError('This composition profile requires foundation49')
    incoming=inputs/request['application_file']
    checked=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(
        incoming,expected_digest=request['application_digest'])
    manifest=checked.manifest;plugin=manifest['plugin']['id'];addon=manifest['runtime'].get('addon_name')
    old=original.get('artifacts',{}).get(plugin)
    if (manifest['runtime']['kind']!='native' or manifest['activation']['scopes']!=['site']
            or old is None or addon!=old['addon'] or Version(manifest['plugin']['version'])<=Version(old['version'])):
        raise ValueError('Only a newer existing site-native application slot may be replaced')
    if Version('0.1.49') not in SpecifierSet(manifest['compatibility']['platform']):
        raise ValueError('Application excludes the pinned foundation version')
    native_root=root/'addons'/addon
    if native_root.is_symlink() or not native_root.is_dir() or not native_root.resolve().is_relative_to(root/'addons'):
        raise ValueError('Expected native application directory required')
    old_file='artifacts/'+old['file']
    if old_file not in original['files']:raise ValueError('Original application archive is not inventoried')
    all_raw={ident:(incoming.read_bytes() if ident==plugin else (root/'artifacts'/row['file']).read_bytes())
             for ident,row in original['artifacts'].items()}
    registry=validate_composition(list(all_raw.values()))
    manifests=[]
    with tempfile.TemporaryDirectory(prefix='mp-layer-validate-') as temporary:
        for ident,raw in all_raw.items():
            path=Path(temporary)/(ident+'.mplug');path.write_bytes(raw)
            manifests.append(ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(path).manifest)
        descriptor,raw,staged=materialize_archive(incoming.read_bytes(),Path(temporary)/'native')
        native=ast.literal_eval((staged/'__manifest__.py').read_text(encoding='utf-8'))
        selected=copy.deepcopy(original['native_addons'])
        selected[addon]=dict(depends=native.get('depends') or ['base'],auto_install=native.get('auto_install',False),license=native.get('license','unspecified'))
        if not set(selected[addon]['depends'])<=set(selected):raise ValueError('Missing admitted native dependency')
        packaged={r['runtime']['addon_name'] for r in manifests if r['runtime']['kind']=='native'}
        validate_dependencies(manifests,selected,set(selected)-packaged)
        active=set();visited=set()
        def visit(name):
            if name in active:raise ValueError('Cyclic native dependency')
            if name in visited:return
            active.add(name)
            for dependency in selected[name]['depends']:visit(dependency)
            active.remove(name);visited.add(name)
        for name in selected:visit(name)
        # All input/dependency checks precede writes. Remove only this known
        # inventoried code directory in an isolated build root, never user data.
        replacement_files={p.relative_to(staged).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in staged.rglob('*') if p.is_file()}
        shutil.rmtree(native_root)
        shutil.copytree(staged,native_root)
        (root/old_file).unlink()
        archive_name='artifacts/'+descriptor['file'];(root/archive_name).write_bytes(raw)
        updated=copy.deepcopy(original)
        prefix='addons/'+addon+'/'
        updated['files']={name:value for name,value in original['files'].items() if not name.startswith(prefix) and name!=old_file}
        updated['files'].update({prefix+name:value for name,value in replacement_files.items()})
        updated['files'][archive_name]=hashlib.sha256(raw).hexdigest()
        updated['artifacts'][plugin]=descriptor
        updated['native_addons']=selected
        updated['package_composition']=registry
        for name,value in updated['files'].items():verify_file(name,value)
        retained={name:value for name,value in original['files'].items() if not name.startswith(prefix) and name!=old_file}
        if any(updated['files'].get(name)!=value for name,value in retained.items()):raise ValueError('Foundation source identity changed')
        (root/'distribution-inventory.json').write_text(json.dumps(updated,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    return dict(result='composed_verified_application_layer',plugin_id=plugin,version=manifest['plugin']['version'],
        previous_version=old['version'],artifact_digest=checked.digest,foundation_image_id=request['foundation_image_id'],
        base_inventory_digest=request['foundation_inventory_digest'],inventory_digest='sha256:'+hashlib.sha256((root/'distribution-inventory.json').read_bytes()).hexdigest(),
        retained_foundation_files=len(retained),policy_unchanged=updated['policy']==original['policy'],
        platform_version='0.1.49',application_code_executed=False)


if __name__=='__main__':
    # The builder pins this helper's bytes separately; core49 supplies all
    # validation/materialization code and dependencies used below.
    sys.path[:0]=['/opt/modular/tools','/opt/modular/packages/platform_sdk']
    result=apply_layer('/opt/modular','/compose-input',json.loads(Path('/compose-input/request.json').read_bytes()))
    print('MP_APPLICATION_LAYER='+json.dumps(result,sort_keys=True))
