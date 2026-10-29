"""Read-only retained targets, effects, source and terminal-replay audit."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-dispatch'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.native_executor import NativeExecutor
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.workers import snapshots
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit.json';assert not dest.exists()
    catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(catalog)==7
    protected=[]
    for name,target,baseline,business,digest in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json','3441ea13f16aef9a26226059df88da2d8992fdb2db95f491e98e0513d41b72c9'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json','8c586a0832f8d0147c3ab491a7897d34d0882d0bd97eecb4fc302df8aa98f8ad')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config);assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        assert reader.state(reader.read(),catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader);assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],full_state_business_configuration_exact=True))
    life=ROOT/'.local/g5-lifecycle';life_state=load(life/'state.json');life_config=load(life/'operator/target.json');baseline=ROOT/'docs/evidence/G5/20261029-worker-fence-01/deploy'
    assert life_config==load(baseline/'configuration-after.json') and life_config['generation']==18
    isolated=Catalog(ROOT/life_state['operator_catalog'],configuration(ROOT/life_state['operator_trust_config']),readonly=True).snapshot();assert len(isolated)==8
    life_reader=DockerObserver(life_config);assert life_reader.state(life_reader.read(),isolated)['state']==load(baseline/'state-after.json')
    assert json.loads(sql(life_reader,BUSINESS_SQL))==load(baseline/'business-after.json') and json.loads(sql(life_reader,SCHEMA))==load(baseline/'schema-after.json')
    assert files(life_reader)==load(baseline/'files-after.json')
    with sqlite3.connect(life/'operator/control/control.sqlite3') as db:
        states=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')]
    assert states==[['completed',17],['failed_before_mutation',3],['revoked',4]],states
    protected.append(dict(target='lifecycle',generation=18,full_state_business_schema_files_configuration_exact=True,operation_states=states))
    state=load(LOCAL/'state.json');config=load(LOCAL/'operator/target.json');recovered=OUTPUT/'recovery';op=load(LOCAL/'dispatch-fault.json')['operation_id']
    assert state['phase']=='dispatch_restored_resumed' and config['generation']==20 and config['project']=='mp-r0-r1dispefb95a06d78f'
    assert config==load(recovered/'configuration-restored.json') and config['image_id']==life_config['image_id']
    reader=DockerObserver(config);assert reader.state(reader.read(),isolated)['state']==load(recovered/'state-restored.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(recovered/'business-before.json') and json.loads(sql(reader,SCHEMA))==load(recovered/'schema-before.json')
    assert files(reader)==load(recovered/'files-restored.json')
    store=OperatorStore(LOCAL/'operator/control');status=store.status(op);assert status['state']=='revoked' and status['phase']=='restore_traffic_resumed' and status['traffic_resumed'] and status['mutation_started']
    recovery=RestoreExecutor(NativeExecutor(store,LOCAL/'operator/target.json',ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config'])))
    assert not any(recovery._supported_effects(config['sites'][0]['database']).values())
    replay=[]
    for filename,method,expected in [('restore-decision.json',recovery.execute,'Fresh-target recovery is permitted only before traffic resumes'),('resume-decision.json',recovery.resume,'Only a verified, still-closed restore can resume traffic')]:
        decision=load(recovered/filename)
        try:method(decision,exact_hash=data_digest(decision),noninteractive=True)
        except OperatorError as error:assert str(error)==expected;replay.append(dict(decision=filename,denied=str(error)))
        else:raise AssertionError('Terminal recovery decision replayed')
        assert store.status(op)==status
    before=load(recovered/'configuration-before.json');failed=DockerObserver(before)
    assert json.loads(sql(failed,BUSINESS_SQL))==load(recovered/'business-after-commit.json') and json.loads(sql(failed,SCHEMA))==load(recovered/'schema-after-commit.json')
    old=json.loads(subprocess.check_output(['docker','inspect',before['worker_id']]))[0];assert not old['State']['Running'] and not old['NetworkSettings']['Networks']
    retained=snapshots(config);assert sum(w['running'] for w in retained)==1 and next(w for w in retained if w['running'])['container_id']==config['worker_id']
    assert all(not w['networks'] for w in retained if not w['running'])
    current=json.loads(subprocess.check_output(['docker','inspect',config['worker_id']]))[0];ip=current['NetworkSettings']['Networks'][config['project']+'_runtime']['IPAddress']
    addresses=json.loads(sql(reader,"SELECT COALESCE(jsonb_agg(DISTINCT client_addr::text),'[]'::jsonb) FROM pg_stat_activity WHERE datname=current_database() AND usename<>'postgres';"));assert all(a in [ip,ip+'/32'] for a in addresses)
    check="import configparser;c=configparser.ConfigParser();c.read('/run/secrets/odoo_config');assert c['options'].getint('max_cron_threads')==0"
    subprocess.run(['docker','exec',config['worker_id'],'/venv/bin/python','-c',check],check=True,capture_output=True,timeout=30)
    effects=[]
    for case in ['failed','restored','late']:
        record=load(LOCAL/('queue-'+case+'.json'));assert record['state']=='explicit_fixture_reconciliation_retained'
        receipt=LOCAL/'operator/fixture-effects'/(record['effect_id']+'.json');assert hashlib.sha256(receipt.read_bytes()).hexdigest()==record['external_receipt_sha256']
        assert load(receipt)['external_writes']==1
        target=failed if case=='failed' else reader
        for table in ['mp_job','mp_outbox']:
            rows=json.loads(sql(target,'SELECT jsonb_agg(to_jsonb(t)) FROM '+record['retained_schema']+'.'+table+' t;'))
            assert rows==[dict(fixture_id=record['fixture_id'],effect_id=record['effect_id'],state='reconciled_completed',result_sha256=record['result_sha256'])]
        effects.append(dict(case=case,effect_id=record['effect_id'],external_writes=1,receipt_sha256=record['external_receipt_sha256'],all_rows_retained=True))
    for filename in ['old-clean-review.json','late-review.json']:
        decision=load(OUTPUT/filename)['decision'];review=load(store.root/'recovery-reviews'/(decision['review']['review_id']+'.revoked.json'));assert review['decision_hash']==data_digest(decision) and review['operation_id']==op
    checkpoint=store.root/'checkpoints'/op;manifest=load(checkpoint/'manifest.json');assert all(hashlib.sha256((checkpoint/n).read_bytes()).hexdigest()==h for n,h in manifest['files'].items())
    with sqlite3.connect(store.root/'control.sqlite3') as db:states=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')]
    assert states==[['revoked',1]]
    source=load(OUTPUT/'source-boundary-input.json')['source_sha256'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
    for name,count in [('source-host2.json',35),('source-linux.json',49)]:
        report=load(OUTPUT/name);assert report['result']=='passed' and report['source_sha256']==source and report['summary']==dict(tests=count,failures=0,errors=0,skipped=0)
    freeze=subprocess.run([sys.executable,'tools/check_contract_freeze.py'],capture_output=True,check=True,timeout=30);frozen=json.loads(freeze.stdout);assert frozen['files']==87
    assert load(OUTPUT/'prepare-restore-refused.json')['result']=='passed_unsupported_queues_refused_before_restore'
    child=json.loads(subprocess.check_output(['docker','inspect',config['project']+'-op-'+op+'-native']))[0];assert child['State']['ExitCode']==0 and not child['State']['Running']
    assert sum(event['code']=='reserved' for event in status['history'])==1
    for name in ['queued-start-refused.json','late-refused.json','http-assets-replay.json']:
        assert load(OUTPUT/name)['result']=='passed'
    private=[p.read_text(encoding='utf8').strip().encode() for p in [LOCAL/n for n in ['bootstrap-password','postgres-password','app-db-password','database-master-password']]+[ROOT/'.local/g5/bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password',life/'bootstrap-password'] if p.exists()]
    count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not value or value not in raw for value in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,restored_generation=20,image_id=config['image_id'],host_source_sha256=source,supported_profile='r1-no-dispatch-v1',terminal_replays=replay,checkpoint_hashes_verified=True,failed_database_retained_unchanged=True,old_worker_stopped_disconnected=True,only_current_worker_connected=True,active_database_client_addresses=addresses,native_cron_disabled=True,effects=effects,private_rejected_reviews_revoked=True,operation_states=states,windows_tests=35,linux_tests=49,skipped=0,frozen_files=87,public_files_checked=count,known_private_values_checked=len(private),limits=['Synthetic queues and harmless durable local receipts; fixture-only reconciliation, no G6 adapter.','Bounded private-value scan, not SEC-03 release qualification.','Actual native commit followed by controlled host exception; OS-process-crash evidence is retained separately.','Independent copied populated fixture, not OPS-02 clean-environment runbook rehearsal.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',protected_targets=len(protected),effects=len(effects),public_files_checked=count)))


if __name__=='__main__':main()
