"""New exact normal core plan after the terminal recovery rehearsal."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL,command
from qualify_client_release_core_fault import IMAGE
from qualify_release_reader_rollout import files
from qualify_staged_planning import invoke,write
import r1,r1_probe

OUTPUT=ROOT/'docs/evidence/G5/20261028-client-release-core-promotion-01'
MARKER=ROOT/'.local/g5/client-release-core-promotion-01.json'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog';local=ROOT/'.local/g5'
    config=json.loads(target.read_text(encoding='utf-8'));state=json.loads((local/'state.json').read_text(encoding='utf-8'))
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==18 and state['disposable']
    assert state['active_db']==config['sites'][0]['database']=='mp_disposable_r0_r1_restore_dc31daa565c94a1d8569db840c246a58'
    assert json.loads((local/'client-release-core-fault-01.json').read_text(encoding='utf-8'))['state']=='restored_verified_and_resumed'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);before=observer.state(observer.read(),catalog)['state'];assert len(before['installations'])==4
    def sql(reader,query):return command(['docker','exec','-i',reader._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',reader.config['sites'][0]['database']],input=query.encode())
    business=json.loads(sql(observer,BUSINESS_SQL));assert len(business['notes'])==4 and business['boards'][0]['revision']==2
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    if args.action=='prepare':
        assert not MARKER.exists() and not OUTPUT.exists();OUTPUT.mkdir(parents=True)
        write(MARKER,{'state':'preparing','evidence':OUTPUT.relative_to(ROOT).as_posix()})
        write(OUTPUT/'state-before.json',before);write(OUTPUT/'business-before.json',business);write(OUTPUT/'files-before.json',files(observer))
        write(OUTPUT/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',IMAGE]+options))
        nomination={'operation_type':'core_upgrade','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write(OUTPUT/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(OUTPUT/'nomination.json')]+options);write(OUTPUT/'bundle.json',bundle)
        assert bundle['plan']['destructive'] and not bundle['plan']['permission_changes'] and len(bundle['operation_lock']['targets'])==4
        assert {row['addon'] for row in bundle['operation_lock']['native_core_changes']}=={'mp_identity','mp_core','mp_shell'}
        assert observer.state(observer.read(),catalog)['state']==before
        record={'state':'prepared_not_registered','operation_id':bundle['plan']['operation_id'],'plan_hash':bundle['plan_hash'],'before_digest':data_digest(before),'candidate_image_id':IMAGE,'evidence':OUTPUT.relative_to(ROOT).as_posix()}
        MARKER.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(record));return
    record=json.loads(MARKER.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['candidate_image_id']==IMAGE
    bundle=json.loads((OUTPUT/'bundle.json').read_text(encoding='utf-8'));operation=record['operation_id']
    assert data_digest(before)==record['before_digest'] and json.loads((OUTPUT/'business-before.json').read_text(encoding='utf-8'))==business
    old_files=json.loads((OUTPUT/'files-before.json').read_text(encoding='utf-8'));assert files(observer)==old_files
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator)
    def phase(name):
        record.update(state=name,utc=datetime.now(timezone.utc).isoformat());MARKER.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    phase('registering')
    write(OUTPUT/'registered.json',invoke(operations+['register','--bundle',str(OUTPUT/'bundle.json')]+validation))
    write(OUTPUT/'independent-review.json',store.review(operation,native._validate()))
    write(OUTPUT/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation))
    phase('approved_exact_plan');print(json.dumps({'stage':'approved_exact_plan','operation_id':operation}),flush=True)
    phase('applying');completed=native.apply(operation);write(OUTPUT/'completed.json',completed)
    assert completed['state']=='completed' and completed['traffic_resumed'];phase('completed_needs_verification')
    current=json.loads(target.read_text(encoding='utf-8'));assert current['image_id']==IMAGE and current['generation']==19
    reader=DockerObserver(current);observed=reader.read();after=reader.state(observed,catalog)['state']
    assert current['published_release']==bundle['operation_lock']['release'] and after['installations']==before['installations'] and after['bindings']==before['bindings']
    assert json.loads(sql(reader,BUSINESS_SQL))==business
    current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in old_files.items())
    expected={row['addon']:row['target_version'] for row in bundle['operation_lock']['native_core_changes']}
    assert {row['addon']:row['version'] for row in observed['sites'][0]['native_modules'] if row['addon'] in expected}==expected
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'))
    assert cache['configuration']['published_release']==current['published_release'] and cache['configuration']['generation']==19
    assert native.apply(operation)==completed;write(OUTPUT/'completed-replay.json',{'same_saved_status_no_native_replay':True})
    state.update(active_db=current['sites'][0]['database'],image_id=current['image_id'],worker_id=current['worker_id'],release_generation=19,stage='client_release_core_promoted')
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]));state['evidence']=OUTPUT.relative_to(ROOT).as_posix()
    (local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    fixture=json.loads((local/'fixtures.json').read_text(encoding='utf-8'));fixture['bindings']={}
    for key,space in fixture['workspaces'].items():
        installation=next(row for row in after['installations'] if row['plugin_id']=='org.example.notes' and row['workspace_id']==space['public_id'])
        fixture['bindings'][key]=next(row for row in after['bindings'] if row['consumer_installation_id']==installation['installation_id'] and row['workspace_id']==space['public_id'] and row['alias']=='documents')
    r1.r0.LOCAL=local;client=r1_probe.Client(state,fixture);assert client.release_token
    row=next(row for row in business['notes'] if row['workspace_id']==1)
    assert client.call('get',{'note_id':row['public_id']})['revision']==row['revision']
    client.native('read',[[row['id']],['title','revision']])
    denied=client.call('update',{'note_id':row['public_id'],'expected_revision':row['revision'],'title':'MUST_NOT_CHANGE'},headers={'X-MP-Client-Release':'sha256:'+'0'*64},expect=409,code='CONFLICT')
    assert denied['error']['details']=={'field':'client_release','outcome':'not_started'}
    assert json.loads(sql(reader,BUSINESS_SQL))==business
    write(OUTPUT/'state-after.json',after);phase('completed_verified')
    write(OUTPUT/'core-promotion.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,'plan_hash':bundle['plan_hash'],'configuration':current,
          'native_core_changes':bundle['operation_lock']['native_core_changes'],'all_four_scopes_bindings_grants_original_business_preserved':True,'original_notes':4,'original_board_revision':2,
          'old_filestore_files_preserved':len(old_files),'automatic_cache_before_ready':True,'completed_same_id_no_native_replay':True,'current_pin_native_gateway_positive':True,'stale_pin_update_denied_before_dispatch':True,
          'limits':['Initial protocol activation from a legacy image; old documents require explicit reload.', 'Actual protocol1-to-protocol1 changed-asset browser activation and full UI07/G5 still pending.']})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'generation':19,'evidence':OUTPUT.relative_to(ROOT).as_posix()}))


if __name__=='__main__':main()
