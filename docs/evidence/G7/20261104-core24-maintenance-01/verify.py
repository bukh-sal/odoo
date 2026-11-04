"""Verify the completed one-time core24 upgrade; never apply/retry it."""
import copy,hashlib,json,os,subprocess,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT));import maintain as m
from modular_platform.catalog import Catalog
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION

state=m.load(m.PRIVATE/'state.json');assert state['phase']=='completed_needs_installed_verification';native=m.context();assert native.config['generation']==5 and native.config['image_id']==state['image_id']
bundle=m.load(OUT/'bundle.json');stage=native.store.root/'stages'/state['operation_id'];checkpoint=native.store.root/'checkpoints'/state['operation_id']
status=native.store.status(state['operation_id']);assert status['state']=='completed' and status['traffic_resumed'] and status['mutation_started']
fence=m.load(stage/'dispatch-fence/fence.json')['result'];ready=m.load(stage/'dispatch-ready.json');enabled=m.load(stage/'dispatch-enable/enable.json')['result']
assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
generations=[fence['before']['control']['generation'],fence['after']['control']['generation'],ready['control']['generation'],enabled['after']['control']['generation']]
assert generations==[generations[0]+n for n in range(4)]
before=m.load(m.PRIVATE/'data-before.json');after=m.snapshot('data-after',native);updated=[]
for table,prior in before.items():
 expected=copy.deepcopy(prior);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual),table
 if table=='mp_job':
  byid={row['public_id']:row for row in actual}
  for old in expected:
   new=byid[old['public_id']];changes={k for k in old if old[k]!=new[k]};assert changes<={'release_digest','claim_generation','dispatch_generation'},changes
   if changes:
    assert old['state']==new['state']=='completed' and new['release_digest']==bundle['plan']['target_release_digest']
    assert new['claim_generation']==old['claim_generation']+1 and new['dispatch_generation']==ready['control']['generation']
    old.update({k:new[k] for k in changes});updated.append(dict(job_id=old['public_id'],changed_fields=sorted(changes)))
 assert expected==actual,table
assert m.worker(native)==m.load(m.PRIVATE/'worker-before.json')
modules=json.loads(m.call('modules-after',['docker','exec',native.config['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',native.config['sites'][0]['database'],'-c',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"]))
expected=copy.deepcopy(m.load(m.PRIVATE/'modules-before.json'))
for row in expected:
 if row['name']=='mp_core':assert row['version']=='19.0.0.1.23';row['version']='19.0.0.1.24'
 if row['name']=='mp_shell':assert row['version']=='19.0.0.1.10';row['version']='19.0.0.1.11'
assert modules==expected
files=json.loads(m.call('files-after',['docker','exec',native.config['worker_id'],'/venv/bin/python','-c',FILE_OBSERVATION,native.config['sites'][0]['database']]));oldfiles=m.load(m.PRIVATE/'files-before.json');retained={};prefix='filestore/'+native.config['sites'][0]['database']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
 for member in archive:
  if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained==oldfiles and all(files.get(name)==digest for name,digest in oldfiles.items())
catalog=Catalog(native.catalog_root,native.validator,readonly=True);observed=native.observer.read();current=native.observer.state(observed,catalog.snapshot())['state'];baseline=m.load(m.PRIVATE/'state-before.json')
assert all(current[k]==baseline[k] for k in ['installations','bindings','endpoints'])
assert observed['runtime']['inventory_digest']==state['inventory_digest']
# Align the separately owned job helper pin to the new selected app only after
# successful journal/queue/data/worker verification. Never change worker image/key.
worker_path=native.target_path.with_name('worker-target.json');worker_before=m.load(m.PRIVATE/'worker-target-before.json');worker_current=m.load(worker_path);assert worker_before==worker_current and worker_current['helper_image']==state['base_image']
worker_current['helper_image']=state['image_id'];temporary=worker_path.with_name('worker-target.core24.tmp');m.create(temporary,worker_current);os.replace(temporary,worker_path)
assert m.worker(native)==m.load(m.PRIVATE/'worker-before.json')
reference=m.load(m.REFERENCE/'state.json');assert reference['image_id']==state['base_image'];reference.update(image_id=state['image_id'],inventory_digest=state['inventory_digest'],phase='kit_reference_core24_completed_needs_UI09',updated_utc=datetime.now(timezone.utc).isoformat());temporary=m.REFERENCE/'state.core24.tmp';m.create(temporary,reference);os.replace(temporary,m.REFERENCE/'state.json')
m.create(m.PRIVATE/'data-after.json',after);m.create(m.PRIVATE/'files-after.json',files);m.create(m.PRIVATE/'observed-after.json',observed)
m.create(OUT/'preservation.json',dict(result='passed_actual_core24_shell11_maintenance_preservation',utc=datetime.now(timezone.utc).isoformat(),operation_id=state['operation_id'],plan_hash=state['plan_hash'],generation=5,image=state['image_id'],inventory=state['inventory_digest'],native_scopes=7,native_module_changes=bundle['operation_lock']['native_core_changes'],no_schema_migrations=True,dispatch_generations=generations,all17tables_exact_except_declared_completed_job_release_fences=True,completed_job_fence_changes=updated,business_counts={k:len(v) for k,v in after.items()},independent_worker_process_image_key_publication_mounts_network_exact=True,plugin_installations_features_bindings_endpoints_exact=True,all_checkpoint_files_byte_exact=len(oldfiles),all_prior_files_retained=True,worker_helper_pin_only_updated=True,actual_independent_heartbeat_during_native_maintenance=m.load(m.PRIVATE/'show-during-apply-01.stdout')['executor_observation'],limits=['One actual approved core upgrade, no apply/replay/fault/newjob. Native views/Labels/UI09/browser/HTTP and complete release closure remain.','Helper image pin update is an OS-owned configuration change; independent worker87/key/endpoint/publication/process stay exact.','Checkpoint archives and whole-table snapshots remain private; only counts/fence fields/source and status summaries are public.']))
m.phase(state,'preserved_core24_needs_HTTP_UI09');print(json.dumps(dict(result='core24_native_versions_dispatch_data_files_worker_preserved',generation=5,dispatch_generations=generations,job_fences_updated=len(updated),prior_files_preserved=len(oldfiles))))
