"""Requalify changed pin/cache restore path with a real committed native install."""
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
from modular_platform.lifecycle_planning import installation_id
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.workers import snapshots
from modular import configuration
from qualify_native_upgrade import sql
from qualify_staged_planning import invoke,write
from qualify_release_reader_rollout import notes_snapshot,files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--apply',action='store_true',required=True);args=parser.parse_args()
    output=args.output.resolve();local=ROOT/'.local/g5';marker=local/'pinned-restore.json'
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():raise ValueError('Fresh once-only restore qualification required; inspect any existing marker/journal')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());state=json.loads((local/'state.json').read_text());fixture=json.loads((local/'fixtures.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and state['disposable'] and config['published_release']
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observation=observer.read();assert observation['runtime']['published_release_protocol']==1
    before=observer.state(observation,catalog)['state'];notes=notes_snapshot(observer);filestore=files(observer)
    assert len(notes)==4 and len(before['installations'])==3
    assert not any(row['plugin_id']=='org.example.canvas' for row in before['installations'])
    assert json.loads(sql(observer,"SELECT to_jsonb(to_regclass('mp_example_canvas_board') IS NOT NULL);")) is False
    output.mkdir(parents=True);write(output/'state-before.json',before)
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',config['image_id']]+options))
    nomination={'operation_type':'install','targets':[{'installation_id':installation_id(observation['sites'][0],'org.example.canvas'),
        'site_id':fixture['site_id'],'workspace_id':fixture['workspaces']['A']['public_id'],'plugin_id':'org.example.canvas','action':'install'}]}
    write(output/'nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle)
    write(marker,{'operation_id':operation,'state':'nominated','evidence':str(output.relative_to(ROOT))})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation}),flush=True)
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator);command=native._private_command
    def fault(arguments,path,**kwargs):
        result=command(arguments,path,**kwargs)
        if path.name=='native.log':raise OperatorError('Disposable pinned-restore qualification fault after native commit')
        return result
    with patch.object(native,'_private_command',side_effect=fault):
        try:native.apply(operation)
        except OperatorError as error:
            if 'Disposable pinned-restore qualification fault' not in str(error):raise
        else:raise AssertionError('Post-native-commit fixture did not run')
    assert not any(row['running'] for row in snapshots(config))
    failed=invoke(operations+['show',operation]);assert failed['state']=='recovery_required' and not failed['traffic_resumed']
    write(output/'independent-cli-no-app.json',failed)
    assert json.loads(sql(observer,"SELECT to_jsonb(to_regclass('mp_example_canvas_board') IS NOT NULL);")) is True
    print(json.dumps({'stage':'committed_schema_recovery_required','operation_id':operation,'no_app_process':True}),flush=True)
    recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
    decision=recovery.prepare(operation);write(output/'restore-decision.json',decision)
    write(output/'restore-result.json',recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True))
    restored=json.loads(target.read_text());reader=DockerObserver(restored);observed=reader.read();after=reader.state(observed,catalog)['state']
    assert restored['image_id']==config['image_id'] and restored['generation']>bundle['operation_lock']['release']['generation']
    assert restored['published_release']==decision['restored_release_lock']
    assert after['installations']==before['installations'] and after['bindings']==before['bindings'] and notes_snapshot(reader)==notes and files(reader)==filestore
    assert json.loads(sql(reader,"SELECT to_jsonb(to_regclass('mp_example_canvas_board') IS NOT NULL);")) is False
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'))
    assert cache['configuration']['published_release']==restored['published_release'] and cache['configuration']['generation']==restored['generation']
    publication=json.loads((control/'recoveries'/operation/'profile-publication.json').read_text());assert publication['profile_published']
    write(output/'automatic-restored-cache.json',publication)
    recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
    resume=recovery.prepare_resume(operation);write(output/'resume-decision.json',resume)
    write(output/'resume-result.json',recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True))
    state.update(active_db=restored['sites'][0]['database'],image_id=restored['image_id'],worker_id=restored['worker_id'],
        release_generation=restored['generation'],stage='pinned_restore_verified')
    state['databases']=list(dict.fromkeys(state['databases']+[state['active_db']]))
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    seeded=json.loads((local/'lifecycle-data.json').read_text());seeded['restored_database']=state['active_db'];(local/'lifecycle-data.json').write_text(json.dumps(seeded,indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id':operation,'state':'restored_verified_and_resumed','generation':restored['generation'],
        'database':state['active_db'],'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    write(output/'state-after.json',after)
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+[Path(__file__),ROOT/'tools/modular.py']
    write(output/'pinned-restore.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,
        'plan_hash':bundle['plan_hash'],'configuration':restored,'published_pin_and_current_validation_checked':True,
        'committed_canvas_table_removed_by_fresh_target_restore':True,'note_rows_and_filestore_unchanged':{'notes':4,'files':len(filestore)},
        'prior_installations_bindings_and_feature_states_preserved':True,'automatic_cache_updated_before_resume':True,
        'independent_cli_read_while_no_app_process':True,'failed_plan_retired':store.status(operation)['state']=='revoked',
        'failed_database_retained':True,'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limitations':['No completed Canvas activation is claimed; native install was deliberately failed and restored.',
            'Default startup/client fencing, native UI preparation, uninstall/removal and complete G5 still pending.']})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'generation':restored['generation'],'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
