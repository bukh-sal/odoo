"""Minimal independently reviewed Notes/Labels read serialization correction."""
import argparse,base64,copy,hashlib,importlib.util,json,sys,tarfile
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('notes8_core20',OUT.parent/'20261102-read-window-02/activate.py');base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
f,j=base.f,base.j;f.OUTPUT=OUT
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular import configuration
MARKER=j.LOCAL/'notes8-labels4-upgrade-01.json';PRIVATE=j.LOCAL/'notes8-labels4-upgrade'
context=base.context;snapshot=base.snapshot;worker=base.worker

def curate():
 state,native=context();record=f.load(MARKER);assert record['state']=='candidate_validated_not_curated' and native.config['generation']==28 and not PRIVATE.exists()
 assert f.load(OUT/'notes8-candidate-readonly-native-results.json')['tests']==33
 assert f.load(OUT/'notes8-candidate-readonly-native-results.json')['successful'] and f.load(OUT/'source-tests.json')['successful']
 protect_directory(PRIVATE)
 admission=f.load(OUT/'candidate-admission.json');items=[admission['artifacts'][p] for p in ['org.example.notes','org.example.notes_labels']]
 assert admission['image_id']==record['image_id'] and [i['version'] for i in items]==['0.2.8','0.2.4']
 record['state']='extracting_once';f.write(MARKER,record)
 code="import base64,json,pathlib;root=pathlib.Path('/opt/modular/artifacts');print(json.dumps({name:base64.b64encode((root/name).read_bytes()).decode() for name in "+repr([i['file'] for i in items])+"}))"
 raw=f.command('notes8-labels4-extract',['docker','run','--name',state['project']+'-notes8-labels4-extract','--log-driver','none','--label','com.modular.disposable='+state['project'],'--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',record['image_id'],'-c',code])
 encoded=json.loads(raw);archives=[]
 for item in items:
  data=base64.b64decode(encoded[item['file']]);assert 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
  archive=j.LOCAL/item['file'];assert not archive.exists();archive.write_bytes(data);archives.append(archive)
 policy_path=j.LOCAL/'operator/trust.json';policy=f.load(policy_path);assert policy['generation']==11
 assert all(item['digest'] not in policy['approved_digests'] for item in items)
 old_count=len(Catalog(native.catalog_root,native.validator,readonly=True).snapshot());assert old_count==16
 record['state']='curating_once';f.write(MARKER,record);policy['generation']=12;policy['approved_digests'].extend(item['digest'] for item in items);f.write(policy_path,policy)
 catalog=Catalog(native.catalog_root,configuration(policy_path))
 for archive,item in zip(archives,items):catalog.add(archive,expected_digest=item['digest'])
 assert len(catalog.snapshot())==18
 f.save('curation.json',dict(result='curated_exact_Notes8_Labels4',artifacts=items,trust_generation=12,previous_catalog_count=16,catalog_count=18,all_old_archives_retained=True,no_grants_or_native_state_changed=True,global_trust_catalog_unchanged=True))
 record['state']='candidate_curated';f.write(MARKER,record);f.phase(state,'notes8-labels4_candidate_curated');f.guard(state)
 print('Notes8/Labels4 exact archives curated in fixture trust12/catalog18; no install/grant/worker change')

def schema_rows(state,label):
 return json.loads(f.sql(state,label,"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_array(c.relname,c.relkind,a.attname,a.atttypid::regtype::text,a.attnotnull) ORDER BY c.relname,a.attnum) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE n.nspname='public' AND c.relkind IN ('r','p','S'); ROLLBACK;"))

def prepare():
 state,native=context();record=f.load(MARKER);assert record['state']=='candidate_curated' and native.config['generation']==28
 build=f.load(ROOT/'docs/evidence/G7/20261102-notes8-labels4-candidate-04/candidate-build.json')
 assert record['image_id']==build['image_id'] and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
 catalog=Catalog(native.catalog_root,native.validator,readonly=True);before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==9
 f.save('state-before.json',before);f.write(PRIVATE/'data-before.json',snapshot(state,'notes8-labels4-data-before'))
 f.write(PRIVATE/'schema-before.json',schema_rows(state,'notes8-labels4-schema-before'));f.write(PRIVATE/'worker-before.json',worker(native,'notes8-labels4-worker-before'))
 f.write(PRIVATE/'modules-before.json',json.loads(f.sql(state,'notes8-labels4-modules-before',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;")))
 record['state']='staging';f.write(MARKER,record);f.phase(state,'notes8-labels4_staging')
 staged=json.loads(f.command('notes8-labels4-stage',base.prefix()+['plugin','stage-image','--image-id',record['image_id']]+base.options(native)));f.save('staged-image.json',staged)
 finish_prepare()

def finish_prepare():
 state,native=context();record=f.load(MARKER);assert record['state']=='staging' and native.config['generation']==28
 before=f.load(OUT/'state-before.json')
 assert snapshot(state,'notes8-labels4-data-preplan')==f.load(PRIVATE/'data-before.json')
 targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='upgrade') for r in before['installations'] if r['plugin_id'] in ('org.example.notes','org.example.notes_labels')];assert len(targets)==5
 f.save('nomination.json',dict(operation_type='upgrade',targets=targets))
 bundle=json.loads(f.command('notes8-labels4-plan',base.prefix()+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+base.options(native)));f.save('bundle.json',bundle)
 assert not bundle['operation_lock'].get('native_core_changes') and not bundle['plan']['permission_changes'] and bundle['plan']['backup']['required']
 assert len(bundle['operation_lock']['targets'])==5 and bundle['operation_lock']['bindings']==before['bindings'] and bundle['operation_lock']['endpoints']==before['endpoints']
 record.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(MARKER,record)
 ops=base.prefix()+['operations','--store',str(native.store.root)]
 f.command('notes8-labels4-register',ops+['register','--bundle',str(OUT/'bundle.json')]+base.validation(native))
 f.save('independent-review.json',native.store.review(record['operation_id'],native._validate()))
 f.command('notes8-labels4-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+base.validation(native))
 record['state']='approved';f.write(MARKER,record);f.phase(state,'notes8-labels4_approved');f.guard(state)
 print('Separate Notes8/Labels4 upgrade for A/B/C independently reconstructed/reviewed/approved; core/Canvas/Stats/worker unchanged')

def apply():
 state,native=context();record=f.load(MARKER);assert record['state']=='approved' and native.config['generation']==28
 record['state']='applying';f.write(MARKER,record);f.phase(state,'notes8-labels4_applying')
 result=json.loads(f.command('notes8-labels4-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600));assert result['state']=='completed' and result['traffic_resumed'];f.save('completed.json',result)
 config=f.load(native.target_path);assert config['generation']==29 and config['image_id']==record['image_id']
 state.update(image_id=config['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'notes8-labels4_completed_needs_verification')
 print('Reviewed Notes8/Labels4 upgrade completed29; actual persistence/scope and strict preservation verification required')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['curate','prepare','finish_prepare','apply']);args=parser.parse_args();globals()[args.action]()
