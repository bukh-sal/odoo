"""Inspect the connector candidate before staging; reject hidden runtime changes."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core15-upgrade-01'))
import activate as base
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_plugin_core_stability
f=base.f;f.OUTPUT=OUT
state,native=base.context();assert native.config['generation']==17
build=f.load(ROOT/'docs/evidence/G6/20261102-notes-stats-candidate-01/candidate-build.json')
assert build['state']=='built' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
old=inspect_image(native.config['image_id']);new=inspect_image(build['image_id'])
assert old['platform_version']==new['platform_version']=='0.1.16'
assert all(new['native_manifests'][k]==v for k,v in old['native_manifests'].items())
assert set(new['native_manifests'])-set(old['native_manifests'])=={'mp_example_notes_stats'}
assert new['native_manifests']['mp_example_notes_stats']['version']=='19.0.0.1.0'
assert all(new['inventory']['artifacts'][k]==v for k,v in old['inventory']['artifacts'].items())
assert set(new['inventory']['artifacts'])-set(old['inventory']['artifacts'])=={'org.example.notes_stats'}
assert new['inventory']['artifacts']['org.example.notes_stats']['digest']==f.load(base.j.LOCAL/'notes-stats-install-01/setup.json')['artifact_digest']
assert new['inventory']['policy']['explicit_install']==old['inventory']['policy']['explicit_install']
validate_plugin_core_stability(old,new)
before={p['name'].lower():p for p in old['python_metadata']};after={p['name'].lower():p for p in new['python_metadata']}
changed=[k for k in sorted(before.keys()|after.keys()) if before.get(k)!=after.get(k)]
passed=not changed and old['python_lock_digest']==new['python_lock_digest']
f.save('candidate-inspection.json',dict(result='passed_connector_only_candidate' if passed else 'rejected_unrequested_python_binary_change',
    base_image=native.config['image_id'],candidate_image=build['image_id'],inventory_digest=new['inventory_digest'],
    old_core_sdk_shell_and_three_artifacts_exact=True,only_new_addon='mp_example_notes_stats',artifact_digest=new['inventory']['artifacts']['org.example.notes_stats']['digest'],
    automatic_install_list_unchanged=True,changed_python_distributions=changed,python_lock_unchanged=old['python_lock_digest']==new['python_lock_digest'],
    deployment_changed=False,approved_for_staging=passed,
    next='Stage and review native C install' if passed else 'Derive from exact approved base layers without adopting rebuilt Python; keep strict guard.'))
record=f.load(base.j.LOCAL/'notes-stats-install-01/setup.json');record.update(state='candidate_validated' if passed else 'compiler_candidate_rejected',candidate_image=build['image_id'],candidate_inventory=new['inventory_digest']);f.write(base.j.LOCAL/'notes-stats-install-01/setup.json',record)
f.guard(state);print(json.dumps(dict(result='passed' if passed else 'rejected',changed_python_distributions=changed,not_deployed=True)))
