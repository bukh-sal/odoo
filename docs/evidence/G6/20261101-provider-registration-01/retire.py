"""Archive completed registration/enable helpers; keep the active worker/volume."""
import gzip,json,subprocess,sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from register import ROOT,OUT,j,f,PRIVATE,REGISTRATION,context,worker
from modular_platform.operator_os import protect_directory,_not_link
from modular_platform.worker_operator import WorkerOperator

def call(args):return subprocess.check_output(args,timeout=30)

state,native=context();assert f.load(REGISTRATION)['state']=='verified' and f.load(PRIVATE/'enable.json')['state']=='verified'
assert not (OUT/'retirement.json').exists()
operations=[f.load(REGISTRATION)['operation_id'],f.load(PRIVATE/'enable.json')['operation_id']]
assert all(native.store.status(op)['state']=='completed' for op in operations)
oldapps={f.load(native.store.root/'stages'/op/'configuration.json')['worker_id'] for op in operations}
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]
remote=worker(native,'worker-before-retirement')
cutoff=datetime.fromisoformat(f.load(OUT/'register-bundle.json')['plan']['created_at'].replace('Z','+00:00'))
ids=call(['docker','ps','--all','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--format','{{.ID}}']).decode().split()
infos=json.loads(call(['docker','inspect',*ids,*oldapps]));selected={}
for info in infos:
    if info['State']['Running'] or info['State']['Status']!='exited':continue
    labels=info['Config']['Labels'] or {}
    if info['Id'] in oldapps:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
    elif not (labels.get('com.modular.deployment')==native.config['deployment_id'] and labels.get('com.modular.operation')
            and info['Name'].startswith('/'+state['project']+'-op-') and datetime.fromisoformat(info['Created'].replace('Z','+00:00'))>=cutoff):continue
    assert info['Image']==native.config['image_id'] and info['State']['ExitCode']==0
    assert info['Id'] not in {current['Id'],remote['container_id']};selected[info['Id']]=info
assert oldapps<=selected.keys()
archive=protect_directory(ROOT/'.local/retired-docker-20261101/provider-registration')
for ident,info in selected.items():
    path=archive/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
assert not selected.keys()&set(remaining) and {current['Id'],remote['container_id']}<=set(remaining)
assert worker(native,'worker-after-retirement')==remote
# Retain the authoritative immutable operator key, remove its generated staging
# duplicate only after exact equality and path/ownership checks.
operator=WorkerOperator(native.store,native.target_path,native.target_path.with_name('worker-target.json'))
staged=PRIVATE/'issuer13.pem';authoritative=operator.publisher.keys/'provider13_issuer.pem'
_not_link(staged);_not_link(authoritative)
assert staged.resolve().is_relative_to(PRIVATE.resolve()) and staged.is_file() and staged.read_bytes()==authoritative.read_bytes()
staged.unlink();assert authoritative.is_file()
report=dict(result='retired_owned_terminal_provider_helpers',removed_containers=len(selected),superseded_apps_removed=2,
    active_host_app_database_edge_and_reference_worker_preserved=True,active_public_config_and_authority_volumes_retained=True,
    volumes_removed=0,images_removed=0,current_and_checkpoint_images_retained=True,private_diagnostics_archived=True,
    generated_private_key_staging_duplicate_removed=True,authoritative_operator_keys_preserved=True,no_global_prune=True)
f.save('retirement.json',report);f.guard(state);print(json.dumps(report))
