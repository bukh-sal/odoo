"""Actual read-only source guards; no preparation/approval/native mutation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.artifact_removal import validate_removal_sites
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import OperatorError
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    assert set(p.name for p in OUTPUT.iterdir())=={'probe.py'}
    state=json.loads((LOCAL/'state.json').read_text());target=LOCAL/'operator/target.json';config=json.loads(target.read_text())
    assert state['disposable'] and state['phase']=='lifecycle_reinstalled_all_enabled'
    assert state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==6
    protected=[ROOT/'.local/operator/targets/g5.json',ROOT/'.local/g5-manager-upgrade/operator/target.json',target]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    reader=DockerObserver(config);catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    observed=reader.read();document=reader.state(observed,catalog)
    business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    requests=sql(reader,'SELECT count(*) FROM mp_operation_request;')
    complete=reader.removal_site_inventory(observed)
    assert complete==dict(site_ids=[state['site_id']],complete=True)
    try:validate_removal_sites(document,observed['sites'],['org.example.notes_labels'],observed['runtime'])
    except OperatorError as error:
        assert str(error)=='Artifact is still needed by an installed or pending native module'
        refusal=str(error)
    else:raise AssertionError('Actual installed Labels source was treated as removable')
    assert len(document['state']['installations'])==6 and len(business['notes'])==4 and len(business['boards'])==2
    assert requests==sql(reader,'SELECT count(*) FROM mp_operation_request;')
    assert document==reader.state(reader.read(),catalog)
    assert business==json.loads(sql(reader,BUSINESS_SQL)) and schema==json.loads(sql(reader,SCHEMA))
    assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    report=dict(result='passed_actual_readonly_guard_only',utc=datetime.now(timezone.utc).isoformat(),generation=6,image_id=config['image_id'],
        independently_queried_complete_site_inventory=complete,installed_package_refusal=refusal,
        database_business_schema_state_requests_configs_exact=True,protected_config_hashes=hashes,
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['packages/platform_sdk/modular_platform/artifact_removal.py','packages/platform_sdk/modular_platform/deployment.py','tests/test_artifact_removal.py']},
        limits=['Source guard only; not yet integrated with prepare/independent approval/staged executor.','No source-removal image has been built or activated; LIFE-06 remains not_run.','Native Odoo views and Canvas code/UI are unchanged.'])
    with (OUTPUT/'qualification.json').open('x',encoding='utf8') as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(result=report['result'],complete_site_inventory=True,installed_labels_rejected=True,no_mutation=True)))


if __name__=='__main__':main()
