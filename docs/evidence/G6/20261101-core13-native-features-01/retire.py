"""Retire only completed feature helpers and the two replaced app containers."""
import gzip,json,subprocess,sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from run import ROOT,OUT,j,f,context
from modular_platform.operator_os import protect_directory

def command(args):return subprocess.check_output(args,timeout=30)

state,native=context()
assert f.load(j.LOCAL/'core13-feature-runner.json')['state']=='completed'
operations=[f.load(j.LOCAL/('core13-feature-'+a+'.json')) for a in ['suspend','enable']]
assert all(r['state']=='verified' and native.store.status(r['operation_id'])['state']=='completed' for r in operations)
assert not (OUT/'retirement.json').exists()
oldapps={f.load(native.store.root/'stages'/r['operation_id']/'configuration.json')['worker_id'] for r in operations}
current=json.loads(command(['docker','inspect',native.observer._container('app')]))[0]
assert current['State']['Running'] and current['Id'] not in oldapps
cutoff=datetime.fromisoformat(f.load(OUT/'suspend-bundle.json')['plan']['created_at'].replace('Z','+00:00'))
ids=command(['docker','ps','--all','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--format','{{.ID}}']).decode().split()
infos=json.loads(command(['docker','inspect',*ids,*oldapps]))
selected={}
for info in infos:
    if info['State']['Status']!='exited' or info['State']['Running']:continue
    labels=info['Config']['Labels'] or {}
    if info['Id'] in oldapps:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
    elif not (labels.get('com.modular.deployment')==native.config['deployment_id'] and labels.get('com.modular.operation')
            and info['Name'].startswith('/'+state['project']+'-op-') and datetime.fromisoformat(info['Created'].replace('Z','+00:00'))>=cutoff):continue
    assert info['Image']==native.config['image_id'] and info['State']['ExitCode']==0 and info['Id']!=current['Id']
    selected[info['Id']]=info
assert oldapps<=selected.keys()
private=protect_directory(ROOT/'.local/retired-docker-20261101/core13-native-features')
for ident,info in selected.items():
    path=private/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    if info['HostConfig']['LogConfig']['Type']!='none':
        logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
        with gzip.open(private/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
    command(['docker','rm',ident])
remaining=command(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
assert not selected.keys()&set(remaining) and current['Id'] in remaining
report=dict(result='retired_owned_terminal_feature_helpers',removed_containers=len(selected),superseded_apps_removed=2,
    current_app_database_edge_preserved=True,current_and_checkpoint_images_retained=True,volumes_removed=0,images_removed=0,
    private_diagnostics_archived=True,normal_job_process_auto_removed=True,no_global_prune=True)
f.save('retirement.json',report);f.guard(state);print(json.dumps(report))
