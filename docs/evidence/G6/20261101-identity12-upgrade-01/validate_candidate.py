"""Admit only the versioned identity correction with all plugins/Python exact."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_core_upgrade
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='identity12_building'
marker=j.LOCAL/'identity12-upgrade-01.json';record=f.load(marker);assert record['state']=='building'
tree=Path(record['path']);origin=tree/record['build_output'];build=f.load(origin/'candidate-build.json');assert build['state']=='built' and not build['deployment_changed']
assert all(hashlib.sha256((tree/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
current=inspect_image(state['image_id']);candidate=inspect_image(build['image_id'])
assert current['platform_version']==candidate['platform_version']=='0.1.10'
assert candidate['native_manifests']['mp_identity']['version']=='19.0.0.1.2'
assert candidate['native_manifests']['mp_core']['version']=='19.0.0.1.10' and candidate['native_manifests']['mp_shell']['version']=='19.0.0.1.9'
assert candidate['inventory']['artifacts']==current['inventory']['artifacts']==build['artifacts']
assert build['artifacts']['org.example.notes']['digest']=='sha256:95d74f8efae9ecf9ed1d59af496df577f912057c4b400ab0ef8ad280cf0c0ad4'
diff,changes=validate_core_upgrade(current,candidate,dict(base_image_id=state['image_id'],target_image_id=build['image_id']))
assert changes==[dict(addon='mp_identity',previous_version='19.0.0.1.1',target_version='19.0.0.1.2',migrations=[])]
assert {row['path'] for row in diff}=={'addons/mp_identity/scopes.py','addons/mp_identity/__manifest__.py'}
for name in ['candidate-build.json','build.log']:
    dest=OUT/name;assert not dest.exists();shutil.copyfile(origin/name,dest)
f.save('candidate-validation.json',dict(result='passed_identity_only_corrective_candidate',image_id=build['image_id'],inventory_digest=candidate['inventory_digest'],source_base_commit=build['git_base'],artifacts_all_exact=build['artifacts'],native_core_changes=changes,source_diff=diff,SDK_core_shell_Python_policy_unchanged=True,contract_files=94,deployment_changed=False,limits=['Corrective image validation is not installed native/HTTP qualification; earlier identity gates remain invalidated until verified.']))
record.update(state='candidate_validated_not_staged',image_id=build['image_id'],inventory_digest=candidate['inventory_digest']);f.write(marker,record);f.phase(state,'identity12_candidate_validated');f.guard(state)
print(json.dumps(dict(result='passed_identity_only_corrective_candidate',image_id=build['image_id'],changed_files=2,artifacts_all_exact=True)))
