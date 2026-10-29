"""Protected targets, default privileges, candidate/source and evidence audit."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL
from qualify_manager_upgrade_operation import snapshot,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    dest=OUTPUT/'final-audit.json';assert not dest.exists()
    catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(catalog)==7
    protected=[]
    for name,target,baseline,business in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config)
        assert reader.state(reader.read(),catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader)
        assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],state_business_exact=True,configuration_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    assert hashlib.sha256((ROOT/'.local/operator/trust.json').read_bytes()).hexdigest()==load(OUTPUT/'catalog.json')['original_trust_unchanged_sha256']
    source=load(ROOT/'docs/evidence/G5/20261029-artifact-removal-source-01/planning-core.json')['source_sha256']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    default=tomllib.loads((ROOT/'plugins/notes_labels/plugin.toml').read_text(encoding='utf8'))
    assert default['plugin']['version']=='0.2.1' and [r['capability'] for r in default['permissions']['requests']]==['org.example.notes:notes.read']
    work=ROOT/'.local/g5-permission-upgrade-source';candidate=load(OUTPUT/'image.json')
    assert all(hashlib.sha256((work/p).read_bytes()).hexdigest()==h for p,h in candidate['source_sha256'].items())
    images=[candidate['image_id'],'sha256:967c4b54371291a54ab5490e438c37358d561fa66e11293943096122a2608bc1','sha256:ea6c34cee2a866b847dff7115674d2a03bd38268c953adf11edc8bc2b572e23c']
    assert subprocess.check_output(['docker','image','inspect',*images,'--format','{{.Id}}']).decode().splitlines()==images
    database=sqlite3.connect(LOCAL/'operator/control/control.sqlite3');states=list(database.execute('select state,count(*) from operations group by state'));assert states==[('completed',14)],states
    config=load(LOCAL/'operator/target.json');assert config['generation']==11 and config['image_id']==candidate['image_id']
    assert load(OUTPUT/'survivor-http-assets.json')['result']=='passed' and load(OUTPUT/'browser/browser-proof.json')['result']=='passed'
    private=[]
    for path in [LOCAL/'bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password',ROOT/'.local/g5/bootstrap-password']:
        if path.exists():private.append(path.read_text(encoding='utf8').strip().encode())
    private.append(load(LOCAL/'permission-upgrade-old-pin.json')['token'].encode())
    count=0
    for path in [*OUTPUT.rglob('*'),*(ROOT/'tests/fixtures/lifecycle_permission_expansion').rglob('*')]:
        if not path.is_file() or '__pycache__' in path.parts:continue
        raw=path.read_bytes();assert all(not secret or secret not in raw for secret in private),path.name
        if path.suffix=='.json':json.loads(raw)
        if path.suffix=='.py':ast.parse(raw)
        if path.suffix=='.toml':tomllib.loads(raw.decode('utf8'))
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,global_catalog_trust_unchanged=True,default_reference_privileges_unchanged=True,qualified_runtime_source_inputs_exact=len(source),isolated_candidate_inputs_exact=len(candidate['source_sha256']),retained_images=images,independent_operation_states=states,lifecycle_generation=11,public_files_checked=count,known_private_values_checked=len(private),limits=['Bounded checkpoint scan, not SEC-03 whole-release audit. No process-crash or clean restore claim.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(value))


if __name__=='__main__':main()
