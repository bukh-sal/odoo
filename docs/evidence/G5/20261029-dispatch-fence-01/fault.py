"""Actual approved native commit failure in the independent dispatch fixture."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent/'fault';LOCAL=ROOT/'.local/g5-dispatch'
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
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','fault']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');target=LOCAL/'operator/target.json';config=load(target);marker=LOCAL/'dispatch-fault.json';fixture=load(LOCAL/'fixtures.json')
    assert state['disposable'] and config['project']==state['project'] and config['project'].startswith('mp-r0-r1disp') and config['generation']==18
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True);store=OperatorStore(LOCAL/'operator/control');native=NativeExecutor(store,target,catalog_root,validator);reader=DockerObserver(config)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];ops=prefix+['operations','--store',str(store.root)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command):
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if r.returncode:
            (LOCAL/('dispatch-fault-'+args.action+'.stderr')).write_bytes(r.stderr);raise RuntimeError('Inspect exact marker/journal; do not replay native work')
        return json.loads(r.stdout)
    record=load(marker) if marker.exists() else dict(state='preparing')
    def phase(value):record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    if args.action=='prepare':
        assert state['phase']=='setup_verified' and not marker.exists() and not OUTPUT.exists();OUTPUT.mkdir();before=reader.state(reader.read(),catalog.snapshot())['state'];record['base_digest']=data_digest(before);phase('preparing')
        for name,value in [('state-before',before),('business-before',json.loads(sql(reader,BUSINESS_SQL))),('schema-before',json.loads(sql(reader,SCHEMA))),('files-before',files(reader)),('configuration-before',config)]:write(name+'.json',value)
        r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator');nomination=dict(schema_version=1,operation='prepare',operation_type='uninstall',site_id=state['site_id'],plugin_id='org.example.notes_labels',workspace_ids=[],cascade=False)
        code,value=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});assert code==200;op=value['data']['operation_id'];record.update(operation_id=op,plan_hash=value['data']['plan_hash']);phase('requesting')
        code,value=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=value['data'];check_bundle(bundle,before);assert len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==4 and bundle['plan']['backup']['required'];write('bundle.json',bundle)
        code,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200;write('requested.json',value)
        write('registered.json',invoke(ops+['import-request',op]+options));write('independent-review.json',store.review(op,native._validate()));phase('independently_reviewed_not_approved');print(json.dumps(record));return
    assert record['state']=='independently_reviewed_not_approved' and record['base_digest']==data_digest(reader.state(reader.read(),catalog.snapshot())['state']);op=record['operation_id']
    write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+options));phase('executing_exact_plan_with_post_commit_fault')
    original=native._private_command
    def fail_after_native(command,path,**kwargs):
        value=original(command,path,**kwargs)
        if path.name=='native.log':raise OperatorError('Qualification post-native commit fault before metadata publication')
        return value
    native._private_command=fail_after_native
    try:native.apply(op)
    except OperatorError as error:assert str(error)=='Qualification post-native commit fault before metadata publication'
    else:raise AssertionError('Injected fault did not stop operation')
    status=store.status(op);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed'];write('failed-status.json',status)
    child=json.loads(subprocess.check_output(['docker','inspect',config['project']+'-op-'+op+'-native']))[0];assert child['State']['ExitCode']==0
    business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));assert not any(c[1]=='x_notes_labels' for c in schema['columns'])
    assert load(target)==config
    for service in ['app','edge']:assert not native._inspect(reader._container(service,stopped=True))['State']['Running']
    write('business-after-commit.json',business);write('schema-after-commit.json',schema);phase('recovery_required_verified')
    state['phase']='dispatch_fault_traffic_closed';(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(state=record['state'],operation_id=op,native_child_exit_code=0,traffic_closed=True)))


if __name__=='__main__':main()
