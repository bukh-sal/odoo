"""Admit precisely the versioned Notes/Labels-only read serialization correction; retain exact OS/Python."""
import hashlib,importlib.util,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('current_base',ROOT/'docs/evidence/G6/20261102-notes-stats-ui-source-01/upgrade.py')
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
from modular_platform.release_staging import validate_plugin_core_stability
base,f,j=m.base,m.f,m.j;f.OUTPUT=OUT
BUILD=OUT.parent/'20261102-notes8-labels4-candidate-03';DERIVED=OUT.parent/'20261102-notes8-labels4-candidate-04'
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
def info(image):return json.loads(call(['docker','image','inspect',image]))[0]
def config(value):return {k:value['Config'].get(k) for k in ['User','Entrypoint','Cmd','Env','WorkingDir','Volumes','ExposedPorts','Healthcheck','StopSignal']}
state,native=m.context();assert native.config['generation']==28
build=f.load(BUILD/'candidate-build.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
base_id=native.config['image_id'];source_id=build['image_id'];old=inspect_image(base_id);source=inspect_image(source_id)
assert old['platform_version']==source['platform_version']=='0.1.20'
assert old['inventory']['policy']==source['inventory']['policy']
assert {p for p in old['inventory']['artifacts'] if old['inventory']['artifacts'][p]!=source['inventory']['artifacts'][p]}=={'org.example.notes','org.example.notes_labels'}
assert old['python_lock_digest']==source['python_lock_digest'] and config(info(base_id))==config(info(source_id))
expected={'addons/mp_example_notes/__manifest__.py','addons/mp_example_notes/models.py','addons/mp_example_notes_labels/__manifest__.py','addons/mp_example_notes_labels/models.py','artifacts/org.example.notes-0.2.7.mplug','artifacts/org.example.notes-0.2.8.mplug','artifacts/org.example.notes_labels-0.2.3.mplug','artifacts/org.example.notes_labels-0.2.4.mplug'}

a,b=old['inventory']['files'],source['inventory']['files'];assert {p for p in a.keys()|b.keys() if a.get(p)!=b.get(p)}==expected
changes=old['python_metadata']!=source['python_metadata']
f.save('compiler-inspection.json',dict(result='application_delta_exact',base_image=base_id,compiler_image=source_id,expected_paths=sorted(expected),python_distributions_changed=changes,not_deployed=True))
if changes:
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(DERIVED.name+'.json');assert not record_path.exists() and not DERIVED.exists()
    context=protect_directory(ROOT/'.local/operator/build-contexts'/DERIVED.name);assert not list(context.iterdir())
    aliases=['modular-platform:notes8-labels4-base-'+base_id[7:],'modular-platform:notes8-labels4-source-'+source_id[7:]]
    for ident,alias in zip([base_id,source_id],aliases):call(['docker','image','tag',ident,alias]);assert info(alias)['Id']==ident
    recipe='ARG SOURCE_IMAGE='+aliases[1]+'\nARG BASE_IMAGE='+aliases[0]+'\nFROM ${SOURCE_IMAGE} AS source\nFROM ${BASE_IMAGE}\nCOPY --from=source /opt/modular/ /opt/modular/\n'
    (context/'Dockerfile').write_text(recipe,encoding='utf8',newline='\n');DERIVED.mkdir(parents=True)
    tag='modular-platform:notes8-labels4-runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    command=['docker','build','--network','none','--pull=false','-f',str(context/'Dockerfile'),'-t',tag,str(context)]
    record=dict(state='building',tag=tag,base_image_id=base_id,source_image_id=source_id,command=command,recipe=recipe,aliases=aliases,source_sha256=build['source_sha256'],deployment_changed=False)
    _write_new(record_path,record)
    with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
        with (DERIVED/'build.log').open('xb') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        assert result.returncode==0,'Inspect original derivation; do not replay'
        image_id=info(tag)['Id'];new=inspect_image(image_id)
    layers=info(base_id)['RootFS']['Layers'];assert info(image_id)['RootFS']['Layers'][:len(layers)]==layers
    assert config(info(image_id))==config(info(base_id)) and new['python_metadata']==old['python_metadata']
    assert new['inventory']==source['inventory'] and new['native_manifests']==source['native_manifests']
    report=record|dict(state='built',image_id=image_id,inventory_digest=new['inventory_digest'],base_OS_Python_exact=True,result='built_exact_base_not_deployed')
    (DERIVED/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');record_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
else:image_id=source_id;new=source
validate_plugin_core_stability(old,new)
assert old['native_manifests'].keys()==new['native_manifests'].keys()
versions={'mp_example_notes':('19.0.0.2.7','19.0.0.2.8'),'mp_example_notes_labels':('19.0.0.2.3','19.0.0.2.4')}
for name in old['native_manifests']:
 if name in versions:
  previous,target=versions[name];assert old['native_manifests'][name]['version']==previous and new['native_manifests'][name]['version']==target
  assert {k:v for k,v in old['native_manifests'][name].items() if k!='version'}=={k:v for k,v in new['native_manifests'][name].items() if k!='version'}
 else:assert old['native_manifests'][name]==new['native_manifests'][name]
assert new['python_metadata']==old['python_metadata'] and new['platform_version']==old['platform_version']
diff=sorted(p for p in old['inventory']['files'].keys()|new['inventory']['files'].keys() if old['inventory']['files'].get(p)!=new['inventory']['files'].get(p))
assert set(diff)==expected
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==97 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
artifacts=new['inventory']['artifacts'];assert artifacts['org.example.notes']['version']=='0.2.8' and artifacts['org.example.notes_labels']['version']=='0.2.4'
marker=j.LOCAL/'notes8-labels4-upgrade-01.json';assert not marker.exists()
f.write(marker,dict(state='candidate_validated_not_curated',image_id=image_id,inventory_digest=new['inventory_digest'],build_output=str(BUILD.relative_to(ROOT))))
f.save('candidate-admission.json',dict(result='passed_exact_Notes8_Labels4_candidate_not_deployed',image_id=image_id,inventory_digest=new['inventory_digest'],base_image_id=base_id,source_diff=diff,artifacts=artifacts,native_changes=versions,core_identity_shell_SDK_other_artifacts_OS_Python_exact=True,frozen_files=97,independent_worker_unchanged=True,approved_for_curating=True))
print(json.dumps(dict(result='Notes8_Labels4_candidate_validated_not_curated_or_deployed',image_id=image_id,compiler_Python_drift=changes)))
