"""Once-only exact numeric-parser maintenance on isolated4; never main."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-native-numeric-core-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.native_versions import PARSER_PATH,SOURCE_SHA256,TARGET_SHA256,patch_record
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from qualify_manager_upgrade_operation import snapshot,files,sql

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));target=LOCAL/'operator/target.json';config=json.loads(target.read_text(encoding='utf-8'))
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1mgr84459f617ab0'
    assert state['phase']=='manager_inspection_core_activated' and state['generation']==config['generation']==4
    assert config['sites'][0]['database']=='mp_disposable_r0_r1_g5_mgr_84459f617ab0'
    marker=LOCAL/'native-numeric-core.json'
    def guard():assert hashlib.sha256((ROOT/'.local/operator/targets/g5.json').read_bytes()).hexdigest()==state['main_target_sha256']
    guard();build=json.loads((ROOT/'docs/evidence/G5/20261029-native-numeric-candidate/candidate-build.json').read_text(encoding='utf-8'));assert build['result']=='built_not_deployed'
    image=build['image_id'];operator=ROOT/'.local/operator';trust=operator/'trust.json';catalog_root=operator/'catalog';control=LOCAL/'operator/control';validator=configuration(trust)
    catalog=Catalog(catalog_root,validator,readonly=True).snapshot();reader=DockerObserver(config);observation=reader.read();before=reader.state(observation,catalog)['state'];business=snapshot(reader)
    assert observation['runtime']['inventory']['files'][PARSER_PATH]==SOURCE_SHA256 and len(business['notes'])==2 and len(before['installations'])==1
    prefix=[sys.executable,'tools/modular.py','--config',str(trust)];options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    def invoke(argv):
        p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=600)
        if p.returncode:raise RuntimeError('Independent numeric-core CLI failed; inspect terminal/private state before retry: '+p.stderr.decode(errors='replace')[:400])
        return json.loads(p.stdout)
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    if args.action=='prepare':
        assert not marker.exists() and not OUTPUT.exists();OUTPUT.mkdir()
        record={'state':'preparing','base_generation':4,'before_digest':data_digest(before),'image_id':image};marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        write('state-before.json',before);write('business-before.json',business);write('files-before.json',files(reader));write('configuration-before.json',config)
        write('staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',image]+options))
        nomination={'operation_type':'core_upgrade','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write('nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(OUTPUT/'nomination.json')]+options)
        assert bundle['operation_lock']['native_core_changes']==[{'addon':'mp_compat','previous_version':'19.0.0.1.0','target_version':'19.0.0.1.1','migrations':[]}]
        changed=next(d for d in bundle['operation_lock']['platform_source_diff'] if d['path']==PARSER_PATH)
        assert changed['previous_sha256']==SOURCE_SHA256 and changed['target_sha256']==TARGET_SHA256
        assert len(bundle['operation_lock']['targets'])==1 and bundle['plan']['backup']['required'] and bundle['plan']['destructive'] and not bundle['plan']['permission_changes']
        write('bundle.json',bundle);guard();assert before==reader.state(reader.read(),catalog)['state']
        record.update(state='prepared_not_registered',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['before_digest']==data_digest(before) and record['image_id']==image
    assert business==json.loads((OUTPUT/'business-before.json').read_text(encoding='utf-8'));old_files=json.loads((OUTPUT/'files-before.json').read_text(encoding='utf-8'));assert files(reader)==old_files
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    op=record['operation_id'];ops=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    phase('registering');write('registered.json',invoke(ops+['register','--bundle',str(OUTPUT/'bundle.json')]+validation))
    store=OperatorStore(control);write('independent-review.json',store.review(op,StagedNativeExecutor(store,target,catalog_root,validator)._validate()))
    write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation));phase('applying');print(json.dumps({'stage':'approved_exact_numeric_core','operation_id':op}),flush=True)
    completed=invoke(prefix+['plugin','apply',op]+options);write('completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed'];phase('completed_needs_verification')
    current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==5 and current['image_id']==image
    after_reader=DockerObserver(current);actual=after_reader.read();after=after_reader.state(actual,catalog)['state'];assert snapshot(after_reader)==business
    assert before['installations']==after['installations'] and before['bindings']==after['bindings']
    assert actual['runtime']['inventory']['files'][PARSER_PATH]==TARGET_SHA256 and actual['runtime']['inventory']['generated_patches'][-1]==patch_record()
    now_files=files(after_reader);assert all(now_files.get(n)==h for n,h in old_files.items())
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-op-'+op+'-native'],text=True))[0]
    assert child['Image']==image and child['State']['ExitCode']==0 and child['Config']['Cmd'][child['Config']['Cmd'].index('-u')+1]=='mp_compat'
    write('native-child.json',{'image_id':image,'arguments':child['Config']['Cmd'],'exit_code':0})
    cache=json.loads(sql(after_reader,'SELECT payload FROM mp_operation_profile;'));assert cache['configuration']['generation']==5 and 'staged_release' not in cache and len(cache['catalog'])==7
    assets=json.loads((control/'stages'/op/'assets.json').read_text(encoding='utf-8'));assert assets['result']=='prepared' and assets['generation']==5
    write('prepared-assets.json',assets);write('state-after.json',after);write('business-after.json',snapshot(after_reader))
    state.update(phase='native_numeric_core_activated',generation=5,image_id=image,worker_id=current['worker_id'],runtime_inventory_digest=actual['runtime']['inventory_digest']);(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');phase('completed_verified');guard()
    write('activation.json',{'result':'passed_exact_numeric_core_activation','utc':datetime.now(timezone.utc).isoformat(),'operation_id':op,'plan_hash':record['plan_hash'],'configuration':current,'native_parser_sha256':TARGET_SHA256,'generated_patch':patch_record(),'native_compatibility_only':True,'business_scopes_bindings_grants_exact':True,'old_files_preserved':len(old_files),'asset_preflight_before_ready':True,'main_target_unchanged':True,'limits':['Full VER02 actual script/database/fresh-install matrix remains pending.']})
    print(json.dumps({'result':'completed_verified','operation_id':op,'generation':5,'image_id':image}))

if __name__=='__main__':main()
