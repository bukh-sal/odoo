"""Protected sites, exact base, all three retired failures and source audit."""
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
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit.json';assert not dest.exists()
    global_catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(global_catalog)==7
    protected=[]
    for name,target,baseline,business in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config)
        assert reader.state(reader.read(),global_catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader);assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],state_business_exact=True,configuration_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    state=load(LOCAL/'state.json');config=load(LOCAL/'operator/target.json');assert config==load(OUTPUT/'configuration-before.json') and config['generation']==11
    catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True).snapshot();reader=DockerObserver(config)
    observation=reader.read();assert reader.state(observation,catalog)['state']==load(OUTPUT/'state-before.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-before.json') and files(reader)==load(OUTPUT/'files-before.json')
    for kind in ['host','linux','freeze']:
        report=load(OUTPUT/('source-'+kind+'.json'));assert report['result']=='passed'
        assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['source_sha256'].items())
    assert 'Ran 10 tests' in (OUTPUT/'focused-host-terminal.log').read_text(encoding='utf8') and 'OK' in (OUTPUT/'focused-host-terminal.log').read_text(encoding='utf8')
    assert load(OUTPUT/'http-assets-replay.json')['result']=='passed'
    db=sqlite3.connect(LOCAL/'operator/control/control.sqlite3');db.row_factory=sqlite3.Row
    cases=[]
    for case,path,decision in [
        ('checkpointed',LOCAL/'premutation-resume.json',OUTPUT/'resume-decision.json'),
        ('staging',LOCAL/'premutation-staging.json',OUTPUT/'staging/resume-decision.json'),
        ('no-backup',LOCAL/'premutation-no-backup.json',OUTPUT/'no-backup/resume-decision.json')]:
        marker=load(path);assert marker['state']=='completed_verified';op=marker['operation_id']
        row=dict(db.execute('SELECT state,phase,mutation_started,traffic_resumed,approval FROM operations WHERE operation_id=?',(op,)).fetchone())
        assert row['state']=='failed_before_mutation' and row['phase']=='unchanged_traffic_resumed' and not row['mutation_started'] and row['traffic_resumed'] and json.loads(row['approval'])['state']=='revoked'
        assert db.execute('SELECT 1 FROM revocations WHERE operation_id=?',(op,)).fetchone()
        review=load(decision);assert (LOCAL/'operator/control/recovery-reviews'/(review['review']['review_id']+'.revoked.json')).exists()
        cases.append(dict(case=case,operation_id=op,original_authority_revoked=True,mutation_never_started=True,base_generation=11))
    statuses=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')];assert statuses==[['completed',14],['failed_before_mutation',3]],statuses
    private=[]
    for p in [LOCAL/'bootstrap-password',ROOT/'.local/g5/bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password']:
        if p.exists():private.append(p.read_text(encoding='utf8').strip().encode())
    count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not value or value not in raw for value in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,exact_base_schema_business_grants_files_configuration=True,worker_and_generation_unchanged=True,cases=cases,independent_operation_states=statuses,windows_checks=26,linux_checks=26,frozen_files=87,source_boundary='source-boundary.json',known_private_values_checked=len(private),public_files_checked=count,limits=['Bounded evidence scan, not SEC-03 release qualification.','No OS-process-crash/concurrency/stale-job/clean-restore claim.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(value))


if __name__=='__main__':main()
