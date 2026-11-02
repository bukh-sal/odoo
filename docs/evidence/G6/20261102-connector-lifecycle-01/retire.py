"""Archive and retire only completed owned pair/inspection containers."""
import gzip,json,subprocess
from pathlib import Path
from lifecycle import ROOT,OUT,PRIVATE,MARKER,context,base,f
from modular_platform.operator_os import protect_directory

def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();cycle=f.load(MARKER)
assert all(cycle[mode]['state']=='probe_verified' for mode in ('suspend','enable')) and not (OUT/'retirement.json').exists()
remote=base.worker(native,'connector-life-worker-before-retirement')
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id'];selected={}
for mode in ('suspend','enable'):
    op=cycle[mode]['operation_id'];assert native.store.status(op)['state']=='completed'
    oldapp=f.load(native.store.root/'stages'/op/'configuration.json')['worker_id']
    ids=call(['docker','ps','--all','--filter','label=com.modular.operation='+op,'--format','{{.ID}}']).decode().split()
    for info in json.loads(call(['docker','inspect',*ids,oldapp])):
        assert not info['State']['Running'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
        labels=info['Config']['Labels'] or {}
        if info['Id']==oldapp:
            assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
        else:
            assert labels['com.modular.operation']==op and labels['com.modular.deployment']==native.config['deployment_id']
            assert info['Name'].startswith('/'+state['project']+'-op-')
        assert info['Image']==native.config['image_id'] and info['Id'] not in (current,remote['container_id'])
        selected[info['Id']]=info
# Exact read-only receipts distinguish completed owned observations from jobs,
# unrelated projects, active services, and unknown/stale daemon assets.
lines=call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines()
observations=0
for line in lines:
    ident,name=line.split();prefix=state['project']+'-op-';suffix='-dispatch-observe'
    if not name.startswith(prefix) or not name.endswith(suffix) or ident in selected:continue
    op=name[len(prefix):-len(suffix)];receipt=native.store.root/'dispatch-inspections'/op/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0]
    if info['Image']!=native.config['image_id']:continue
    labels=info['Config']['Labels'] or {};record=f.load(receipt)
    assert labels['com.modular.operation']==op and labels['com.modular.deployment']==native.config['deployment_id']
    assert record['child']==name and record['action']=='observe' and info['State']['ExitCode']==0 and not info['State']['Running']
    selected[ident]=info;observations+=1
archive=protect_directory(PRIVATE/'retired-containers')
f.write(PRIVATE/'retirement-marker.json',dict(state='removing_verified_terminal_owned_containers',ids=list(selected)))
for ident,info in selected.items():
    with gzip.open(archive/(ident+'.json.gz'),'xb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'xb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
assert not set(selected)&remaining and {current,remote['container_id']}<=remaining
assert base.worker(native,'connector-life-worker-after-retirement')==remote
report=dict(result='retired_exact_owned_completed_connector_lifecycle_helpers',removed_containers=len(selected),readonly_observations=observations,
    superseded_apps=2,active_host_database_edge_worker_preserved=True,current_checkpoint_images_and_volumes_preserved=True,
    diagnostics_archived_privately=True,new_images=0,new_volumes=0,removed_images=0,removed_volumes=0,no_global_prune=True)
f.save('retirement.json',report);f.write(PRIVATE/'retirement-marker.json',dict(state='verified',removed_containers=len(selected)));f.guard(state)
print('Retired %d exact owned terminal containers; active/current/checkpoint assets preserved'%len(selected),flush=True)
