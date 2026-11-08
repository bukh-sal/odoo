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


def apply_set_layer(root,inputs,request):
    """Build contract2: add/replace native app slots, retaining the pinned core."""
    from modular_platform.artifacts import ArtifactValidator,TrustPolicy
    from modular_platform.native_scope import require_site_manifest
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    from package_materialization import materialize_archive
    from package_composition import validate_composition,validate_dependencies

    keys={'schema_version','foundation_image_id','foundation_inventory_digest','applications'}
    if (not isinstance(request,dict) or set(request)!=keys or type(request['schema_version']) is not int
            or request['schema_version']!=2 or not isinstance(request['applications'],list)
            or not 1<=len(request['applications'])<=16
            or any(not isinstance(request[k],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',request[k]) for k in ('foundation_image_id','foundation_inventory_digest'))):
        raise ValueError('Exact pinned application-set input v2 required')
    rows=request['applications'];seen=set()
    for row in rows:
        if (not isinstance(row,dict) or set(row)!={'file','digest'} or not isinstance(row['file'],str)
                or not re.fullmatch(r'application-[0-9]{2}\.mplug',row['file']) or row['file'] in seen
                or not isinstance(row['digest'],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',row['digest'])):
            raise ValueError('Exact unique application archive leaf/digest required')
        seen.add(row['file'])
    root=Path(root).resolve();inputs=Path(inputs).resolve();original_raw=(root/'distribution-inventory.json').read_bytes()
    if 'sha256:'+hashlib.sha256(original_raw).hexdigest()!=request['foundation_inventory_digest']:
        raise ValueError('Foundation inventory differs from operator-selected pin')
    original=json.loads(original_raw)
    def verify_file(name,expected):
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Inventoried foundation source drift: '+name)
    for name,value in original['files'].items():verify_file(name,value)
    if ast.literal_eval((root/'addons/mp_core/__manifest__.py').read_text(encoding='utf-8')).get('version')!='19.0.0.1.49':
        raise ValueError('Application-set profile requires foundation49')
    verifier=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True))
    incoming={};addon_ids=set()
    with tempfile.TemporaryDirectory(prefix='mp-app-set-') as temporary:
        temporary=Path(temporary)
        for index,row in enumerate(rows):
            path=inputs/row['file']
            if path.is_symlink() or path.resolve().parent!=inputs:raise ValueError('Linked application archive refused')
            raw=path.read_bytes();private=temporary/(str(index)+'.mplug');private.write_bytes(raw)
            checked=verifier.verify(private,expected_digest=row['digest']);manifest=checked.manifest
            require_site_manifest(manifest)
            if Version('0.1.49') not in SpecifierSet(manifest['compatibility']['platform']):raise ValueError('Application excludes pinned foundation')
            plugin=manifest['plugin']['id'];addon=manifest['runtime']['addon_name']
            if plugin in incoming or addon in addon_ids:raise ValueError('Duplicate application/addon identity')
            addon_ids.add(addon);old=original.get('artifacts',{}).get(plugin)
            native_root=root/'addons'/addon
            if native_root.is_symlink() or not native_root.resolve().is_relative_to(root/'addons'):raise ValueError('Unsafe native application target')
            if old:
                if addon!=old['addon'] or not native_root.is_dir():raise ValueError('Existing application addon identity changed')
                if Version(manifest['plugin']['version'])<Version(old['version']):raise ValueError('Application downgrade refused')
                if manifest['plugin']['version']==old['version'] and checked.digest!=old['digest']:
                    raise ValueError('Same version cannot identify changed application bytes')
            elif addon in original['native_addons'] or native_root.exists():raise ValueError('New application cannot shadow foundation/native source')
            descriptor,_,staged=materialize_archive(raw,temporary/'native')
            native=ast.literal_eval((staged/'__manifest__.py').read_text(encoding='utf-8'))
            if native.get('auto_install',False) is not False:raise ValueError('Site-native application requires explicit installation')
            incoming[plugin]=dict(manifest=manifest,raw=raw,digest=checked.digest,descriptor=descriptor,old=old,staged=staged,
                                  native=dict(depends=native.get('depends') or ['base'],auto_install=False,license=native.get('license','unspecified')))
        all_raw={ident:(root/'artifacts'/row['file']).read_bytes() for ident,row in original.get('artifacts',{}).items()}
        # Replacements cannot convert an existing workspace/reference package.
        for plugin,item in incoming.items():
            if item['old']:
                old_path=temporary/'old.mplug';old_path.write_bytes(all_raw[plugin]);require_site_manifest(verifier.verify(old_path).manifest)
            all_raw[plugin]=item['raw']
        registry=validate_composition(list(all_raw.values()));manifests=[]
        for index,(plugin,raw) in enumerate(sorted(all_raw.items())):
            path=temporary/('combined-'+str(index)+'.mplug');path.write_bytes(raw);manifests.append(verifier.verify(path).manifest)
        selected=copy.deepcopy(original['native_addons'])
        for plugin,item in incoming.items():selected[item['descriptor']['addon']]=item['native']
        if any(not set(row['depends'])<=set(selected) for row in selected.values()):raise ValueError('Missing admitted native dependency')
        packaged={m['runtime']['addon_name'] for m in manifests if m['runtime']['kind']=='native'}
        validate_dependencies(manifests,selected,set(selected)-packaged)
        active=set();visited=set()
        def visit(name):
            if name in active:raise ValueError('Cyclic native dependency')
            if name in visited:return
            active.add(name)
            for dependency in selected[name]['depends']:visit(dependency)
            active.remove(name);visited.add(name)
        for name in selected:visit(name)
        updated=copy.deepcopy(original);changes=[];changed_prefixes=[];removed_files=set()
        for plugin,item in sorted(incoming.items()):
            old=item['old'];descriptor=item['descriptor'];addon=descriptor['addon'];prefix='addons/'+addon+'/'
            action='added' if old is None else 'unchanged' if old['digest']==item['digest'] else 'replaced'
            row=dict(plugin_id=plugin,addon=addon,version=descriptor['version'],previous_version=old['version'] if old else None,
                     digest=item['digest'],action=action)
            if not old:
                slot='applications/'+plugin+'/application.toml'
                if slot in updated['policy'].get('application_packages',[]):raise ValueError('New application recipe slot already exists')
                updated['policy'].setdefault('application_packages',[]).append(slot)
                updated['policy']['addons'].append(addon);row['logical_recipe_slot']=slot
            changes.append(row)
            if action=='unchanged':continue
            changed_prefixes.append(prefix)
            if old:
                old_file='artifacts/'+old['file']
                if old_file not in original['files']:raise ValueError('Original archive absent from inventory')
                removed_files.add(old_file)
            archive_name='artifacts/'+descriptor['file']
            if archive_name in original['files'] and archive_name not in removed_files:raise ValueError('Application archive target collision')
            updated['files']={n:v for n,v in updated['files'].items() if not n.startswith(prefix) and n not in removed_files}
            updated['files'].update({prefix+p.relative_to(item['staged']).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in item['staged'].rglob('*') if p.is_file()})
            updated['files'][archive_name]=hashlib.sha256(item['raw']).hexdigest();updated['artifacts'][plugin]=descriptor
        updated['native_addons']=selected;updated['package_composition']=registry
        # All archive,dependency,policy and target-collision checks precede writes.
        for row in changes:
            if row['action']=='unchanged':continue
            item=incoming[row['plugin_id']];destination=root/'addons'/row['addon']
            if item['old']:shutil.rmtree(destination);(root/'artifacts'/item['old']['file']).unlink()
            shutil.copytree(item['staged'],destination)
            with (root/'artifacts'/item['descriptor']['file']).open('xb') as stream:stream.write(item['raw'])
        for name,value in updated['files'].items():verify_file(name,value)
        retained={n:v for n,v in original['files'].items() if not any(n.startswith(p) for p in changed_prefixes) and n not in removed_files}
        if any(updated['files'].get(n)!=v for n,v in retained.items()):raise ValueError('Unselected foundation source changed')
        (root/'distribution-inventory.json').write_text(json.dumps(updated,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    return dict(result='composed_verified_application_set',applications=changes,platform_version='0.1.49',
                foundation_image_id=request['foundation_image_id'],base_inventory_digest=request['foundation_inventory_digest'],
                inventory_digest='sha256:'+hashlib.sha256((root/'distribution-inventory.json').read_bytes()).hexdigest(),
                retained_foundation_files=len(retained),policy_delta_derived=True,application_code_executed=False)


if __name__=='__main__':
    # The builder pins this helper's bytes separately; core49 supplies all
    # validation/materialization code and dependencies used below.
    sys.path[:0]=['/opt/modular/tools','/opt/modular/packages/platform_sdk']
    request=json.loads(Path('/compose-input/request.json').read_bytes())
    result=(apply_set_layer if request.get('schema_version')==2 else apply_layer)('/opt/modular','/compose-input',request)
    print('MP_APPLICATION_LAYER='+json.dumps(result,sort_keys=True))
