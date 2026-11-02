"""Inspect core17 candidate; never deploy or weaken runtime stability guards."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import inspect_image
from modular_platform.release_staging import validate_core_upgrade
from modular_platform.operator_os import OperatorError
target=json.loads((ROOT/'.local/g6-events/operator/target.json').read_bytes());assert target['generation']==19
build=json.loads((ROOT/'docs/evidence/G6/20261102-core17-candidate-01/candidate-build.json').read_bytes())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
base=inspect_image(target['image_id']);new=inspect_image(build['image_id'])
assert base['platform_version']=='0.1.16' and new['platform_version']=='0.1.17'
assert base['inventory']['artifacts']==new['inventory']['artifacts']
assert base['inventory']['policy']==new['inventory']['policy']
assert all(new['native_manifests'][k]==v for k,v in base['native_manifests'].items() if k!='mp_core')
record=dict(base_image=target['image_id'],candidate_image=build['image_id'],inventory_digest=new['inventory_digest'],deployment_changed=False)
before={p['name'].lower():p for p in base['python_metadata']};after={p['name'].lower():p for p in new['python_metadata']}
record['changed_python_distributions']=[k for k in sorted(before.keys()|after.keys()) if before.get(k)!=after.get(k)]
try:
    diff,changes=validate_core_upgrade(base,new,dict(base_image_id=target['image_id'],target_image_id=build['image_id']))
    record.update(result='passed_candidate_not_deployed',source_diff=diff,native_core_changes=changes)
except OperatorError as exc:
    record.update(result='rejected_compiler_runtime',reason=str(exc),next='Derive exact application tree onto approved BB1 OS/Python layers, then revalidate; do not deploy compiler image.')
with (OUT/'candidate-inspection.json').open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(record))
