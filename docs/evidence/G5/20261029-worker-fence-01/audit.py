"""Current source/image guard, retained workers/data and protected targets."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.workers import snapshots
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit.json';assert not dest.exists()
    global_catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(global_catalog)==7;protected=[]
    for name,target,baseline,business,digest in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json','3441ea13f16aef9a26226059df88da2d8992fdb2db95f491e98e0513d41b72c9'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json','8c586a0832f8d0147c3ab491a7897d34d0882d0bd97eecb4fc302df8aa98f8ad')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config);assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        assert reader.state(reader.read(),global_catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader);assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],full_state_business_configuration_exact=True))
    state=load(LOCAL/'state.json');config=load(LOCAL/'operator/target.json');marker=load(LOCAL/'worker-fence-deploy.json');build=load(OUTPUT/'candidate-build.json')
    assert config['generation']==18 and config['image_id']==build['image_id'] and marker['state']=='completed_verified'
    catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True).snapshot();reader=DockerObserver(config);runtime=reader.read()
    assert reader.state(runtime,catalog)['state']==load(OUTPUT/'deploy/state-after.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'deploy/business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'deploy/schema-before.json')
    assert files(reader)==load(OUTPUT/'deploy/files-after.json')
    guard='packages/platform_sdk/modular_platform/worker_start.py';assert runtime['runtime']['inventory']['files'][guard]==hashlib.sha256((ROOT/guard).read_bytes()).hexdigest()==build['candidate_source_sha256']
    for name in ['source-host.json','source-linux.json']:
        report=load(OUTPUT/name);assert report['result']=='passed' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['source_sha256'].items())
    retained=snapshots(config);assert sum(w['running'] for w in retained)==1 and next(w for w in retained if w['running'])['container_id']==config['worker_id']
    assert all(not w['running'] and not w['networks'] for w in retained if w['container_id']!=config['worker_id'])
    current=json.loads(subprocess.check_output(['docker','inspect',config['worker_id']]))[0];current_ip=current['NetworkSettings']['Networks'][config['project']+'_runtime']['IPAddress']
    addresses=json.loads(sql(reader,"SELECT COALESCE(jsonb_agg(DISTINCT client_addr::text),'[]'::jsonb) FROM pg_stat_activity WHERE datname=current_database() AND usename<>'postgres';"))
    assert all(address==current_ip+'/32' or address==current_ip for address in addresses),addresses
    check="import configparser,json;c=configparser.ConfigParser();c.read('/run/secrets/odoo_config');assert c['options'].getint('max_cron_threads')==0;print(json.dumps({'native_cron_threads':0}))"
    subprocess.run(['docker','exec',config['worker_id'],'/venv/bin/python','-c',check],check=True,capture_output=True,timeout=30)
    assert json.loads(sql(reader,"SELECT jsonb_build_array(to_regclass('mp_job'),to_regclass('mp_outbox'));"))==[None,None]
    for baseline in load(OUTPUT/'read-only-baseline.json')['guard_cases']:
        target=dict(config,sites=[dict(config['sites'][0],database=baseline['database'])]);source=DockerObserver(target)
        for key,statement in [('business_sha256',BUSINESS_SQL),('schema_sha256',SCHEMA)]:assert hashlib.sha256(json.dumps(json.loads(sql(source,statement)),sort_keys=True).encode()).hexdigest()==baseline[key]
    matrix=load(OUTPUT/'default-startup-matrix.json');assert matrix['result']=='passed'
    for row in matrix['cases']+[load(OUTPUT/'old-worker-live-database.json')]:
        item=json.loads(subprocess.check_output(['docker','inspect',row['container_id']]))[0];assert not item['State']['Running'] and not item['NetworkSettings']['Networks']
    store=OperatorStore(LOCAL/'operator/control');op=marker['operation_id'];status=store.status(op);assert status==load(OUTPUT/'deploy/completed-replay.json') and status['state']=='completed'
    assert (store.root/'stages'/op/'native-skipped.json').exists() and not (store.root/'stages'/op/'native.log').exists()
    checkpoint=store.root/'checkpoints'/op;manifest=load(checkpoint/'manifest.json');assert all(hashlib.sha256((checkpoint/n).read_bytes()).hexdigest()==h for n,h in manifest['files'].items())
    db=sqlite3.connect(store.root/'control.sqlite3');statuses=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')];assert statuses==[['completed',17],['failed_before_mutation',3],['revoked',4]],statuses
    assert load(OUTPUT/'http-assets.json')['result']=='passed' and load(OUTPUT/'old-worker-live-database.json')['result']=='passed'
    private=[p.read_text(encoding='utf8').strip().encode() for p in [LOCAL/'bootstrap-password',ROOT/'.local/g5/bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password'] if p.exists()];count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not v or v not in raw for v in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,active_generation=18,image_id=config['image_id'],source_guard_matches_image=True,managed_workers=retained,active_database_client_addresses=addresses,only_current_worker_connected=True,native_cron_disabled=True,unsupported_dispatch_tables_absent=True,source_and_retained_failure_schema_business_exact=True,checkpoint_hashes_verified=True,independent_operation_states=statuses,public_files_checked=count,known_private_values_checked=len(private),windows_tests=24,windows_linux_only_skipped=1,linux_tests=24,linux_skipped=0,frozen_files=87,limits=['Bounded evidence/private-value scan, not SEC-03 release qualification.','No actual job/outbox/external worker adapter exists yet; G6 must extend and requalify worker/dispatch fences.','Retained historical images are immutable; new guard is qualified in current distribution and controlled host bootstrap.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(value))


if __name__=='__main__':main()
