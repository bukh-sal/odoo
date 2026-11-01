"""Validate exact core-only image before any independent stage enrollment."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_core_upgrade
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='core10_built_needs_validation'
marker=j.LOCAL/'core10-upgrade-01.json';record=f.load(marker);assert record['state']=='built_needs_artifact_validation'
tree=Path(record['path']);origin=tree/record['build_output'];build=f.load(origin/'candidate-build.json')
assert build['image_id']==record['image_id'] and build['state']=='built' and not build['deployment_changed']
assert all(hashlib.sha256((tree/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
current=inspect_image(state['image_id']);candidate=inspect_image(build['image_id'])
assert current['platform_version']=='0.1.9' and candidate['platform_version']=='0.1.10'
assert candidate['native_manifests']['mp_core']['version']=='19.0.0.1.10'
assert candidate['native_manifests']['mp_shell']['version']=='19.0.0.1.9'
assert candidate['native_manifests']['mp_example_notes']['version']=='19.0.0.2.6'
assert candidate['inventory']['artifacts']==current['inventory']['artifacts']==build['artifacts']
assert build['artifacts']['org.example.notes']['digest']=='sha256:95d74f8efae9ecf9ed1d59af496df577f912057c4b400ab0ef8ad280cf0c0ad4'
diff,changes=validate_core_upgrade(current,candidate,dict(base_image_id=state['image_id'],target_image_id=build['image_id']))
assert changes==[dict(addon='mp_core',previous_version='19.0.0.1.9',target_version='19.0.0.1.10',migrations=[]),dict(addon='mp_shell',previous_version='19.0.0.1.8',target_version='19.0.0.1.9',migrations=[])]
for name in ['candidate-build.json','build.log']:
    dest=OUT/name;assert not dest.exists();shutil.copyfile(origin/name,dest)
f.save('candidate-validation.json',dict(result='passed_exact_core_only_candidate',image_id=build['image_id'],inventory_digest=candidate['inventory_digest'],artifacts_all_exact=current['inventory']['artifacts'],python_and_policy_unchanged=True,native_core_changes=changes,source_diff=diff,source_worktree='.local/worktrees/g6-core10',source_base_commit=build['git_base'],frozen_files=94,deployment_changed=False,stage_enrolled=False,limits=['Build and strict immutable source validation are prerequisites, not native upgrade/EVT/browser qualification.','Notes0.2.6 remains exact; its batch flush fix needs the separate Notes0.2.7 upgrade.']))
record['state']='candidate_validated_not_staged';record['inventory_digest']=candidate['inventory_digest'];f.write(marker,record);f.phase(state,'core10_candidate_validated');f.guard(state)
print(json.dumps(dict(result='passed_exact_core_only_candidate',image_id=build['image_id'],core_changes=2,all_artifacts_exact=True,deployment_changed=False)))
