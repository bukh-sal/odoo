"""Fresh once-only plans: staging and drained-before-backup failure cases."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','reconcile-import','fault','resume']);parser.add_argument('--case',choices=['staging','no-backup'],required=True);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'));folder=OUTPUT/args.case;marker=LOCAL/('premutation-'+args.case+'.json')
    config=load(LOCAL/'operator/target.json');state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json')
    assert config==load(OUTPUT/'configuration-before.json') and state['phase']=='premutation_unchanged_resumed' and load(LOCAL/'premutation-resume.json')['state']=='completed_verified'
    if args.case=='no-backup':assert load(LOCAL/'premutation-staging.json')['state']=='completed_verified'
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];catalog=Catalog(catalog_root,configuration(trust),readonly=True)
    reader=DockerObserver(config);store=OperatorStore(LOCAL/'operator/control');native=NativeExecutor(store,LOCAL/'operator/target.json',catalog_root,configuration(trust))
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];options=['--store',str(store.root),'--deployment-config',str(LOCAL/'operator/target.json'),'--catalog',str(catalog_root)]
    ops=prefix+['operations','--store',str(store.root)]
    def write(name,value):
        with (folder/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command):
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if r.returncode:
            (LOCAL/('premutation-'+args.case+'-'+args.action+'.log')).write_bytes(r.stderr)
            raise RuntimeError('CLI failed: reconcile marker/journal; never repeat a fault or recovery decision')
        return json.loads(r.stdout)
    def stable(offline=False):
        assert load(LOCAL/'operator/target.json')==config
        actual=reader.state(reader.read(quiesced=offline),catalog.snapshot())['state'];assert actual==load(OUTPUT/'state-before.json')
        assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-before.json')
        protected=load(LOCAL/'premutation-fault.json')['protected_hashes'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
        return actual
    if args.action=='prepare':
        assert not folder.exists() and not marker.exists();folder.mkdir();before=stable();assert files(reader)==load(OUTPUT/'files-before.json')
        record=dict(state='preparing');marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
        nomination=dict(schema_version=1,operation='prepare',operation_type='uninstall',site_id=state['site_id'],plugin_id='org.example.notes_labels',workspace_ids=[],cascade=False)
        code,value=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});write('prepare-response.json',dict(status=code,response=value));assert code==200
        op=value['data']['operation_id'];code,value=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=value['data'];check_bundle(bundle,before)
        assert len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==4 and bundle['plan']['backup']['required'];write('bundle.json',bundle)
        record.update(operation_id=op,plan_hash=bundle['plan_hash'],state='importing');marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        code,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200;write('requested.json',value)
        write('registered.json',invoke(ops+['import-request',op]+options[2:]));write('independent-review.json',store.review(op,native._validate()));stable()
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));return
    record=load(marker);op=record['operation_id']
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    if args.action=='reconcile-import':
        assert record['state']=='importing' and not (folder/'registered.json').exists();stable()
        with store._connect() as db:assert not db.execute('SELECT 1 FROM operations WHERE operation_id=?',(op,)).fetchone()
        write('import-reconciliation.json',dict(result='same_existing_application_request',reason='First CLI parse failed before registration: --store belongs on operations group',operation_id=op))
        write('registered.json',invoke(ops+['import-request',op]+options[2:]));write('independent-review.json',store.review(op,native._validate()));stable()
        phase('independently_reviewed_not_approved');print(json.dumps(record));return
    if args.action=='fault':
        assert record['state']=='independently_reviewed_not_approved';stable()
        phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--ack-trust','--ack-destructive','--noninteractive']+options[2:]))
        expected='reserved' if args.case=='staging' else 'drained'
        def fault(*a,**kw):
            status=store.status(op);assert status['phase']==expected and not status['mutation_started'] and status['backup_id'] is None
            phase('injecting_'+args.case+'_fault');raise OperatorError('Qualification '+args.case+' fault before mutation')
        phase('applying_bounded_fault')
        with patch.object(native,'_topology' if args.case=='staging' else '_checkpoint',side_effect=fault):
            try:native.apply(op)
            except OperatorError as error:assert str(error)=='Qualification '+args.case+' fault before mutation'
            else:raise AssertionError('Expected bounded fault')
        phase('fault_verifying');status=store.status(op);assert status['state']=='failed_before_mutation' and status['phase']==expected and status['backup_id'] is None and not status['mutation_started']
        assert not (store.root/'checkpoints'/op).exists();assert subprocess.run(['docker','inspect',config['project']+'-op-'+op+'-native'],capture_output=True).returncode!=0
        stable(offline=args.case=='no-backup');write('fault-status.json',status)
        envelope=invoke(prefix+['plugin','recover','prepare-unchanged-resume',op]+options);decision=envelope['decision']
        assert decision['worker_running']==(args.case=='staging') and decision['edge']['running']==(args.case=='staging')
        write('resume-review.json',envelope);write('resume-decision.json',decision);record['decision_hash']=envelope['decision_hash'];phase('resume_independently_reviewed_not_executed');print(json.dumps(record));return
    assert record['state']=='resume_independently_reviewed_not_executed';phase('resuming_reviewed_base')
    result=invoke(prefix+['plugin','recover','resume-unchanged',op,'--decision',str(folder/'resume-decision.json'),'--decision-hash',record['decision_hash'],'--noninteractive']+options)
    write('resume-result.json',result);assert result['state']=='unchanged_release_resumed' and not result['database_restore'] and not result['worker_replaced'];phase('resumed_needs_verification')
    stable();assert files(reader)==load(OUTPUT/'files-before.json')
    status=store.status(op);assert status['state']=='failed_before_mutation' and status['phase']=='unchanged_traffic_resumed' and not status['mutation_started'] and status['traffic_resumed'] and status['backup_id'] is None
    write('status-after-resume.json',status);write('qualification.json',dict(result='passed_actual_'+args.case+'_failure_and_resume',operation_id=op,generation=11,checkpoint_absent=True,exact_base_business_schema_configuration_files=True,worker_unchanged=True,traffic_continuously_available=args.case=='staging',limits=['Injected exception, not process-crash evidence.']))
    phase('completed_verified');print(json.dumps(dict(result='completed_verified',case=args.case,operation_id=op,generation=11)))


if __name__=='__main__':main()
