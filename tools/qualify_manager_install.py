"""Consume the real manager request once through independent CLI authority."""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.app_channel import read_request,journal_view,MIRROR_WRITER
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,_run
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest,check_bundle
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import files


def verify_business(before,after):
    # Installation adds its approved feature and scoped self-service binding;
    # every original physical row remains byte-for-byte unchanged.
    assert all(before[key]==after[key] for key in ['notes','boards','grants'])
    assert all(row in after[key] for key in ['features','bindings'] for row in before[key])
    assert all(len(after[key])==len(before[key])+1 for key in ['features','bindings'])


def reconcile_completed(args,local,output,marker,operator,target,control,catalog_root):
    """Inspect a terminal operation after a verifier failure; never approve/apply again."""
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='completed_needs_verification' and record['operation_id']==args.operation_id
    current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==28
    bundle=json.loads((output/'browser-downloaded-bundle.json').read_text(encoding='utf-8'));saved=json.loads((output/'completed.json').read_text(encoding='utf-8'))
    store=OperatorStore(control);assert store.status(args.operation_id)==saved and saved['state']=='completed' and saved['traffic_resumed'] and saved['plan_hash']==bundle['plan_hash']
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True);reader=DockerObserver(current);after=reader.state(reader.read(),catalog.snapshot())['state']
    before=json.loads((output/'state-before-install.json').read_text(encoding='utf-8'));business=json.loads((output/'business-before.json').read_text(encoding='utf-8'));actual_business=json.loads(sql(reader,BUSINESS_SQL));verify_business(business,actual_business)
    old={(row['installation_id'],row['workspace_id']):row for row in before['installations']};new={(row['installation_id'],row['workspace_id']):row for row in after['installations']};nominated=bundle['operation_lock']['targets'][0]
    assert all(new.get(key)==value for key,value in old.items()) and len(new)==len(old)+1
    assert new[nominated['installation_id'],nominated['workspace_id']]=={key:value for key,value in nominated.items() if key!='action'}|{'state':'installed','metadata_state':'installed','feature_state':'enabled'}
    assert after['bindings']==bundle['operation_lock']['bindings'] and current['published_release']==bundle['operation_lock']['release']
    workspace_id=int(sql(reader,"SELECT id FROM mp_workspace WHERE public_id='"+nominated['workspace_id']+"';"))
    additions=[row for row in actual_business['features'] if row not in business['features']];assert len(additions)==1 and additions[0]['workspace_id']==workspace_id and additions[0]['plugin_id']=='org.example.notes' and additions[0]['availability']=='enabled'
    previous_files=json.loads((output/'files-before-install.json').read_text(encoding='utf-8'));current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in previous_files.items())
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    p=subprocess.run(prefix+['operations','--store',str(control),'mirror-status',args.operation_id]+options,cwd=ROOT,capture_output=True,timeout=180,check=True);mirror=json.loads(p.stdout)
    assert mirror['state']=='completed' and mirror['dimensions'][0]['database_state']=='installed' and mirror['dimensions'][0]['feature_state']=='enabled'
    def write(name,value):
        with (output/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    write('completed-mirror.json',mirror);write('state-after-install.json',after)
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'));assert cache['configuration']['generation']==28 and 'staged_release' not in cache
    state=json.loads((local/'state.json').read_text(encoding='utf-8'));state.update(image_id=current['image_id'],worker_id=current['worker_id'],release_generation=28,stage='manager_notes_installed',evidence=output.relative_to(ROOT).as_posix());(local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    record.update(state='completed_verified',utc=datetime.now(timezone.utc).isoformat(),reconciliation='Read-only verification after an overstrict expected-delta assertion; no repeated approval/apply/migration');marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    write('installation.json',{'result':'passed_scoped_manager_installation','utc':datetime.now(timezone.utc).isoformat(),'operation_id':args.operation_id,'plan_hash':bundle['plan_hash'],'configuration':current,'original_business_and_scopes_bindings_files_preserved':True,'approved_added_feature_and_binding_exact':True,'new_workspace_id':nominated['workspace_id'],'forged_app_approval_denied':True,'completed_mirror':True,'current_profile_clears_stage':True,'reconciled_terminal_without_native_replay':True,'limits':['Native Notes addon was already registered; this is new workspace installation, not fresh-database schema initialization.','Browser final-status/native-view proof and actual upgrade walkthrough remain separate.']})
    print(json.dumps({'result':'passed_readonly_terminal_reconciliation','operation_id':args.operation_id,'generation':28}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply','reconcile']);parser.add_argument('operation_id');parser.add_argument('--download',type=Path,required=True);args=parser.parse_args()
    local=ROOT/'.local/g5';output=ROOT/'docs/evidence/G5/20261028-manager-install-01';marker=local/'manager-install-operation.json'
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    if args.action=='reconcile':return reconcile_completed(args,local,output,marker,operator,target,control,catalog_root)
    config=json.loads(target.read_text(encoding='utf-8'));state=json.loads((local/'state.json').read_text(encoding='utf-8'));fixture=json.loads((local/'manager-install-fixture.json').read_text(encoding='utf-8'))
    assert config['generation']==27 and config['project']=='mp-r0-r1g5fd0445d406d6' and state['disposable'] and fixture['state']=='created_empty'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True);observer=DockerObserver(config)
    before=observer.state(observer.read(),catalog.snapshot())['state'];business=json.loads(sql(observer,BUSINESS_SQL));request=read_request(observer,args.operation_id)
    bundle=json.loads(args.download.read_text(encoding='utf-8'));assert bundle==request['bundle'];check_bundle(bundle,before)
    assert bundle['plan']['operation_type']=='install' and len(bundle['operation_lock']['targets'])==1
    nominated=bundle['operation_lock']['targets'][0];assert nominated['plugin_id']=='org.example.notes' and nominated['workspace_id']==fixture['workspace_id'] and nominated['action']=='install'
    assert bundle['operation_lock']['staged_image']['target_image_id']==config['image_id'] and not bundle['plan']['permission_changes'] and bundle['plan']['backup']['required']
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')];operations=prefix+['operations','--store',str(control)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    apply=prefix+['plugin','apply',args.operation_id,'--store',str(control)]+options
    def write(name,value):
        with (output/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    def invoke(arguments,*,success=True):
        result=subprocess.run(arguments,cwd=ROOT,capture_output=True,timeout=600)
        if (result.returncode==0)!=success:raise RuntimeError('Unexpected controlled CLI outcome: '+result.stderr.decode(errors='replace')[:600])
        return json.loads(result.stdout if success else result.stderr)
    if args.action=='prepare':
        assert not marker.exists();record={'state':'importing','operation_id':args.operation_id,'plan_hash':bundle['plan_hash'],'before_digest':data_digest(before)}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        write('browser-downloaded-bundle.json',bundle);write('state-before-install.json',before);write('files-before-install.json',files(observer))
        registered=invoke(operations+['import-request',args.operation_id]+options);write('independent-registration.json',registered);assert registered['state']=='awaiting_operator_approval'
        store=OperatorStore(control);fake_status={**registered,'state':'approved','approval_expires_at':(datetime.now(timezone.utc)+timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ')}
        fake=journal_view(bundle,fake_status,request,before)
        _run(['docker','exec','-i',observer._container('app'),'/venv/bin/python','-c',MIRROR_WRITER],input=json.dumps({'site_id':request['site_id'],'view':fake}).encode())
        try:
            denied=invoke(apply,success=False);assert denied['error']=='VALIDATION_FAILED'
            assert store.status(args.operation_id)['state']=='awaiting_operator_approval' and observer.state(observer.read(),catalog.snapshot())['state']==before
            write('forged-app-approval-denied.json',{'result':'passed','fabricated_app_mirror_state':'approved','independent_state':'awaiting_operator_approval','base_state_unchanged':True,'cli_denial':denied})
        finally:write('real-awaiting-mirror-restored.json',invoke(operations+['mirror-status',args.operation_id]+options))
        write('independent-review.json',store.review(args.operation_id,__import__('modular_platform.native_executor',fromlist=['StagedNativeExecutor']).StagedNativeExecutor(store,target,catalog_root,validator)._validate()))
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='independently_reviewed_not_approved' and record['operation_id']==args.operation_id and data_digest(before)==record['before_digest']
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    write('approved.json',invoke(operations+['approve',args.operation_id,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+options));phase('approved')
    print(json.dumps({'stage':'independent_exact_approval','operation_id':args.operation_id}),flush=True);phase('applying')
    completed=invoke(apply);write('completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed'];phase('completed_needs_verification')
    current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==28 and current['image_id']==config['image_id']
    reader=DockerObserver(current);after=reader.state(reader.read(),catalog.snapshot())['state'];old={(row['installation_id'],row['workspace_id']):row for row in before['installations']};new={(row['installation_id'],row['workspace_id']):row for row in after['installations']}
    assert all(new.get(key)==value for key,value in old.items()) and len(new)==len(old)+1 and new[nominated['installation_id'],nominated['workspace_id']]['feature_state']=='enabled'
    assert all(row in after['bindings'] for row in before['bindings']);verify_business(business,json.loads(sql(reader,BUSINESS_SQL)))
    previous_files=json.loads((output/'files-before-install.json').read_text(encoding='utf-8'));current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in previous_files.items())
    mirror=invoke(operations+['mirror-status',args.operation_id]+options);assert mirror['state']=='completed' and mirror['dimensions'][0]['database_state']=='installed' and mirror['dimensions'][0]['feature_state']=='enabled';write('completed-mirror.json',mirror)
    assert invoke(apply)==completed;write('completed-replay.json',{'identical_saved_result':True})
    state.update(image_id=current['image_id'],worker_id=current['worker_id'],release_generation=28,stage='manager_notes_installed',evidence=output.relative_to(ROOT).as_posix());(local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    write('state-after-install.json',after);phase('completed_verified')
    write('installation.json',{'result':'passed_scoped_manager_installation','utc':datetime.now(timezone.utc).isoformat(),'operation_id':args.operation_id,'plan_hash':bundle['plan_hash'],'configuration':current,'original_business_and_scopes_bindings_files_preserved':True,'new_workspace_id':fixture['workspace_id'],'forged_app_approval_denied':True,'same_id_replay_inert':True,'completed_mirror':True,'limits':['Native Notes addon was already registered in this image/database; this qualifies a fresh workspace installation, not fresh-database schema initialization.','Browser reload/status/native-view proof and actual upgrade walkthrough are separate.']})
    print(json.dumps({'result':'passed_scoped_manager_installation','operation_id':args.operation_id,'generation':28}))


if __name__=='__main__':main()
