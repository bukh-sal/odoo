"""Fixed one-file SDK guard overlay; preserve approved Python/core/artifact bytes."""
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
from modular_platform.release_staging import validate_platform_deploy
from build_removal_candidate import configuration as image_configuration

APPLY="""import hashlib,json,pathlib
root=pathlib.Path('/opt/modular');path=root/'packages/platform_sdk/modular_platform/worker_start.py'
raw=(root/'distribution-inventory.json').read_bytes();before=json.loads(raw)
data=json.loads(pathlib.Path('/tmp/worker-guard-input.json').read_bytes())
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==data['base_inventory_digest']
source=pathlib.Path('/tmp/worker-guard.py').read_bytes();name='packages/platform_sdk/modular_platform/worker_start.py'
assert hashlib.sha256(path.read_bytes()).hexdigest()==before['files'][name]
assert hashlib.sha256(source).hexdigest()==data['inventory']['files'][name]
expected=json.loads(raw);expected['files'][name]=hashlib.sha256(source).hexdigest();assert expected==data['inventory']
path.write_bytes(source);path.chmod(0o444)
(root/'distribution-inventory.json').write_text(json.dumps(expected,sort_keys=True,indent=2)+'\\n')
for name in ['worker-guard-input.json','worker-guard.py','worker-guard-apply.py']:(pathlib.Path('/tmp')/name).unlink()
print('exact one-file guard overlay; no database, artifact or Python rebuild')
"""


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'candidate-build.json';assert not dest.exists()
    target=load(LOCAL/'operator/target.json');base_id=target['image_id'];assert target['generation']==17 and base_id=='sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea'
    source=ROOT/'packages/platform_sdk/modular_platform/worker_start.py';raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    for name in ['source-host.json','source-linux.json']:
        report=load(OUTPUT/name);assert report['result']=='passed' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['source_sha256'].items())
    assert load(OUTPUT/'candidate-read-only.json')['candidate_source_sha256']==digest
    marker=ROOT/'.local/operator/builds/worker-fence-01.json';assert not marker.exists()
    context=ROOT/'.local/operator/build-contexts/worker-fence-01';assert not context.exists();context=protect_directory(context)
    base=inspect_image(base_id);inventory=copy.deepcopy(base['inventory']);path='packages/platform_sdk/modular_platform/worker_start.py';assert inventory['files'][path]!=digest;inventory['files'][path]=digest
    _write_new(context/'worker-guard-input.json',dict(base_inventory_digest=base['inventory_digest'],inventory=inventory));(context/'worker-guard.py').write_bytes(raw);(context/'worker-guard-apply.py').write_text(APPLY,encoding='utf8',newline='\n')
    alias='modular-platform:guard-base-'+base_id[7:];subprocess.run(['docker','image','tag',base_id,alias],capture_output=True,check=True)
    assert subprocess.check_output(['docker','image','inspect',alias,'--format','{{.Id}}']).decode().strip()==base_id
    dockerfile='ARG BASE_IMAGE='+alias+'\nFROM ${BASE_IMAGE}\nUSER root\nCOPY worker-guard-input.json worker-guard.py worker-guard-apply.py /tmp/\nRUN ["/venv/bin/python", "-I", "/tmp/worker-guard-apply.py"]\nUSER 10001:10001\n'
    (context/'Dockerfile').write_text(dockerfile,encoding='utf8',newline='\n');recipe={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in context.iterdir()}
    tag='modular-platform:worker-guard-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz');command=['docker','build','--network','none','--pull=false','-t',tag,str(context)]
    record=dict(state='building',base_image_id=base_id,tag=tag,command=command,recipe_sha256=recipe,candidate_source_sha256=digest,expected_changed_file=path)
    _write_new(marker,record)
    with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
        with (OUTPUT/'build.log').open('xb') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        if r.returncode:raise RuntimeError('Build failed; reconcile exact private build record/log/tag before another action')
        image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip();runtime=inspect_image(image)
    assert source.read_bytes()==raw and recipe=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in context.iterdir()}
    changes=validate_platform_deploy(base,runtime,dict(base_image_id=base_id,target_image_id=image))
    assert changes==[dict(path=path,previous_sha256=base['inventory']['files'][path],target_sha256=digest)]
    assert runtime['inventory']==inventory and image_configuration(image)==image_configuration(base_id)
    old=json.loads(subprocess.check_output(['docker','image','inspect',base_id]))[0]['RootFS']['Layers'];new=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]['RootFS']['Layers'];assert new[:len(old)]==old
    record.update(state='built',result='built_verified_not_deployed',image_id=image,inventory_digest=runtime['inventory_digest'],changed_files=changes,python_runtime_and_native_inventory_exact=True,base_layers_preserved=len(old),utc=datetime.now(timezone.utc).isoformat())
    dest.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))


if __name__=='__main__':main()
