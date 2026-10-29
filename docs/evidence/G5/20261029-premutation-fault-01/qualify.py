"""Once-only real checkpointed failure BEFORE any native mutation."""
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
from modular_platform.restore_executor import RestoreExecutor
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','fault']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    target=LOCAL/'operator/target.json';config=load(target);state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');marker=LOCAL/'premutation-fault.json'
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==11
    assert config['image_id']=='sha256:486c2857ea32db6c9db0a27a61a4dc2de02c238e375c4148b1b4e4e2bad441ea' and state['phase']=='permission_upgrade_completed'
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True)
    reader=DockerObserver(config);observation=reader.read();before=reader.state(observation,catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    assert len(business['notes'])==4 and len(business['boards'])==2 and len(before['installations'])==6 and len(before['bindings'])==10
    protected=[ROOT/'.local/operator/targets/g5.json',ROOT/'.local/g5-manager-upgrade/operator/target.json',ROOT/'.local/operator/trust.json',trust]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard():assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    control=LOCAL/'operator/control';store=OperatorStore(control);executor=NativeExecutor(store,target,catalog_root,validator)
    prefix=[sys.executable,'tools/modular.py','--config',str(trust)];ops=prefix+['operations','--store',str(control)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def invoke(command):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:
            (LOCAL/('premutation-fault-'+args.action+'.log')).write_bytes(result.stderr)
            raise RuntimeError('CLI failure: reconcile exact marker/journal before any next action')
        return json.loads(result.stdout)
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    if args.action=='prepare':
        assert not marker.exists() and not (OUTPUT/'state-before.json').exists()
        record=dict(state='preparing',base_digest=data_digest(before),protected_hashes=hashes);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        for name,value in [('state-before',before),('business-before',business),('schema-before',schema),('configuration-before',config),('files-before',files(reader))]:write(name+'.json',value)
        r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
        nomination=dict(schema_version=1,operation='prepare',operation_type='uninstall',site_id=state['site_id'],plugin_id='org.example.notes_labels',workspace_ids=[],cascade=False)
        code,response=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});write('prepare-response.json',dict(status=code,response=response));assert code==200,(code,response)
        op=response['data']['operation_id'];record.update(state='prepared_not_imported',operation_id=op,plan_hash=response['data']['plan_hash']);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        code,value=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=value['data'];check_bundle(bundle,before)
        assert len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==4 and bundle['plan']['destructive'] and bundle['plan']['backup']['required']
        assert all(c['action']=='revoke' for c in bundle['plan']['permission_changes']) and all(a['version']=='0.2.2' for a in bundle['plan']['artifacts'])
        write('bundle.json',bundle)
        code,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200;write('requested.json',value)
        write('registered.json',invoke(ops+['import-request',op]+options));write('independent-review.json',store.review(op,executor._validate()))
        assert before==reader.state(reader.read(),catalog.snapshot())['state'];guard();record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));return
    record=load(marker);assert record['state']=='independently_reviewed_not_approved' and record['base_digest']==data_digest(before) and record['protected_hashes']==hashes
    assert business==load(OUTPUT/'business-before.json') and schema==load(OUTPUT/'schema-before.json')
    op=record['operation_id']
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+options))
    def fault(operation,locks,revalidate,**kwargs):
        status=store.status(operation);assert operation==op and status['phase']=='checkpointed' and not status['mutation_started'] and not status['traffic_resumed']
        phase('injecting_fault_before_mutation');raise OperatorError('Qualification fault before mutation boundary')
    phase('applying_with_bounded_fault')
    with patch.object(store,'before_mutation',side_effect=fault):
        try:executor.apply(op)
        except OperatorError as error:assert str(error)=='Qualification fault before mutation boundary'
        else:raise AssertionError('Injected pre-mutation fault was not observed')
    phase('fault_needs_verification');status=store.status(op)
    assert status['state']=='failed_before_mutation' and status['phase']=='checkpointed' and not status['mutation_started'] and not status['traffic_resumed']
    assert load(target)==config
    actual=reader.state(reader.read(quiesced=True),catalog.snapshot())['state'];assert actual==before
    assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema
    for service in ['app','edge']:
        assert not executor._inspect(reader._container(service,stopped=True))['State']['Running']
    missing=subprocess.run(['docker','inspect',state['project']+'-op-'+op+'-native'],capture_output=True);assert missing.returncode!=0
    checkpoint=load(control/'checkpoints'/op/'manifest.json');assert checkpoint['previous_release']==before and checkpoint['configuration']==config
    for name,digest in checkpoint['files'].items():assert hashlib.sha256((control/'checkpoints'/op/name).read_bytes()).hexdigest()==digest
    try:RestoreExecutor(executor).prepare(op)
    except OperatorError as error:write('existing-restore-refusal.json',dict(result='denied_as_designed',reason=str(error)))
    else:raise AssertionError('Pre-mutation failure treated as possibly committed restore')
    write('failed-status.json',status);write('state-after-fault.json',actual);write('checkpoint-manifest.json',checkpoint)
    guard();phase('fault_verified_maintenance_closed')
    write('fault-qualification.json',dict(result='verified_gap_before_mutation',operation_id=op,plan_hash=record['plan_hash'],generation=11,base_state_business_schema_configuration_exact=True,native_child_absent=True,checkpoint_hashes_verified=True,traffic_closed=True,limits=['Required verified unchanged-release resume path is not yet implemented; MIG-01 remains not_run.','Injected exception is not OS-process-crash evidence.']))
    print(json.dumps(dict(result='fault_verified_maintenance_closed',operation_id=op,generation=11)))


if __name__=='__main__':main()
