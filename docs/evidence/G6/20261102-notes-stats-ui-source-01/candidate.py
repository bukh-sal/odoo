"""Admit only the NotesStats successor, retaining the exact current OS/Python."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import driver as d
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory,ProcessLock
from modular_platform.operator_store import _write_new
from modular_platform.release_staging import validate_plugin_core_stability
ROOT,OUT,f=d.ROOT,d.OUT,d.f
BUILD=ROOT/'docs/evidence/G6/20261102-notes-stats-ui-candidate-01'
DERIVED=ROOT/'docs/evidence/G6/20261102-notes-stats-ui-candidate-02'

def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
def info(image):return json.loads(call(['docker','image','inspect',image]))[0]
def config(value):return {k:value['Config'].get(k) for k in ['User','Entrypoint','Cmd','Env','WorkingDir','Volumes','ExposedPorts','Healthcheck','StopSignal']}

def application(old,new):
    validate_plugin_core_stability(old,new)
    assert old['platform_version']==new['platform_version']=='0.1.17'
    assert old['inventory']['policy']==new['inventory']['policy']
    assert old['inventory']['native_addons']==new['inventory']['native_addons']
    assert old['native_manifests'].keys()==new['native_manifests'].keys()
    assert all(new['native_manifests'][k]==v for k,v in old['native_manifests'].items() if k!='mp_example_notes_stats')
    assert new['native_manifests']['mp_example_notes_stats']['version']=='19.0.0.1.1'
    assert old['inventory']['artifacts'].keys()==new['inventory']['artifacts'].keys()
    assert all(new['inventory']['artifacts'][k]==v for k,v in old['inventory']['artifacts'].items() if k!='org.example.notes_stats')
    assert new['inventory']['artifacts']['org.example.notes_stats']['digest']==f.load(d.MARKER)['artifact_digest']
    before,after=old['inventory']['files'],new['inventory']['files']
    changed=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
    assert changed and all(k.startswith(('addons/mp_example_notes_stats/','artifacts/org.example.notes_stats')) for k in changed),changed
    return changed

state,native=d.current.context();assert native.config['generation']==23
build=f.load(BUILD/'candidate-build.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
base_id=native.config['image_id'];source_id=build['image_id'];old=inspect_image(base_id);new=inspect_image(source_id)
changed=application(old,new)
assert old['python_lock_digest']==new['python_lock_digest'] and config(info(base_id))==config(info(source_id))
before={p['name'].lower():p for p in old['python_metadata']};after={p['name'].lower():p for p in new['python_metadata']}
python_changed=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
f.save('compiler-inspection.json',dict(result='compiler_only_requires_exact_base_derivation' if python_changed else 'compiler_runtime_exact',
    image_id=source_id,changed_paths=changed,changed_python_distributions=python_changed,not_deployed=True))
if python_changed:
    private=protect_directory(ROOT/'.local/operator/builds');record_path=private/(DERIVED.name+'.json')
    assert not record_path.exists() and not DERIVED.exists()
    context=protect_directory(ROOT/'.local/operator/build-contexts'/DERIVED.name);assert not list(context.iterdir())
    aliases=['modular-platform:notes-ui-base-'+base_id[7:],'modular-platform:notes-ui-source-'+source_id[7:]]
    for ident,alias in zip([base_id,source_id],aliases):
        call(['docker','image','tag',ident,alias]);assert info(alias)['Id']==ident
    recipe='ARG SOURCE_IMAGE='+aliases[1]+'\nARG BASE_IMAGE='+aliases[0]+'\nFROM ${SOURCE_IMAGE} AS source\nFROM ${BASE_IMAGE}\nCOPY --from=source /opt/modular/ /opt/modular/\n'
    (context/'Dockerfile').write_text(recipe,encoding='utf8',newline='\n');DERIVED.mkdir(parents=True)
    tag='modular-platform:notes-ui-runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S%fz')
    command=['docker','build','--network','none','--pull=false','-f',str(context/'Dockerfile'),'-t',tag,str(context)]
    record=dict(state='building',tag=tag,base_image_id=base_id,source_image_id=source_id,command=command,recipe=recipe,
                source_sha256=build['source_sha256'],deployment_changed=False,aliases=aliases)
    _write_new(record_path,record)
    with ProcessLock(ROOT/'.local/operator/control/locks','candidate-build'):
        with (DERIVED/'build.log').open('xb') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        assert result.returncode==0,'Inspect retained attempt, do not replay'
        image_id=info(tag)['Id'];derived=inspect_image(image_id)
    assert config(info(image_id))==config(info(base_id))
    layers=info(base_id)['RootFS']['Layers'];assert info(image_id)['RootFS']['Layers'][:len(layers)]==layers
    assert derived['python_metadata']==old['python_metadata'] and derived['python_lock_digest']==old['python_lock_digest']
    assert derived['inventory']==new['inventory'] and derived['native_manifests']==new['native_manifests']
    application(old,derived)
    report=record|dict(state='built',image_id=image_id,inventory_digest=derived['inventory_digest'],base_layers_python_exact=True,result='built_exact_base_not_deployed')
    (DERIVED/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');record_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    new=derived
else:image_id=source_id
f.save('candidate-admission.json',dict(result='passed_notes_stats_only_candidate',base_image=base_id,candidate_image=image_id,
    inventory_digest=new['inventory_digest'],changed_paths=changed,other_three_artifacts_core_sdk_shell_python_exact=True,
    approved_for_staging=True,deployment_changed=False,browser_verified=False))
record=f.load(d.MARKER);record.update(state='candidate_validated',candidate_image=image_id,candidate_inventory=new['inventory_digest']);f.write(d.MARKER,record)
print(json.dumps(dict(result='candidate_validated_not_deployed',image_id=image_id,compiler_changed_python=python_changed)))
