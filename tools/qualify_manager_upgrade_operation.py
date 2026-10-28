"""Real isolated manager requests: first native install, then package upgrade."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-manager-upgrade-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.app_channel import read_request
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle,data_digest
from modular import configuration
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import files


def snapshot(observer):
    present=json.loads(sql(observer,"SELECT to_jsonb(to_regclass('mp_example_note') IS NOT NULL);"))
    notes=json.loads(sql(observer,"SELECT COALESCE(jsonb_agg(to_jsonb(n) ORDER BY id),'[]'::jsonb) FROM mp_example_note n;")) if present else None
    metadata=json.loads(sql(observer,"""SELECT jsonb_build_object(
        'features',(SELECT COALESCE(jsonb_agg(to_jsonb(f) ORDER BY id),'[]'::jsonb) FROM mp_workspace_plugin f),
        'bindings',(SELECT COALESCE(jsonb_agg(to_jsonb(b) ORDER BY id),'[]'::jsonb) FROM mp_service_binding b),
        'grants',(SELECT COALESCE(jsonb_agg(to_jsonb(g) ORDER BY id),'[]'::jsonb) FROM mp_plugin_grant g),
        'native_state',(SELECT state FROM ir_module_module WHERE name='mp_example_notes'),
        'native_version',(SELECT latest_version FROM ir_module_module WHERE name='mp_example_notes'),
        'positive_constraint',EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('mp_example_note') AND conname='mp_example_note_revision_positive' AND convalidated),
        'migration_pre',(SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.pre'),
        'migration_post',(SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.post'));
        """))
    return metadata|{'notes':notes}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);parser.add_argument('--mode',choices=['install','upgrade'],required=True);parser.add_argument('--operation-id',required=True);parser.add_argument('--download',required=True,type=Path);args=parser.parse_args()
    mode=args.mode;base={'install':1,'upgrade':2}[mode];version={'install':'0.2.2','upgrade':'0.2.3'}[mode]
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));target_path=LOCAL/'operator/target.json';config=json.loads(target_path.read_text(encoding='utf-8'))
    main_path=ROOT/'.local/operator/targets/g5.json';assert hashlib.sha256(main_path.read_bytes()).hexdigest()==state['main_target_sha256']
    assert config['project']==state['project']=='mp-r0-r1mgr84459f617ab0' and config['generation']==base and config['sites'][0]['database']==state['active_db']
    output=OUTPUT/('first-native-install' if mode=='install' else 'manager-package-upgrade');marker=LOCAL/(mode+'-operation.json')
    catalog_root=ROOT/'.local/operator/catalog';trust=ROOT/'.local/operator/trust.json';control=LOCAL/'operator/control';validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True)
    observer=DockerObserver(config);before=observer.state(observer.read(),catalog.snapshot())['state'];business=snapshot(observer)
    request=read_request(observer,args.operation_id);bundle=json.loads(args.download.read_text(encoding='utf-8'));assert bundle==request['bundle'];check_bundle(bundle,before)
    targets=bundle['operation_lock']['targets'];assert bundle['plan']['operation_type']==mode and len(targets)==1 and targets[0]['plugin_id']=='org.example.notes' and targets[0]['action']==mode
    assert bundle['plan']['artifacts'][0]['version']==version and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
    if mode=='install':
        assert not before['installations'] and business['notes'] is None and business['native_state']=='uninstalled'
        assert bundle['plan']['artifacts'][0]['migration_digests']==[] and business['migration_pre'] is None and business['migration_post'] is None
        assert bundle['operation_lock']['staged_image']['target_image_id']==config['image_id']
    else:
        assert business['native_version']=='19.0.0.2.2' and len(business['notes'])==2 and not business['positive_constraint']
        assert business['migration_pre'] is None and business['migration_post'] is None
        assert bundle['plan']['artifacts'][0]['migration_digests']==[
            'sha256:11543770959a6676dfa0123295370c3be184e05d4c4287b35b99f3b586db9133',
            'sha256:43f44b974f4f29c6d599866e0bfaa236f622ba86130fc154acb08de19ff7a2e1']
        assert bundle['operation_lock']['staged_image']['target_image_id']=='sha256:2c7eeda91f213aea51091f1c7a2523a04c3fb51b2c30f4dd12d292da55544383'
    prefix=[sys.executable,'tools/modular.py','--config',str(trust)];operations=prefix+['operations','--store',str(control)];options=['--deployment-config',str(target_path),'--catalog',str(catalog_root)]
    def invoke(arguments):
        result=subprocess.run(arguments,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:raise RuntimeError('Actual fixture CLI failed; inspect private journal/logs, never blind retry: '+result.stderr.decode(errors='replace')[:500])
        return json.loads(result.stdout)
    def write(name,value):
        with (output/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    if args.action=='prepare':
        assert not marker.exists() and not output.exists();output.mkdir()
        record={'state':'importing','mode':mode,'operation_id':args.operation_id,'plan_hash':bundle['plan_hash'],'base_state_digest':data_digest(before),'generation':base}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');write('browser-downloaded-bundle.json',bundle);write('state-before.json',before);write('business-before.json',business);write('files-before.json',files(observer))
        registered=invoke(operations+['import-request',args.operation_id]+options);assert registered['state']=='awaiting_operator_approval';write('independent-registration.json',registered)
        store=OperatorStore(control);write('independent-review.json',store.review(args.operation_id,StagedNativeExecutor(store,target_path,catalog_root,validator)._validate()))
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='independently_reviewed_not_approved' and record['operation_id']==args.operation_id and record['base_state_digest']==data_digest(before)
    assert json.loads((output/'business-before.json').read_text(encoding='utf-8'))==business
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    write('approved.json',invoke(operations+['approve',args.operation_id,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+options));phase('approved')
    print(json.dumps({'stage':'exact_local_approval','mode':mode,'operation_id':args.operation_id}),flush=True);phase('applying')
    completed=invoke(prefix+['plugin','apply',args.operation_id,'--store',str(control)]+options);write('completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed'];phase('completed_needs_verification')
    current=json.loads(target_path.read_text(encoding='utf-8'));assert current['generation']==base+1 and current['image_id']==bundle['operation_lock']['staged_image']['target_image_id']
    reader=DockerObserver(current);after=reader.state(reader.read(),catalog.snapshot())['state'];actual=snapshot(reader);assert actual['native_state']=='installed' and actual['native_version']=='19.0.'+version
    assert after['bindings']==bundle['operation_lock']['bindings'] and current['published_release']==bundle['operation_lock']['release']
    assert actual['grants']==business['grants'] and len(after['installations'])==1
    if mode=='install':
        assert actual['notes']==[] and actual['migration_pre'] is None and actual['migration_post'] is None
        assert len(actual['features'])==len(actual['bindings'])==1
    else:
        assert actual['notes']==business['notes'] and actual['features']==business['features'] and actual['bindings']==business['bindings'] and actual['positive_constraint']
        witness=json.loads(actual['migration_pre']);assert witness==json.loads(actual['migration_post']) and witness['from_native_version']=='19.0.0.2.2'
        assert witness['rows_sha256']==hashlib.sha256(json.dumps(business['notes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    original_files=json.loads((output/'files-before.json').read_text(encoding='utf-8'));now_files=files(reader);assert all(now_files.get(name)==digest for name,digest in original_files.items())
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-op-'+args.operation_id+'-native'],text=True))[0];cmd=child['Config']['Cmd']
    assert ('-i' if mode=='install' else '-u') in cmd and ('-u' if mode=='install' else '-i') not in cmd and child['Image']==current['image_id'] and child['State']['ExitCode']==0
    write('native-child.json',{'image_id':child['Image'],'arguments':cmd,'exit_code':child['State']['ExitCode']})
    mirror=invoke(operations+['mirror-status',args.operation_id]+options);assert mirror['state']=='completed' and mirror['dimensions'][0]['database_state']=='installed';write('completed-mirror.json',mirror)
    write('state-after.json',after);write('business-after.json',actual)
    state.update(phase='notes_installed' if mode=='install' else 'notes_upgraded',image_id=current['image_id'],worker_id=current['worker_id'],generation=current['generation'],runtime_inventory_digest=bundle['operation_lock']['staged_image']['inventory_digest']);(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');phase('completed_verified')
    assert hashlib.sha256(main_path.read_bytes()).hexdigest()==state['main_target_sha256']
    write('result.json',{'result':'passed_real_first_native_install' if mode=='install' else 'passed_real_manager_native_upgrade','utc':datetime.now(timezone.utc).isoformat(),'operation_id':args.operation_id,'plan_hash':bundle['plan_hash'],'configuration':current,'before_schema':{key:business[key] for key in ['native_state','native_version','positive_constraint','migration_pre','migration_post']},'after_schema':{key:actual[key] for key in ['native_state','native_version','positive_constraint','migration_pre','migration_post']},'native_flags_verified':True,'old_files_preserved':len(original_files),'original_rows_preserved':True,'main_target_unchanged':True,'limits':['Browser final-status/native-view evidence is separate.','Adjacent2.2-to2.3 only; the full skipped/numeric migration matrix and all G5 requirements remain open.']})
    print(json.dumps({'result':'completed_verified','mode':mode,'operation_id':args.operation_id,'generation':current['generation']}))


if __name__=='__main__':main()
