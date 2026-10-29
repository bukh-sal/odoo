"""Once-only staged restore prerequisite for the real LIFE-05 upgrade."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent/'restore';LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperationLocks
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.release_staging import StageStore
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe

FULL='sha256:967c4b54371291a54ab5490e438c37358d561fa66e11293943096122a2608bc1'
REMOVED='sha256:ea6c34cee2a866b847dff7115674d2a03bd38268c953adf11edc8bc2b572e23c'
PLUGIN='org.example.notes_labels'
IDENTITIES="SELECT jsonb_build_object('installations',(SELECT jsonb_agg(jsonb_build_array(id,public_id,plugin_id) ORDER BY id) FROM mp_plugin_installation),'scopes',(SELECT jsonb_agg(jsonb_build_array(id,workspace_id,plugin_id,installation_id) ORDER BY id) FROM mp_workspace_plugin));"


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    marker=LOCAL/'permission-restore.json';target=LOCAL/'operator/target.json'
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    config=load(target);state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json')
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1lifef99acae9d906'
    assert state['phase']=='artifact_source_removed' and config['generation']==9 and config['image_id']==REMOVED
    protected=[ROOT/'.local/operator/targets/g5.json',ROOT/'.local/g5-manager-upgrade/operator/target.json',ROOT/'.local/operator/trust.json']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard():assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    trust=ROOT/'.local/operator/trust.json';catalog_root=ROOT/'.local/operator/catalog';validator=configuration(trust)
    catalog=Catalog(catalog_root,validator,readonly=True);reader=DockerObserver(config)
    before=reader.state(reader.read(),catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));identity=json.loads(sql(reader,IDENTITIES))
    assert len(business['notes'])==4 and len(business['boards'])==2 and len(before['installations'])==6
    control=LOCAL/'operator/control';store=OperatorStore(control);executor=StagedNativeExecutor(store,target,catalog_root,validator)
    prefix=[sys.executable,'tools/modular.py','--config',str(trust)];ops=prefix+['operations','--store',str(control)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:
            (LOCAL/('permission-restore-'+args.action+'.log')).write_bytes(result.stderr)
            raise RuntimeError('CLI failure: reconcile marker and journal, never replay')
        return json.loads(result.stdout)
    if args.action=='prepare':
        assert not marker.exists() and not OUTPUT.exists();OUTPUT.mkdir()
        record=dict(state='staging',base_digest=data_digest(before),protected_hashes=hashes)
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        for name,value in [('state-before',before),('business-before',business),('schema-before',schema),('identity-before',identity),('configuration-before',config),('files-before',files(reader))]:write(name+'.json',value)
        stages=StageStore(store,config,catalog);descriptor=stages.stage(FULL);loaded=stages.load(descriptor);write('stage.json',descriptor)
        with OperationLocks(store.root/'locks',config['deployment_id'],[s['site_id'] for s in config['sites']]):write('publication.json',publish_profile(reader,catalog,staged=loaded))
        r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
        artifact=next(a for a in catalog.snapshot() if a['manifest']['plugin']['id']==PLUGIN and a['manifest']['plugin']['version']=='0.2.1')
        nomination=dict(schema_version=1,operation='prepare',operation_type='install',site_id=state['site_id'],plugin_id=PLUGIN,artifact_version='0.2.1',artifact_digest=artifact['digest'],workspace_ids=[fixture['workspaces'][w]['public_id'] for w in ['A','B']],cascade=False)
        code,prepared=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});write('prepare-response.json',dict(status=code,response=prepared));assert code==200,(code,prepared)
        op=prepared['data']['operation_id'];record.update(state='prepared_not_imported',operation_id=op,plan_hash=prepared['data']['plan_hash']);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        code,response=client.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=response['data'];check_bundle(bundle,before)
        assert bundle['plan']['operation_type']=='install' and len(bundle['operation_lock']['targets'])==2 and len(bundle['plan']['permission_changes'])==2
        assert all(t['plugin_id']==PLUGIN and t['action']=='install' for t in bundle['operation_lock']['targets'])
        assert all(f['availability']=='enabled' for f in bundle['operation_lock']['feature_states'])
        assert all(a['migration_digests']==[] for a in bundle['plan']['artifacts']) and bundle['plan']['backup']['required']
        assert bundle['operation_lock']['staged_image']['target_image_id']==FULL
        write('bundle.json',bundle)
        code,requested=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200;write('requested.json',requested)
        write('registered.json',invoke(ops+['import-request',op]+options));write('independent-review.json',store.review(op,executor._validate()))
        assert before==reader.state(reader.read(),catalog.snapshot())['state'];guard()
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));return
    record=load(marker);assert record['state']=='independently_reviewed_not_approved' and record['base_digest']==data_digest(before) and record['protected_hashes']==hashes
    assert business==load(OUTPUT/'business-before.json') and schema==load(OUTPUT/'schema-before.json')
    op=record['operation_id'];bundle=load(OUTPUT/'bundle.json')
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions','--ack-destructive']+options))
    phase('applying');result=executor.apply(op);write('completed.json',result);assert result['state']=='completed' and result['traffic_resumed'];phase('completed_needs_verification')
    current=load(target);assert current['generation']==10 and current['image_id']==FULL and current['worker_id']!=config['worker_id']
    new= DockerObserver(current);after=new.state(new.read(),catalog.snapshot())['state'];actual=json.loads(sql(new,BUSINESS_SQL));actual_schema=json.loads(sql(new,SCHEMA))
    assert [{k:v for k,v in n.items() if k!='x_notes_labels'} for n in actual['notes']]==business['notes'] and actual['boards']==business['boards']
    assert all(n['x_notes_labels'] is None for n in actual['notes']) and json.loads(sql(new,IDENTITIES))==identity
    assert len(after['bindings'])==10 and len(after['installations'])==6 and all(i['state']==i['metadata_state']=='installed' and i['feature_state']=='enabled' for i in after['installations'])
    assert after['bindings']==bundle['operation_lock']['bindings']
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-op-'+op+'-native']))[0]
    assert child['State']['ExitCode']==0 and '-i' in child['Config']['Cmd'] and '-u' not in child['Config']['Cmd']
    logs=(control/'stages'/op/'native.log').read_text(encoding='utf8')+(control/'stages'/op/'native.log.stderr.log').read_text(encoding='utf8');assert 'Labels extension migration normalized' not in logs
    old_files=load(OUTPUT/'files-before.json');now=files(new);assert all(now[n]==h for n,h in old_files.items())
    for name,value in [('state-after',after),('business-after',actual),('schema-after',actual_schema),('files-after',now),('native-initialization',dict(arguments=child['Config']['Cmd'],current_version='0.2.1',historical_migrations_absent=True))]:write(name+'.json',value)
    write('mirror.json',invoke(ops+['mirror-status',op]+options));guard()
    state.update(phase='permission_upgrade_base_ready',generation=10,image_id=FULL,worker_id=current['worker_id']);(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('qualification.json',dict(result='passed_staged_reinstall_prerequisite',operation_id=op,plan_hash=record['plan_hash'],generation=10,stable_identities=True,notes_boards_preserved=True,old_files_preserved=len(old_files),historical_migrations_absent=True,limits=['Prerequisite only; LIFE-05 permission-expanding upgrade has not run.']))
    print(json.dumps(dict(result='completed_verified',operation_id=op,generation=10)))


if __name__=='__main__':main()
