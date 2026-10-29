"""Exact independently reviewed SDK-only activation on the owned lifecycle target."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent/'deploy';LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'));target=LOCAL/'operator/target.json';config=load(target);state=load(LOCAL/'state.json');marker=LOCAL/'worker-fence-deploy.json'
    assert state['disposable'] and config['project']==state['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==17
    parent=OUTPUT.parent;assert load(parent/'default-startup-matrix.json')['result']=='passed';build=load(parent/'candidate-build.json');image=build['image_id']
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];control=LOCAL/'operator/control';validator=configuration(trust);catalog=Catalog(catalog_root,validator,readonly=True)
    reader=DockerObserver(config);before=reader.state(reader.read(),catalog.snapshot())['state'];store=OperatorStore(control)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];options=['--store',str(control),'--deployment-config',str(target),'--catalog',str(catalog_root)];ops=prefix+['operations','--store',str(control)];validation=['--deployment-config',str(target),'--catalog',str(catalog_root)]
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(command):
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        if r.returncode:
            (LOCAL/('worker-fence-deploy-'+args.action+'.stderr')).write_bytes(r.stderr);raise RuntimeError('Deployment CLI failed; reconcile journal/marker/target, never reapply blindly')
        return json.loads(r.stdout)
    if args.action=='prepare':
        assert not marker.exists() and not OUTPUT.exists();OUTPUT.mkdir()
        record=dict(state='preparing',before_digest=data_digest(before),image_id=image)
    else:
        record=load(marker);assert record['state']=='independently_reviewed_not_approved' and record['before_digest']==data_digest(before)
    def phase(value):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    if args.action=='prepare':
        phase('preparing')
        for name,value in [('state-before',before),('business-before',json.loads(sql(reader,BUSINESS_SQL))),('schema-before',json.loads(sql(reader,SCHEMA))),('configuration-before',config),('files-before',files(reader))]:write(name+'.json',value)
        write('staged-image.json',invoke(prefix+['plugin','stage-image','--image-id',image]+options))
        nomination=dict(operation_type='deploy',targets=[{k:r[k] for k in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='deploy') for r in before['installations']]);write('nomination.json',nomination)
        bundle=invoke(prefix+['plugin','plan-staged','--input',str(OUTPUT/'nomination.json')]+options);write('bundle.json',bundle)
        assert [d['path'] for d in bundle['operation_lock']['platform_source_diff']]==['packages/platform_sdk/modular_platform/worker_start.py']
        assert len(bundle['operation_lock']['targets'])==6 and 'native_core_changes' not in bundle['operation_lock']
        assert bundle['plan']['backup']['required'] and not bundle['plan']['destructive'] and not bundle['plan']['permission_changes']
        record.update(operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);phase('registering')
        write('registered.json',invoke(ops+['register','--bundle',str(OUTPUT/'bundle.json')]+validation))
        write('independent-review.json',store.review(record['operation_id'],StagedNativeExecutor(store,target,catalog_root,validator)._validate()))
        assert reader.state(reader.read(),catalog.snapshot())['state']==before;phase('independently_reviewed_not_approved');print(json.dumps(record));return
    op=record['operation_id'];assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-before.json') and files(reader)==load(OUTPUT/'files-before.json')
    phase('approving');write('approved.json',invoke(ops+['approve',op,'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+validation))
    phase('applying_exact_reviewed_guard_deploy');result=invoke(prefix+['plugin','apply',op]+options);write('completed.json',result);assert result['state']=='completed' and result['traffic_resumed'];phase('completed_needs_verification')
    current=load(target);assert current['generation']==18 and current['image_id']==image and current['worker_id']!=config['worker_id']
    after=DockerObserver(current);observation=after.read();observed=after.state(observation,catalog.snapshot())['state']
    assert json.loads(sql(after,BUSINESS_SQL))==load(OUTPUT/'business-before.json') and json.loads(sql(after,SCHEMA))==load(OUTPUT/'schema-before.json')
    assert observed['installations']==before['installations'] and observed['bindings']==before['bindings']
    assert observation['runtime']['inventory']['files']['packages/platform_sdk/modular_platform/worker_start.py']==build['candidate_source_sha256']
    assert (control/'stages'/op/'native-skipped.json').exists() and not (control/'stages'/op/'native.log').exists()
    now=files(after);assert all(now[n]==h for n,h in load(OUTPUT/'files-before.json').items())
    replay=invoke(prefix+['plugin','apply',op]+options);assert replay==result;write('completed-replay.json',replay)
    for name,value in [('state-after',observed),('business-after',json.loads(sql(after,BUSINESS_SQL))),('schema-after',json.loads(sql(after,SCHEMA))),('configuration-after',current),('files-after',now)]:write(name+'.json',value)
    state.update(phase='worker_guard_sdk_activated',generation=18,image_id=image,worker_id=current['worker_id'],runtime_inventory_digest=observation['runtime']['inventory_digest'])
    (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('activation.json',dict(result='passed_exact_guard_sdk_activation',operation_id=op,generation=18,image_id=image,native_maintenance_skipped=True,full_business_schema_metadata_exact=True,old_files_preserved=len(load(OUTPUT/'files-before.json')),completed_replay_exact=True))
    print(json.dumps(dict(state=record['state'],operation_id=op,generation=18,image_id=image)))


if __name__=='__main__':main()
