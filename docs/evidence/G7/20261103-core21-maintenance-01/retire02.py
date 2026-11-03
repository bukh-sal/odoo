"""Retire only exact terminal core21 operation/test helpers; preserve images."""
import copy,hashlib,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('core21_retire_context',OUT/'activate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();record=f.load(m.MARKER);operation=record['operation_id'];http=f.load(m.j.LOCAL/'core21-HTTP-01.json');assert http['state']=='completed'
names=[http['edge'],http['secondary'],state['project']+'-core21-stale-image-refusal',state['project']+'-core21-data-addon-refusal',state['project']+'-g7-core21-canvas-paths-02',state['project']+'-g7-read-core21-installed-native-01']
ids=f.command('core21-terminal-operation-list02',['docker','ps','-aq','--filter','label=com.modular.disposable='+state['project']]).decode().split()
ids+=f.command('core21-sdk-operation-list02',['docker','ps','-aq','--filter','label=com.modular.operation='+operation]).decode().split()
ids=sorted(set(ids))
info=json.loads(f.command('core21-terminal-operation-inspect02',['docker','inspect',*ids]))
prefix=state['project']+'-op-'+operation+'-';selected=[r for r in info if r['Name'].lstrip('/') in names or r['Name'].lstrip('/').startswith(prefix)]
assert len(selected)>=13 and {r['Name'].lstrip('/') for r in selected if not r['Name'].lstrip('/').startswith(prefix)}==set(names)
retired=[]
for index,item in enumerate(selected):
 name=item['Name'].lstrip('/');expected=1 if name in names[2:4] else 0
 assert item['State']['Status']=='exited' and item['State']['ExitCode']==expected
 assert item['Id']!=native.config['worker_id']
 labels=item['Config']['Labels']
 if name.startswith(prefix):
  assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id'] and item['Image'] in {state['image_id'],f.load(OUT/'state-before.json')['image_id']}
 else:assert labels['com.modular.disposable']==state['project']
 f.command('core21-retire-'+str(index),['docker','rm',item['Id']])
 gone=subprocess.run(['docker','inspect','--type','container',item['Id']],capture_output=True,timeout=30);assert gone.returncode!=0 and b'no such' in gone.stderr.lower()
 retired.append(dict(name=name,id=item['Id'],exit_code=expected,removed=True))
before=f.load(m.PRIVATE/'data-before.json');after=m.snapshot(state,'core21-final-data');job=f.load(m.PRIVATE/'remote-job.json');fixture=f.load(m.j.LOCAL/'fixtures.json')
owned={r['public_id'] for r in http['owned_notes']};epochs=0
for table,rows in before.items():
 expected=copy.deepcopy(rows);actual=copy.deepcopy(after[table])
 if table=='mp_job':
  new=[r for r in actual if r['public_id']==job['job_id']];assert len(new)==1 and new[0]['state']=='completed' and new[0]['attempts']==1
  actual=[r for r in actual if r['public_id']!=job['job_id']];byid={r['id']:r for r in actual}
  for old in expected:
   current=byid[old['id']];changed={k for k in old if old[k]!=current[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
   if changed:
    assert current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==134 and current['release_digest']==f.load(OUT/'bundle.json')['plan']['target_release_digest']
    old.update(**{k:current[k] for k in changed});epochs+=1
 elif table=='mp_outbox':
  known={r['id'] for r in expected};new=[r for r in actual if r['id'] not in known]
  assert len(new)==6 and {r['aggregate_id'] for r in new}==owned
  for ident in owned:
   subset=[r for r in new if r['aggregate_id']==ident]
   assert [r['aggregate_sequence'] for r in subset]==[1,2,3]
   assert all(r['topic']=='org.example.notes.changed' and r['plugin_id']=='org.example.notes' for r in subset)
  actual=[r for r in actual if r['id'] in known]
 elif table=='mp_workspace':
  a=fixture['workspaces']['A']['id']
  for old in expected:
   if old['id']==a:old['policy_generation']+=4
 elif table=='mp_membership':
  member=http['original_A_membership']['id']
  for old in expected:
   if old['id']==member:
    current=next(r for r in actual if r['id']==member);assert current['write_date']>=old['write_date'];old['write_date']=current['write_date']
 assert expected==actual,table+' changed beyond exact upgrade/owned test effects'
assert m.worker(native,'core21-final-worker')==f.load(m.PRIVATE/'worker-before.json')
assert m.schema(state,'core21-final-schema')==f.load(m.PRIVATE/'schema-before.json')['digest']
files=json.loads(f.command('core21-final-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',m.FILE_OBSERVATION,state['active_db']]))
original=f.load(m.PRIVATE/'files-before.json');assert all(files.get(n)==h for n,h in original.items())
f.save('retirement.json',dict(result='retired_exact_terminal_helpers_and_verified_final_dataset',retired=retired,images_volumes_networks_removed=0,
 current_app_retained=native.config['worker_id'],current_image=state['image_id'],rollback_images_checkpoints_issuer_retained=True,
 counts={table:len(rows) for table,rows in after.items()},original_17tables_preserved_except_explicit_upgrade_and_owned_test_effects=True,
 changes=dict(old_jobs_epoch_updates=epochs,new_completed_remote_test_job=job['job_id'],two_owned_notes_created_updated_deleted=True,six_owned_outbox_events_retained=True,A_policy_generation_increment=4,A_membership_authority_restored_audit_timestamp_only=True),
 original_files_exact=len(original),schema_exact=True,independent_worker_image_key_start_mount_network_publication_exact=True,
 limits=['Current normal upgrade and bounded backend qualification, not dependency-changing fault/restore/fresh release/final security or updated worker approval.']))
record['state']='backend_regressions_verified';f.write(m.MARKER,record);f.phase(state,'core21_backend_regressions_verified');f.guard(state)
print(json.dumps(dict(result='retired_and_preserved',containers=len(retired),jobs=len(after['mp_job']),outbox=len(after['mp_outbox']),files=len(original))))
