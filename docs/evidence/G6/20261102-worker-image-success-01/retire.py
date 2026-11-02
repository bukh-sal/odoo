"""Retire exact terminal lifecycle helpers and the now-obsolete old worker runtime."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from approve_runtime import ROOT,OUT,PRIVATE,context,op,base,f,j
from modular_platform.operator_os import protect_directory
def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();assert f.load(PRIVATE/'qualification-marker.json')['state']=='qualified_SVC05'
assert not (OUT/'retirement.json').exists()
before=base.snapshot(state,'image-success-retire-before');assert len(before['mp_job'])==30
remote=base.worker(native,'image-success-retire-worker-before');current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
operations=[f.load(PRIVATE/(a+'.json'))['operation_id'] for a in ['upgrade','enable']]
assert all(native.store.status(o)['state']=='completed' and native.store.status(o)['traffic_resumed'] for o in operations)
present=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split());ids=set();old_apps=set()
for operation in operations:
    old_apps.add(f.load(native.store.root/'stages'/operation/'configuration.json')['worker_id'])
    ids.update(call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.operation='+operation,'--format','{{.ID}}']).decode().split())
ids|=old_apps&present;assert current not in old_apps
selected={}
for info in json.loads(call(['docker','inspect',*sorted(ids)])):
    if info['Id'] in (current,remote['container_id']):continue
    assert not info['State']['Running'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
    labels=info['Config']['Labels'] or {}
    if info['Id'] in old_apps:assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
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
old_runtime=f.load(j.LOCAL/'worker-image-upgrade-01/runtime.json');old_id=old_runtime['old_container'];volume='mp-disposable-document-stats-05-public-config'
old=json.loads(call(['docker','inspect',old_id]))[0];assert old_id not in (current,remote['container_id'])
assert old['Config']['Labels']['com.docker.compose.project']=='mp-disposable-document-stats-05' and not old['State']['Running'] and old['State']['ExitCode']==0
assert old['Image']=='sha256:1d919d0c5cbb05d927dd163f6f7997486e2baf84277cd9cc3b294d2eab68beca'
assert len(old['Mounts'])==1 and old['Mounts'][0]['Name']==volume and not old['Mounts'][0]['RW']
assert op(native).config['runtime']['public_config_volume']!=volume
volume_info=json.loads(call(['docker','volume','inspect',volume]))[0];assert volume_info['Labels']['com.modular.disposable']=='mp-disposable-document-stats-05'
assert set(call(['docker','ps','--all','--no-trunc','--filter','volume='+volume,'--format','{{.ID}}']).decode().split())=={old_id}
archive=protect_directory(ROOT/'.local/retired-docker-20261102/worker-image-success')
code="import hashlib,json,pathlib;r=pathlib.Path('/config');assert {p.name for p in r.iterdir()}=={'config.json','public.pem'};print(json.dumps(dict(config=json.loads((r/'config.json').read_bytes()),public=(r/'public.pem').read_text(),digest=hashlib.sha256((r/'public.pem').read_bytes()).hexdigest())))"
public=json.loads(f.command('image-success-retire-old-public-read',['docker','run','--rm','--network','none','--read-only','--user','10002:10002','--cap-drop','ALL','--log-driver','none','--mount','type=volume,source='+volume+',target=/config,readonly','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code]))
assert public['config']==dict(f.load(PRIVATE/'runtime.json')['scope'],public_key_file='/run/worker/public.pem',key_id='recovery19-key',endpoint_generation=5)
assert public['digest']==remote['public_digest'];f.write(archive/'old-public-config.json',public);f.write(archive/'old-public-volume.json',volume_info)
selected[old_id]=old;f.write(PRIVATE/'retirement-marker.json',dict(state='removing_verified_terminal_targets',ids=sorted(selected),old_public_volume=volume))
for ident,info in selected.items():
    with gzip.open(archive/(ident+'.json.gz'),'xb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'xb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
assert not call(['docker','ps','--all','-q','--filter','volume='+volume]).strip();call(['docker','volume','rm',volume])
gone=subprocess.run(['docker','volume','inspect',volume],capture_output=True,timeout=15);assert gone.returncode!=0
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
assert not selected.keys()&remaining and {current,remote['container_id']}<=remaining
assert base.worker(native,'image-success-retire-worker-after')==remote and base.snapshot(state,'image-success-retire-after')==before
assert json.loads(call(['docker','image','inspect',old['Image']]))[0]['Id']==old['Image']
f.save('retirement.json',dict(result='retired_exact_terminal_success_helpers_and_obsolete_old_worker',removed_containers=len(selected),readonly_observations=observations,
    superseded_hosts_removed=len(old_apps&present),obsolete_worker05_removed=True,volumes_removed=1,old_public_volume=volume,
    old_public_only_configuration_and_private_diagnostics_archived=True,images_removed=0,old_image_retained_as_actual_checkpoint_and_derivation_base=True,
    current_host_worker06_database_edge_config9_authority11_preserved=True,all30jobs_other17tables_exact=True,no_global_prune_or_force=True))
f.write(PRIVATE/'retirement-marker.json',dict(state='verified',removed_containers=len(selected),volumes_removed=1));f.guard(state)
print('Retired %d exact terminal containers and obsolete worker05 public volume; active/current/checkpoint image roles preserved'%len(selected),flush=True)
