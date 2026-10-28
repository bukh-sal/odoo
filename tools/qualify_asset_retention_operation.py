"""Exact core asset adapter operations: pre-ready fault/restore, then normal.

Never replay a partially executed operation; private markers and the independent
journal are authoritative. The runtime source/image is already clone-qualified.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sys
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL,command
from qualify_release_reader_rollout import files
from qualify_staged_planning import invoke,write
from qualify_asset_retention_clone import NoRedirect
import r1,r1_probe

IMAGE='sha256:93fd708303d10d12efc526de07ae0c07b32c0c186b03b365820dd88c641d765a'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);parser.add_argument('--mode',choices=['fault','normal','binding'],required=True)
    parser.add_argument('--image-id',default=IMAGE);args=parser.parse_args();image=args.image_id
    mode=args.mode;base={'fault':22,'normal':24,'binding':25}[mode];output=ROOT/('docs/evidence/G5/20261028-asset-retention-'+mode+'-01');local=ROOT/'.local/g5'
    assert (mode=='binding') or image==IMAGE
    marker=local/('asset-retention-'+mode+'-01.json');operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text(encoding='utf-8'));state=json.loads((local/'state.json').read_text(encoding='utf-8'))
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==base and state['disposable'] and state['active_db']==config['sites'][0]['database']
    assert re.fullmatch(r'mp_disposable_r0_r1_[a-z0-9_]+',state['active_db'])
    clone=json.loads((ROOT/'docs/evidence/G5/20261028-asset-retention-identity-clone-01/asset-retention.json').read_text(encoding='utf-8'))
    assert clone['result']=='passed_native_asset_clone' and clone['image_id']==IMAGE
    if mode=='normal':assert json.loads((local/'asset-retention-fault-01.json').read_text(encoding='utf-8'))['state']=='restored_verified_and_resumed'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot();observer=DockerObserver(config)
    observation=observer.read();before=observer.state(observation,catalog)['state'];assert len(before['installations'])==4
    def sql(reader,query):return command(['docker','exec','-i',reader._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',reader.config['sites'][0]['database']],input=query.encode())
    business=json.loads(sql(observer,BUSINESS_SQL));assert len(business['notes'])==4 and business['boards'][0]['revision']==2
    asset_query="SELECT jsonb_agg(jsonb_build_object('url',url,'checksum',checksum,'mimetype',mimetype) ORDER BY url,id) FROM ir_attachment WHERE public AND res_model='ir.ui.view' AND res_id=0 AND create_uid=1 AND url LIKE '/web/assets/%/mp_shell.assets_host%';"
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    if args.action=='prepare':
        assert not marker.exists() and not output.exists();output.mkdir(parents=True)
        write(marker,{'state':'preparing','mode':mode,'evidence':output.relative_to(ROOT).as_posix()})
        write(output/'state-before.json',before);write(output/'business-before.json',business);write(output/'files-before.json',files(observer));write(output/'assets-before.json',json.loads(sql(observer,asset_query)))
        write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',image]+options))
        nomination={'operation_type':'deploy' if mode=='binding' else 'core_upgrade','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options);write(output/'bundle.json',bundle)
        if mode=='binding':
            assert 'native_core_changes' not in bundle['operation_lock'] and not bundle['plan']['destructive']
            assert [row['path'] for row in bundle['operation_lock']['platform_source_diff']]==['packages/platform_sdk/modular_platform/prepare_assets.py']
        else:assert bundle['operation_lock']['native_core_changes']==[{'addon':'mp_shell','previous_version':'19.0.0.1.2','target_version':'19.0.0.1.3','migrations':[]}]
        assert len(bundle['operation_lock']['targets'])==4 and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
        assert observer.state(observer.read(),catalog)['state']==before
        record={'state':'prepared_not_registered','mode':mode,'operation_id':bundle['plan']['operation_id'],'plan_hash':bundle['plan_hash'],'base_generation':base,
                'image_id':image,'before_digest':data_digest(before),'evidence':output.relative_to(ROOT).as_posix()}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['mode']==mode and record['image_id']==image
    bundle=json.loads((output/'bundle.json').read_text(encoding='utf-8'));operation=record['operation_id']
    assert data_digest(before)==record['before_digest'] and json.loads((output/'business-before.json').read_text(encoding='utf-8'))==business
    old_files=json.loads((output/'files-before.json').read_text(encoding='utf-8'));assert files(observer)==old_files
    old_assets=json.loads((output/'assets-before.json').read_text(encoding='utf-8'))
    def phase(name,**details):
        record.update(state=name,utc=datetime.now(timezone.utc).isoformat(),**details);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator);phase('registering')
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation));write(output/'independent-review.json',store.review(operation,native._validate()))
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation))
    phase('applying');print(json.dumps({'stage':'approved_exact_plan','operation_id':operation,'mode':mode}),flush=True)
    if mode=='fault':
        original=native._private_command
        def fault(arguments,path,**kwargs):
            result=original(arguments,path,**kwargs)
            if path.name=='assets.json':raise OperatorError('Disposable asset preflight-stage failure after actual preparation before ready')
            return result
        with patch.object(native,'_private_command',side_effect=fault):
            try:native.apply(operation)
            except OperatorError as error:
                if 'Disposable asset preflight-stage failure' not in str(error):raise
            else:raise AssertionError('Expected pre-ready asset-stage fault absent')
        failed=invoke(operations+['show',operation]);write(output/'failed-status.json',failed)
        assert failed['state']=='recovery_required' and not failed['traffic_resumed'] and failed['phase']=='workers_replaced'
        assert json.loads(target.read_text(encoding='utf-8'))==config,'Pre-ready failure must not publish configuration'
        phase('recovery_required');print(json.dumps({'stage':'recovery_required','operation_id':operation,'before_ready':True}),flush=True)
        recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator));decision=recovery.prepare(operation)
        write(output/'restore-decision.json',decision);phase('restoring',restore_hash=data_digest(decision))
        write(output/'restore-result.json',recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True))
        current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==24 and current['image_id']==config['image_id'] and current['sites'][0]['database']!=config['sites'][0]['database']
        prepared=json.loads((control/'recoveries'/operation/'assets.json').read_text(encoding='utf-8'));assert prepared['result']=='prepared' and prepared['generation']==24
        write(output/'restore-prepared-assets.json',prepared);phase('restored_before_separate_resume',restored_database=current['sites'][0]['database'])
        recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator));resume=recovery.prepare_resume(operation)
        write(output/'resume-decision.json',resume);write(output/'resume-result.json',recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True));assert store.status(operation)['state']=='revoked'
    else:
        completed=native.apply(operation);write(output/'completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed']
        phase('completed_needs_verification');current=json.loads(target.read_text(encoding='utf-8'));assert current['image_id']==image and current['generation']==base+1
        if mode=='binding':assert (control/'stages'/operation/'native-skipped.json').is_file() and not (control/'stages'/operation/'native.log').exists()
        assert native.apply(operation)==completed;write(output/'completed-replay.json',{'same_saved_status_no_new_asset_or_native_child':True})
    prepared=json.loads((control/'stages'/operation/'assets.json').read_text(encoding='utf-8'));assert prepared['result']=='prepared' and prepared['generation']==base+1
    assert all(re.fullmatch(r'/web/assets/[0-9a-f]{64}/mp_shell.assets_host.min.(js|css)',asset['url']) for asset in prepared['assets'])
    write(output/'prepared-assets.json',prepared)
    reader=DockerObserver(current);observed=reader.read();after=reader.state(observed,catalog)['state']
    assert json.loads(sql(reader,BUSINESS_SQL))==business and before['installations']==after['installations'] and before['bindings']==after['bindings']
    expected='19.0.0.1.2' if mode=='fault' else '19.0.0.1.3';assert next(row for row in observed['sites'][0]['native_modules'] if row['addon']=='mp_shell')['version']==expected
    now_files=files(reader);assert all(now_files.get(name)==value for name,value in old_files.items())
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'));assert cache['configuration']['generation']==current['generation'] and cache['configuration']['published_release']==current['published_release']
    state.update(active_db=current['sites'][0]['database'],image_id=current['image_id'],worker_id=current['worker_id'],release_generation=current['generation'],stage='asset_retention_'+mode)
    state['databases']=list(dict.fromkeys(state['databases']+[state['active_db']]));state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]));state['evidence']=output.relative_to(ROOT).as_posix()
    (local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    if mode=='fault':
        seeded=json.loads((local/'lifecycle-data.json').read_text(encoding='utf-8'));seeded['restored_database']=state['active_db'];(local/'lifecycle-data.json').write_text(json.dumps(seeded,indent=2)+'\n',encoding='utf-8')
    fixture=json.loads((local/'fixtures.json').read_text(encoding='utf-8'));r1.r0.LOCAL=local;client=r1_probe.Client(state,fixture)
    http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(client.jar),NoRedirect());responses=[]
    for asset in old_assets+([] if mode=='fault' else prepared['assets']):
        with http.open(client.base+asset['url'],timeout=30) as response:
            import hashlib
            raw=response.read();assert response.status==200 and response.geturl()==client.base+asset['url']
            if 'checksum' in asset:assert hashlib.sha1(raw).hexdigest()==asset['checksum']
            if 'sha256' in asset:assert hashlib.sha256(raw).hexdigest()==asset['sha256']
            assert 'immutable' in response.headers.get('Cache-Control','') and response.headers.get_content_type()==asset['mimetype']
            responses.append({'url':asset['url'],'sha256':hashlib.sha256(raw).hexdigest(),'redirected':False})
    write(output/'state-after.json',after);phase('restored_verified_and_resumed' if mode=='fault' else 'completed_verified')
    write(output/'asset-operation.json',{'result':'passed_runtime_subset','mode':mode,'utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,'plan_hash':bundle['plan_hash'],
          'configuration':current,'regular_assets_prepared_before_ready':True,'native_shell_version':expected,'old_and_current_asset_responses':responses,
          'original4_notes_board2_features_grants_bindings_exact':True,'old_filestore_files_preserved':len(old_files),'automatic_cache_current':True,
          'limits':['Fault injected after a successful real asset child, before ready; not an OS executor crash or a real compiler failure.','Full G5 and locale/RTL/accessibility remain pending.']})
    print(json.dumps({'result':'passed_runtime_subset','mode':mode,'operation_id':operation,'generation':current['generation'],'database':state['active_db']}),flush=True)


if __name__=='__main__':main()
