"""Bounded once-only real uninstall/source removal on the existing owned site."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor,StagedNativeExecutor
from modular_platform.operator_os import OperationLocks,OperatorError
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply','stage'])
    parser.add_argument('--case',required=True,choices=['uninstall','remove']);parser.add_argument('--operation-id');args=parser.parse_args()
    uninstall=args.case=='uninstall';base=7 if uninstall else 8
    target=LOCAL/'operator/target.json';config=json.loads(target.read_text());state=json.loads((LOCAL/'state.json').read_text())
    fixture=json.loads((LOCAL/'fixtures.json').read_text());assert state['disposable']
    assert state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==base and config['image_id']==FULL
    assert state['active_db']==config['sites'][0]['database']=='mp_disposable_r0_r1_g5_life_f99acae9d906'
    assert state['phase']==('artifact_removal_core_ready' if uninstall else 'artifact_removal_labels_absent')
    protected=[ROOT/'.local/operator/targets/g5.json',ROOT/'.local/g5-manager-upgrade/operator/target.json']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard():assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    validator=configuration(ROOT/'.local/operator/trust.json');catalog_root=ROOT/'.local/operator/catalog'
    catalog=Catalog(catalog_root,validator,readonly=True);reader=DockerObserver(config);observation=reader.read()
    before=reader.state(observation,catalog.snapshot())['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    assert len(business['notes'])==4 and len(business['boards'])==2 and len(before['installations'])==6
    control=LOCAL/'operator/control';store=OperatorStore(control);executor=(NativeExecutor if uninstall else StagedNativeExecutor)(store,target,catalog_root,validator)
    output=OUTPUT/args.case;marker=LOCAL/('source-live-'+args.case+'.json')
    prefix=[sys.executable,'tools/modular.py','--config',str(ROOT/'.local/operator/trust.json')]
    ops=prefix+['operations','--store',str(control)];options=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def invoke(command):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if result.returncode:
            (LOCAL/('source-live-'+args.case+'-'+args.action+'.log')).write_bytes(result.stderr)
            raise RuntimeError('CLI failure: reconcile exact marker/journal/private diagnostics; never blind replay')
        return json.loads(result.stdout)
    def write(name,value,folder=None):
        with ((folder or output)/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    if args.action=='stage':
        assert not uninstall and not (OUTPUT/'restage').exists();stage_output=OUTPUT/'restage';stage_output.mkdir()
        stages=StageStore(store,config,catalog)
        try:stages.load()
        except OperatorError as error:
            assert 'stale deployment' in str(error)
            write('previous-stage-stale.json',dict(result='rejected',reason=str(error)),stage_output)
        else:raise AssertionError('Previous generation7 stage was silently adopted at8')
        descriptor=stages.stage(REMOVED);loaded=stages.load(descriptor)
        with OperationLocks(store.root/'locks',config['deployment_id'],[s['site_id'] for s in config['sites']]):
            write('profile-publication.json',publish_profile(reader,catalog,staged=loaded),stage_output)
        write('staged-image.json',descriptor,stage_output)
        assert before==reader.state(reader.read(),catalog.snapshot())['state'] and business==json.loads(sql(reader,BUSINESS_SQL))
        guard();print(json.dumps(dict(result='restaged_same_image_after_uninstall',base_generation=8,image_id=REMOVED)));return
    r1_probe.r1.r0.LOCAL=LOCAL;operator=r1_probe.Client(state,fixture,'operator')
    if args.action=='prepare':
        assert not marker.exists() and not output.exists();output.mkdir()
        record=dict(state='preparing',base_digest=data_digest(before),base_generation=base,protected_config_hashes=hashes)
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        write('state-before.json',before);write('business-before.json',business);write('schema-before.json',schema)
        write('configuration-before.json',config);write('files-before.json',files(reader))
        old=next(p for p in before['release_lock']['plugins'] if p['plugin_id']==PLUGIN)
        if args.operation_id:
            op=args.operation_id
            code,requested=operator.request('/api/v1/operations/status/'+op)
            assert code==200 and any(e['code']=='requested' for e in requested['data']['history'])
        else:
            nomination=dict(schema_version=1,operation='prepare',operation_type=args.case,site_id=state['site_id'],plugin_id=PLUGIN,workspace_ids=[],cascade=False)
            if not uninstall:nomination['artifact_digest']=old['digest']
            code,prepared=operator.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':operator.csrf})
            write('nomination.json',nomination);write('prepare-response.json',dict(status=code,response=prepared))
            assert code==200,(code,prepared)
            op=prepared['data']['operation_id']
        code,response=operator.request('/api/v1/operations/bundle/'+op);assert code==200;bundle=response['data'];check_bundle(bundle,before)
        assert bundle['plan']['operation_type']==args.case and len(bundle['operation_lock']['targets'])==2
        assert all(t['plugin_id']==PLUGIN and t['action']==args.case for t in bundle['operation_lock']['targets'])
        assert bundle['plan']['backup']['required'] and len(bundle['operation_lock']['bindings'])==6
        if uninstall:
            assert bundle['plan']['destructive'] and len(bundle['plan']['permission_changes'])==2
            code,impact=operator.request('/api/v1/operations/impact/'+op);assert code==200
            assert impact['data']['impact']==bundle['operation_lock']['native_uninstall_impact'];write('impact.json',impact['data'])
            assert any(f['field']=='x_notes_labels' and f['non_null_records']==sum(n['x_notes_labels'] is not None for n in business['notes']) for f in impact['data']['impact']['fields'])
        else:
            assert not bundle['plan']['permission_changes'] and not bundle['plan']['destructive']
            assert bundle['operation_lock']['staged_image']['target_image_id']==REMOVED
            assert len(bundle['operation_lock']['platform_source_diff'])==7 and all(r['target_sha256'] is None for r in bundle['operation_lock']['platform_source_diff'])
        write('bundle.json',bundle);record.update(operation_id=op,plan_hash=bundle['plan_hash'],state='prepared_not_imported')
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        if not args.operation_id:
            code,requested=operator.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=op,plan_hash=bundle['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':operator.csrf})
            assert code==200
        write('requested-status.json',requested['data'])
        record['state']='importing';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        write('registered.json',invoke(ops+['import-request',op]+options));write('independent-review.json',store.review(op,executor._validate()))
        (LOCAL/('source-live-'+args.case+'-old-pin.json')).write_text(json.dumps(dict(token=operator.release_token)),encoding='utf8')
        assert before==reader.state(reader.read(),catalog.snapshot())['state'];guard()
        record['state']='independently_reviewed_not_approved';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        print(json.dumps(record));return
    record=json.loads(marker.read_text());assert record['state']=='independently_reviewed_not_approved'
    assert record['base_digest']==data_digest(before) and record['protected_config_hashes']==hashes
    assert business==json.loads((output/'business-before.json').read_text()) and schema==json.loads((output/'schema-before.json').read_text())
    op=record['operation_id'];bundle=json.loads((output/'bundle.json').read_text())
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+options))
    phase('applying');result=executor.apply(op);write('completed.json',result);assert result['state']=='completed' and result['traffic_resumed']
    phase('completed_needs_verification')
    current=json.loads(target.read_text());assert current['generation']==base+1 and current['image_id']==(FULL if uninstall else REMOVED)
    assert current['worker_id']!=config['worker_id'];after_reader=DockerObserver(current);actual_observation=after_reader.read()
    after=after_reader.state(actual_observation,catalog.snapshot())['state'];actual=json.loads(sql(after_reader,BUSINESS_SQL));actual_schema=json.loads(sql(after_reader,SCHEMA))
    assert after['bindings']==bundle['operation_lock']['bindings'] and len(after['installations'])==6
    labels=[i for i in after['installations'] if i['plugin_id']==PLUGIN]
    assert len(labels)==2 and all(i['state']=='not_installed' and i['metadata_state']=='removed' and i['feature_state']=='suspended' for i in labels)
    assert [i for i in after['installations'] if i['plugin_id']!=PLUGIN]==[i for i in before['installations'] if i['plugin_id']!=PLUGIN]
    if uninstall:
        assert actual['notes']==[{k:v for k,v in n.items() if k!='x_notes_labels'} for n in business['notes']] and actual['boards']==business['boards']
        assert actual_schema['columns']==[c for c in schema['columns'] if c[1]!='x_notes_labels'] and actual_schema['constraints']==schema['constraints']
        effects=json.loads((control/'stages'/op/'native-effects.json').read_text());assert effects['surviving_native_versions_unchanged'];write('native-effects.json',effects)
    else:
        assert actual==business and actual_schema==schema and after['installations']==before['installations']
        assert PLUGIN not in actual_observation['runtime']['inventory']['artifacts']
        assert not any(n.startswith('addons/mp_example_notes_labels/') or n.endswith('org.example.notes_labels-0.2.1.mplug') for n in actual_observation['runtime']['inventory']['files'])
        assert json.loads((control/'stages'/op/'native-skipped.json').read_text())['reason']=='Reviewed source removal; native schema already absent'
        check=subprocess.run(['docker','inspect',state['project']+'-op-'+op+'-native'],capture_output=True);assert check.returncode!=0
        write('native-maintenance-skipped.json',dict(result='verified',native_child_exists=False))
    old_files=json.loads((output/'files-before.json').read_text());now=files(after_reader);assert all(now[n]==v for n,v in old_files.items())
    checkpoint=json.loads((control/'checkpoints'/op/'manifest.json').read_text())
    for n,v in checkpoint['files'].items():assert hashlib.sha256((control/'checkpoints'/op/n).read_bytes()).hexdigest()==v
    old=next(p for p in before['release_lock']['plugins'] if p['plugin_id']==PLUGIN)
    assert 'sha256:'+hashlib.sha256(catalog.path(old['digest']).read_bytes()).hexdigest()==old['digest']
    write('checkpoint-manifest.json',checkpoint);write('state-after.json',after);write('business-after.json',actual);write('schema-after.json',actual_schema);write('files-after.json',now)
    new_client=r1_probe.Client(state,fixture,'operator');pin=json.loads((LOCAL/('source-live-'+args.case+'-old-pin.json')).read_text())['token']
    code,rejected=new_client.request('/api/v1/navigation',workspace='A',headers={'X-MP-Client-Release':pin});assert code==409 and rejected['error']['code']=='CONFLICT'
    write('old-client-rejected.json',rejected);write('completed-mirror.json',invoke(ops+['mirror-status',op]+options))
    guard();state.update(phase=('artifact_removal_labels_absent' if uninstall else 'artifact_source_removed'),generation=base+1,image_id=current['image_id'],worker_id=current['worker_id'])
    (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('qualification.json',dict(result='passed_actual_'+args.case,utc=datetime.now(timezone.utc).isoformat(),operation_id=op,plan_hash=record['plan_hash'],generation=base+1,image_id=current['image_id'],notes_boards_preserved=True,stable_tombstone_scopes=2,checkpoint_hashes_verified=True,old_files_preserved=len(old_files),old_catalog_archive_retained=True,old_client_rejected=True,protected_config_hashes=hashes,limits=['Actual browser/native/API/assets survivor checks remain separate; no permission-expanding upgrade or clean restore claim.']))
    print(json.dumps(dict(result='completed_verified',case=args.case,operation_id=op,generation=base+1)))


if __name__=='__main__':main()
