"""Derive exact source subtraction from an approved immutable runtime image.

The normal compiler image supplies only the desired verified source inventory.
Its rebuilt Python binaries are not adopted. No live mounts, database, secrets,
plugin imports, caller commands or publication are part of this build.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.artifact_removal import validate_removal_image
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import ProcessLock, protect_directory
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest


SUBTRACT = r'''import hashlib,json,pathlib,re
root=pathlib.Path('/opt/modular').resolve()
source=pathlib.Path('/tmp/mp-source-removal.json')
data=json.loads(source.read_bytes())
assert set(data)=={'base_inventory_digest','inventory','removed_files','addons'}
raw=(root/'distribution-inventory.json').read_bytes()
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==data['base_inventory_digest']
before=json.loads(raw);after=data['inventory'];names=data['removed_files']
assert names and len(set(names))==len(names)
assert after['files']=={name:value for name,value in before['files'].items() if name not in names}
assert set(names)<=before['files'].keys()
assert all(re.fullmatch(r'[a-z_][a-z0-9_]*',addon) for addon in data['addons'])
prefixes=tuple('addons/'+addon+'/' for addon in data['addons'])
archives={'artifacts/'+entry['file'] for entry in before.get('artifacts',{}).values() if entry['addon'] in data['addons']}
assert all(name.startswith(prefixes) or name in archives for name in names)
for name in names:
    path=root/name
    assert path.resolve()==path and path.is_relative_to(root) and path.is_file() and not path.is_symlink()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before['files'][name]
for name in names:(root/name).unlink()
for addon in data['addons']:
    directory=root/'addons'/addon
    assert directory.resolve()==directory and directory.is_relative_to(root/'addons') and not directory.is_symlink()
    for path in sorted(directory.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        assert path.is_dir() and not path.is_symlink(),'Uninventoried source remained in removed addon'
        path.rmdir()
    directory.rmdir()
(root/'distribution-inventory.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
source.unlink();pathlib.Path('/tmp/mp-source-subtract.py').unlink()
print(json.dumps({'removed_inventoried_files':len(names),'database_or_filestore_access':False,'python_runtime_rebuilt':False}))
'''


def configuration(image):
    value=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]['Config']
    return {key:value.get(key) for key in ('User','Entrypoint','Cmd','Env','WorkingDir','Volumes','ExposedPorts','Healthcheck','StopSignal')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-image',required=True);parser.add_argument('--inventory-image',required=True)
    parser.add_argument('--plugin',action='append',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or not re.fullmatch('[A-Za-z0-9_-]+',output.name):
        raise ValueError('Fresh named G5 evidence directory required')
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(output.name+'.json')
    if record_path.exists():raise RuntimeError('Existing derivation attempt must be reconciled, never blindly rebuilt')
    base=inspect_image(args.base_image);inventory_source=inspect_image(args.inventory_image)
    base_config=configuration(args.base_image)
    if base_config['User']!='10001:10001' or base_config['Volumes']:
        raise ValueError('Qualified immutable non-root, no-volume base image required')
    # BuildKit treats bare sha256:... FROM values as repository names. Bind a
    # local alias to this exact ID, then recheck its ID/runtime/parent layers.
    base_alias='modular-platform:removal-base-'+args.base_image[7:]
    subprocess.run(['docker','image','tag',args.base_image,base_alias],check=True,capture_output=True)
    if subprocess.check_output(['docker','image','inspect',base_alias,'--format','{{.Id}}']).decode().strip()!=args.base_image:
        raise ValueError('Local base alias differs from the selected immutable image')
    expected=copy.deepcopy(base)
    for key in ('inventory','inventory_digest','native_manifests'):expected[key]=copy.deepcopy(inventory_source[key])
    descriptor=dict(base_image_id=args.base_image,target_image_id='sha256:'+'0'*64,
        inventory_digest=expected['inventory_digest'],runtime_digest=data_digest(expected))
    diff=validate_removal_image(base,expected,descriptor,args.plugin)
    addons=sorted(base['inventory']['artifacts'][key]['addon'] for key in args.plugin)
    if any(not re.fullmatch('[a-z_][a-z0-9_]*',name) for name in addons):raise ValueError('Canonical native addon identity required')
    raw=json.dumps(expected['inventory'],sort_keys=True,indent=2)+'\n'
    if 'sha256:'+hashlib.sha256(raw.encode()).hexdigest()!=expected['inventory_digest']:
        raise ValueError('Compiler inventory serialization is not the exact expected format')
    context=ROOT/'.local/operator/build-contexts'/output.name
    if context.exists():raise RuntimeError('Existing derivation context requires reconciliation')
    context=protect_directory(context);output.mkdir(parents=True)
    payload=dict(base_inventory_digest=base['inventory_digest'],inventory=expected['inventory'],removed_files=[r['path'] for r in diff],addons=addons)
    _write_new(context/'removal-input.json',payload)
    (context/'subtract.py').write_text(SUBTRACT,encoding='utf8',newline='\n')
    dockerfile='ARG BASE_IMAGE='+base_alias+'\nFROM ${BASE_IMAGE}\nUSER root\nCOPY removal-input.json /tmp/mp-source-removal.json\nCOPY subtract.py /tmp/mp-source-subtract.py\nRUN ["/venv/bin/python", "-I", "/tmp/mp-source-subtract.py"]\nUSER 10001:10001\n'
    (context/'Dockerfile').write_text(dockerfile,encoding='utf8',newline='\n')
    assert set(p.name for p in context.iterdir())=={'Dockerfile','subtract.py','removal-input.json'}
    tag='modular-platform:removal-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    command=['docker','build','--network','none','--pull=false','-f',str(context/'Dockerfile'),'--build-arg','BASE_IMAGE='+base_alias,'-t',tag,str(context)]
    recipe={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in context.iterdir()}
    record=dict(state='building',tag=tag,command=command,base_image_id=args.base_image,inventory_source_image_id=args.inventory_image,
        plugins=args.plugin,expected_inventory_digest=expected['inventory_digest'],recipe_sha256=recipe,
        base_alias=base_alias,tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),output=str(output.relative_to(ROOT)))
    _write_new(record_path,record)
    with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
        with (output/'build.log').open('xb') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        if result.returncode:
            record.update(state='failed',exit_code=result.returncode)
            record_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
            raise RuntimeError('Removal derivation failed; retain build/context/log and reconcile before retry')
        image_id=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
        runtime=inspect_image(image_id)
    assert recipe=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in context.iterdir()}
    actual_descriptor=dict(base_image_id=args.base_image,target_image_id=image_id,inventory_digest=runtime['inventory_digest'],runtime_digest=data_digest(runtime))
    actual_diff=validate_removal_image(base,runtime,actual_descriptor,args.plugin)
    assert actual_diff==diff and runtime==expected and configuration(image_id)==base_config
    assert subprocess.check_output(['docker','image','inspect',base_alias,'--format','{{.Id}}']).decode().strip()==args.base_image
    base_layers=json.loads(subprocess.check_output(['docker','image','inspect',args.base_image]))[0]['RootFS']['Layers']
    target_layers=json.loads(subprocess.check_output(['docker','image','inspect',image_id]))[0]['RootFS']['Layers']
    assert target_layers[:len(base_layers)]==base_layers
    report=record|dict(state='built',result='built_verified_not_deployed',utc=datetime.now(timezone.utc).isoformat(),image_id=image_id,
        removed_files=diff,python_metadata_exact=True,image_execution_configuration_exact=True,compiled_source_inventory_exact=True,base_layers_preserved=len(base_layers),
        deployment_changed=False,limits=['No native uninstall/source-removal operation has run. The independent plan/approval/executor must still reject every in-use site.'])
    (output/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    record_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result=report['result'],image_id=image_id,removed_files=len(diff),python_metadata_exact=True,output=str(output.relative_to(ROOT)))))


if __name__=='__main__':main()
