"""Admit one coherent core14/shell10 image without deploying it."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.deployment import inspect_image
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.release_staging import validate_core_upgrade
from modular_platform.catalog import Catalog
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'core14-upgrade-01.json'
state=f.load(j.LOCAL/'state.json');f.guard(state);assert not MARKER.exists()
native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
assert native.config['generation']==13 and native.config['image_id']==state['image_id']
build=f.load(ROOT/'docs/evidence/G6/20261102-core14-candidate-01/candidate-build.json')
assert build['state']=='built' and not build['deployment_changed']
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
old=inspect_image(state['image_id']);new=inspect_image(build['image_id'])
assert old['platform_version']=='0.1.13' and new['platform_version']=='0.1.14'
assert old['inventory']['artifacts']==new['inventory']['artifacts']==build['artifacts']
assert old['inventory']['policy']==new['inventory']['policy']
assert all(old[k]==new[k] for k in ['python_metadata','python_lock_digest'])
diff,changes=validate_core_upgrade(old,new,dict(base_image_id=state['image_id'],target_image_id=build['image_id']))
assert changes==[dict(addon='mp_core',previous_version='19.0.0.1.13',target_version='19.0.0.1.14',migrations=[]),
    dict(addon='mp_shell',previous_version='19.0.0.1.9',target_version='19.0.0.1.10',migrations=[])]
assert all(old['native_manifests'][n]==new['native_manifests'][n] for n in old['native_manifests'] if n not in ('mp_core','mp_shell'))
assert 'mp_example_notes_stats' not in new['native_manifests']
catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot()
before=native.observer.state(native.observer.read(),catalog)['state']
external=[r for r in before['release_lock']['plugins'] if r['runtime']=='external_service']
assert len(external)==1 and external[0]['version']=='0.1.1'
f.save('candidate-validation.json',dict(result='passed_exact_core14_shell10_candidate_not_deployed',
    image_id=build['image_id'],inventory_digest=new['inventory_digest'],native_core_changes=changes,source_diff=diff,
    native_plugin_artifacts_manifests_python_policy_exact=True,external_metadata_outside_native_image=True,
    retained_external_pins=external,connector_not_in_image=True,live_configuration_generation=13,live_installations=len(before['installations']),
    deployment_changed=False,limits=['Admission only; no staged operation/approval/apply or installed manager qualification yet.']))
f.write(MARKER,dict(state='candidate_validated',image_id=build['image_id'],inventory_digest=new['inventory_digest']))
f.guard(state);print('Core14/shell10 candidate admitted; native plugins/Python/policy and live external metadata retained; not deployed')
