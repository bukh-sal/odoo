"""Independent exact core upgrade and pretraffic fresh-DB restore rehearsal.

Prepare once, inspect its full review, then apply only that recorded plan. Every
mutation is journaled; an interrupted apply must be reconciled, never replayed.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
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
from modular_platform.workers import snapshots
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL,command
from qualify_release_reader_rollout import files
from qualify_staged_planning import invoke,write

IMAGE='sha256:a34c6b6f6d2cac53ce7ac46158a31b616b148204a19aad2116cab21ad2414eb8'
OUTPUT=ROOT/'docs/evidence/G5/20261028-client-release-core-fault-01'
MARKER=ROOT/'.local/g5/client-release-core-fault-01.json'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text(encoding='utf-8'));local=ROOT/'.local/g5';state=json.loads((local/'state.json').read_text(encoding='utf-8'))
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==16 and state['disposable']
    assert state['active_db']==config['sites'][0]['database']=='mp_disposable_r0_r1_restore_736f872ff76d4cd8af14ce8049452691'
    qualified=json.loads((ROOT/'docs/evidence/G5/20261028-client-release-ingress-requalification/requalification.json').read_text(encoding='utf-8'))
    assert qualified['result']=='passed_changed_ingress_subset' and qualified['image_id']==IMAGE
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in qualified['current_source_hashes_match'].items())
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observed=observer.read();before=observer.state(observed,catalog)['state']
    assert len(before['installations'])==4 and data_digest(before)=='sha256:022ffa357fb3d3af74cd62debb0f8609d01a52668acc17a6536bf7de02a138bc'

    def sql(reader,query):return command(['docker','exec','-i',reader._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',reader.config['sites'][0]['database']],input=query.encode())
    business=json.loads(sql(observer,BUSINESS_SQL));assert len(business['notes'])==4 and len(business['boards'])==1 and business['boards'][0]['revision']==2
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    store=OperatorStore(control)
    if args.action=='prepare':
        assert not OUTPUT.exists() and not MARKER.exists();OUTPUT.mkdir(parents=True)
        write(MARKER,{'state':'preparing','candidate_image_id':IMAGE,'evidence':OUTPUT.relative_to(ROOT).as_posix()})
        old_files=files(observer);write(OUTPUT/'state-before.json',before)
        # Explicit private preimage contains no credentials and is needed after
        # a process interruption; approval records remain independently owned.
        write(OUTPUT/'business-before.json',business);write(OUTPUT/'files-before.json',old_files)
        write(OUTPUT/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',IMAGE]+options))
        nomination={'operation_type':'core_upgrade','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write(OUTPUT/'nomination.json',nomination)
        bundle=invoke(prefix+['plugin','plan-staged','--input',str(OUTPUT/'nomination.json')]+options);write(OUTPUT/'bundle.json',bundle)
        changes=bundle['operation_lock']['native_core_changes']
        assert {row['addon'] for row in changes}=={'mp_identity','mp_core','mp_shell'} and len(bundle['operation_lock']['targets'])==4
        assert bundle['plan']['destructive'] and not bundle['plan']['permission_changes']
        assert observer.state(observer.read(),catalog)['state']==before
        record={'state':'prepared_not_registered','operation_id':bundle['plan']['operation_id'],'plan_hash':bundle['plan_hash'],
                'candidate_image_id':IMAGE,'evidence':OUTPUT.relative_to(ROOT).as_posix(),'before_digest':data_digest(before)}
        MARKER.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        write(OUTPUT/'core-plan.json',{'result':'prepared_not_registered','utc':datetime.now(timezone.utc).isoformat(),**record,
              'targets':4,'native_core_changes':changes,'base_generation':16,'target_generation':bundle['operation_lock']['release']['generation'],
              'destructive_ack_required':True,'trust_ack_required':True,'main_unchanged':True})
        print(json.dumps({'result':'prepared_not_registered','operation_id':record['operation_id'],'plan_hash':record['plan_hash'],'targets':4,'native_core_changes':changes}));return
    record=json.loads(MARKER.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['candidate_image_id']==IMAGE
    bundle=json.loads((OUTPUT/'bundle.json').read_text(encoding='utf-8'));operation=record['operation_id']
    assert bundle['plan_hash']==record['plan_hash'] and data_digest(before)==record['before_digest']
    assert json.loads((OUTPUT/'business-before.json').read_text(encoding='utf-8'))==business
    old_files=json.loads((OUTPUT/'files-before.json').read_text(encoding='utf-8'));assert files(observer)==old_files

    def phase(name,**details):
        record.update(state=name,utc=datetime.now(timezone.utc).isoformat(),**details)
        MARKER.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    phase('registering')
    write(OUTPUT/'registered.json',invoke(operations+['register','--bundle',str(OUTPUT/'bundle.json')]+validation))
    review=store.review(operation,StagedNativeExecutor(store,target,catalog_root,validator)._validate())
    write(OUTPUT/'independent-review.json',review)
    denied=invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation,success=False)
    assert 'destructive' in denied['message'].lower();write(OUTPUT/'missing-destructive-ack-denied.json',denied)
    write(OUTPUT/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation))
    phase('approved_exact_plan');print(json.dumps({'stage':'approved_exact_plan','operation_id':operation}),flush=True)
    native=StagedNativeExecutor(store,target,catalog_root,validator);advance=store.advance
    def fault(selected,locks,selected_phase,**details):
        result=advance(selected,locks,selected_phase,**details)
        if selected==operation and selected_phase=='release_published':raise OperatorError('Disposable core qualification fault after publication before traffic')
        return result
    phase('applying_with_pretraffic_fault')
    with patch.object(store,'advance',side_effect=fault):
        try:native.apply(operation)
        except OperatorError as error:
            if 'Disposable core qualification fault' not in str(error):raise
        else:raise AssertionError('Expected pretraffic fault absent')
    failed=invoke(operations+['show',operation]);write(OUTPUT/'failed-status.json',failed)
    assert failed['state']=='recovery_required' and failed['mutation_started'] and not failed['traffic_resumed']
    changed=json.loads(target.read_text(encoding='utf-8'));assert changed['image_id']==IMAGE and changed['generation']==17
    changed_reader=DockerObserver(changed);new_observation=changed_reader.read()
    assert json.loads(sql(changed_reader,BUSINESS_SQL))==business
    expected={row['addon']:row['target_version'] for row in bundle['operation_lock']['native_core_changes']}
    versions={row['addon']:row['version'] for row in new_observation['sites'][0]['native_modules'] if row['addon'] in expected}
    assert versions==expected
    edge=changed_reader._container('edge',stopped=True)
    assert json.loads(command(['docker','inspect',edge]))[0]['State']['Running'] is False
    write(OUTPUT/'failed-workers.json',snapshots(changed));phase('recovery_required',failed_generation=17)
    print(json.dumps({'stage':'recovery_required','operation_id':operation,'core_versions':versions,'traffic_closed':True}),flush=True)
    recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
    decision=recovery.prepare(operation);write(OUTPUT/'restore-decision.json',decision);phase('restore_reviewed',restore_hash=data_digest(decision))
    write(OUTPUT/'restore-result.json',recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True))
    restored=json.loads(target.read_text(encoding='utf-8'));reader=DockerObserver(restored);restored_observation=reader.read();after=reader.state(restored_observation,catalog)['state']
    assert restored['image_id']==config['image_id'] and restored['generation']>17 and restored['sites'][0]['database']!=config['sites'][0]['database']
    assert json.loads(sql(reader,BUSINESS_SQL))==business and files(reader)==old_files
    assert after['installations']==before['installations'] and after['bindings']==before['bindings']
    previous={row['addon']:row['previous_version'] for row in bundle['operation_lock']['native_core_changes']}
    assert {row['addon']:row['version'] for row in restored_observation['sites'][0]['native_modules'] if row['addon'] in previous}==previous
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'))
    assert cache['configuration']['published_release']==restored['published_release'] and cache['configuration']['generation']==restored['generation']
    phase('restored_before_separate_resume',restored_generation=restored['generation'],restored_database=restored['sites'][0]['database'])
    recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
    resume=recovery.prepare_resume(operation);write(OUTPUT/'resume-decision.json',resume)
    write(OUTPUT/'resume-result.json',recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True))
    assert store.status(operation)['state']=='revoked'
    state.update(active_db=restored['sites'][0]['database'],image_id=restored['image_id'],worker_id=restored['worker_id'],release_generation=restored['generation'],stage='core_fault_restored_verified')
    state['databases']=list(dict.fromkeys(state['databases']+[state['active_db']]))
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=OUTPUT.relative_to(ROOT).as_posix();(local/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    seeded=json.loads((local/'lifecycle-data.json').read_text(encoding='utf-8'));seeded['restored_database']=state['active_db'];(local/'lifecycle-data.json').write_text(json.dumps(seeded,indent=2)+'\n',encoding='utf-8')
    phase('restored_verified_and_resumed')
    write(OUTPUT/'state-after.json',after)
    write(OUTPUT/'core-fault-restore.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,'plan_hash':bundle['plan_hash'],
          'configuration':restored,'native_core_changes':bundle['operation_lock']['native_core_changes'],'all_four_scopes_preserved':True,
          'original_notes':4,'original_board_revision':2,'original_business_rows_exact':True,'filestore_files':len(old_files),'fresh_db_restore_previous_versions':True,
          'postpublication_pretraffic_failure_recovery_required':True,'new_epoch_and_automatic_cache':True,'separately_reviewed_resume':True,'old_databases_workers_checkpoint_retained':True,
          'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits':['A bounded exception after real native commit/publication; not an OS executor crash.', 'Candidate traffic never opened; normal rollout/client activation remain required.']})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'generation':restored['generation'],'database':state['active_db'],'evidence':OUTPUT.relative_to(ROOT).as_posix()}))


if __name__=='__main__':main()
