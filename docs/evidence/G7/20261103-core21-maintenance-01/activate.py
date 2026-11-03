"""Exact populated core21 dependency maintenance; never rebuild/re-stage."""
import argparse,copy,hashlib,importlib.util,json,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('core21_prior_helpers',OUT.parent/'20261102-read-window-02/activate.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
f,j=base.f,base.j;f.OUTPUT=OUT
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular_platform.plans import data_digest
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
PRIVATE=j.LOCAL/'core21-upgrade';MARKER=j.LOCAL/'core21-upgrade-01.json'
context=base.context;snapshot=base.snapshot;schema=base.schema;worker=base.worker
IMAGE='sha256:570275717add25f201d315ebfbd71ca63882bf7f4a6a7708077ae9e18ebc1886'

def prepare():
 state,native=context();assert native.config['generation']==29 and native.config['image_id']==state['image_id']
 assert not PRIVATE.exists() and not MARKER.exists();protect_directory(PRIVATE)
 admission=f.load(OUT.parent/'20261103-core21-dependencies-image-01/candidate-admission.json')
 assert admission['image_id']==IMAGE and admission['result']=='passed_static_candidate_admission'
 record=dict(state='observing',image_id=IMAGE,inventory_digest=admission['inventory_digest'],base_generation=29)
 f.write(MARKER,record)
 catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot()
 before=native.observer.state(native.observer.read(),catalog)['state'];f.save('state-before.json',before)
 data=snapshot(state,'core21-data-before');f.write(PRIVATE/'data-before.json',data)
 assert len(data['mp_job'])==36 and all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
 assert not any(r['state']=='leased' for r in data['mp_event_delivery'])
 f.write(PRIVATE/'schema-before.json',dict(digest=schema(state,'core21-schema-before')))
 f.write(PRIVATE/'worker-before.json',worker(native,'core21-worker-before'))
 modules=json.loads(f.sql(state,'core21-modules-before',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;"));f.write(PRIVATE/'modules-before.json',modules)
 files=json.loads(f.command('core21-files-before',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]));f.write(PRIVATE/'files-before.json',files)
 staged=f.load(OUT.parent/'20261103-core21-dependencies-image-01/staged-image.json');assert staged['base_image_id']==state['image_id'] and staged['target_image_id']==IMAGE
 native_plugins={p['plugin_id'] for p in before['release_lock']['plugins'] if p['runtime']=='native'}
 targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='deploy') for r in before['installations'] if r['state']=='installed' and r['plugin_id'] in native_plugins]
 assert targets and len(targets)==len({(t['installation_id'],t['workspace_id']) for t in targets})
 f.save('nomination.json',dict(operation_type='core_upgrade',targets=targets));record.update(state='planning',native_scopes=len(targets));f.write(MARKER,record)
 bundle=json.loads(f.command('core21-plan',base.prefix()+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+base.options(native)));f.save('bundle.json',bundle)
 assert bundle['operation_lock']['native_core_changes']==admission['native_changes']
 assert bundle['operation_lock']['python_dependency_changes']==admission['python_dependency_changes']
 assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
 assert bundle['operation_lock']['bindings']==before['bindings'] and bundle['operation_lock']['endpoints']==before['endpoints']
 assert [p for p in bundle['operation_lock']['release']['plugins'] if p['runtime']=='external_service']==[p for p in before['release_lock']['plugins'] if p['runtime']=='external_service']
 record.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(MARKER,record)
 ops=base.prefix()+['operations','--store',str(native.store.root)]
 f.command('core21-register',ops+['register','--bundle',str(OUT/'bundle.json')]+base.validation(native))
 f.save('independent-review.json',native.store.review(record['operation_id'],native._validate()))
 f.command('core21-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+base.validation(native))
 record['state']='approved';f.write(MARKER,record);f.phase(state,'core21_approved');f.guard(state)
 print(json.dumps(dict(result='independently_reviewed_approved',operation_id=record['operation_id'],plan_hash=record['plan_hash'],native_scopes=len(targets),dependency_changes=len(bundle['operation_lock']['python_dependency_changes']['distributions']))))

def apply():
 state,native=context();record=f.load(MARKER);assert record['state']=='approved' and native.config['generation']==29
 record['state']='applying';f.write(MARKER,record);f.phase(state,'core21_applying')
 result=json.loads(f.command('core21-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600));f.save('completed.json',result)
 assert result['state']=='completed' and result['traffic_resumed']
 configuration=f.load(native.target_path);assert configuration['generation']==30 and configuration['image_id']==IMAGE and configuration['sites'][0]['database']==state['active_db']
 state.update(image_id=IMAGE,inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'core21_completed_needs_verification');f.guard(state)
 print('Actual core21 dependency maintenance completed; strict preservation/current regressions pending')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args();globals()[args.action]()
