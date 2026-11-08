"""Compose one independently authored application on an exact sealed core49 kit."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from verify import verify,digest
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory

DOCKERFILE='''ARG FOUNDATION_IMAGE
FROM ${FOUNDATION_IMAGE}
USER 0:0
COPY . /compose-input
RUN /venv/bin/python -B /compose-input/application_layer.py && rm -rf /compose-input
USER 10001:10001
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--foundation-kit',required=True,type=Path)
    p.add_argument('--artifact',required=True,type=Path);p.add_argument('--digest',required=True)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path)
    a=p.parse_args();output=a.output.absolute();receipt=a.receipt.absolute()
    if output.exists() or output.is_symlink() or output.is_junction() or receipt.exists():
        raise ValueError('Fresh owned composition output/receipt required; inspect previous attempts')
    if not re.fullmatch('[a-z0-9][a-z0-9-]{2,60}',output.name):raise ValueError('Bounded composition name required')
    kit=a.foundation_kit.resolve();manifest=verify(kit)
    if manifest['stage']!='qualified_local_foundation_tasks_1' or digest(kit/'kit-inventory.json')!='396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404':
        raise ValueError('Exact sealed core49 Tasks foundation kit required')
    images=json.loads((kit/'images.json').read_bytes());base=images['images']['application']['image_id']
    checked=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(a.artifact,expected_digest=a.digest)
    before=inspect_image(base);plugin=checked.manifest['plugin']['id'];old=before['inventory'].get('artifacts',{}).get(plugin)
    if old is None or checked.manifest['runtime'].get('addon_name')!=old['addon']:
        raise ValueError('The selected artifact must replace an existing application slot')
    if before['inventory_digest']!=images['application_inventory_digest'] or before['platform_version']!='0.1.49':
        raise ValueError('Selected foundation runtime differs from verified kit')
    tag='modular-platform:'+output.name
    if subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode==0:
        raise ValueError('Composition tag already exists; do not overwrite it')
    output=protect_directory(output);context=output/'context';context.mkdir()
    (context/'Dockerfile').write_text(DOCKERFILE,encoding='utf-8',newline='\n')
    helper=Path(__file__).with_name('application_layer.py');shutil.copyfile(helper,context/'application_layer.py')
    (context/'application.mplug').write_bytes(a.artifact.read_bytes())
    request=dict(schema_version=1,foundation_image_id=base,foundation_inventory_digest=before['inventory_digest'],
                 application_digest=checked.digest,application_file='application.mplug')
    (context/'request.json').write_text(json.dumps(request,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    alias='modular-platform:compose-base-'+secrets.token_hex(8)
    record=dict(state='prepared',utc=datetime.now(timezone.utc).isoformat(),tag=tag,foundation_kit_manifest=digest(kit/'kit-inventory.json'),
        request=request,helper_sha256=digest(helper),builder_sha256=digest(Path(__file__)),
        context_sha256={f.name:digest(f) for f in context.iterdir() if f.is_file()},base_alias=alias)
    def save():
        (output/'composition.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    save();subprocess.run(['docker','image','tag',base,alias],check=True)
    assert json.loads(subprocess.check_output(['docker','image','inspect',alias]))[0]['Id']==base
    try:
        record['state']='building';save()
        with (output/'build.log').open('xb') as log:
            result=subprocess.run(['docker','build','--pull=false','--network=none','--no-cache','--build-arg',
                'FOUNDATION_IMAGE='+alias,'-t',tag,str(context)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            record.update(state='build_failed',exit_code=result.returncode);save()
            raise RuntimeError('Inspect private composition build log before another attempt')
        image_id=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]['Id'];record.update(state='built_pending_verification',image_id=image_id);save()
        after=inspect_image(image_id);addon=old['addon'];prefix='addons/'+addon+'/'
        new=after['inventory']['artifacts'][plugin]
        assert new['digest']==checked.digest and new['version']==checked.manifest['plugin']['version']
        assert after['platform_version']==before['platform_version']=='0.1.49'
        comparisons={k:before[k]==after[k] for k in ('python','architecture','markers','python_lock_digest','python_metadata')}
        assert all(comparisons.values()),comparisons
        assert after['inventory']['policy']==before['inventory']['policy']
        assert after['inventory']['generated_patches']==before['inventory']['generated_patches']
        assert all(after['inventory']['native_addons'][name]==row for name,row in before['inventory']['native_addons'].items() if name!=addon)
        assert all(after['inventory']['artifacts'][name]==row for name,row in before['inventory']['artifacts'].items() if name!=plugin)
        assert not any(after[k] for k in ('modified_files','missing_addon_files','unexpected_addon_files'))
        old_files=before['inventory']['files'];new_files=after['inventory']['files']
        differences=[name for name in sorted(set(old_files)|set(new_files)) if old_files.get(name)!=new_files.get(name)]
        assert differences and all(name.startswith(prefix) or name in {'artifacts/'+old['file'],'artifacts/'+new['file']} for name in differences),differences
        record.update(state='verified',result='verified_application_only_image_on_pinned_foundation',image_id=image_id,
            inventory_digest=after['inventory_digest'],platform_version=after['platform_version'],plugin_id=plugin,
            previous_application_version=old['version'],application_version=new['version'],artifact_digest=checked.digest,
            retained_foundation_files=sum(not n.startswith(prefix) and n!='artifacts/'+old['file'] for n in old_files),
            allowed_changed_files=differences,environment_comparisons=comparisons,policy_unchanged=True,
            no_native_application_code_executed_during_assembly=True,trust_or_installation_granted=False)
        save();receipt.parent.mkdir(parents=True,exist_ok=True)
        with receipt.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(record,indent=2)+'\n')
        print(json.dumps({k:record[k] for k in ('result','image_id','inventory_digest','application_version','platform_version')}))
    finally:
        current=subprocess.run(['docker','image','inspect',alias],capture_output=True)
        if current.returncode==0:
            assert json.loads(current.stdout)[0]['Id']==base,'Temporary base alias changed; refuse unrelated untag'
            subprocess.run(['docker','image','rm',alias],check=True,capture_output=True)


if __name__=='__main__':main()
