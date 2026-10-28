"""Once-only core prerequisite on the retained isolated manager fixture, never main."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-manager-inspection-core-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from qualify_manager_upgrade_operation import snapshot,files,sql

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));target=LOCAL/'operator/target.json'
    config=json.loads(target.read_text(encoding='utf-8'));marker=LOCAL/'manager-inspection-core.json'
    main_path=ROOT/'.local/operator/targets/g5.json'
    def guard():assert hashlib.sha256(main_path.read_bytes()).hexdigest()==state['main_target_sha256']
    guard();assert state['disposable'] and state['project']==config['project']=='mp-r0-r1mgr84459f617ab0'
    assert state['phase']=='notes_upgraded' and state['generation']==config['generation']==3
    assert config['sites'][0]['database']==state['active_db']=='mp_disposable_r0_r1_g5_mgr_84459f617ab0'
    build=json.loads((ROOT/'docs/evidence/G5/20261029-manager-inspection-candidate/candidate-build.json').read_text(encoding='utf-8'))
    assert build['state']=='built' and build['result']=='built_not_deployed'
    image=build['image_id'];operator=ROOT/'.local/operator';catalog_root=operator/'catalog';trust=operator/'trust.json';control=LOCAL/'operator/control'
    validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True).snapshot();reader=DockerObserver(config)
    before=reader.state(reader.read(),catalog)['state'];business=snapshot(reader)
    assert len(before['installations'])==1 and len(business['notes'])==2 and business['positive_constraint']
    prefix=[sys.executable,'tools/modular.py','--config',str(trust)];options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    def invoke(argv):
        p=subprocess.run(argv,capture_output=True,cwd=ROOT,timeout=600)
        if p.returncode:raise RuntimeError('Independent CLI failed; inspect retained private journal, never blind retry: '+p.stderr.decode(errors='replace')[:400])
        return json.loads(p.stdout)
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    if args.action=='prepare':
        assert not marker.exists() and not OUTPUT.exists();OUTPUT.mkdir()
        record={'state':'preparing','base_generation':3,'image_id':image,'before_digest':data_digest(before)}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        write('configuration-before.json',config);write('state-before.json',before);write('business-before.json',business);write('files-before.json',files(reader))
        write('staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',image]+options))
        nomination={'operation_type':'core_upgrade','targets':[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|{'action':'deploy'} for row in before['installations']]}
        write('nomination.json',nomination);bundle=invoke(prefix+['plugin','plan-staged','--input',str(OUTPUT/'nomination.json')]+options)
        assert bundle['operation_lock']['native_core_changes']==[
            {'addon':'mp_core','previous_version':'19.0.0.1.3','target_version':'19.0.0.1.4','migrations':[]},
            {'addon':'mp_shell','previous_version':'19.0.0.1.4','target_version':'19.0.0.1.5','migrations':[]}]
        assert len(bundle['operation_lock']['targets'])==1 and bundle['plan']['backup']['required'] and bundle['plan']['destructive'] and not bundle['plan']['permission_changes']
        write('bundle.json',bundle);assert before==reader.state(reader.read(),catalog)['state'];guard()
        record.update(state='prepared_not_registered',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'])
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='prepared_not_registered' and record['image_id']==image and record['before_digest']==data_digest(before)
    assert business==json.loads((OUTPUT/'business-before.json').read_text(encoding='utf-8'))
    old_files=json.loads((OUTPUT/'files-before.json').read_text(encoding='utf-8'));assert old_files==files(reader)
    op=record['operation_id'];operations=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    phase('registering');write('registered.json',invoke(operations+['register','--bundle',str(OUTPUT/'bundle.json')]+validation))
    store=OperatorStore(control)
    write('independent-review.json',store.review(op,StagedNativeExecutor(store,target,catalog_root,validator)._validate()))
    write('approved.json',invoke(operations+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation))
    phase('applying');print(json.dumps({'stage':'approved_exact_isolated_core','operation_id':op}),flush=True)
    completed=invoke(prefix+['plugin','apply',op]+options);write('completed.json',completed);assert completed['state']=='completed' and completed['traffic_resumed'];phase('completed_needs_verification')
    current=json.loads(target.read_text(encoding='utf-8'));assert current['generation']==4 and current['image_id']==image
    after_reader=DockerObserver(current);after=after_reader.state(after_reader.read(),catalog)['state'];actual=snapshot(after_reader)
    assert before['installations']==after['installations'] and before['bindings']==after['bindings'] and business==actual
    now_files=files(after_reader);assert all(now_files.get(n)==h for n,h in old_files.items())
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-op-'+op+'-native'],text=True))[0]
    assert child['Image']==image and child['State']['ExitCode']==0 and child['Config']['Cmd'][child['Config']['Cmd'].index('-u')+1]=='mp_core,mp_shell'
    write('native-child.json',{'image_id':image,'arguments':child['Config']['Cmd'],'exit_code':0})
    cache=json.loads(sql(after_reader,'SELECT payload FROM mp_operation_profile;'));assert cache['configuration']['generation']==4 and 'staged_release' not in cache
    assets=json.loads((control/'stages'/op/'assets.json').read_text(encoding='utf-8'));assert assets['result']=='prepared' and assets['generation']==4
    write('prepared-assets.json',assets);write('state-after.json',after);write('business-after.json',actual)
    state.update(phase='manager_inspection_core_activated',generation=4,image_id=image,worker_id=current['worker_id'],runtime_inventory_digest=current['published_release']['core_inventory_digest'])
    (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');phase('completed_verified');guard()
    write('activation.json',{'result':'passed_isolated_core_activation','utc':datetime.now(timezone.utc).isoformat(),'operation_id':op,'plan_hash':record['plan_hash'],'configuration':current,'original_business_features_bindings_grants_exact':True,'old_files_preserved':len(old_files),'native_core_versions_only':True,'preflight_before_ready':True,'main_target_unchanged':True,'limits':['Proxy volume configuration and actual new HTTP/browser upload/details qualification remain pending.','No G5-X02/full gate pass inferred.']})
    print(json.dumps({'result':'completed_verified','operation_id':op,'generation':4,'image_id':image}))

if __name__=='__main__':main()
