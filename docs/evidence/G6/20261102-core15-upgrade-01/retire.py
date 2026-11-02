"""Archive and retire only this verified operation's exact terminal containers."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from activate import ROOT,OUT,PRIVATE,MARKER,context,f,worker
from modular_platform.operator_os import protect_directory
def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified' and not (OUT/'retirement.json').exists()
op=record['operation_id'];assert native.store.status(op)['state']=='completed'
base=f.load(native.store.root/'stages'/op/'configuration.json');oldapp=base['worker_id']
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
remote=worker(native,'core15-worker-before-retirement')
assert remote==f.load(PRIVATE/'worker-before.json') and oldapp!=current
ids=call(['docker','ps','--all','--filter','label=com.modular.operation='+op,'--format','{{.ID}}']).decode().split()
infos=json.loads(call(['docker','inspect',*ids,oldapp]));selected={}
for info in infos:
    if info['State']['Running'] or info['State']['Status']!='exited':continue
    labels=info['Config']['Labels'] or {}
    if info['Id']==oldapp:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app' and info['Image']==base['image_id']
    else:
        assert labels['com.modular.operation']==op and labels['com.modular.deployment']==native.config['deployment_id']
        assert info['Name'].startswith('/'+state['project']+'-op-') and info['Image'] in (base['image_id'],native.config['image_id'])
    assert info['State']['ExitCode']==0 and info['Id'] not in (current,remote['container_id']);selected[info['Id']]=info
assert oldapp in selected
archive=protect_directory(ROOT/'.local/retired-docker-20261102/core15-upgrade')
for ident,info in selected.items():
    path=archive/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
assert not selected.keys()&set(remaining) and {current,remote['container_id']}<=set(remaining)
assert worker(native,'core15-worker-after-retirement')==remote
f.save('retirement.json',dict(result='retired_owned_terminal_core15_helpers',removed_containers=len(selected),
    superseded_apps_removed=1,private_diagnostics_archived=True,current_app_external_worker_database_edge_preserved=True,
    images_removed=0,volumes_removed=0,current_and_actual_checkpoint_images_retained=True,no_global_prune=True))
f.guard(state);print('Core15 operation terminal helpers/superseded app retired; current/worker/recovery assets preserved')
