"""Keep exact approved OS/Python layers; copy only the verified application tree."""
import json,hashlib,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'docs/evidence/G6/20261102-notes-stats-candidate-02'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
from modular_platform.release_staging import validate_plugin_core_stability

def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
def info(image):return json.loads(call(['docker','image','inspect',image]))[0]
def config(value):return {k:value['Config'].get(k) for k in ['User','Entrypoint','Cmd','Env','WorkingDir','Volumes','ExposedPorts','Healthcheck','StopSignal']}
target=json.loads((ROOT/'.local/g6-events/operator/target.json').read_text());assert target['generation']==17
build=json.loads((ROOT/'docs/evidence/G6/20261102-notes-stats-candidate-01/candidate-build.json').read_text())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
base_id=target['image_id'];source_id=build['image_id'];base=inspect_image(base_id);source=inspect_image(source_id)
validate_plugin_core_stability(base,source)
assert source['platform_version']==base['platform_version']=='0.1.16'
assert all(source['inventory']['artifacts'][k]==v for k,v in base['inventory']['artifacts'].items())
assert set(source['inventory']['artifacts'])-set(base['inventory']['artifacts'])=={'org.example.notes_stats'}
assert set(base['inventory']['files'])<=set(source['inventory']['files'])
assert all(source['inventory']['files'][k]==v for k,v in base['inventory']['files'].items())
assert base['python_lock_digest']==source['python_lock_digest'] and config(info(base_id))==config(info(source_id))
private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(OUT.name+'.json');assert not record_path.exists() and not OUT.exists()
context=protect_directory(ROOT/'.local/operator/build-contexts'/OUT.name);assert not list(context.iterdir())
aliases=['modular-platform:notes-stats-base-'+base_id[7:],'modular-platform:notes-stats-source-'+source_id[7:]]
for ident,alias in zip([base_id,source_id],aliases):
    call(['docker','image','tag',ident,alias]);assert info(alias)['Id']==ident
recipe='ARG SOURCE_IMAGE='+aliases[1]+'\nARG BASE_IMAGE='+aliases[0]+'\nFROM ${SOURCE_IMAGE} AS source\nFROM ${BASE_IMAGE}\nCOPY --from=source /opt/modular/ /opt/modular/\n'
(context/'Dockerfile').write_text(recipe,encoding='utf8',newline='\n');OUT.mkdir(parents=True)
tag='modular-platform:notes-stats-runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
command=['docker','build','--network','none','--pull=false','-f',str(context/'Dockerfile'),'--build-arg','BASE_IMAGE='+aliases[0],'--build-arg','SOURCE_IMAGE='+aliases[1],'-t',tag,str(context)]
record=dict(state='building',tag=tag,base_image_id=base_id,source_image_id=source_id,command=command,recipe=recipe,recipe_sha256=hashlib.sha256(recipe.encode()).hexdigest(),source_sha256=build['source_sha256'],deployment_changed=False)
_write_new(record_path,record)
with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
    with (OUT/'build.log').open('xb') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    assert result.returncode==0,'Inspect original derivation record without replay'
    ident=info(tag)['Id'];new=inspect_image(ident);image=info(ident);parent=info(base_id)
assert config(image)==config(parent) and image['RootFS']['Layers'][:len(parent['RootFS']['Layers'])]==parent['RootFS']['Layers']
assert new['python_metadata']==base['python_metadata'] and new['python_lock_digest']==base['python_lock_digest']
assert new['inventory']==source['inventory'] and new['inventory_digest']==source['inventory_digest'] and new['native_manifests']==source['native_manifests']
validate_plugin_core_stability(base,new)
for old,alias in zip([base_id,source_id],aliases):assert info(alias)['Id']==old
report=record|dict(state='built',result='built_exact_base_runtime_connector_candidate_not_deployed',image_id=ident,inventory_digest=new['inventory_digest'],artifacts=new['inventory']['artifacts'],base_os_python_layers_exact=True,python_distributions_exact=True,source_application_tree_exact=True)
(OUT/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');record_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=report['result'],image_id=ident,inventory_digest=new['inventory_digest'],not_deployed=True)))
