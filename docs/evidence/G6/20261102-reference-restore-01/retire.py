"""Retire exact exited recovery helpers and old host; retain failed DB/checkpoint."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from recovery import ROOT,context,base,f,j,OUT,PRIVATE,MARKER
from modular_platform.operator_os import protect_directory

def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();record=f.load(MARKER);assert record['state']=='resumed' and f.load(PRIVATE/'finish.json')['state']=='verified'
assert not (OUT/'retirement.json').exists()
operation=record['operation_id'];assert native.store.status(operation)['traffic_resumed']
current=native.observer._container('app');current=json.loads(call(['docker','inspect',current]))[0]['Id']
remote=base.worker(native,'reference-retire-worker-before');assert remote==f.load(PRIVATE/'worker-current.json')
oldapp=f.load(native.store.root/'stages'/operation/'configuration.json')['worker_id'];assert oldapp!=current
ids=call(['docker','ps','--all','--filter','label=com.modular.operation='+operation,'--format','{{.ID}}']).decode().split()
selected={}
for info in json.loads(call(['docker','inspect',*ids,oldapp])):
    if info['Id'] in (current,remote['container_id']) or info['State']['Running']:continue
    assert info['State']['Status']=='exited' and info['State']['ExitCode']==0
    labels=info['Config']['Labels'] or {}
    if info['Id']==oldapp:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
    else:
        assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id']
        assert info['Name'].startswith('/'+state['project']+'-op-')
    assert info['Image']==native.config['image_id'];selected[info['Id']]=info
assert oldapp in selected
observations=0
lines=call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines()
for line in lines:
    ident,name=line.split();prefix=state['project']+'-op-';suffix='-dispatch-observe'
    if ident in selected or not name.startswith(prefix) or not name.endswith(suffix):continue
    op=name[len(prefix):-len(suffix)];receipt=native.store.root/'dispatch-inspections'/op/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0]
    if info['Image']!=native.config['image_id']:continue
    labels=info['Config']['Labels'] or {};value=f.load(receipt)
    assert labels['com.modular.operation']==op and labels['com.modular.deployment']==native.config['deployment_id']
    assert value['child']==name and value['action']=='observe' and not info['State']['Running'] and info['State']['ExitCode']==0
    selected[ident]=info;observations+=1
archive=protect_directory(PRIVATE/'retired-containers');f.write(PRIVATE/'retirement-marker.json',dict(state='removing_verified_terminal_targets',ids=list(selected)))
for ident,info in selected.items():
    with gzip.open(archive/(ident+'.json.gz'),'xb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'xb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
assert not set(selected)&remaining and {current,remote['container_id']}<=remaining
assert base.worker(native,'reference-retire-worker-after')==remote
f.save('retirement.json',dict(result='retired_exact_completed_reference_recovery_helpers',removed_containers=len(selected),readonly_observations=observations,superseded_host_apps=1,
    active_host_database_edge_rotated_worker_preserved=True,failed_database_and_checkpoint_files_images_volumes_retained=True,
    private_diagnostics_archived=True,new_images=0,new_volumes=0,images_removed=0,volumes_removed=0,no_global_prune=True))
f.write(PRIVATE/'retirement-marker.json',dict(state='verified',removed_containers=len(selected)));f.guard(state)
print('Retired %d exact owned exited recovery containers; active/current/failed-source/checkpoint roles retained'%len(selected),flush=True)
