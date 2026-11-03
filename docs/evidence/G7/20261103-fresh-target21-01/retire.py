"""Remove exact terminal qualification helpers/obsolete apps; retain active realm."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,LOCAL,f,context,snapshot,worker
from target import NEW,OLD
from modular_platform.workers import snapshots
f.OUTPUT=OUT/'fresh-smoke';state,native=context('connector');assert f.load(LOCAL/'fresh-smoke/state.json')['state']=='qualified'
before=snapshot(state,'fresh-retire-before');identity=worker(native,'fresh-retire-worker-before')
operations={state['bootstrap_id'],f.load(LOCAL/'install.json')['operation_id']}
operations.update(f.load(LOCAL/'reference-lifecycle'/(action+'.json'))['operation_id'] for action in ('register','enable','connector'))
operations.update(p.name for p in (native.store.root/'dispatch-inspections').iterdir() if p.is_dir())
prior=f.load(LOCAL/'prior-qualification-target.json');prior_id=prior['worker_id']
apps=[x for x in snapshots(native.config) if x['container_id']!=native.config['worker_id'] and (x['image_id']==NEW or x['container_id']==prior_id)]
names={state['project']+'-core-init',state['project']+'-core-provision'}
ids=f.command('fresh-retire-deployment-list',['docker','ps','-aq','--filter','label=com.modular.deployment='+state['deployment_id']]).decode().split()
ids+=[x['container_id'] for x in apps];ids+=list(names);ids=sorted(set(ids))
rows=json.loads(f.command('fresh-retire-inspect',['docker','inspect',*ids]));selected=[]
for row in rows:
 labels=row['Config']['Labels'];name=row['Name'].lstrip('/');operation=labels.get('com.modular.operation')
 select=name in names or row['Id'] in {x['container_id'] for x in apps} or (operation in operations and name.startswith(state['project']+'-op-'+operation+'-'))
 if not select:continue
 assert row['Id'] not in {native.config['worker_id'],identity['id']} and row['State']['Status']=='exited' and row['State']['ExitCode']==0
 assert row['Image']==(OLD if row['Id']==prior_id else NEW)
 if name in names:assert labels['com.modular.disposable']==state['project']
 elif row['Id'] in {x['container_id'] for x in apps}:
  assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
  assert row['Id']==prior_id or labels['com.modular.release_operation'] in operations
 else:assert labels['com.modular.deployment']==state['deployment_id'] and labels['com.modular.operation'] in operations
 selected.append(row)
assert names<={r['Name'].lstrip('/') for r in selected} and {a['container_id'] for a in apps}<={r['Id'] for r in selected}
retired=[]
for index,row in enumerate(selected):
 f.command('fresh-retire-container-'+str(index),['docker','rm',row['Id']]);retired.append(dict(id=row['Id'],name=row['Name'].lstrip('/'),image=row['Image'],exit_code=0))
assert snapshot(state,'fresh-retire-after')==before and worker(native,'fresh-retire-worker-after')==identity;f.guard(state)
f.save('retirement.json',dict(result='retired_exact_owned_fresh_qualification_terminal_helpers_and_old_apps',containers=retired,current_app=native.config['worker_id'],current_worker=identity['id'],images_removed=0,volumes_removed=0,networks_removed=0,old_checkpoint_app_container_retired=prior_id,old_checkpoint_images_DBs_control_retained=True,current_reusable_realm_retained=True,all17fresh_tables_worker_and_protected_original_configs_exact=True))
print(json.dumps(dict(result='retired_fresh_helpers',containers=len(retired),images=0,volumes=0,networks=0)))
