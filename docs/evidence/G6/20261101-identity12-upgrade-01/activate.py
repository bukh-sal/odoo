"""Existing independent executor for the bounded earlier-gate correction."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'identity12-upgrade-01.json'
def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state);record=f.load(MARKER)
    native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,record,native
def prepare():
    state,record,native=context();assert state['phase']=='identity12_candidate_validated' and record['state']=='candidate_validated_not_staged' and native.config['generation']==6
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==7;f.save('state-before.json',before)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')];options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    record['state']='staging';f.write(MARKER,record);f.phase(state,'identity12_staging')
    staged=json.loads(f.command('identity12-stage-01',prefix+['plugin','stage-image','--image-id',record['image_id']]+options));f.save('staged-image.json',staged)
    nomination=dict(operation_type='core_upgrade',targets=[{key:row[key] for key in ['installation_id','site_id','workspace_id','plugin_id']}|dict(action='deploy') for row in before['installations']]);f.save('nomination.json',nomination)
    bundle=json.loads(f.command('identity12-plan-01',prefix+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options));f.save('bundle.json',bundle)
    assert bundle['operation_lock']['native_core_changes']==f.load(OUT/'candidate-validation.json')['native_core_changes']
    assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes'] and len(bundle['operation_lock']['targets'])==7
    operation=bundle['plan']['operation_id'];record.update(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('identity12-register-01',ops+['register','--bundle',str(OUT/'bundle.json')]+validation);f.save('independent-review.json',native.store.review(operation,native._validate()))
    f.command('identity12-approve-01',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation)
    record['state']='approved';f.write(MARKER,record);f.phase(state,'identity12_approved');f.guard(state);print('Exact identity-only core correction independently staged/reviewed/approved.')
def apply():
    state,record,native=context();assert state['phase']=='identity12_approved' and record['state']=='approved' and native.config['generation']==6
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')];record['state']='applying';f.write(MARKER,record);f.phase(state,'identity12_applying')
    result=json.loads(f.command('identity12-apply-01',prefix+['plugin','apply',record['operation_id'],'--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)],timeout=600));assert result['state']=='completed' and result['traffic_resumed']
    current=f.load(native.target_path);assert current['generation']==7 and current['image_id']==record['image_id'] and current['sites'][0]['database']==state['active_db']
    reader=DockerObserver(current);catalog=Catalog(native.catalog_root,native.validator,readonly=True);after=reader.state(reader.read(),catalog.snapshot())['state'];before=f.load(OUT/'state-before.json')
    assert before['installations']==after['installations'] and before['bindings']==after['bindings'];f.save('completed.json',result);f.save('state-after.json',after)
    state.update(image_id=current['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'identity12_completed_needs_verification');f.guard(state)
    print('Normal identity1.2 correction completed on same populated DB, generation7; no plugin/binding change.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args();globals()[args.action]()
