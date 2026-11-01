"""Read-only finish of completed removals after short/full ID assertion mismatch."""
import gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from retire_helpers import run
from activate import ROOT,j,f,MARKER,context

state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified'
base=f.load(native.store.root/'stages'/record['operation_id']/'configuration.json')
archives=ROOT/'.local/retired-docker-20261101/core13-upgrade'
infos=[json.loads(gzip.decompress(p.read_bytes())) for p in archives.glob('*.json.gz')]
assert infos
remaining=run(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
current=json.loads(run(['docker','inspect',native.observer._container('app')]))[0]
assert current['Id'] in remaining and current['State']['Running'] and current['Image']==state['image_id']
for info in infos:
    assert info['State']['Status']=='exited' and info['State']['ExitCode']==0 and info['Id'] not in remaining
    assert info['Name'].startswith('/'+state['project'])
assert base['worker_id'] in {i['Id'] for i in infos}
assert native._inspect(native.observer._container('db'))['State']['Running']
assert native._inspect(native.observer._container('edge'))['State']['Running']
report=dict(result='retired_owned_terminal_helpers',removed_containers=len(infos),superseded_app_removed=True,
    current_app_database_edge_preserved=True,volumes_removed=0,images_removed=0,current_and_checkpoint_images_retained=True,
    private_diagnostics_archived=True,no_global_prune=True,
    verification_correction='Retirement succeeded; final assertion compared short app ID with full inventory IDs. This read-only verification normalizes IDs and does not repeat removal.')
f.save('retirement.json',report);f.guard(state);print(json.dumps(report))
