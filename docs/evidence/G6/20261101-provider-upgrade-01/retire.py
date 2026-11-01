"""Retire terminal helpers for the verified metadata upgrade, exact owned IDs."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from upgrade import ROOT,OUT,PRIVATE,MARKER,context,f,previous
from modular_platform.operator_os import protect_directory

def call(args):return subprocess.check_output(args,timeout=30)
state,native=context();marker=f.load(MARKER);assert marker['state']=='verified' and not (OUT/'retirement.json').exists()
op=marker['operation_id'];assert native.store.status(op)['state']=='completed'
oldapp=f.load(native.store.root/'stages'/op/'configuration.json')['worker_id']
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
archive=protect_directory(ROOT/'.local/retired-docker-20261101/provider-upgrade')
if sys.argv[1:]==['--verify-only']:
    saved=[json.loads(gzip.decompress(p.read_bytes())) for p in archive.glob('*.json.gz')]
    assert saved and oldapp in {i['Id'] for i in saved}
    for info in saved:
        labels=info['Config']['Labels'] or {}
        assert info['State']['Status']=='exited' and info['State']['ExitCode']==0 and info['Image']==native.config['image_id']
        assert info['Id']==oldapp or (labels.get('com.modular.operation')==op and labels.get('com.modular.deployment')==native.config['deployment_id'])
    remaining=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
    remote=previous.worker(native,'worker-after-successor-retirement-02')
    assert not {i['Id'] for i in saved}&set(remaining) and {current,remote['container_id']}<=set(remaining)
    assert remote==f.load(PRIVATE/'worker-before.json')
    f.save('retirement.json',dict(result='retired_owned_terminal_upgrade_helpers',removed_containers=len(saved),superseded_apps_removed=1,
        private_diagnostics_archived=True,active_host_worker_database_edge_preserved=True,new_images=0,new_volumes=0,
        images_removed=0,volumes_removed=0,active_and_recovery_assets_retained=True,no_global_prune=True,
        post_delete_short_vs_full_id_assertion_corrected_without_repeating_deletion=True))
    f.guard(state);print('Archived exact retired IDs reconciled; current full ID and unchanged reference worker retained');sys.exit(0)
assert not sys.argv[1:]
remote=previous.worker(native,'worker-before-successor-retirement')
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
    assert info['Image']==native.config['image_id'] and info['State']['ExitCode']==0
    assert info['Id'] not in {current,remote['container_id']};selected[info['Id']]=info
assert oldapp in selected
for ident,info in selected.items():
    path=archive/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    call(['docker','rm',ident])
remaining=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
assert not selected.keys()&set(remaining) and {current,remote['container_id']}<=set(remaining)
assert previous.worker(native,'worker-after-successor-retirement')==remote
f.save('retirement.json',dict(result='retired_owned_terminal_upgrade_helpers',removed_containers=len(selected),
    superseded_apps_removed=1,private_diagnostics_archived=True,active_host_worker_database_edge_preserved=True,
    new_images=0,new_volumes=0,images_removed=0,volumes_removed=0,active_and_recovery_assets_retained=True,no_global_prune=True))
f.guard(state);print('Owned terminal upgrade helpers archived and retired; active services and recovery assets retained')
