"""Review and run the existing CLI's unchanged-release resume exactly once."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    config=load(LOCAL/'operator/target.json');state=load(LOCAL/'state.json');fault=load(LOCAL/'premutation-fault.json');marker=LOCAL/'premutation-resume.json'
    assert fault['state']=='fault_verified_maintenance_closed' and config==load(OUTPUT/'configuration-before.json') and config['generation']==11
    assert config['project']=='mp-r0-r1lifef99acae9d906';op=fault['operation_id']
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];store=OperatorStore(LOCAL/'operator/control')
    command=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust),'plugin','recover']
    options=['--store',str(store.root),'--deployment-config',str(LOCAL/'operator/target.json'),'--catalog',str(catalog_root)]
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(arguments):
        result=subprocess.run(arguments,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:
            (LOCAL/('premutation-resume-'+args.action+'.log')).write_bytes(result.stderr)
            raise RuntimeError('Recovery CLI failed: reconcile marker, journal and actual worker state before fresh review')
        return json.loads(result.stdout)
    if args.action=='prepare':
        assert not marker.exists() and not (OUTPUT/'resume-decision.json').exists()
        record=dict(state='preparing_review',operation_id=op);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        report=invoke(command+['prepare-unchanged-resume',op]+options);decision=report['decision']
        assert decision['action']=='resume_unchanged_release' and decision['configuration']==config and decision['database_restore'] is False
        assert decision['base_state_digest']==data_digest(load(OUTPUT/'state-before.json')) and not decision['worker_running'] and not decision['edge']['running']
        write('resume-review.json',report);write('resume-decision.json',decision)
        record.update(state='independently_reviewed_not_executed',decision_hash=report['decision_hash'],review_id=decision['review']['review_id'])
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));return
    assert load(OUTPUT/'source-host.json')['result']=='passed' and load(OUTPUT/'source-linux.json')['result']=='passed' and load(OUTPUT/'source-freeze.json')['result']=='passed'
    record=load(marker);assert record['state']=='independently_reviewed_not_executed'
    old=store.status(op);assert old['state']=='failed_before_mutation' and old['phase']=='checkpointed' and not old['traffic_resumed'] and not old['mutation_started']
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    bad=subprocess.run(command+['resume-unchanged',op,'--decision',str(OUTPUT/'resume-decision.json'),'--decision-hash','sha256:'+'0'*64,'--noninteractive']+options,cwd=ROOT,capture_output=True,timeout=120)
    assert bad.returncode!=0 and b'Exact reviewed recovery hash' in bad.stderr and store.status(op)==old
    write('wrong-resume-hash.json',dict(result='denied',exit_code=bad.returncode,reason='Exact reviewed recovery hash required; journal unchanged'))
    phase('resuming_reviewed_unchanged_release')
    result=invoke(command+['resume-unchanged',op,'--decision',str(OUTPUT/'resume-decision.json'),'--decision-hash',record['decision_hash'],'--noninteractive']+options)
    write('resume-result.json',result);assert result['state']=='unchanged_release_resumed' and not result['database_restore'] and not result['worker_replaced'];phase('resumed_needs_verification')
    assert load(LOCAL/'operator/target.json')==config
    reader=DockerObserver(config);catalog=Catalog(catalog_root,configuration(trust),readonly=True).snapshot()
    observed=reader.state(reader.read(),catalog)['state'];assert observed==load(OUTPUT/'state-before.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-before.json')
    now=files(reader);assert now==load(OUTPUT/'files-before.json')
    status=store.status(op);assert status['state']=='failed_before_mutation' and status['phase']=='unchanged_traffic_resumed' and status['traffic_resumed'] and not status['mutation_started']
    with store._connect() as db:
        assert db.execute('SELECT 1 FROM revocations WHERE operation_id=?',(op,)).fetchone()
        assert load_json_approval(db.execute('SELECT approval FROM operations WHERE operation_id=?',(op,)).fetchone()[0])=='revoked'
    protected=fault['protected_hashes'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
    write('state-after-resume.json',observed);write('status-after-resume.json',status);write('files-after-resume.json',now)
    state['phase']='premutation_unchanged_resumed';(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('resume-qualification.json',dict(result='passed_actual_unchanged_release_resume',operation_id=op,generation=11,original_approval_permanently_revoked=True,native_mutation_never_started=True,state_schema_business_configuration_files_exact=True,worker_unchanged=True,limits=['Supported HTTP/API/assets and protected full-state audit remain separate.','Injected exception is not process-crash qualification.']))
    print(json.dumps(dict(result='completed_verified',operation_id=op,generation=11)))


def load_json_approval(raw):return json.loads(raw)['state']


if __name__=='__main__':main()
