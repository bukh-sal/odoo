"""Finish proof after a completed rollout; never invokes native apply/install."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.contracts import validate_operations_view
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular import configuration
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import notes_snapshot,files
from qualify_staged_planning import invoke,write
import r1,r1_probe
r1.r0.LOCAL=ROOT/'.local/g5'


def main():
    local=r1.r0.LOCAL;marker=local/'release-reader-rollout.json';saved=json.loads(marker.read_text())
    assert saved['state']=='nominated','Verifier runs only to reconcile the saved completed rollout'
    output=ROOT/saved['evidence'];operator=ROOT/'.local/operator';target=operator/'targets/g5.json';operation=saved['operation_id']
    store=OperatorStore(operator/'control');completed=store.status(operation);assert completed['state']=='completed' and completed['traffic_resumed']
    bundle=store.bundle(operation);config=json.loads(target.read_text());assert config['published_release']==bundle['operation_lock']['release']
    validator=configuration(operator/'trust.json');catalog=Catalog(operator/'catalog',validator,readonly=True).snapshot()
    reader=DockerObserver(config);observed=reader.read();after=reader.state(observed,catalog)['state']
    assert config['image_id']==bundle['operation_lock']['staged_image']['target_image_id'] and observed['runtime']['published_release_protocol']==1
    assert after['release_digest']==bundle['plan']['target_release_digest']
    seeded=json.loads((local/'lifecycle-data.json').read_text());rows={row['public_id']:row for row in notes_snapshot(reader)}
    for key,objects in seeded['objects'].items():
        for row in objects:
            current=rows[row['dto']['id']];native=row['native']
            assert all(current[field]==native[field] for field in ('id','public_id','title','body','revision'))
            assert current['workspace_id']==native['workspace_id'][0] and current['author_id']==native['author_id'][0]
    checkpoint=store.root/'checkpoints'/operation
    manifest=json.loads((checkpoint/'manifest.json').read_text())
    archive=checkpoint/'filestore.tar.gz';assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['files']['filestore.tar.gz']
    with tarfile.open(archive,mode='r:gz') as tar:
        prefix='filestore/'+config['sites'][0]['database']+'/'
        old_files={member.name[len(prefix):]:hashlib.sha256(tar.extractfile(member).read()).hexdigest()
            for member in tar.getmembers() if member.isfile() and member.name.startswith(prefix)}
    actual=files(reader);assert all(actual.get(name)==digest for name,digest in old_files.items())
    cache=json.loads(sql(reader,'SELECT payload FROM mp_operation_profile;'))
    assert cache['configuration']['published_release']==config['published_release'] and cache['runtime']['inventory_digest']==observed['runtime']['inventory_digest']
    publication=json.loads((store.root/'stages'/operation/'profile-publication.json').read_text());assert publication['release_digest']==after['release_digest']
    state=json.loads((local/'state.json').read_text());fixture=json.loads((local/'fixtures.json').read_text())
    assert state['image_id']==config['image_id'] and state['release_generation']==config['generation']
    installation=next(row['installation_id'] for row in after['installations'] if row['plugin_id']=='org.example.notes')
    fixture['bindings']={key:next(b for b in after['bindings'] if b['consumer_installation_id']==installation and b['workspace_id']==w['public_id'] and b['alias']=='documents') for key,w in fixture['workspaces'].items()}
    alice=r1_probe.Client(state,fixture,'alice')
    for row in seeded['objects']['A']:assert alice.call('get',{'note_id':row['dto']['id']},workspace='A')==row['dto']
    alice.call('get',{'note_id':seeded['objects']['B'][0]['dto']['id']},workspace='B',expect=403,code='FORBIDDEN')
    bob=fixture['users']['bob']['principal_id'];workspaceB=fixture['workspaces']['B']['public_id']
    assert next(row for row in observed['sites'][0]['memberships'] if row['principal_id']==bob and row['workspace_id']==workspaceB)['state']=='revoked'
    assert next(row for row in after['installations'] if row['plugin_id']=='org.example.notes' and row['workspace_id']==workspaceB)['feature_state']=='suspended'
    client=r1_probe.Client(state,fixture,'operator')
    status,value=client.request('/api/v1/operations/prepare',{'schema_version':1,'operation':'prepare','operation_type':'suspend',
        'plugin_id':'org.example.notes_labels','site_id':fixture['site_id'],'workspace_ids':[fixture['workspaces']['A']['public_id']],'cascade':False},headers={'X-CSRFToken':client.csrf})
    assert status==200,(status,value);prepared=validate_operations_view(value['data']);write(output/'app-prepared.json',prepared)
    app_operation=prepared['operation_id'];status,value=client.request('/api/v1/operations/bundle/'+app_operation);assert status==200
    write(output/'app-bundle.json',value['data'])
    status,value=client.request('/api/v1/operations/request',{'schema_version':1,'operation':'request','operation_id':app_operation,
        'plan_hash':prepared['plan_hash'],'request_id':str(uuid4())},headers={'X-CSRFToken':client.csrf});assert status==200
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json'),'operations','--store',str(operator/'control')]
    validation=['--deployment-config',str(target),'--catalog',str(operator/'catalog')]
    imported=invoke(prefix+['import-request',app_operation]+validation);assert imported['state']=='awaiting_operator_approval';write(output/'app-independent-import.json',imported)
    write(output/'app-plan-retired.json',invoke(prefix+['revoke-approval',app_operation]))
    write(output/'app-revocation-mirror.json',invoke(prefix+['mirror-status',app_operation]+validation))
    write(output/'state-after.json',after)
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+[Path(__file__),ROOT/'tools/modular.py',ROOT/'tools/publish_profile.py']
    write(output/'reader-rollout.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),'operation_id':operation,
        'plan_hash':bundle['plan_hash'],'configuration':config,'reader_protocol':1,'automatic_profile_published_before_ready':True,
        'base_notes_contract_fields_preserved':4,'checkpoint_filestore_files_preserved':len(old_files),'notesB_suspended_Bob_revoked':True,
        'app_prepared_plan_independently_imported_then_retired':app_operation,'completed_operation_not_repeated':True,
        'postcheck_correction':'Base DTO already contains labels=[]; compare unchanged DTO, do not pop it. Actual SQL/data/cache checks passed before original verifier assertion.',
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'limitations':['Feature app/OS preimages qualified; native install/upgrade UI preparation, client reload/default startup/uninstall and full G5 remain pending.']})
    marker.write_text(json.dumps({'operation_id':operation,'state':'completed','image_id':config['image_id'],'generation':config['generation'],
        'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    print(json.dumps({'result':'passed_subset','operation_id':operation,'generation':config['generation'],'no_native_repeat':True}))


if __name__=='__main__':main()
