"""Checkpoint audit: protected targets, runtime identity and public evidence."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL
from qualify_manager_upgrade_operation import snapshot,sql


def main():
    dest=OUTPUT/'final-audit.json';assert not dest.exists()
    catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    protected=[]
    for name,target,baseline,business in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json')]:
        path=ROOT/target;config=json.loads(path.read_text());reader=DockerObserver(config)
        assert reader.state(reader.read(),catalog)['state']==json.loads((ROOT/baseline).read_text())
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader)
        assert actual==json.loads((ROOT/business).read_text())
        protected.append(dict(target=name,generation=config['generation'],state_business_exact=True,configuration_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    source=json.loads((ROOT/'docs/evidence/G5/20261029-artifact-removal-source-01/planning-core.json').read_text())['source_sha256']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    private=[]
    for path in [LOCAL/'bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password',ROOT/'.local/g5/bootstrap-password']:
        if path.exists():private.append(path.read_text().strip().encode())
    for case in ['uninstall','remove']:
        private.append(json.loads((LOCAL/('source-live-'+case+'-old-pin.json')).read_text())['token'].encode())
    count=0
    for path in OUTPUT.rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts:continue
        raw=path.read_bytes();assert all(not secret or secret not in raw for secret in private),path.name
        if path.suffix=='.json':json.loads(raw)
        if path.suffix=='.py':ast.parse(raw)
        count+=1
    database=sqlite3.connect(LOCAL/'operator/control/control.sqlite3')
    states=list(database.execute('select state,count(*) from operations group by state'))
    assert states==[('completed',12)],states
    config=json.loads((LOCAL/'operator/target.json').read_text());assert config['generation']==9
    assert json.loads((OUTPUT/'survivor-http-assets.json').read_text())['result']=='passed'
    assert json.loads((OUTPUT/'browser/browser-proof.json').read_text())['result']=='passed'
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,qualified_runtime_source_inputs_exact=len(source),independent_operation_states=states,lifecycle_generation=9,public_files_checked=count,known_private_values_checked=len(private),limits=['Bounded checkpoint scan, not SEC-03 whole-release audit. No permission-expanding upgrade, process-crash or clean restore claim.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(value))


if __name__=='__main__':main()
