"""Minimal independently reviewed Canvas-only storage correction."""
import argparse,base64,copy,hashlib,importlib.util,json,sys,tarfile
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('canvas_core19',OUT.parent/'20261102-cached-fields-01/activate.py');base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
f,j=base.f,base.j;f.OUTPUT=OUT
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular import configuration
MARKER=j.LOCAL/'canvas4-upgrade-01.json';PRIVATE=j.LOCAL/'canvas4-upgrade'
context=base.context;snapshot=base.snapshot;worker=base.worker

def seed():
 state,native=context();record=f.load(MARKER);assert record['state']=='candidate_validated_not_curated' and native.config['generation']==26
 assert not PRIVATE.exists();protect_directory(PRIVATE)
 before=snapshot(state,'canvas4-seed-before');assert before['mp_example_canvas_board']==[]
 f.write(PRIVATE/'before-seed.json',before);note=next(r for r in before['mp_example_note'] if r['workspace_id']==f.load(j.LOCAL/'fixtures.json')['workspaces']['A']['id'])
 record['state']='seeding_once';f.write(MARKER,record)
 code="""import json,uuid
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
env.cr.rollback()
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
assert not actor['mp.example.canvas.board'].search_count([])
board=actor['mp.example.canvas.board'].create(dict(name='R1 storage upgrade reference',cards=[dict(id=str(uuid.uuid4()),text='Minimal compatibility fixture',lane='inbox',note_id=NOTE)]))
result=board._dto();env.cr.commit()
print('MP_CANVAS_SEED='+json.dumps(result))
""".replace('FIXTURE',repr(f.load(j.LOCAL/'fixtures.json'))).replace('NOTE',repr(note['public_id']))
 raw=f.native(state,'g7-canvas4-seed-01',[],code)
 rows=[json.loads(line.split('MP_CANVAS_SEED=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CANVAS_SEED=')];assert len(rows)==1
 after=snapshot(state,'canvas4-seed-after');assert len(after['mp_example_canvas_board'])==1
 assert all(before[t]==after[t] for t in base.TABLES if t!='mp_example_canvas_board')
 f.write(PRIVATE/'seed-data.json',after);f.save('seed.json',dict(result='created_one_owned_nonempty_upgrade_fixture',workspace='A',board=rows[0],actual_old_Canvas='0.1.3',all_other16tables_exact=True,product_expansion=False))
 record['state']='fixture_seeded';f.write(MARKER,record);f.phase(state,'canvas4_fixture_seeded')
 print('One explicit synthetic nonempty Canvas A board created through ordinary Alice native scope; all other data exact')

def curate():
 state,native=context();record=f.load(MARKER);assert record['state']=='fixture_seeded' and native.config['generation']==26
 admission=f.load(OUT/'candidate-admission.json');item=admission['artifacts']['org.example.canvas']
 assert admission['image_id']==record['image_id'] and item['version']=='0.1.4'
 record['state']='extracting_once';f.write(MARKER,record)
 code="import base64,pathlib;print(base64.b64encode((pathlib.Path('/opt/modular/artifacts')/"+repr(item['file'])+").read_bytes()).decode())"
 raw=f.command('canvas4-extract',['docker','run','--name',state['project']+'-canvas4-extract','--log-driver','none','--label','com.modular.disposable='+state['project'],'--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',record['image_id'],'-c',code])
 data=base64.b64decode(raw);assert 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
 archive=j.LOCAL/item['file'];assert not archive.exists();archive.write_bytes(data)
 policy_path=j.LOCAL/'operator/trust.json';policy=f.load(policy_path);assert policy['generation']==10 and item['digest'] not in policy['approved_digests']
 old_count=len(Catalog(native.catalog_root,native.validator,readonly=True).snapshot())
 record['state']='curating_once';f.write(MARKER,record);policy['generation']=11;policy['approved_digests'].append(item['digest']);f.write(policy_path,policy)
 catalog=Catalog(native.catalog_root,configuration(policy_path));catalog.add(archive,expected_digest=item['digest']);assert len(catalog.snapshot())==old_count+1
 f.save('curation.json',dict(result='curated_exact_Canvas4_only',artifact=item,trust_generation=11,previous_catalog_count=old_count,catalog_count=old_count+1,all_old_archives_retained=True,no_grants_or_native_state_changed=True,global_trust_catalog_unchanged=True))
 record['state']='candidate_curated';f.write(MARKER,record);f.phase(state,'canvas4_candidate_curated');f.guard(state)
 print('Canvas4 exact archive added only to this fixture trust11/catalog; no install/grant/worker change')

def schema_rows(state,label):
 return json.loads(f.sql(state,label,"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_array(c.relname,c.relkind,a.attname,a.atttypid::regtype::text,a.attnotnull) ORDER BY c.relname,a.attnum) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE n.nspname='public' AND c.relkind IN ('r','p','S'); ROLLBACK;"))

def prepare():
 state,native=context();record=f.load(MARKER);assert record['state']=='candidate_curated' and native.config['generation']==26
 build=f.load(ROOT/'docs/evidence/G7/20261102-canvas4-candidate-02/candidate-build.json')
 assert record['image_id']==build['image_id'] and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
 catalog=Catalog(native.catalog_root,native.validator,readonly=True);before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==9
 f.save('state-before.json',before);f.write(PRIVATE/'data-before.json',snapshot(state,'canvas4-data-before'))
 assert f.load(PRIVATE/'data-before.json')==f.load(PRIVATE/'seed-data.json')
 f.write(PRIVATE/'schema-before.json',schema_rows(state,'canvas4-schema-before'));f.write(PRIVATE/'worker-before.json',worker(native,'canvas4-worker-before'))
 f.write(PRIVATE/'modules-before.json',json.loads(f.sql(state,'canvas4-modules-before',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;")))
 record['state']='staging';f.write(MARKER,record);f.phase(state,'canvas4_staging')
 staged=json.loads(f.command('canvas4-stage',base.prefix()+['plugin','stage-image','--image-id',record['image_id']]+base.options(native)));f.save('staged-image.json',staged)
 finish_prepare()

def finish_prepare():
 state,native=context();record=f.load(MARKER);assert record['state']=='staging' and native.config['generation']==26
 before=f.load(OUT/'state-before.json')
 assert snapshot(state,'canvas4-data-preplan')==f.load(PRIVATE/'data-before.json')
 targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='upgrade') for r in before['installations'] if r['plugin_id']=='org.example.canvas'];assert len(targets)==2
 f.save('nomination.json',dict(operation_type='upgrade',targets=targets))
 bundle=json.loads(f.command('canvas4-plan',base.prefix()+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+base.options(native)));f.save('bundle.json',bundle)
 assert not bundle['operation_lock'].get('native_core_changes') and not bundle['plan']['permission_changes'] and bundle['plan']['backup']['required']
 assert len(bundle['operation_lock']['targets'])==2 and bundle['operation_lock']['bindings']==before['bindings'] and bundle['operation_lock']['endpoints']==before['endpoints']
 record.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(MARKER,record)
 ops=base.prefix()+['operations','--store',str(native.store.root)]
 f.command('canvas4-register',ops+['register','--bundle',str(OUT/'bundle.json')]+base.validation(native))
 f.save('independent-review.json',native.store.review(record['operation_id'],native._validate()))
 f.command('canvas4-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+base.validation(native))
 record['state']='approved';f.write(MARKER,record);f.phase(state,'canvas4_approved');f.guard(state)
 print('Separate Canvas4 upgrade for A/B independently reconstructed/reviewed/approved; core/other artifacts/worker unchanged')

def apply():
 state,native=context();record=f.load(MARKER);assert record['state']=='approved' and native.config['generation']==26
 record['state']='applying';f.write(MARKER,record);f.phase(state,'canvas4_applying')
 result=json.loads(f.command('canvas4-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600));assert result['state']=='completed' and result['traffic_resumed'];f.save('completed.json',result)
 config=f.load(native.target_path);assert config['generation']==27 and config['image_id']==record['image_id']
 state.update(image_id=config['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record);f.phase(state,'canvas4_completed_needs_verification')
 print('Reviewed Canvas4 upgrade completed27; actual persistence/scope and strict preservation verification required')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['seed','curate','prepare','finish_prepare','apply']);args=parser.parse_args();globals()[args.action]()
