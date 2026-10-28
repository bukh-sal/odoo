"""Once-only approved reader rollout/Labels install with automatic app cache."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.contracts import validate_operations_view
from modular_platform.deployment import DockerObserver,_run
from modular_platform.lifecycle_planning import installation_id
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from qualify_staged_planning import invoke,write
from qualify_native_upgrade import sql
import r1,r1_probe
r1.r0.LOCAL=ROOT/'.local/g5'


def notes_snapshot(observer):
    return json.loads(sql(observer,"SELECT COALESCE(jsonb_agg(to_jsonb(n)-'x_notes_labels' ORDER BY id),'[]'::jsonb) FROM mp_example_note n;"))


def files(observer):
    code="import json,pathlib,hashlib,sys;root=pathlib.Path('/var/lib/modular/filestore')/sys.argv[1]; print(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}))"
    return json.loads(_run(['docker','exec',observer._container('app'),'/venv/bin/python','-c',code,observer.config['sites'][0]['database']]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--image-id',required=True);parser.add_argument('--apply',action='store_true',required=True);args=parser.parse_args()
    output=args.output.resolve();local=ROOT/'.local/g5';marker=local/'release-reader-rollout.json'
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():raise ValueError('Fresh once-only rollout required; reconcile marker before any retry')
    operator=ROOT/'.local/operator';target=operator/'targets/g5.json';control=operator/'control';catalog_root=operator/'catalog'
    config=json.loads(target.read_text());state=json.loads((local/'state.json').read_text());fixture=json.loads((local/'fixtures.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==9 and config['published_release'] and state['disposable']
    assert json.loads((local/'release-adoption.json').read_text())['state']=='adopted_verified'
    validator=configuration(operator/'trust.json');snapshot=Catalog(catalog_root,validator,readonly=True).snapshot()
    observer=DockerObserver(config);observed=observer.read();before=observer.state(observed,snapshot)['state']
    notes=notes_snapshot(observer);old_files=files(observer);assert len(notes)==4
    assert not any(item['plugin_id']=='org.example.notes_labels' for item in before['installations'])
    output.mkdir(parents=True);write(output/'state-before.json',before)
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',args.image_id]+options))
    nomination={'operation_type':'install','targets':[{'installation_id':installation_id(observed['sites'][0],'org.example.notes_labels'),
        'site_id':config['sites'][0]['site_id'],'workspace_id':fixture['workspaces']['A']['public_id'],
        'plugin_id':'org.example.notes_labels','action':'install'}]}
    write(output/'nomination.json',nomination)
    bundle=invoke(prefix+['plugin','plan-staged','--input',str(output/'nomination.json')]+options)
    operation=bundle['plan']['operation_id'];write(output/'bundle.json',bundle)
    assert len(bundle['plan']['permission_changes'])==1 and bundle['plan']['permission_changes'][0]['action']=='grant'
    write(marker,{'operation_id':operation,'plan_hash':bundle['plan_hash'],'state':'nominated','evidence':str(output.relative_to(ROOT))})
    operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    write(output/'registered.json',invoke(operations+['register','--bundle',str(output/'bundle.json')]+validation))
    denied=invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation,success=False)
    assert 'explicit acknowledgment' in denied['message'];write(output/'permission-ack-denied.json',denied)
    write(output/'approved.json',invoke(operations+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+validation))
    print(json.dumps({'stage':'approved','operation_id':operation,'scoped_grant':bundle['plan']['permission_changes']}),flush=True)
    native=StagedNativeExecutor(OperatorStore(control),target,catalog_root,validator)
    completed=native.apply(operation);assert completed['state']=='completed';write(output/'completed.json',completed)
    current=json.loads(target.read_text());reader=DockerObserver(current);actual=reader.read();after=reader.state(actual,snapshot)['state']
    assert actual['runtime']['published_release_protocol']==1 and current['published_release']==bundle['operation_lock']['release']
    assert after['release_digest']==bundle['plan']['target_release_digest'] and notes_snapshot(reader)==notes
    current_files=files(reader);assert all(current_files.get(name)==digest for name,digest in old_files.items())
    assert len(after['installations'])==3
    assert next(row for row in after['installations'] if row['plugin_id']=='org.example.notes' and row['workspace_id']==fixture['workspaces']['B']['public_id'])['feature_state']=='suspended'
    cache=json.loads(sql(reader,"SELECT payload FROM mp_operation_profile;"))
    assert cache['configuration']['published_release']==current['published_release'] and cache['configuration']['generation']==current['generation']
    assert cache['runtime']['inventory_digest']==actual['runtime']['inventory_digest']
    publication=json.loads((control/'stages'/operation/'profile-publication.json').read_text())
    assert publication['profile_published'] and publication['release_digest']==after['release_digest']
    write(output/'automatic-profile-publication.json',publication)
    assert native.apply(operation)==completed;write(output/'completed-replay.json',{'same_status_no_new_mutation':True})
    state.update(image_id=current['image_id'],worker_id=current['worker_id'],release_generation=current['generation'],stage='published_reader_labelsA')
    state['evidence_history']=list(dict.fromkeys(state.get('evidence_history',[])+[state['evidence']]))
    state['evidence']=str(output.relative_to(ROOT));(local/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    fixture['bindings']={key:next(b for b in after['bindings'] if b['workspace_id']==row['public_id'] and b['consumer_installation_id']==
        next(item['installation_id'] for item in after['installations'] if item['plugin_id']=='org.example.notes') and b['alias']=='documents') for key,row in fixture['workspaces'].items()}
    seeded=json.loads((local/'lifecycle-data.json').read_text());alice=r1_probe.Client(state,fixture,'alice')
    for row in seeded['objects']['A']:
        value=alice.call('get',{'note_id':row['dto']['id']},workspace='A');assert value['labels']==[] and value==row['dto']
    alice.call('get',{'note_id':seeded['objects']['B'][0]['dto']['id']},workspace='B',expect=403,code='FORBIDDEN')
    operator_client=r1_probe.Client(state,fixture,'operator')
    request={'schema_version':1,'operation':'prepare','operation_type':'suspend','plugin_id':'org.example.notes_labels',
        'site_id':fixture['site_id'],'workspace_ids':[fixture['workspaces']['A']['public_id']],'cascade':False}
    status,response=operator_client.request('/api/v1/operations/prepare',request,headers={'X-CSRFToken':operator_client.csrf})
    assert status==200;prepared=validate_operations_view(response['data']);write(output/'app-prepared.json',prepared)
    app_operation=prepared['operation_id']
    status,response=operator_client.request('/api/v1/operations/bundle/'+app_operation);assert status==200
    app_bundle=response['data'];write(output/'app-bundle.json',app_bundle)
    status,response=operator_client.request('/api/v1/operations/request',{'schema_version':1,'operation':'request',
        'operation_id':app_operation,'plan_hash':prepared['plan_hash'],'request_id':str(uuid4())},headers={'X-CSRFToken':operator_client.csrf})
    assert status==200
    imported=invoke(operations+['import-request',app_operation]+validation);assert imported['state']=='awaiting_operator_approval'
    write(output/'app-independent-import.json',imported)
    # This follow-up request only verifies matching app/OS preimages. Retire
    # it without approving/applying another feature mutation.
    write(output/'app-plan-retired.json',invoke(operations+['revoke-approval',app_operation]))
    write(output/'app-revocation-mirror.json',invoke(operations+['mirror-status',app_operation]+validation))
    write(output/'state-after.json',after)
    marker.write_text(json.dumps({'operation_id':operation,'state':'completed','image_id':current['image_id'],'generation':current['generation'],
        'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+[Path(__file__),ROOT/'tools/modular.py',ROOT/'tools/publish_profile.py']
    write(output/'reader-rollout.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'plan_hash':bundle['plan_hash'],'configuration':current,'reader_protocol':1,
        'automatic_profile_published_before_ready':True,'base_note_rows_unchanged':4,'old_filestore_files_preserved':len(old_files),
        'new_extension_field_default':[],'notesB_suspension_preserved':True,'explicit_permission_ack_required':True,
        'app_prepared_plan_independently_reconstructed_imported_and_retired':app_operation,
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limitations':['No frontend source rewrite. Client release reload/default startup/uninstall/fault matrix and full G5 remain pending.',
            'App preparation here is the existing feature operation; native install/upgrade UI preparation remains a separate G5 integration item.']})
    print(json.dumps({'result':'passed_subset','operation_id':operation,'generation':current['generation'],'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
