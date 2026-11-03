"""Current core22 exact preservation and approved helper pin advancement."""
import copy,hashlib,json,sys,tarfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT))
import activate as m
from modular_platform.catalog import Catalog
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
from lifecycle_data_probe import SCHEMA
from modular_platform.worker_operator import WorkerPlanningReader
from modular_platform.plans import data_digest
import subprocess
f=m.f;f.OUTPUT=OUT;state,native=m.context('connector');r=f.load(m.PRIVATE/'state.json');assert r['state']=='completed_needs_verification' and native.config['generation']==5
stage=native.store.root/'stages'/r['operation_id'];checkpoint=native.store.root/'checkpoints'/r['operation_id'];bundle=f.load(OUT/'bundle.json')
fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result'];initial=fence['before']['control']['generation']
assert initial==12 and fence['after']['control']['generation']==13 and ready['control']['generation']==14 and enabled['after']['control']['generation']==15
assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
before=f.load(m.PRIVATE/'data-before.json');after=f.load(m.LOCAL/'logs/core22-data-after.stdout');updated=0
for table,oldrows in before.items():
 expected=copy.deepcopy(oldrows);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual),table
 if table=='mp_job':
  byid={x['public_id']:x for x in actual}
  for old in expected:
   new=byid[old['public_id']];changed={k for k in old if old[k]!=new[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'},changed
   if changed:assert new['release_digest']==bundle['plan']['target_release_digest'] and new['claim_generation']==old['claim_generation']+1 and new['dispatch_generation']==14;old.update({k:new[k] for k in changed});updated+=1
 assert expected==actual,table
reader=WorkerPlanningReader(native.store,native.target_path,m.LOCAL/'operator/worker-target.json');entry=reader.publisher._document()['endpoints'][0]
observed=reader.observer(entry['descriptor'],reader.publisher._key_digest(entry['descriptor']),entry['key_id']);info=json.loads(subprocess.check_output(['docker','inspect',observed['container_id']]))[0]
worker_after=dict(id=info['Id'],image=info['Image'],started=info['State']['StartedAt'],restarts=info['RestartCount'],mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],publication=data_digest(reader.publisher._document()))
assert worker_after==f.load(m.PRIVATE/'worker-before.json')
modules=f.load(m.LOCAL/'logs/core22v02-modules-after.stdout');expected=f.load(m.PRIVATE/'modules-before.json')
for row in expected:
 if row['name']=='mp_core':row['version']='19.0.0.1.22'
assert modules==expected
files=f.load(m.LOCAL/'logs/core22v02-files-after.stdout');oldfiles=f.load(m.PRIVATE/'files-before.json');retained={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
 for member in archive:
  if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained==oldfiles and all(files.get(n)==sha for n,sha in oldfiles.items())
current=native.observer.state(native.observer.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state'];baseline=f.load(OUT/'state-before.json')
assert current['installations']==baseline['installations'] and current['bindings']==baseline['bindings'] and current['endpoints']==baseline['endpoints']
f.save('state-after.json',current)
path=m.LOCAL/'operator/worker-target.json';cfg=f.load(path);previous=copy.deepcopy(cfg);assert cfg['helper_image']==baseline['image_id'];cfg['helper_image']=r['image_id'];f.write(path,cfg)
assert {k:v for k,v in previous.items() if k!='helper_image'}=={k:v for k,v in cfg.items() if k!='helper_image'} and m.worker(native,'core22v03-worker-after-helperpin')==f.load(m.PRIVATE/'worker-before.json')
f.save('preservation.json',dict(result='passed_actual_core22_fresh_realm_maintenance_preservation',operation_id=r['operation_id'],image_id=r['image_id'],inventory_digest=r['inventory_digest'],configuration_generation=5,dispatch_generation=15,table_counts={n:len(v) for n,v in after.items()},all17tables_exact_except_reviewed_terminal_job_epochs=True,terminal_job_epoch_updates=updated,native_modules_exact_except_core21_to22=True,old_files_exact=len(oldfiles),checkpoint_files_exact=True,installations_bindings_endpoints_exact=True,worker_identity_image_key_publication_exact=True,worker_helper_only_advanced_to_approved_image=True,limits=['Actual normal maintenance/preservation; installed native parser/import/CRUD and HTTP checks pending.','No fresh-install/restore/globalExpat/security/reprobuild claim.']))
r['state']='preservation_verified';f.write(m.PRIVATE/'state.json',r);f.phase(state,'core22_preservation_verified');f.guard(state);print(json.dumps(dict(result='core22_preservation_passed',configuration=5,dispatch=15,files=len(oldfiles),jobs_updated=updated)))
