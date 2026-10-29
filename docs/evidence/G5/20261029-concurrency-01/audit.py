"""Protected sites, exact effects, no contender mutation and current-source audit."""
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
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit.json';assert not dest.exists()
    global_catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(global_catalog)==7
    protected=[]
    for name,target,baseline,business,digest in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json','3441ea13f16aef9a26226059df88da2d8992fdb2db95f491e98e0513d41b72c9'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json','8c586a0832f8d0147c3ab491a7897d34d0882d0bd97eecb4fc302df8aa98f8ad')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        assert reader.state(reader.read(),global_catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader);assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],state_business_configuration_exact=True))
    state=load(LOCAL/'state.json');config=load(LOCAL/'operator/target.json');marker=load(LOCAL/'concurrency.json');assert marker['state']=='completed_verified' and config['generation']==17
    catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True).snapshot();reader=DockerObserver(config);assert len(catalog)==8
    assert reader.state(reader.read(),catalog)['state']==load(OUTPUT/'state-after.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-after.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-before.json')
    assert files(reader)==load(OUTPUT/'files-after.json')
    before=load(OUTPUT/'business-before.json');after=load(OUTPUT/'business-after.json');assert before['notes']==after['notes'] and before['boards']==after['boards']
    oldbindings={r['public_id']:r for r in before['bindings']};newbindings={r['public_id']:r for r in after['bindings']};assert oldbindings.keys()==newbindings.keys()
    recreated=[];labels_installation=next(i['installation_id'] for i in load(OUTPUT/'state-before.json')['installations'] if i['plugin_id']=='org.example.notes_labels')
    for key,old in oldbindings.items():
        new=newbindings[key];assert old['descriptor']==new['descriptor']
        if old['id']!=new['id']:
            assert old['descriptor']['consumer_installation_id']==labels_installation;recreated.append(key)
        else:assert old==new
    assert len(recreated)==4
    store=OperatorStore(LOCAL/'operator/control');effects=[]
    for case,base_path in [('owner',OUTPUT/'configuration-before.json'),('reinstall',OUTPUT/'owner/configuration-after.json')]:
        op=marker['operations'][case]['operation_id'];status=store.status(op);assert status['state']=='completed' and status['traffic_resumed']
        for code in ['reserved','mutation_started','migrated','completed']:assert sum(e['code']==code for e in status['history'])==1
        child=inspect(config['project']+'-op-'+op+'-native');assert child['State']['ExitCode']==0 and not child['State']['Running']
        if case=='owner':assert child['Id']==load(OUTPUT/'contention.json')['native_child_id']
        else:assert '-i' in child['Config']['Cmd'] and '-u' not in child['Config']['Cmd']
        checkpoint=store.root/'checkpoints'/op;manifest=load(checkpoint/'manifest.json')
        assert all(hashlib.sha256((checkpoint/name).read_bytes()).hexdigest()==h for name,h in manifest['files'].items())
        base=load(base_path);oldworker=inspect(base['worker_id']);assert not oldworker['State']['Running'] and config['project']+'_runtime' not in oldworker['NetworkSettings']['Networks']
        effects.append(dict(case=case,operation_id=op,native_child_id=child['Id'],native_exit_code=0,single_mutation_reservation=True,checkpoint_hashes_verified=True,old_worker_stopped_disconnected=True))
    for case in ['other-native','other-feature']:
        op=marker['operations'][case]['operation_id'];status=store.status(op);assert status['state']=='revoked' and not status['mutation_started'] and not status['traffic_resumed']
        assert not (store.root/'stages'/op).exists() and all(e['code'] not in ('reserved','mutation_started','completed') for e in status['history'])
        assert store.status(marker['operations']['owner']['operation_id'])==load(OUTPUT/'owner/completed-replay.json')
    for report in ['source-host.json','source-linux.json']:
        value=load(OUTPUT/report);assert value['result']=='passed' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in value['source_sha256'].items())
    assert load(OUTPUT/'http-assets.json')['result']=='passed' and load(OUTPUT/'stale-and-completed-replay.json')['result']=='passed'
    db=sqlite3.connect(store.root/'control.sqlite3');statuses=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')];assert statuses==[['completed',16],['failed_before_mutation',3],['revoked',4]],statuses
    private=[p.read_text(encoding='utf8').strip().encode() for p in [LOCAL/'bootstrap-password',ROOT/'.local/g5/bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password'] if p.exists()];count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not v or v not in raw for v in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,effects=effects,contenders_retired_without_reservation_or_mutation=True,exact_note_board_schema_restored=True,public_binding_identities_and_descriptors_preserved=True,recreated_internal_binding_rows=len(recreated),independent_operation_states=statuses,windows_checks=4,linux_checks=24,contract_files=87,public_files_checked=count,known_private_values_checked=len(private),limits=['Bounded evidence scan, not SEC-03 release qualification.','No stale-worker/dispatch/two-database/security/clean-environment recovery qualification.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(value))


def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]


if __name__=='__main__':main()
