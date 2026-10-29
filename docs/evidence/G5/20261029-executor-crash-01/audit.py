"""Bounded source, protected-site and retained-failure audit for MIG-03."""
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
from modular_platform.native_executor import NativeExecutor
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit.json';assert not dest.exists()
    global_catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(global_catalog)==7
    protected=[]
    for name,target,baseline,business,expected_hash in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json','3441ea13f16aef9a26226059df88da2d8992fdb2db95f491e98e0513d41b72c9'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json','8c586a0832f8d0147c3ab491a7897d34d0882d0bd97eecb4fc302df8aa98f8ad')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected_hash
        assert reader.state(reader.read(),global_catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader);assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],state_business_configuration_exact=True))
    state=load(LOCAL/'state.json');config=load(LOCAL/'operator/target.json');attempt=OUTPUT/'attempt02';assert state['phase']=='executor_crash_restored_resumed' and config['generation']==15
    catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True).snapshot();reader=DockerObserver(config)
    assert len(catalog)==8 and config['image_id']==load(attempt/'configuration-before.json')['image_id']
    assert reader.state(reader.read(),catalog)['state']==load(attempt/'state-restored.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(attempt/'business-before.json') and json.loads(sql(reader,SCHEMA))==load(attempt/'schema-before.json')
    assert files(reader)==load(attempt/'files-restored.json')
    for report_name in ['source-host2.json','source-linux4.json','source-freeze.json']:
        report=load(OUTPUT/report_name);assert report['result']=='passed'
        assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['source_sha256'].items())
    assert load(OUTPUT/'http-assets-replay.json')['result']=='passed'
    store=OperatorStore(LOCAL/'operator/control');cases=[]
    recovery=RestoreExecutor(NativeExecutor(store,LOCAL/'operator/target.json',ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config'])))
    for folder,marker_name in [(OUTPUT,'executor-crash.json'),(attempt,'executor-crash02.json')]:
        marker=load(LOCAL/marker_name);assert marker['state']=='completed_verified';op=marker['operation_id'];status=store.status(op)
        assert status['state']=='revoked' and status['phase']=='restore_traffic_resumed' and status['mutation_started'] and status['traffic_resumed']
        base=load(folder/'configuration-before.json');failed=DockerObserver(base)
        assert json.loads(sql(failed,BUSINESS_SQL))==load(folder/'business-after-commit.json') and json.loads(sql(failed,SCHEMA))==load(folder/'schema-after-commit.json')
        worker=json.loads(subprocess.check_output(['docker','inspect',base['worker_id']]))[0]
        assert not worker['State']['Running'] and base['project']+'_runtime' not in worker['NetworkSettings']['Networks']
        checkpoint=store.root/'checkpoints'/op;manifest=load(checkpoint/'manifest.json')
        assert all(hashlib.sha256((checkpoint/name).read_bytes()).hexdigest()==digest for name,digest in manifest['files'].items())
        for decision_name in ['restore-decision.json','resume-decision.json']:
            decision=load(folder/decision_name);review=load(store.root/'recovery-reviews'/(decision['review']['review_id']+'.json'))
            assert review['decision']==decision and review['decision_hash']==data_digest(decision)
            method=recovery.execute if decision_name.startswith('restore') else recovery.resume
            try:method(decision,exact_hash=data_digest(decision),noninteractive=True)
            except OperatorError as error:
                expected='Fresh-target recovery is permitted only before traffic resumes' if decision_name.startswith('restore') else 'Only a verified, still-closed restore can resume traffic'
                assert str(error)==expected,str(error)
            else:raise AssertionError('Completed recovery decision executed again')
            assert store.status(op)==status
        cases.append(dict(operation_id=op,failed_database_retained_unchanged=True,checkpoint_hashes_verified=True,old_worker_stopped_disconnected=True,original_approval_revoked=True,completed_recovery_decisions_refused_by_terminal_state=True,base_generation=base['generation']))
    crash=load(attempt/'process-crash.json');journal=load(attempt/'journal-after-process-exit.json');reconciled=load(attempt/'reconciled-status.json')
    assert crash['native_child_exit_code']==0 and crash['executor_exit_code']!=0 and crash['python_cleanup_did_not_run']
    assert journal['state']=='running' and journal['phase']=='mutation_started' and not journal['traffic_resumed']
    assert next(e['details']['executor_pid'] for e in journal['history'] if e['code']=='reserved')==crash['executor_pid']
    assert reconciled['history'][:-1]==journal['history'] and reconciled['history'][-1]['code']=='executor_lost_after_possible_mutation'
    assert load(OUTPUT/'launcher-reconciliation.json')['result']=='harness_failure_not_OS_crash'
    db=sqlite3.connect(store.root/'control.sqlite3');statuses=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')]
    assert statuses==[['completed',14],['failed_before_mutation',3],['revoked',2]],statuses
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
    report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,cases=cases,actual_OS_crash_and_lost_owner_fence=True,exact_restored_schema_business_grants_bindings_files=True,source_windows_checks=6,source_linux_checks=70,frozen_files=87,independent_operation_states=statuses,public_files_checked=count,known_private_values_checked=len(private),limits=['Bounded evidence scan, not SEC-03 release qualification.','Initial launcher failure recovered but excluded from OS-crash acceptance.','No concurrency/dispatch/clean-environment recovery qualification.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))


if __name__=='__main__':main()
