"""Strict populated preservation after the exact dependency maintenance."""
import copy,hashlib,importlib.util,json,tarfile
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
spec=importlib.util.spec_from_file_location('core21_activation',OUT/'activate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT
from modular_platform.catalog import Catalog
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION

state,native=m.context();record=f.load(m.MARKER)
assert record['state']=='completed_needs_verification' and native.config['generation']==30 and state['image_id']==m.IMAGE
operation=record['operation_id'];stage=native.store.root/'stages'/operation;checkpoint=native.store.root/'checkpoints'/operation
bundle=f.load(OUT/'bundle.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
initial=fence['before']['control']['generation']
assert initial==132 and fence['after']['control']['generation']==initial+1
assert ready['control']['generation']==initial+2 and enabled['after']['control']['generation']==initial+3
assert ready['external_installations']==1 and ReferenceDispatchMaintenance(native).inspect()==enabled['after']
before=f.load(m.PRIVATE/'data-before.json');after=m.snapshot(state,'core21-data-after');updated=0;closed=0
for table in m.base.TABLES:
 expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual),table
 if table=='mp_job':
  byid={r['public_id']:r for r in actual}
  for old in expected:
   current=byid[old['public_id']];changed={key for key in old if old[key]!=current[key]}
   assert changed<={'release_digest','claim_generation','dispatch_generation'},(table,old['id'],changed)
   if changed:
    assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==initial+2
    old.update(**{key:current[key] for key in changed});updated+=1
 elif table=='mp_event_subscription':
  for old in expected:
   if old['state']=='active':old['state']='closed';closed+=1
 assert expected==actual,table+' changed beyond reviewed epoch/receipt effects'
assert m.schema(state,'core21-schema-after')==f.load(m.PRIVATE/'schema-before.json')['digest']
assert m.worker(native,'core21-worker-after')==f.load(m.PRIVATE/'worker-before.json')
modules=json.loads(f.sql(state,'core21-modules-after',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;"))
expected=copy.deepcopy(f.load(m.PRIVATE/'modules-before.json'))
for row in expected:
 if row['name']=='mp_core':assert row['version']=='19.0.0.1.20';row['version']='19.0.0.1.21'
assert expected==modules
files=json.loads(f.command('core21-files-after',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
original_files=f.load(m.PRIVATE/'files-before.json');assert original_files and all(files.get(name)==digest for name,digest in original_files.items())
retained={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
 for member in archive:
  if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained==original_files and all(files.get(name)==digest for name,digest in retained.items())
current=native.observer.state(native.observer.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
baseline=f.load(OUT/'state-before.json')
assert current['installations']==baseline['installations'] and current['bindings']==baseline['bindings'] and current['endpoints']==baseline['endpoints']
assert current['release_lock']['python_lock_digest']==bundle['operation_lock']['release']['python_lock_digest']
assert current['release_lock']['python_solution']==bundle['operation_lock']['release']['python_solution']
f.save('state-after.json',current)
# Advance only the worker maintenance helper; running external image/key and
# endpoint publication stay exactly as observed before this core operation.
path=m.j.LOCAL/'operator/worker-target.json';worker_configuration=f.load(path);previous=copy.deepcopy(worker_configuration)
assert worker_configuration['helper_image']==baseline['image_id'];worker_configuration['helper_image']=state['image_id'];f.write(path,worker_configuration)
assert {k:v for k,v in previous.items() if k!='helper_image'}=={k:v for k,v in worker_configuration.items() if k!='helper_image'}
assert m.worker(native,'core21-worker-after-helperpin')==f.load(m.PRIVATE/'worker-before.json')
f.save('preservation.json',dict(result='passed_actual_populated_core21_dependency_upgrade',operation_id=operation,image_id=state['image_id'],inventory_digest=state['inventory_digest'],configuration_generation=30,dispatch_generation=initial+3,
 counts={table:len(rows) for table,rows in after.items()},schema_columns_exact=True,native_modules_exact_except_core20_to21=True,old_filestore_files_exact=len(original_files),checkpoint_files_exact=len(retained),all_17tables_preserved_except_explicit_queue_epoch_and_active_receipt_closure=True,
 old_job_outcomes_inputs_attempts_preserved=36,jobs_epoch_updated=updated,active_subscriptions_closed=closed,plugin_scopes_bindings_endpoints_unchanged=True,actual_python_lock_and_complete_solution_published=True,
 external_worker_image_start_restart_identity_mounts_network_key_publication_exact=True,worker_helper_only_moved_to_approved_image=True,
 limits=['Normal reviewed upgrade/preservation only; current native/HTTP/security regressions and dependency-changing failure/recovery/fresh release/worker rebuild remain.']))
record['state']='preservation_verified';f.write(m.MARKER,record);f.phase(state,'core21_preservation_verified');f.guard(state)
print(json.dumps(dict(result='populated_upgrade_preserved',configuration=30,dispatch=initial+3,files=len(original_files),jobs_updated=updated,subscriptions_closed=closed)))
