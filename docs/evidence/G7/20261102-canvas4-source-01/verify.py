"""Verify the exact approved Canvas-only DDL and populated preservation."""
import copy,hashlib,importlib.util,json,tarfile
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('canvas4_verify',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();record=f.load(m.MARKER)
assert record['state']=='completed_needs_verification' and native.config['generation']==27
op=record['operation_id'];stage=native.store.root/'stages'/op;checkpoint=native.store.root/'checkpoints'/op
bundle=f.load(OUT/'bundle.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert fence['before']['control']['generation']==123 and fence['after']['control']['generation']==124
assert ready['control']['generation']==125 and enabled['after']['control']['generation']==126 and ready['external_installations']==1
adapter=m.ReferenceDispatchMaintenance(native);assert adapter.inspect()==enabled['after']
assert enabled['after']['job_states']==dict(completed=15,dead_letter=19,cancelled=2)
before=f.load(m.PRIVATE/'data-before.json');after=m.snapshot(state,'canvas4-data-after');admission=f.load(OUT/'candidate-admission.json')
fixture=f.load(m.j.LOCAL/'fixtures.json');changed_workspaces={fixture['workspaces'][w]['id'] for w in ['A','B']};updated_jobs=0
for table in m.base.TABLES:
 expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
 if table=='mp_job':
  byid={r['public_id']:r for r in actual}
  for old in expected:
   current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
   if changed:
    assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==125
    old.update(**{k:current[k] for k in changed});updated_jobs+=1
 elif table=='mp_workspace':
  for old in expected:
   if old['id'] in changed_workspaces:old['policy_generation']+=1
 elif table=='mp_plugin_installation':
  for old in expected:
   if old['plugin_id']=='org.example.canvas':
    current=next(r for r in actual if r['id']==old['id']);assert old['version']=='0.1.3' and current['write_date']>old['write_date']
    old.update(version='0.1.4',artifact_digest=admission['artifacts']['org.example.canvas']['digest'],write_date=current['write_date']);old['manifest']['plugin']['version']='0.1.4'
 assert expected==actual,table+' changed beyond exact reviewed plugin/queue/policy effects'
assert len(after['mp_example_canvas_board'])==1 and after['mp_example_canvas_board']==f.load(m.PRIVATE/'seed-data.json')['mp_example_canvas_board']
old_schema=f.load(m.PRIVATE/'schema-before.json');schema=m.schema_rows(state,'canvas4-schema-after');expected=copy.deepcopy(old_schema);changed=0
for row in expected:
 if row[0]=='mp_example_canvas_board' and row[2]=='cards':assert row[4] is True;row[4]=False;changed+=1
assert changed==1 and expected==schema
assert m.worker(native,'canvas4-worker-after')==f.load(m.PRIVATE/'worker-before.json')
modules=json.loads(f.sql(state,'canvas4-modules-after',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;"));expected=f.load(m.PRIVATE/'modules-before.json')
for row in expected:
 if row['name']=='mp_example_canvas':assert row['version']=='19.0.0.1.3';row['version']='19.0.0.1.4'
assert expected==modules
files=json.loads(f.command('canvas4-files-after',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',m.FILE_OBSERVATION,state['active_db']]))
retained={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
 for member in archive:
  if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained and all(files.get(p)==h for p,h in retained.items())
current=native.observer.state(native.observer.read(),m.Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state'];base=f.load(OUT/'state-before.json')
assert current['bindings']==base['bindings'] and current['endpoints']==base['endpoints'] and len(current['installations'])==len(base['installations'])
for old in base['installations']:
 actual=next(r for r in current['installations'] if (r['installation_id'],r['workspace_id'])==(old['installation_id'],old['workspace_id']))
 if old['plugin_id']!='org.example.canvas':assert old==actual
 else:
  for key in ['installation_id','site_id','workspace_id','plugin_id','state','feature_state','metadata_state']:assert old[key]==actual[key]
f.save('state-after.json',current)
helper_path=m.j.LOCAL/'operator/worker-target.json';helper=f.load(helper_path);assert helper['helper_image']==admission['base_image_id'];helper['helper_image']=state['image_id'];f.write(helper_path,helper)
assert m.worker(native,'canvas4-worker-after-helper')==f.load(m.PRIVATE/'worker-before.json')
f.save('preservation.json',dict(result='passed_actual_Canvas4_only_upgrade',operation_id=op,image=state['image_id'],inventory=state['inventory_digest'],configuration_generation=27,dispatch_generation=126,all36jobs_outcomes_inputs_attempts_retained=True,jobs_epoch_updated=updated_jobs,all30Notes_one_existing_Canvas_reference_other_business_events_credentials_bindings_endpoints_exact=True,
 reviewed_metadata_delta='Only Canvas manifest/version/digest/write_date and A/B policy generations +1; no grants or feature availability change.',only_schema_delta=['mp_example_canvas_board.cards','NOT NULL','nullable'],only_native_version_delta=['mp_example_canvas','19.0.0.1.3','19.0.0.1.4'],retained_checkpoint_files=len(retained),worker_identity_image_start_restart_network_mounts_key_publication_exact=True,helper_image_only_moved_to_approved_image=True,limits=['Upgrade/preservation only; actual empty storage/get/save and HTTP checks still required. Full G7 remains open.']))
record['state']='preservation_verified';f.write(m.MARKER,record);f.phase(state,'canvas4_preservation_verified');f.guard(state)
print('Canvas4 actual27/126 preserves existing nonempty board/all old data/worker; only reviewed Json NOTNULL removed')
