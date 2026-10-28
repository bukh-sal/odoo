"""Once-only real native schema upgrade/commit failure and populated recovery."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,_run
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.workers import snapshots
from modular import configuration
from qualify_staged_execution import business_snapshot
from qualify_staged_planning import invoke,write
from qualify_worker_guards import PROBE
import r1,r1_probe
r1.r0.LOCAL=ROOT/'.local/g5'

SCHEMA_SQL="""BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT jsonb_build_object(
 'native_version',(SELECT latest_version FROM ir_module_module WHERE name='mp_example_notes'),
 'native_state',(SELECT state FROM ir_module_module WHERE name='mp_example_notes'),
 'positive_constraint',(SELECT convalidated FROM pg_constraint WHERE conrelid='mp_example_note'::regclass AND conname='mp_example_note_revision_positive'),
 'migration_pre',(SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.pre'),
 'migration_post',(SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.post'),
 'metadata_version',(SELECT version FROM mp_plugin_installation WHERE plugin_id='org.example.notes'));
ROLLBACK;"""


def sql(observer,statement):
    return _run(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres',
        '-d',observer.config['sites'][0]['database'],'-v','ON_ERROR_STOP=1'],input=statement.encode())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--image-id',required=True);parser.add_argument('--apply',action='store_true',required=True);args=parser.parse_args()
    output=args.output.resolve();local=ROOT/'.local/g5';marker=local/'native023-fault.json'
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():
        raise OperatorError('Fresh once-only native qualification required; reconcile any existing marker first')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());state=json.loads((local/'state.json').read_text());fixture=json.loads((local/'fixtures.json').read_text())
    seeded=json.loads((local/'lifecycle-data.json').read_text());prepared=json.loads((local/'upgrade-preparation.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and state['disposable'] and state['active_db']==config['sites'][0]['database']
    assert seeded['state']=='completed' and prepared['state']=='completed'
    validator=configuration(operator/'trust.json');catalog=Catalog(catalog_root,validator,readonly=True)
    snapshot=catalog.snapshot();observer=DockerObserver(config);observation=observer.read();before=observer.state(observation,snapshot)['state']
    business=business_snapshot(observer);assert business['notes_count']==4 and business['attachment_count']==0
    old_schema=json.loads(sql(observer,SCHEMA_SQL));assert old_schema['native_version']=='19.0.0.2.2' and old_schema['positive_constraint'] is None
    rows=[row for row in before['installations'] if row['plugin_id']=='org.example.notes']
    assert len(rows)==2 and {row['feature_state'] for row in rows}=={'enabled','suspended'}
    output.mkdir(parents=True);write(output/'state-before.json',before);write(output/'schema-before.json',old_schema)
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',args.image_id]+options))
    nomination={'operation_type':'upgrade','targets':[{name:row[name] for name in ('installation_id','site_id','workspace_id','plugin_id')}|{'action':'upgrade'} for row in rows]}
    write(output/'nomination.json',nomination)
    bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle)
    artifact=next(item for item in bundle['plan']['artifacts'] if item['plugin_id']=='org.example.notes')
    assert artifact['version']=='0.2.3' and len(artifact['migration_digests'])==2
    write(marker,{'operation_id':operation,'plan_hash':bundle['plan_hash'],'state':'nominated','evidence':str(output.relative_to(ROOT))})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    denied=invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive']+validation,success=False)
    assert 'explicit acknowledgment' in denied['message'];write(output/'native-ack-denied.json',denied)
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation,'migration_digests':artifact['migration_digests']}),flush=True)
    store=OperatorStore(control);native=StagedNativeExecutor(store,target,catalog_root,validator);command=native._private_command
    def fault(arguments,path,**kwargs):
        result=command(arguments,path,**kwargs)
        if path.name=='native.log':raise OperatorError('Disposable qualification fault after committed native upgrade')
        return result
    with patch.object(native,'_private_command',side_effect=fault):
        try:native.apply(operation)
        except OperatorError as error:
            if 'Disposable qualification fault' not in str(error):raise
        else:raise AssertionError('Native commit fault was not exercised')
    failed=store.status(operation);assert failed['state']=='recovery_required' and failed['mutation_started'] and not failed['traffic_resumed']
    write(output/'failed-status.json',failed)
    changed=json.loads(sql(observer,SCHEMA_SQL));write(output/'schema-after-native-commit.json',changed)
    assert changed['native_version']=='19.0.0.2.3' and changed['native_state']=='installed' and changed['positive_constraint'] is True
    assert changed['metadata_version']=='0.2.2' and changed['migration_pre']==changed['migration_post']
    assert json.loads(changed['migration_pre'])['from_native_version']=='19.0.0.2.2'
    # The SQL constraint is real. An expected error closes/rolls back this
    # isolated transaction; no invalid revision or public error text persists.
    note=seeded['objects']['A'][0]['native']['id'];assert type(note) is int
    violation=subprocess.run(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres',
        '-d',config['sites'][0]['database'],'-v','ON_ERROR_STOP=1'],input=f'BEGIN; UPDATE mp_example_note SET revision=0 WHERE id={note}; ROLLBACK;'.encode(),capture_output=True,timeout=30)
    assert violation.returncode!=0 and b'mp_example_note_revision_positive' in violation.stderr
    write(output/'revision-zero-denied.json',{'real_sql_constraint_rejected_zero':True,'transaction_rolled_back':True})
    # Reuse the production guard against the actual committed incompatible DB.
    # It opens READ ONLY and must fail before any native import/startup.
    probe=['docker','run','--rm','-i','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--network',config['project']+'_runtime','--tmpfs','/tmp','--mount','type=volume,source='+config['project']+'_appconfig,target=/run/secrets,readonly',
        '--entrypoint','/venv/bin/python',config['image_id'],'-c',PROBE]
    result=subprocess.run(probe,input=json.dumps({'case':'native_version_mismatch','source':(ROOT/'packages/platform_sdk/modular_platform/worker_start.py').read_text(),
        'database':config['sites'][0]['database'],'inventory':before['release_lock']['core_inventory_digest'],
        'message':'Native module state/version differs'}).encode(),capture_output=True,timeout=90)
    assert result.returncode==0;write(output/'old-worker-denied.json',json.loads(result.stdout))
    assert not any(row['running'] for row in snapshots(config))
    # A current revocation after the backup must survive restoration of that
    # older snapshot. This is a fixed OS recovery fixture, not app-supplied SQL.
    bob=fixture['users']['bob']['principal_id'];workspace=fixture['workspaces']['B']['public_id']
    from uuid import UUID
    assert str(UUID(bob))==bob and str(UUID(workspace))==workspace
    revoked=sql(observer,"UPDATE mp_membership m SET state='revoked' FROM mp_principal p,mp_workspace w WHERE m.principal_id=p.id AND m.workspace_id=w.id AND p.public_id='"+bob+"' AND w.public_id='"+workspace+"' AND m.state='active' RETURNING m.id;")
    assert len(revoked.decode().split())==1
    write(output/'current-revocation.json',{'principal_id':bob,'workspace_id':workspace,'state':'revoked','after_checkpoint':True})
    print(json.dumps({'stage':'native_committed_recovery_required','operation_id':operation,'old_worker_denied_before_import':True}),flush=True)
    recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
    decision=recovery.prepare(operation);write(output/'restore-decision.json',decision)
    write(output/'restore-result.json',recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True))
    restored_config=json.loads(target.read_text());restored_observer=DockerObserver(restored_config)
    after=restored_observer.state(restored_observer.read(),snapshot)['state'];assert after['installations']==before['installations'] and after['bindings']==before['bindings']
    assert restored_config['image_id']==config['image_id'] and restored_config['generation']>bundle['operation_lock']['release']['generation']
    assert business_snapshot(restored_observer)==business
    restored_schema=json.loads(sql(restored_observer,SCHEMA_SQL));assert restored_schema==old_schema
    write(output/'schema-restored.json',restored_schema)
    # Refresh only the sanitized planning cache before the separate traffic
    # review; automatic lifecycle publication remains a tracked G5 follow-up.
    refreshed=subprocess.run([sys.executable,'tools/publish_profile.py','--target',str(target)],capture_output=True,timeout=90,cwd=ROOT)
    assert refreshed.returncode==0;write(output/'profile-refresh.json',json.loads(refreshed.stdout))
    recovery=RestoreExecutor(StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator))
    resume=recovery.prepare_resume(operation);write(output/'resume-decision.json',resume)
    write(output/'resume-result.json',recovery.resume(resume,exact_hash=data_digest(resume),noninteractive=True))
    state['active_db']=restored_config['sites'][0]['database'];state['image_id']=restored_config['image_id'];state['worker_id']=restored_config['worker_id'];state['release_generation']=restored_config['generation']
    state['databases']=list(dict.fromkeys(state['databases']+[state['active_db']]))
    state['stage']='native023_fault_restored';state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    fixture['bindings']={key:next(b for b in after['bindings'] if b['workspace_id']==row['public_id'] and b['alias']=='documents') for key,row in fixture['workspaces'].items()}
    alice=r1_probe.Client(state,fixture,'alice')
    for row in seeded['objects']['A']:assert alice.call('get',{'note_id':row['dto']['id']},workspace='A')==row['dto']
    bob_client=r1_probe.Client(state,fixture,'bob')
    bob_client.call('get',{'note_id':seeded['objects']['B'][0]['dto']['id']},workspace='B',expect=403,code='FORBIDDEN')
    memberships=restored_observer.read()['sites'][0]['memberships']
    assert next(row for row in memberships if row['principal_id']==bob and row['workspace_id']==workspace)['state']=='revoked'
    assert next(row for row in after['installations'] if row['workspace_id']==workspace)['feature_state']=='suspended'
    write(output/'state-after.json',after)
    seeded['restored_database']=state['active_db'];(local/'lifecycle-data.json').write_text(json.dumps(seeded,indent=2)+'\n')
    marker.write_text(json.dumps({'operation_id':operation,'state':'restored_verified_and_resumed','database':state['active_db'],'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+list((ROOT/'platform_addons/mp_example_notes').rglob('*.py'))+[Path(__file__),ROOT/'plugins/notes/plugin.toml']
    paths=[path for path in paths if '__pycache__' not in path.parts]
    write(output/'native-upgrade-recovery.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':bundle['plan_hash'],'from_version':'0.2.2','native_target_version':'0.2.3',
        'target_image_id':args.image_id,'final_configuration':restored_config,'business_preserved':business,
        'actual_native_commit_and_constraint':True,'old_worker_denied_before_native_import':True,
        'current_revocation_preserved':True,'suspended_scope_preserved':True,'failed_approval_retired':store.status(operation)['state']=='revoked',
        'checks':['Hash-bound migration digests and both sharing workspace scopes',
            'New native code acknowledgement required','Pre/post migration and new SQL constraint actually committed',
            'Zero revision rejected by SQL; expected invalid transaction rolled back','Post-commit failure recorded recovery_required, traffic closed',
            'Old code refused incompatible native version before importing Odoo','Fresh-target previous-code/schema/data/filestore restore',
            'Current post-checkpoint human revocation and suspended B survived restore','Separate reviewed resume; Alice data available, Bob denied'],
        'limitations':['This failed upgrade was restored, not reported completed. A separate successful upgrade and skipped-release/fresh-install qualification remain.',
            'Workspace attachments are excluded; four real Notes records and40filestoreassets are covered.',
            'Automatic profile publication, general startup/client fences and remaining G5 lifecycle qualification are pending.'],
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'outcome':'native_upgrade_restored','evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
