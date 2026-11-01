"""Corrective identity source, exact old plugins, preinitialized private lock."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.operator_os import protect_directory
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='identity12_source_verified'
source=f.load(ROOT/'docs/evidence/G6/20261101-authority-flush-01/source-checkpoint.json');assert source['successful_cases']==18
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source['source_sha256'].items())
marker=j.LOCAL/'identity12-upgrade-01.json';assert not marker.exists();tree=ROOT/'.local/worktrees/g6-identity12'
assert not tree.exists() and tree.resolve().is_relative_to((ROOT/'.local/worktrees').resolve())
base=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip();f.write(marker,dict(state='creating_owned_identity_source',path=str(tree),base_commit=base,branch='codex/g6-identity12'))
f.command('identity12-worktree-create-01',['git','worktree','add','-b','codex/g6-identity12',str(tree),base],timeout=300)
f.command('identity12-retain-notes-source-01',['git','-C',str(tree),'restore','--source=5daaf2019d313d664243e37d5dbeac2b53674397','--worktree','--','platform_addons/mp_example_notes','plugins/notes/plugin.toml'])
archive=j.LOCAL/'org.example.notes-0.2.6.mplug'
with zipfile.ZipFile(archive) as z:
    prefix='org.example.notes/backend/odoo_addons/mp_example_notes/';paths={n:'platform_addons/mp_example_notes/'+n[len(prefix):] for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')};paths['org.example.notes/plugin.toml']='plugins/notes/plugin.toml'
    assert len(paths)==12 and all((tree/p).read_bytes()==z.read(n) for n,p in paths.items())
assert all((tree/p).read_bytes()==(ROOT/p).read_bytes() for p in ['platform_addons/mp_identity/scopes.py','platform_addons/mp_identity/__manifest__.py'])
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((tree/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
protect_directory(tree/'.local/operator/control/locks')
record=dict(state='source_ready',path=str(tree),base_commit=base,branch='codex/g6-identity12',build_output='docs/evidence/G6/20261101-identity12-candidate-01');f.write(marker,record)
f.save('source-worktree.json',dict(result='prepared_versioned_identity12_corrective_source',base_commit=base,worktree='.local/worktrees/g6-identity12',source_case_proof='../20261101-authority-flush-01/source-checkpoint.json',retained_notes_files=12,retained_notes_digest='sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest(),private_build_lock_initialized=True,frozen_files=94,current_target_generation=6,deployment_changed=False))
f.phase(state,'identity12_source_ready');f.guard(state);print('New identity1.2 source worktree/old Notes.6/private build lock prepared; deployment unchanged.')
