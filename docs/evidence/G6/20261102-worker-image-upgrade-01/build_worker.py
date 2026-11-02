"""Distinct compatible worker release identity using the exact approved layers."""
import hashlib,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
def inspect(image):return json.loads(call(['docker','image','inspect',image]))[0]
config=json.loads((ROOT/'.local/g6-events/operator/worker-target.json').read_bytes())
base_id=config['runtime']['image'].split('@')[1]
assert base_id=='sha256:1d919d0c5cbb05d927dd163f6f7997486e2baf84277cd9cc3b294d2eab68beca'
base=inspect(base_id);assert not (OUT/'worker-build.json').exists()
context=protect_directory(ROOT/'.local/operator/build-contexts/20261102-worker-image-release-01');assert not list(context.iterdir())
alias='modular-document-stats:image-transition-base-'+base_id[7:]
call(['docker','image','tag',base_id,alias]);assert inspect(alias)['Id']==base_id
recipe='FROM '+alias+'\nLABEL org.opencontainers.image.version="1.0.1" org.modular.reference.release="r1-image-transition-01"\n'
(context/'Dockerfile').write_text(recipe,encoding='utf8',newline='\n')
tag='modular-document-stats:release-20261102-image-transition-01'
command=['docker','build','--network','none','--pull=false','-f',str(context/'Dockerfile'),'-t',tag,str(context)]
record=dict(state='building',base_image_id=base_id,tag=tag,recipe=recipe,recipe_sha256=hashlib.sha256(recipe.encode()).hexdigest(),command=command)
marker=ROOT/'.local/operator/builds/20261102-worker-image-release-01.json';_write_new(marker,record)
with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
    with (OUT/'worker-build.log').open('xb') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=120)
    assert result.returncode==0
    new=inspect(tag)
assert new['Id']!=base_id and new['RootFS']==base['RootFS']
assert {k:v for k,v in new['Config'].items() if k!='Labels'}=={k:v for k,v in base['Config'].items() if k!='Labels'}
assert new['Config']['Labels']['org.opencontainers.image.version']=='1.0.1'
call(['docker','image','rm',alias]);assert inspect(base_id)['Id']==base_id
record.update(state='built',image_id=new['Id'],expected_image='modular-document-stats@'+new['Id'],utc=datetime.now(timezone.utc).isoformat(),
    result='passed_distinct_compatible_release_identity',exact_original_runtime_code_OS_Python_layers=True,no_runtime_started=True,
    temporary_alias_removed=True,limits='Release-label-only compatible image; does not claim an API/storage migration or new computation behavior.')
_write_new(OUT/'worker-build.json',record);marker.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(result=record['result'],image_id=new['Id'],no_runtime_started=True)))
