"""One owned core-only build worktree; main Notes0.2.7 stays unchanged."""
import ast,hashlib,json,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='native_unchanged_enabled_qualified'
previous=f.load(ROOT/'docs/evidence/G6/20261101-unchanged-native-01/qualification.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in previous['source_sha256'].items())
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
assert f.load(j.LOCAL/'operator/target.json')['generation']==5
baseline=json.loads(f.sql(state,'core10-initial-state-01',"SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'notes',(SELECT count(*) FROM mp_example_note),'events',(SELECT count(*) FROM mp_outbox),'state',(SELECT state FROM mp_dispatch_control),'generation',(SELECT generation FROM mp_dispatch_control));"))
assert baseline==dict(jobs=4,notes=24,events=34,state='enabled',generation=28)
marker=j.LOCAL/'core10-upgrade-01.json';assert not marker.exists()
tree=ROOT/'.local/worktrees/g6-core10';assert not tree.exists() and tree.resolve().is_relative_to((ROOT/'.local/worktrees').resolve())
base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
prior=f.load(ROOT/'docs/evidence/G6/20261101-unchanged-native-01/core-only-input-inspection.json')
f.write(marker,dict(state='creating_owned_source_worktree',path=str(tree),branch='codex/g6-core10',base_commit=base))
f.command('core10-worktree-create-01',['git','worktree','add','-b','codex/g6-core10',str(tree),base],timeout=300)
f.command('core10-retain-exact-notes-source-01',['git','-C',str(tree),'restore','--source='+prior['retained_source_commit'],'--worktree','--','platform_addons/mp_example_notes','plugins/notes/plugin.toml'])
archive=j.LOCAL/'org.example.notes-0.2.6.mplug';assert 'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()==prior['artifact_digest']
with zipfile.ZipFile(archive) as zipped:
    prefix='org.example.notes/backend/odoo_addons/mp_example_notes/'
    expected={n:'platform_addons/mp_example_notes/'+n[len(prefix):] for n in zipped.namelist() if n.startswith(prefix) and not n.endswith('/')}
    expected['org.example.notes/plugin.toml']='plugins/notes/plugin.toml'
    for member,path in expected.items():assert (tree/path).read_bytes()==zipped.read(member),path
    actual={p.relative_to(tree).as_posix() for p in (tree/'platform_addons/mp_example_notes').rglob('*') if p.is_file()}
    assert actual=={p for p in expected.values() if p.startswith('platform_addons/')}
assert len(expected)==12
for path in ['platform_addons/mp_core/__manifest__.py','platform_addons/mp_shell/__manifest__.py','platform_addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/restore_executor.py','packages/platform_sdk/modular_platform/restore_continuation.py']:
    assert (tree/path).read_bytes()==(ROOT/path).read_bytes()
assert ast.literal_eval((tree/'platform_addons/mp_core/__manifest__.py').read_text())['version']=='19.0.0.1.10'
assert ast.literal_eval((tree/'platform_addons/mp_shell/__manifest__.py').read_text())['version']=='19.0.0.1.9'
assert ast.literal_eval((ROOT/'platform_addons/mp_example_notes/__manifest__.py').read_text())['version']=='19.0.0.2.7'
assert all(hashlib.sha256((tree/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
source=dict(result='prepared_exact_core_only_source_worktree',utc=datetime.now(timezone.utc).isoformat(),previous_goal_turn='progress',current_goal_turn='progress',base_commit=base,worktree=str(tree.relative_to(ROOT)),branch='codex/g6-core10',retained_notes_source_commit=prior['retained_source_commit'],retained_notes_artifact=prior['artifact_digest'],retained_notes_files=12,core_version='19.0.0.1.10',shell_version='19.0.0.1.9',main_notes_version='19.0.0.2.7',frozen_files=94,protected_configurations=9,fixture_baseline=baseline,deployment_changed=False,candidate_built=False)
f.save('source-worktree.json',source);f.write(marker,dict(state='source_ready',path=str(tree),branch=source['branch'],base_commit=base));f.phase(state,'core10_source_ready');f.guard(state)
print(json.dumps(dict(result=source['result'],retained_notes_files=12,candidate_built=False,deployment_changed=False)))
