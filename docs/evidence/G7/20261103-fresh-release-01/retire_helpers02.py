"""Retire exact terminal helpers/old managed workers; keep reusable realm/data."""
import json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import LOCAL,PRIVATE,MARKER,f,OLD,NEW,context,snapshot
state,native=context();r=f.load(MARKER);assert r['state']=='dependency_fault_restore_qualified'
before=snapshot(state,'g7-dependency-retire02-before')
operations={r['operation_id'],f.load(LOCAL/'install.json')['operation_id'],state['bootstrap_id']}
operations.update(p.name for p in (native.store.root/'dispatch-inspections').iterdir() if p.is_dir())
managed={x['container_id'] for x in f.load(PRIVATE/'restore-decision.json')['managed_workers']}
names={state['project']+'-'+name:exit for name,exit in [('seed-private-volumes',0),('core-init',0),('core-provision',0),('g7-recovery-seed01',1),('g7-recovery-seed02',1),('g7-recovery-seed03',0),('g7-recovery-attachment-read',0)]}
ids=f.command('g7-dependency-terminal02-disposable-list',['docker','ps','-aq','--filter','label=com.modular.disposable='+state['project']]).decode().split()
ids+=f.command('g7-dependency-terminal02-deployment-list',['docker','ps','-aq','--filter','label=com.modular.deployment='+state['deployment_id']]).decode().split();ids=sorted(set(ids));assert ids
rows=json.loads(f.command('g7-dependency-terminal02-inspect',['docker','inspect',*ids]));selected=[]
for row in rows:
 name=row['Name'].lstrip('/');labels=row['Config']['Labels'];operation=labels.get('com.modular.operation')
 if name in names or row['Id'] in managed or (operation in operations and name.startswith(state['project']+'-op-'+operation+'-')):
  assert row['Id']!=native.config['worker_id'] and row['Image'] in {OLD,NEW} and row['State']['Status']=='exited'
  assert row['State']['ExitCode']==names.get(name,0)
  if name in names:assert labels['com.modular.disposable']==state['project']
  else:assert labels['com.modular.deployment']==state['deployment_id']
  selected.append(row)
assert set(names)<={row['Name'].lstrip('/') for row in selected}
already_removed=[]
for ident in managed-{row['Id'] for row in selected}:
 missing=subprocess.run(['docker','inspect','--type','container',ident],capture_output=True,timeout=15);assert missing.returncode!=0 and b'no such' in missing.stderr.lower();already_removed.append(ident)
retired=[]
for index,row in enumerate(selected):
 f.command('g7-dependency-retire02-helper-'+str(index),['docker','rm',row['Id']]);retired.append(dict(id=row['Id'],name=row['Name'].lstrip('/'),image=row['Image'],exit_code=row['State']['ExitCode']))
assert snapshot(state,'g7-dependency-retire02-after')==before;f.guard(state)
f.save('retirement.json',dict(result='retired_exact_owned_terminal_helpers_and_obsolete_managed_workers',containers=retired,old_workers_already_retired_by_restore=already_removed,current_app=native.config['worker_id'],active_project=state['project'],reusable_six_volumes_two_networks_retained=True,failed_and_restored_databases_checkpoint_retained=True,images_removed=0,volumes_removed=0,networks_removed=0,working_original_configs_exact=True))
print(json.dumps(dict(result='retired_owned_helpers',containers=len(retired),images=0,volumes=0,networks=0)))
