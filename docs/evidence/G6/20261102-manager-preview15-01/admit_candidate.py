"""Admit the corrective core15 image; no deployment or browser retry."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core14-upgrade-01'))
import activate as base
from modular_platform.deployment import inspect_image
from modular_platform.catalog import Catalog
from modular_platform.release_staging import validate_core_upgrade
f=base.f;f.OUTPUT=OUT;MARKER=base.j.LOCAL/'core15-upgrade-01.json'
state,native=base.context();assert native.config['generation']==14 and not MARKER.exists()
build=f.load(ROOT/'docs/evidence/G6/20261102-core15-candidate-01/candidate-build.json')
assert build['state']=='built' and not build['deployment_changed']
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
old=inspect_image(state['image_id']);new=inspect_image(build['image_id'])
assert old['platform_version']=='0.1.14' and new['platform_version']=='0.1.15'
assert old['inventory']['artifacts']==new['inventory']['artifacts']==build['artifacts'] and old['inventory']['policy']==new['inventory']['policy']
assert all(old[k]==new[k] for k in ['python_metadata','python_lock_digest'])
diff,changes=validate_core_upgrade(old,new,dict(base_image_id=state['image_id'],target_image_id=build['image_id']))
assert changes==[dict(addon='mp_core',previous_version='19.0.0.1.14',target_version='19.0.0.1.15',migrations=[])]
assert all(old['native_manifests'][n]==new['native_manifests'][n] for n in old['native_manifests'] if n!='mp_core')
assert new['native_manifests']['mp_shell']['version']=='19.0.0.1.10' and 'mp_example_notes_stats' not in new['native_manifests']
current=native.observer.state(native.observer.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
external=[r for r in current['release_lock']['plugins'] if r['runtime']=='external_service'];assert len(external)==1 and external[0]['version']=='0.1.1'
f.save('candidate-validation.json',dict(result='passed_exact_corrective_core15_candidate_not_deployed',image_id=build['image_id'],inventory_digest=new['inventory_digest'],
    native_core_changes=changes,source_diff=diff,shell10_and_native_plugin_artifacts_manifests_python_policy_exact=True,
    retained_external_pins=external,connector_not_in_image=True,live_configuration_generation=14,live_installations=len(current['installations']),deployment_changed=False))
f.write(MARKER,dict(state='candidate_validated',image_id=build['image_id'],inventory_digest=new['inventory_digest']))
f.guard(state);print('Corrective core15 candidate admitted: only core14→15, shell/plugins/Python/policy unchanged; not deployed')
