"""Compile a portable application-set recipe on an exact sealed foundation49."""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from compose_application import DOCKERFILE
from verify import verify,digest
from application_package import source_path
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.native_scope import require_site_manifest
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory


def read_recipe(path):
    path=Path(path)
    if path.is_symlink() or path.is_junction():raise ValueError('Linked release recipe refused')
    path=path.resolve(strict=True);root=path.parent
    if path.stat().st_size>65536:raise ValueError('Bounded release recipe required')
    raw=path.read_bytes();value=tomllib.loads(raw.decode('utf-8'))
    if (set(value)!={'schema_version','foundation','applications'} or type(value['schema_version']) is not int
            or value['schema_version']!=2 or not isinstance(value['foundation'],dict)
            or set(value['foundation'])!={'kit_manifest','image_id','inventory_digest'}
            or any(not isinstance(v,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in value['foundation'].values())
            or not isinstance(value['applications'],list) or not 1<=len(value['applications'])<=16):
        raise ValueError('Exact application-set release recipe2 required')
    paths=set();plugins=set();addons=set();selected=[]
    verifier=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True))
    with tempfile.TemporaryDirectory(prefix='mp-release-recipe-') as temporary:
        for index,row in enumerate(value['applications']):
            if (not isinstance(row,dict) or set(row)!={'artifact','digest'} or not isinstance(row['artifact'],str)
                    or row['artifact'] in paths or not isinstance(row['digest'],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',row['digest'])):
                raise ValueError('Exact unique release artifact path/digest required')
            paths.add(row['artifact']);source=source_path(root,row['artifact'])
            if not source.is_file() or source.stat().st_size>64*1024*1024:raise ValueError('Bounded regular release artifact required')
            payload=source.read_bytes();private=Path(temporary)/(str(index)+'.mplug');private.write_bytes(payload)
            checked=verifier.verify(private,expected_digest=row['digest']);require_site_manifest(checked.manifest)
            plugin=checked.manifest['plugin']['id'];addon=checked.manifest['runtime']['addon_name']
            if plugin in plugins or addon in addons:raise ValueError('Duplicate release package/addon identity')
            plugins.add(plugin);addons.add(addon)
            selected.append(dict(plugin_id=plugin,addon=addon,version=checked.manifest['plugin']['version'],digest=checked.digest,
                                 artifact=row['artifact'],raw=payload))
    return value,sorted(selected,key=lambda r:r['plugin_id']),'sha256:'+hashlib.sha256(raw).hexdigest()


def expected_policy(before,selected):
    result=copy.deepcopy(before['inventory']['policy'])
    for row in selected:
        if row['plugin_id'] not in before['inventory']['artifacts']:
            if row['addon'] in before['inventory']['native_addons']:raise ValueError('Application addon shadows foundation')
            slot='applications/'+row['plugin_id']+'/application.toml'
            if slot in result.get('application_packages',[]):raise ValueError('Application recipe slot collision')
            result['addons'].append(row['addon']);result.setdefault('application_packages',[]).append(slot)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--foundation-kit',required=True,type=Path);p.add_argument('--recipe',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path);a=p.parse_args()
    recipe,selected,recipe_digest=read_recipe(a.recipe);output=a.output.absolute();receipt=a.receipt.absolute()
    if output.exists() or output.is_symlink() or output.is_junction() or receipt.exists():raise ValueError('Fresh composition output/receipt required;inspect prior attempt')
    if not re.fullmatch('[a-z0-9][a-z0-9-]{2,60}',output.name):raise ValueError('Bounded composition name required')
    kit=a.foundation_kit.resolve();manifest=verify(kit);pin=recipe['foundation']
    if manifest['stage']!='qualified_local_foundation_tasks_1' or 'sha256:'+digest(kit/'kit-inventory.json')!=pin['kit_manifest'] or pin['kit_manifest']!='sha256:396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404':
        raise ValueError('Exact sealed foundation49 kit required')
    images=json.loads((kit/'images.json').read_bytes())
    if images['images']['application']['image_id']!=pin['image_id'] or images['application_inventory_digest']!=pin['inventory_digest']:
        raise ValueError('Recipe foundation image/inventory differs from verified kit')
    base=pin['image_id'];before=inspect_image(base)
    if before['inventory_digest']!=pin['inventory_digest'] or before['platform_version']!='0.1.49':raise ValueError('Selected foundation runtime differs from recipe')
    policy=expected_policy(before,selected)
    if all(before['inventory']['artifacts'].get(r['plugin_id'],{}).get('digest')==r['digest'] for r in selected):raise ValueError('Release recipe has no application change')
    tag='modular-platform:'+output.name
    if subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode==0:raise ValueError('Composition tag exists;do not overwrite')
    output=protect_directory(output);context=output/'context';context.mkdir()
    (context/'Dockerfile').write_text(DOCKERFILE,encoding='utf-8',newline='\n')
    helper=Path(__file__).with_name('application_layer.py');shutil.copyfile(helper,context/helper.name)
    request=dict(schema_version=2,foundation_image_id=base,foundation_inventory_digest=pin['inventory_digest'],applications=[])
    for index,row in enumerate(selected,1):
        name='application-'+str(index).zfill(2)+'.mplug';(context/name).write_bytes(row['raw']);request['applications'].append(dict(file=name,digest=row['digest']))
    (context/'request.json').write_text(json.dumps(request,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    alias='modular-platform:compose-base-'+secrets.token_hex(8)
    record=dict(state='prepared',utc=datetime.now(timezone.utc).isoformat(),tag=tag,foundation=pin,recipe_digest=recipe_digest,
        applications=[{k:v for k,v in row.items() if k!='raw'} for row in selected],request=request,
        helper_sha256=digest(helper),builder_sha256=digest(Path(__file__)),base_alias=alias,
        context_sha256={f.name:digest(f) for f in context.iterdir() if f.is_file()})
    def save():(output/'composition.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    save();subprocess.run(['docker','image','tag',base,alias],check=True)
    assert json.loads(subprocess.check_output(['docker','image','inspect',alias]))[0]['Id']==base
    try:
        record['state']='building';save()
        with (output/'build.log').open('xb') as log:
            result=subprocess.run(['docker','build','--pull=false','--network=none','--no-cache','--build-arg','FOUNDATION_IMAGE='+alias,'-t',tag,str(context)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            record.update(state='build_failed',exit_code=result.returncode);save();raise RuntimeError('Inspect retained build log;do not replay')
        image_id=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]['Id'];record.update(state='built_pending_verification',image_id=image_id);save()
        after=inspect_image(image_id);assert after['platform_version']==before['platform_version']=='0.1.49'
        comparisons={k:before[k]==after[k] for k in ('python','architecture','markers','python_lock_digest','python_metadata')};assert all(comparisons.values())
        assert after['inventory']['policy']==policy and after['inventory']['generated_patches']==before['inventory']['generated_patches']
        assert after['inventory']['reference_composition']==before['inventory']['reference_composition']
        assert not any(after[k] for k in ('modified_files','missing_addon_files','unexpected_addon_files'))
        identities={r['plugin_id'] for r in selected};addons={r['addon'] for r in selected}
        assert all(after['inventory']['artifacts'][k]==v for k,v in before['inventory']['artifacts'].items() if k not in identities)
        assert all(after['inventory']['native_addons'][k]==v for k,v in before['inventory']['native_addons'].items() if k not in addons)
        prefixes=tuple('addons/'+name+'/' for name in addons);archives=set()
        for row in selected:
            actual=after['inventory']['artifacts'][row['plugin_id']];assert all(actual[k]==row[k] for k in ('addon','version','digest'))
            archives.add('artifacts/'+actual['file']);old=before['inventory']['artifacts'].get(row['plugin_id'])
            if old:archives.add('artifacts/'+old['file'])
        old_files=before['inventory']['files'];new_files=after['inventory']['files']
        changed=[n for n in sorted(old_files.keys()|new_files.keys()) if old_files.get(n)!=new_files.get(n)]
        assert changed and all(n.startswith(prefixes) or n in archives for n in changed)
        record.update(state='verified',result='verified_application_set_on_pinned_foundation',image_id=image_id,inventory_digest=after['inventory_digest'],
            platform_version='0.1.49',allowed_changed_files=changed,derived_policy=policy,environment_comparisons=comparisons,
            retained_foundation_files=sum(not n.startswith(prefixes) and n not in archives for n in old_files),
            no_native_application_code_executed_during_assembly=True,trust_or_installation_granted=False)
        save();receipt.parent.mkdir(parents=True,exist_ok=True)
        with receipt.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(record,indent=2)+'\n')
        print(json.dumps(dict(result=record['result'],image_id=image_id,inventory_digest=after['inventory_digest'],applications=len(selected))))
    finally:
        current=subprocess.run(['docker','image','inspect',alias],capture_output=True)
        if current.returncode==0:
            assert json.loads(current.stdout)[0]['Id']==base;subprocess.run(['docker','image','rm',alias],check=True,capture_output=True)

if __name__=='__main__':main()
