"""Actual stage/manager/CLI in-use refusal; no approval or native mutation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.artifact_removal import validate_removal_image
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import OperationLocks
from modular_platform.operator_store import OperatorStore
from modular_platform.profile_channel import publish_profile
from modular_platform.release_staging import StageStore
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
import r1_probe


def main():
    assert set(p.name for p in OUTPUT.iterdir())=={'probe.py'}
    marker=LOCAL/'source-removal-inuse.json';assert not marker.exists()
    state=json.loads((LOCAL/'state.json').read_text());target=LOCAL/'operator/target.json';config=json.loads(target.read_text())
    fixture=json.loads((LOCAL/'fixtures.json').read_text());assert state['phase']=='artifact_removal_core_ready'
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==7
    derived=json.loads((ROOT/'docs/evidence/G5/20261029-removal-derived-02/candidate-build.json').read_text())
    assert derived['result']=='built_verified_not_deployed' and derived['base_image_id']==config['image_id']
    image=derived['image_id'];control=LOCAL/'operator/control';validator=configuration(ROOT/'.local/operator/trust.json')
    catalog_root=ROOT/'.local/operator/catalog';catalog=Catalog(catalog_root,validator,readonly=True)
    reader=DockerObserver(config);observation=reader.read();before=reader.state(observation,catalog.snapshot())['state']
    business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));count=sql(reader,'SELECT count(*) FROM mp_operation_request;')
    protected=[ROOT/'.local/operator/targets/g5.json',ROOT/'.local/g5-manager-upgrade/operator/target.json',target]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    record=dict(state='staging_only',generation=7,image_id=image);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    store=OperatorStore(control);stages=StageStore(store,config,catalog)
    descriptor=stages.stage(image);_,staged=stages.load(descriptor)
    diff=validate_removal_image(observation['runtime'],staged['runtime'],descriptor,['org.example.notes_labels'])
    assert len(diff)==7
    with OperationLocks(store.root/'locks',config['deployment_id'],[r['site_id'] for r in config['sites']]):
        profile=publish_profile(reader,catalog,staged=(descriptor,staged))
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    write('staged-image.json',descriptor);write('profile-publication.json',profile);write('image-subtraction.json',diff)
    r1_probe.r1.r0.LOCAL=LOCAL;operator=r1_probe.Client(state,fixture,'operator')
    old=next(p for p in before['release_lock']['plugins'] if p['plugin_id']=='org.example.notes_labels')
    nomination=dict(schema_version=1,operation='prepare',operation_type='remove',plugin_id=old['plugin_id'],
        artifact_digest=old['digest'],site_id=state['site_id'],workspace_ids=[],cascade=False)
    code,response=operator.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':operator.csrf})
    write('manager-refusal.json',dict(status=code,response=response))
    assert code==400 and response['error']['code']=='VALIDATION_FAILED',(code,response)
    targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='remove')
             for r in before['installations'] if r['plugin_id']==old['plugin_id']]
    write('cli-nomination.json',dict(operation_type='remove',targets=targets))
    command=[sys.executable,'tools/modular.py','--config',str(ROOT/'.local/operator/trust.json'),'plugin','plan-staged',
        '--input',str(OUTPUT/'cli-nomination.json'),'--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180)
    assert result.returncode!=0 and b'installed or pending native module' in result.stderr
    write('independent-cli-refusal.json',dict(result='denied_before_operation_creation',exit_code=result.returncode,
        reason='Artifact is still needed by an installed or pending native module'))
    assert before==reader.state(reader.read(),catalog.snapshot())['state']
    assert business==json.loads(sql(reader,BUSINESS_SQL)) and schema==json.loads(sql(reader,SCHEMA))
    assert count==sql(reader,'SELECT count(*) FROM mp_operation_request;')
    assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    record['state']='qualified_inuse_refusal_no_operation';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    write('qualification.json',dict(result='passed_actual_inuse_refusal_only',utc=datetime.now(timezone.utc).isoformat(),
        generation=7,base_image_id=config['image_id'],staged_image_id=image,exact_removed_files=7,
        manager_http_refused=400,independent_cli_refused=True,database_business_schema_requests_configuration_exact=True,
        protected_config_hashes=hashes,limits=['Staging/profile publication only; no independent operation/approval/native source removal.','Successful removal/worker/assets/client/survivor verification remain required for LIFE-06.','Restage the same image after a freshly approved uninstall because generation/base configuration will advance.']))
    print(json.dumps(dict(result='passed_actual_inuse_refusal_only',generation=7,manager_refused=True,independent_cli_refused=True,no_native_mutation=True)))


if __name__=='__main__':main()
