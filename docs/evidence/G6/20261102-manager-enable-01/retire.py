"""Retire only owned terminal helpers for this completed metadata enablement."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,PRIVATE,MARKER,context,f,base
from modular_platform.operator_os import protect_directory
def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();cycle=f.load(MARKER);record=cycle['enable'];assert record['state']=='preservation_verified' and not (OUT/'enable-retirement.json').exists()
op=record['operation_id'];assert native.store.status(op)['state']=='completed'
configuration=f.load(native.store.root/'stages'/op/'configuration.json');oldapp=configuration['worker_id']
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id'];assert oldapp!=current
remote=base.worker(native,'manager-enable01-worker-before-retirement');assert remote==f.load(PRIVATE/'worker-before.json')
ids=call(['docker','ps','--all','--filter','label=com.modular.operation='+op,'--format','{{.ID}}']).decode().split()
infos=json.loads(call(['docker','inspect',*ids,oldapp]));selected={}
for info in infos:
    if info['State']['Running'] or info['State']['Status']!='exited':continue
    labels=info['Config']['Labels'] or {}
    if info['Id']==oldapp:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
    else:
        assert labels['com.modular.operation']==op and labels['com.modular.deployment']==native.config['deployment_id']
        assert info['Name'].startswith('/'+state['project']+'-op-')
    assert info['Image']==native.config['image_id'] and info['State']['ExitCode']==0 and info['Id'] not in (current,remote['container_id'])
    selected[info['Id']]=info
assert oldapp in selected
archive=protect_directory(ROOT/'.local/retired-docker-20261102/manager-enable01-enable')
for ident,info in selected.items():
    path=archive/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
assert not selected.keys()&set(remaining) and {current,remote['container_id']}<=set(remaining)
assert base.worker(native,'manager-enable01-worker-after-retirement')==remote
f.save('enable-retirement.json',dict(result='retired_owned_terminal_manager_enablement_helpers',removed_containers=len(selected),superseded_apps_removed=1,
    current_host_database_edge_external_worker_preserved=True,private_diagnostics_archived=True,host_workers_replaced=True,
    new_images=0,new_volumes=0,images_removed=0,volumes_removed=0,current_and_actual_checkpoint_roles_retained=True,no_global_prune=True))
f.guard(state);print('Owned metadata enablement terminal helpers/old host app retired; independent worker unchanged; no new images/volumes')
