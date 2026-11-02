"""Retire only verified terminal suspension/recovery helpers and superseded hosts."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from recover import ROOT,context,base,f,j,OUT,PRIVATE,MARKER
from authority import AUTH,physical
from modular_platform.operator_os import protect_directory
from modular_platform.plans import data_digest
def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();record=f.load(MARKER);assert record['state']=='resumed' and f.load(PRIVATE/'recovery-finish.json')['state']=='verified'
assert not (OUT/'retirement.json').exists()
operations=[f.load(PRIVATE/'cycle.json')['suspend']['operation_id'],record['operation_id']]
assert native.store.status(operations[0])['state']=='completed'
assert native.store.status(operations[1])['state']=='revoked' and native.store.status(operations[1])['traffic_resumed']
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
authority=f.load(AUTH);remote=physical(native,authority,'image-retire-worker-before')
assert remote==f.load(PRIVATE/'image-authority-worker-before.json')
runtime=f.load(PRIVATE/'runtime.json');old_worker=runtime['old_container']
present=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
ids=set();old_apps=set()
for operation in operations:
    old=native.store.root/'stages'/operation/'configuration.json';configuration=f.load(old);old_apps.add(configuration['worker_id'])
    ids.update(call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.operation='+operation,'--format','{{.ID}}']).decode().split())
ids|=old_apps&present;assert current not in old_apps
selected={}
for info in json.loads(call(['docker','inspect',*sorted(ids)])):
    if info['Id'] in (current,remote['container_id'],old_worker):continue
    assert not info['State']['Running'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
    labels=info['Config']['Labels'] or {}
    if info['Id'] in old_apps:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
    else:
        assert labels['com.modular.operation'] in operations and labels['com.modular.deployment']==native.config['deployment_id']
        assert info['Name'].startswith('/'+state['project']+'-op-')
    assert info['Image']==native.config['image_id'];selected[info['Id']]=info
observations=0
for line in call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines():
    ident,name=line.split();prefix=state['project']+'-op-';suffix='-dispatch-observe'
    if ident in selected or not name.startswith(prefix) or not name.endswith(suffix):continue
    operation=name[len(prefix):-len(suffix)];receipt=native.store.root/'dispatch-inspections'/operation/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0]
    if info['Image']!=native.config['image_id']:continue
    labels=info['Config']['Labels'] or {};value=f.load(receipt)
    assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id']
    assert value['child']==name and value['action']=='observe' and not info['State']['Running'] and info['State']['ExitCode']==0
    selected[ident]=info;observations+=1
assert old_apps&present<=selected.keys()
archive=protect_directory(ROOT/'.local/retired-docker-20261102/worker-image-recovery')
f.write(PRIVATE/'retirement-marker.json',dict(state='removing_verified_terminal_targets',ids=sorted(selected)))
for ident,info in selected.items():
    with gzip.open(archive/(ident+'.json.gz'),'xb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'xb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
assert not selected.keys()&remaining and {current,remote['container_id'],old_worker}<=remaining
assert physical(native,authority,'image-retire-worker-after')==remote
assert base.snapshot(state,'image-retire-data-after')==f.load(PRIVATE/'data-closed.json')
control=json.loads(f.sql(state,'image-retire-control','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(c) ORDER BY id) FROM mp_dispatch_control c;ROLLBACK;'))
assert len(control)==1 and control[0]['state']=='enabled' and control[0]['release_digest']==data_digest(native.config['published_release'])
f.save('retirement.json',dict(result='retired_exact_completed_suspension_and_changed_image_recovery_helpers',removed_containers=len(selected),
    readonly_observations=observations,superseded_hosts_removed=len(old_apps&present),original_misconfigured_container_already_removed=1,
    private_diagnostics_archived=True,current_host_database_edge_new_worker_preserved=True,old_stopped_worker_retained_pending_final_image_qualification=True,
    actual_checkpoint_images_volumes_and_failed_source_database_retained=True,images_removed=0,volumes_removed=0,no_global_prune_or_force=True,
    current_generation=native.config['generation'],dispatch_generation=control[0]['generation'],all29jobs_and_other17tables_exact=True))
f.write(PRIVATE/'retirement-marker.json',dict(state='verified',removed_containers=len(selected)))
f.guard(state);print('Retired %d exact terminal helpers/old hosts; current22/newworker/DB/edge and actual recovery roles retained'%len(selected),flush=True)
