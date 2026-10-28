"""Actual protocol1 static activation/fault recovery; exact once-only plans.

Browser drafts must be staged before apply. Preparation and execution have
separate recorded phases. Never replay an interrupted/terminal execution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import validate_platform_deploy
from modular_platform.restore_executor import RestoreExecutor
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL,command
from qualify_release_reader_rollout import files
from qualify_staged_planning import invoke,write


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply'])
    parser.add_argument('--mode',choices=['fault','normal'],required=True);parser.add_argument('--image-id',required=True)
    parser.add_argument('--expected-generation',type=int,required=True);args=parser.parse_args()
    mode=args.mode;generation=args.expected_generation;image=args.image_id
    assert generation==({'fault':19,'normal':21}[mode])
    output=ROOT/('docs/evidence/G5/20261028-client-refresh-static-'+mode+'-01')
    local=ROOT/'.local/g5';marker=local/('client-refresh-static-'+mode+'-01.json')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text(encoding='utf-8'));state=json.loads((local/'state.json').read_text(encoding='utf-8'))
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==generation and state['disposable']
    assert config['sites'][0]['database']==state['active_db']
    if mode=='normal':assert json.loads((local/'client-refresh-static-fault-01.json').read_text(encoding='utf-8'))['state']=='restored_verified_and_resumed'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observation=observer.read();before=observer.state(observation,catalog)['state']
    assert len(before['installations'])==4 and observation['runtime']['published_release_protocol']==1
    def sql(reader,query):return command(['docker','exec','-i',reader._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',reader.config['sites'][0]['database']],input=query.encode())
    business=json.loads(sql(observer,BUSINESS_SQL));assert len(business['notes'])==4 and business['boards'][0]['revision']==2
    versions={row['addon']:row['version'] for row in observation['sites'][0]['native_modules']}
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    if args.action=='prepare':
        assert not output.exists() and not marker.exists();output.mkdir(parents=True);(output/'browser').mkdir()
        write(marker,{'state':'preparing','mode':mode,'image_id':image,'expected_generation':generation,'evidence':output.relative_to(ROOT).as_posix()})
        candidate=inspect_image(image)
        changed=validate_platform_deploy(observation['runtime'],candidate,{'base_image_id':config['image_id'],'target_image_id':image})
        assert changed
        old=observation['runtime']['inventory']['files'];new=candidate['inventory']['files']
        paths=sorted(name for name in old.keys()|new.keys() if old.get(name)!=new.get(name))
        assert paths==['addons/mp_shell/static/src/host.js'],paths
        write(output/'state-before.json',before);write(output/'business-before.json',business);write(output/'files-before.json',files(observer));write(output/'native-versions-before.json',versions)
        write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',image]+options))
        nomination={'operation_type':'deploy','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options);write(output/'bundle.json',bundle)
        assert len(bundle['operation_lock']['targets'])==4 and not bundle['plan']['permission_changes'] and not bundle['plan']['destructive']
        assert 'native_core_changes' not in bundle['operation_lock'] and observer.state(observer.read(),catalog)['state']==before
        record={'state':'prepared_not_registered','mode':mode,'image_id':image,'expected_generation':generation,'operation_id':bundle['plan']['operation_id'],
                'plan_hash':bundle['plan_hash'],'before_digest':data_digest(before),'changed_inventory_paths':paths,'evidence':output.relative_to(ROOT).as_posix()}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['mode']==mode and record['image_id']==image
    bundle=json.loads((output/'bundle.json').read_text(encoding='utf-8'));operation=record['operation_id']
    assert data_digest(before)==record['before_digest'] and json.loads((output/'business-before.json').read_text(encoding='utf-8'))==business
    old_files=json.loads((output/'files-before.json').read_text(encoding='utf-8'));assert files(observer)==old_files
    # The browser record proves actual dirty documents exist before mutation;
    # no test silently substitutes seeded records for in-memory draft recovery.
    browser=json.loads((output/'browser/before.json').read_text(encoding='utf-8'))
    assert browser['generation']==generation and browser['native_dirty'] and browser['canvas_dirty'] and browser['no_saved_mutations']
    def phase(name,**details):
        record.update(state=name,utc=datetime.now(timezone.utc).isoformat(),**details);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator);phase('registering')
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    write(output/'independent-review.json',store.review(operation,native._validate()))
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation))
    phase('applying');print(json.dumps({'stage':'approved_exact_plan','mode':mode,'operation_id':operation}),flush=True)
    if mode=='fault':
        advance=store.advance
        def fault(selected,locks,selected_phase,**details):
            result=advance(selected,locks,selected_phase,**details)
            if selected==operation and selected_phase=='release_published':raise OperatorError('Disposable protocol1 asset activation fault before traffic')
            return result
        with patch.object(store,'advance',side_effect=fault):
            try:native.apply(operation)
            except OperatorError as error:
                if 'Disposable protocol1 asset activation fault' not in str(error):raise
            else:raise AssertionError('Expected static activation fault absent')
        failed=invoke(operations+['show',operation]);write(output/'failed-status.json',failed)
        assert failed['state']=='recovery_required' and failed['mutation_started'] and not failed['traffic_resumed']
        changed=json.loads(target.read_text(encoding='utf-8'));assert changed['image_id']==image and changed['generation']==generation+1
        phase('recovery_required');print(json.dumps({'stage':'recovery_required','operation_id':operation}),flush=True)
        recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator));decision=recovery.prepare(operation)
        write(output/'restore-decision.json',decision);phase('restoring',restore_hash=data_digest(decision))
        write(output/'restore-result.json',recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True))
        current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==generation+2 and current['image_id']==config['image_id'] and current['sites'][0]['database']!=config['sites'][0]['database']
        phase('restored_before_separate_resume',restored_database=current['sites'][0]['database'])
        recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator));resume=recovery.prepare_resume(operation)
        write(output/'resume-decision.json',resume);write(output/'resume-result.json',recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True))
        assert store.status(operation)['state']=='revoked'
    else:
        completed=native.apply(operation);write(output/'completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed']
        phase('completed_needs_verification');current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==generation+1 and current['image_id']==image
        assert native.apply(operation)==completed;write(output/'completed-replay.json',{'same_saved_status_no_new_mutation':True})
    assert (control/'stages'/operation/'native-skipped.json').is_file() and not (control/'stages'/operation/'native.log').exists()
    reader=DockerObserver(current);observed=reader.read();after=reader.state(observed,catalog)['state']
    assert json.loads(sql(reader,BUSINESS_SQL))==business and after['installations']==before['installations'] and after['bindings']==before['bindings']
    assert {row['addon']:row['version'] for row in observed['sites'][0]['native_modules']}==versions
    current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in old_files.items())
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'));assert cache['configuration']['published_release']==current['published_release'] and cache['configuration']['generation']==current['generation']
    state.update(active_db=current['sites'][0]['database'],image_id=current['image_id'],worker_id=current['worker_id'],release_generation=current['generation'],stage='client_refresh_static_'+mode)
    state['databases']=list(dict.fromkeys(state['databases']+[state['active_db']]));state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]));state['evidence']=output.relative_to(ROOT).as_posix()
    (local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    if mode=='fault':
        seeded=json.loads((local/'lifecycle-data.json').read_text(encoding='utf-8'));seeded['restored_database']=state['active_db'];(local/'lifecycle-data.json').write_text(json.dumps(seeded,indent=2)+'\n',encoding='utf-8')
    phase('restored_verified_and_resumed' if mode=='fault' else 'completed_verified')
    write(output/'state-after.json',after)
    write(output/'activation.json',{'result':'passed_runtime_browser_pending','mode':mode,'utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,'plan_hash':bundle['plan_hash'],
          'configuration':current,'changed_inventory_paths':record['changed_inventory_paths'],'all_four_scopes_preserved':True,'original_business_exact':True,
          'original_notes':4,'original_board_revision':2,'old_files_preserved':len(old_files),'native_versions_unchanged_no_native_maintenance':True,'automatic_cache_current':True,
          'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':['Actual dirty client recovery/explicit refresh is verified separately in browser evidence.','No OS executor crash or whole G5 completion claim.']})
    print(json.dumps({'result':'passed_runtime_browser_pending','mode':mode,'generation':current['generation'],'database':state['active_db'],'operation_id':operation}),flush=True)


if __name__=='__main__':main()
