"""Continue recorded build after verified no-launch lock-directory refusal."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='core10_building'
marker=j.LOCAL/'core10-upgrade-01.json';saved=f.load(marker);assert saved['state']=='building'
tree=Path(saved['path']);output=tree/saved['build_output'];record_path=tree/'.local/operator/builds/20261101-core10-candidate-01.json'
record=f.load(record_path);assert record['state']=='building' and record['git_base']==saved['base_commit']
assert not (output/'build.log').exists() and not (output/'candidate-build.json').exists()
assert subprocess.run(['docker','image','inspect',record['tag']],capture_output=True).returncode!=0
assert record['command'][-1]=='.' and record['command'][:4]==['docker','build','-f','deploy/Dockerfile']
assert all(hashlib.sha256((tree/p).read_bytes()).hexdigest()==h for p,h in record['source_sha256'].items())
sys.path.insert(0,str(tree/'packages/platform_sdk'))
from modular_platform.operator_os import ProcessLock,protect_directory
from modular_platform.deployment import inspect_image
lock=tree/'.local/operator/control/locks';assert not lock.exists() and lock.resolve().is_relative_to(tree.resolve())
f.save('build-attempt-01.json',dict(result='pre_Docker_launch_lock_directory_refusal',observed_tool_chunk='381c50',before_Docker_build_or_log=True,image_tag_absent=True,source_hashes_exact=True,diagnosis='Existing builder requires an initialized private candidate-build lock directory. Fresh owned source worktree has no control store. Create only that owned directory and continue the original recorded tag/command/input; no new build attempt/tag or Docker cleanup.',recorded_tag=record['tag']))
protect_directory(lock);saved['state']='build_continuing_recorded_command';f.write(marker,saved)
with ProcessLock(lock,'candidate-build'):
    with (output/'build.log').open('xb') as log:
        result=subprocess.run(record['command'],cwd=tree,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    assert result.returncode==0,'Inspect retained build/daemon state; never repeat without a new diagnosis'
    image_id=subprocess.check_output(['docker','image','inspect',record['tag'],'--format','{{.Id}}']).decode().strip()
    runtime=inspect_image(image_id)
assert all(hashlib.sha256((tree/p).read_bytes()).hexdigest()==h for p,h in record['source_sha256'].items())
report=record|dict(state='built',image_id=image_id,utc=datetime.now(timezone.utc).isoformat(),inventory_digest=runtime['inventory_digest'],artifacts=runtime['inventory']['artifacts'],deployment_changed=False,result='built_not_deployed',preflight_continuation='Main evidence/G6/20261101-core10-upgrade-01/build-attempt-01.json; no prior Docker launch')
(output/'candidate-build.json').write_text(json.dumps(report,indent=2)+'\n');record_path.write_text(json.dumps(report,indent=2)+'\n')
saved['state']='built_needs_artifact_validation';saved['image_id']=image_id;f.write(marker,saved);f.phase(state,'core10_built_needs_validation');f.guard(state)
print(json.dumps(dict(result='built_not_deployed',image_id=image_id,inventory_digest=runtime['inventory_digest'],same_recorded_tag=True)))
