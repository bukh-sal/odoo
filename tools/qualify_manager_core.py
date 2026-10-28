"""Once-only exact manager core activation; preserve the populated G5 target."""
import argparse
from datetime import datetime,timezone
import json
import re
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
from qualify_release_reader_rollout import files
from qualify_staged_planning import invoke,write


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);parser.add_argument('--image-id',required=True)
    parser.add_argument('--run-id',default='manager-core-activation');args=parser.parse_args()
    assert re.fullmatch(r'manager-core-[a-z0-9-]+',args.run_id)
    output=ROOT/('docs/evidence/G5/20261028-'+args.run_id);local=ROOT/'.local/g5';marker=local/(args.run_id+'.json')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text(encoding='utf-8'));state=json.loads((local/'state.json').read_text(encoding='utf-8'))
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==26 and state['disposable']
    assert state['active_db']==config['sites'][0]['database']=='mp_disposable_r0_r1_restore_9c577916f75c4e06ae8ed62444fcca48'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot();observer=DockerObserver(config)
    observed=observer.read();before=observer.state(observed,catalog)['state'];assert len(before['installations'])==4
    def sql(reader,query):return command(['docker','exec','-i',reader._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',reader.config['sites'][0]['database']],input=query.encode())
    business=json.loads(sql(observer,BUSINESS_SQL));assert len(business['notes'])==4 and business['boards'][0]['revision']==2
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    if args.action=='prepare':
        assert not marker.exists() and not output.exists();output.mkdir(parents=True)
        write(marker,{'state':'preparing','image_id':args.image_id})
        write(output/'state-before.json',before);write(output/'business-before.json',business);write(output/'files-before.json',files(observer))
        write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',args.image_id]+options))
        nomination={'operation_type':'core_upgrade','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options);write(output/'bundle.json',bundle)
        assert bundle['operation_lock']['native_core_changes']==[
            {'addon':'mp_core','previous_version':'19.0.0.1.2','target_version':'19.0.0.1.3','migrations':[]},
            {'addon':'mp_shell','previous_version':'19.0.0.1.3','target_version':'19.0.0.1.4','migrations':[]}]
        assert len(bundle['operation_lock']['targets'])==4 and bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
        assert observer.state(observer.read(),catalog)['state']==before
        record={'state':'prepared_not_registered','operation_id':bundle['plan']['operation_id'],'plan_hash':bundle['plan_hash'],'image_id':args.image_id,'before_digest':data_digest(before),'evidence':output.relative_to(ROOT).as_posix()}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['image_id']==args.image_id and record['before_digest']==data_digest(before)
    bundle=json.loads((output/'bundle.json').read_text(encoding='utf-8'));operation=record['operation_id']
    assert json.loads((output/'business-before.json').read_text(encoding='utf-8'))==business
    old_files=json.loads((output/'files-before.json').read_text(encoding='utf-8'));assert files(observer)==old_files
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator)
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    phase('registering');operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    write(output/'independent-review.json',store.review(operation,native._validate()))
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation))
    phase('applying');print(json.dumps({'stage':'approved_exact_core_plan','operation_id':operation}),flush=True)
    result=native.apply(operation);write(output/'completed.json',result);assert result['state']=='completed' and result['traffic_resumed'];phase('completed_needs_verification')
    current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==27 and current['image_id']==args.image_id
    reader=DockerObserver(current);observation=reader.read();after=reader.state(observation,catalog)['state']
    assert before['installations']==after['installations'] and before['bindings']==after['bindings'] and json.loads(sql(reader,BUSINESS_SQL))==business
    current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in old_files.items())
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'));assert cache['configuration']['generation']==27 and 'staged_release' not in cache
    assert native.apply(operation)==result
    state.update(image_id=current['image_id'],worker_id=current['worker_id'],release_generation=27,stage='manager_core_activated',evidence=output.relative_to(ROOT).as_posix())
    (local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');write(output/'state-after.json',after)
    assets=json.loads((control/'stages'/operation/'assets.json').read_text(encoding='utf-8'));assert assets['result']=='prepared' and assets['generation']==27
    write(output/'prepared-assets.json',assets);phase('completed_verified')
    write(output/'activation.json',{'result':'passed_core_activation','utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,'plan_hash':bundle['plan_hash'],'configuration':current,'original_business_scopes_bindings_preserved':True,'old_files_preserved':len(old_files),'preflight_before_ready':True,'profile_current_and_candidate_preview_cleared':True,'same_id_saved_status_inert':True,'limitations':['Manager UI install/upgrade flow and current-source authority qualification still required; this is only the core prerequisite.']})
    print(json.dumps({'result':'passed_core_activation','operation_id':operation,'generation':27}))


if __name__=='__main__':main()
