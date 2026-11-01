"""Separate normal immutable Notes plugin upgrade on the populated fixture."""
import argparse,base64,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.release_staging import validate_plugin_core_stability
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'notes7-upgrade-01.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state);record=f.load(MARKER)
    native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,record,native

def candidate():
    state,record,native=context();assert state['phase']=='notes7_building' and record['state']=='building' and native.config['generation']==7
    build=f.load(ROOT/record['build_output']/'candidate-build.json');assert build['state']=='built'
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
    old,new=inspect_image(state['image_id']),inspect_image(build['image_id']);validate_plugin_core_stability(old,new)
    for name in ['platform_version','python_metadata','python_lock_digest']:assert old[name]==new[name]
    for name in ['native_addons','policy','generated_patches']:assert old['inventory'].get(name)==new['inventory'].get(name)
    assert old['native_manifests'].keys()==new['native_manifests'].keys()
    assert all(old['native_manifests'][n]==new['native_manifests'][n] for n in old['native_manifests'] if n!='mp_example_notes')
    assert old['native_manifests']['mp_example_notes']['version']=='19.0.0.2.6' and new['native_manifests']['mp_example_notes']['version']=='19.0.0.2.7'
    artifacts=build['artifacts'];assert artifacts==new['inventory']['artifacts']
    assert {n for n in artifacts if artifacts[n]!=old['inventory']['artifacts'][n]}=={'org.example.notes'}
    oldfiles,newfiles=old['inventory']['files'],new['inventory']['files'];diff=sorted(p for p in oldfiles.keys()|newfiles.keys() if oldfiles.get(p)!=newfiles.get(p))
    assert diff and all(p.startswith(('addons/mp_example_notes/','artifacts/org.example.notes-')) for p in diff),diff
    freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
    item=artifacts['org.example.notes'];assert item['version']=='0.2.7'
    record.update(state='extracting_once',image_id=build['image_id'],inventory_digest=new['inventory_digest']);f.write(MARKER,record)
    code="import base64,pathlib;print(base64.b64encode((pathlib.Path('/opt/modular/artifacts')/"+repr(item['file'])+").read_bytes()).decode())"
    raw=f.command('notes7-extract-01',['docker','run','--name',state['project']+'-notes7-extract-01','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',build['image_id'],'-c',code])
    data=base64.b64decode(raw,validate=False);assert 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
    archive=j.LOCAL/item['file'];assert not archive.exists();archive.write_bytes(data)
    policy=f.load(j.LOCAL/'operator/trust.json');assert policy['generation']==4 and item['digest'] not in policy['approved_digests']
    record['state']='curating_once';f.write(MARKER,record);policy['generation']=5;policy['approved_digests'].append(item['digest']);f.write(j.LOCAL/'operator/trust.json',policy)
    catalog=Catalog(native.catalog_root,configuration(j.LOCAL/'operator/trust.json'));assert len(catalog.snapshot())==9
    catalog.add(archive,expected_digest=item['digest']);assert len(catalog.snapshot())==10
    f.save('candidate-validation.json',dict(result='passed_notes_only_candidate',image_id=build['image_id'],inventory_digest=new['inventory_digest'],source_base=build['git_base'],artifacts=artifacts,source_diff=diff,core_identity_shell_SDK_Python_policy_exact=True,only_native_version_change=['mp_example_notes','19.0.0.2.6','19.0.0.2.7'],frozen_files=94,isolated_trust_generation=5,isolated_catalog_entries=10,global_trust_catalog_unchanged=True,deployment_changed=False))
    record['state']='candidate_validated_not_staged';f.write(MARKER,record);f.phase(state,'notes7_candidate_validated');f.guard(state)
    print('Notes-only .7 immutable candidate and isolated trust5/catalog10 verified; runtime remains config7.')

def prepare():
    state,record,native=context();assert state['phase']=='notes7_candidate_validated' and record['state']=='candidate_validated_not_staged' and native.config['generation']==7
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);reader=DockerObserver(native.config);before=reader.state(reader.read(),catalog.snapshot())['state'];assert len(before['installations'])==7;f.save('state-before.json',before)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')];options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    record['state']='staging';f.write(MARKER,record);f.phase(state,'notes7_staging')
    staged=json.loads(f.command('notes7-stage-01',prefix+['plugin','stage-image','--image-id',record['image_id']]+options));f.save('staged-image.json',staged)
    targets=[{k:row[k] for k in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='upgrade') for row in before['installations'] if row['plugin_id']=='org.example.notes'];assert len(targets)==3
    nomination=dict(operation_type='upgrade',targets=targets);f.save('nomination.json',nomination)
    bundle=json.loads(f.command('notes7-plan-01',prefix+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options));f.save('bundle.json',bundle)
    assert not bundle['operation_lock'].get('native_core_changes') and not bundle['plan']['permission_changes'] and len(bundle['operation_lock']['targets'])==3
    assert bundle['operation_lock']['bindings']==before['bindings'] and bundle['plan']['backup']['required']
    operation=bundle['plan']['operation_id'];record.update(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('notes7-register-01',ops+['register','--bundle',str(OUT/'bundle.json')]+validation);f.save('independent-review.json',native.store.review(operation,native._validate()))
    f.command('notes7-approve-01',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust']+validation)
    record['state']='approved';f.write(MARKER,record);f.phase(state,'notes7_approved');f.guard(state)
    print('Separate Notes .7 plugin upgrade for A/B/C independently reviewed and approved; core unchanged.')

def apply():
    state,record,native=context();assert state['phase']=='notes7_approved' and record['state']=='approved' and native.config['generation']==7
    record['state']='applying';f.write(MARKER,record);f.phase(state,'notes7_applying')
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    result=json.loads(f.command('notes7-apply-01',prefix+['plugin','apply',record['operation_id'],'--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)],timeout=600))
    assert result['state']=='completed' and result['traffic_resumed']
    config=f.load(native.target_path);assert config['generation']==8 and config['image_id']==record['image_id'] and config['sites'][0]['database']==state['active_db']
    reader=DockerObserver(config);catalog=Catalog(native.catalog_root,native.validator,readonly=True);after=reader.state(reader.read(),catalog.snapshot())['state'];before=f.load(OUT/'state-before.json')
    assert before['bindings']==after['bindings'] and len(after['installations'])==7
    f.save('completed.json',result);f.save('state-after.json',after)
    state.update(image_id=config['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'notes7_completed_needs_verification');f.guard(state)
    print('Approved separate Notes .7 upgrade completed config8; populated native batch/history verification next.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['candidate','prepare','apply']);args=parser.parse_args();globals()[args.action]()
