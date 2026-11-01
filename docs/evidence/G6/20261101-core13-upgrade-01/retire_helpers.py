"""Archive exact owned terminal core13 helpers and superseded app, then retire."""
import gzip,json,subprocess,sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from activate import ROOT,OUT,j,f,MARKER,context
from modular_platform.operator_os import protect_directory

def run(args):return subprocess.check_output(args,timeout=30)

def main():
    state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified'
    assert native.store.status(record['operation_id'])['state']=='completed'
    destination=OUT/'retirement.json';assert not destination.exists()
    base=f.load(native.store.root/'stages'/record['operation_id']/'configuration.json')
    current=json.loads(run(['docker','inspect',native.observer._container('app')]))[0]['Id'];old=base['worker_id']
    assert old!=current and native.config['image_id']==record['image_id']
    cutoff=datetime.fromisoformat(f.load(ROOT/'docs/evidence/G6/20261101-core13-candidate-01/candidate-build.json')['utc'])
    ids=run(['docker','ps','--all','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--format','{{.ID}}']).decode().split()
    ids.append(old);infos=json.loads(run(['docker','inspect',*dict.fromkeys(ids)]))
    selected=[]
    for info in infos:
        labels=info['Config']['Labels'] or {};terminal=info['State']['Status']=='exited' and not info['State']['Running']
        if not terminal:continue
        if info['Id']==old:
            assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app' and info['Image']==base['image_id']
        elif not (labels.get('com.modular.deployment')==native.config['deployment_id'] and labels.get('com.modular.operation')
                and info['Name'].startswith('/'+state['project']+'-op-') and datetime.fromisoformat(info['Created'].replace('Z','+00:00'))>=cutoff):continue
        assert info['Id']!=current and info['State']['ExitCode']==0
        selected.append(info)
    assert selected
    private=protect_directory(ROOT/'.local/retired-docker-20261101/core13-upgrade')
    removed=[]
    for info in selected:
        path=private/(info['Id']+'.json.gz');assert not path.exists()
        with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
        if info['HostConfig']['LogConfig']['Type']!='none':
            logs=subprocess.run(['docker','logs',info['Id']],capture_output=True,timeout=30)
            with gzip.open(private/(info['Id']+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
        run(['docker','rm',info['Id']]);removed.append(info['Id'])
    remaining=run(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
    assert not set(removed)&set(remaining)
    assert current in remaining
    report=dict(result='retired_owned_terminal_helpers',removed_containers=len(removed),superseded_app_removed=old in removed,
        current_app_database_edge_preserved=True,volumes_removed=0,images_removed=0,
        current_and_checkpoint_images_retained=True,private_diagnostics_archived=True,no_global_prune=True)
    f.save('retirement.json',report);f.guard(state);print(json.dumps(report))

if __name__=='__main__':main()
