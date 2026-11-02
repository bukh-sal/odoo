"""Admit precisely the versioned finite read-serialization correction; retain exact OS/Python."""
import hashlib,importlib.util,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('current_base',ROOT/'docs/evidence/G6/20261102-notes-stats-ui-source-01/upgrade.py')
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
from modular_platform.release_staging import validate_core_upgrade
base,f,j=m.base,m.f,m.j;f.OUTPUT=OUT
BUILD=OUT.parent/'20261102-core20-candidate-01';DERIVED=OUT.parent/'20261102-core20-candidate-02'
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
def info(image):return json.loads(call(['docker','image','inspect',image]))[0]
def config(value):return {k:value['Config'].get(k) for k in ['User','Entrypoint','Cmd','Env','WorkingDir','Volumes','ExposedPorts','Healthcheck','StopSignal']}
state,native=m.context();assert native.config['generation']==27
build=f.load(BUILD/'candidate-build.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
base_id=native.config['image_id'];source_id=build['image_id'];old=inspect_image(base_id);source=inspect_image(source_id)
assert old['platform_version']=='0.1.19' and source['platform_version']=='0.1.20'
assert old['inventory']['artifacts']==source['inventory']['artifacts'] and old['inventory']['policy']==source['inventory']['policy']
assert old['python_lock_digest']==source['python_lock_digest'] and config(info(base_id))==config(info(source_id))
expected={'addons/mp_core/__manifest__.py','addons/mp_identity/__manifest__.py','addons/mp_identity/models/scoped.py','addons/mp_identity/scopes.py','addons/mp_identity/read_window.py','addons/mp_core/models.py','packages/platform_sdk/modular_platform/projection.py'}
a,b=old['inventory']['files'],source['inventory']['files'];assert {p for p in a.keys()|b.keys() if a.get(p)!=b.get(p)}==expected
changes=old['python_metadata']!=source['python_metadata']
f.save('compiler-inspection.json',dict(result='application_delta_exact',base_image=base_id,compiler_image=source_id,expected_paths=sorted(expected),python_distributions_changed=changes,not_deployed=True))
if changes:
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(DERIVED.name+'.json');assert not record_path.exists() and not DERIVED.exists()
    context=protect_directory(ROOT/'.local/operator/build-contexts'/DERIVED.name);assert not list(context.iterdir())
    aliases=['modular-platform:core20-base-'+base_id[7:],'modular-platform:core20-source-'+source_id[7:]]
    for ident,alias in zip([base_id,source_id],aliases):call(['docker','image','tag',ident,alias]);assert info(alias)['Id']==ident
    recipe='ARG SOURCE_IMAGE='+aliases[1]+'\nARG BASE_IMAGE='+aliases[0]+'\nFROM ${SOURCE_IMAGE} AS source\nFROM ${BASE_IMAGE}\nCOPY --from=source /opt/modular/ /opt/modular/\n'
    (context/'Dockerfile').write_text(recipe,encoding='utf8',newline='\n');DERIVED.mkdir(parents=True)
    tag='modular-platform:core20-runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
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
diff,versions=validate_core_upgrade(old,new,dict(base_image_id=base_id,target_image_id=image_id))
assert versions==[dict(addon='mp_core',previous_version='19.0.0.1.19',target_version='19.0.0.1.20',migrations=[]),dict(addon='mp_identity',previous_version='19.0.0.1.4',target_version='19.0.0.1.5',migrations=[])]
assert {r['path'] for r in diff}==expected
f.save('candidate-admission.json',dict(result='passed_exact_ID03_core_identity_candidate_not_deployed',image_id=image_id,inventory_digest=new['inventory_digest'],base_image_id=base_id,
    native_changes=versions,source_diff=diff,all_four_plugin_artifacts_shell_contracts_OS_Python_exact=True,independent_worker_unchanged=True,approved_for_staging=True))
f.write(j.LOCAL/'core20-upgrade-01.json',dict(state='candidate_validated',image_id=image_id,inventory_digest=new['inventory_digest']))
print(json.dumps(dict(result='candidate_validated_not_deployed',image_id=image_id,compiler_Python_drift=changes)))
