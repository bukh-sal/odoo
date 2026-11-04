"""Qualify the resumed unchanged release, terminal-job fence, and replay refusal."""
import copy,hashlib,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import probe as p
from modular_platform.plans import data_digest
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='resumed_needs_verification'
assert p.load(native.target_path)==record['configuration'] and p.load(p.OUT/'resume-result.json')['state']=='unchanged_release_resumed'
seal=p.load(p.OUT/'resume-decision.json');directory=native.store.root/'unchanged-resumes'/record['operation_id']/seal['decision']['review']['review_id']
ready=p.load(directory/'dispatch-ready.json');enabled=p.load(directory/'dispatch-enable/enable.json')['result'];initial=p.load(p.PRIVATE/'dispatch-before.json')
assert initial['control']['state']=='enabled' and ready['control']['generation']==initial['control']['generation']+2
assert enabled['after']['control']['state']=='enabled' and enabled['after']['control']['generation']==initial['control']['generation']+3
assert p.ReferenceDispatchMaintenance(native).inspect()==enabled['after']
before=p.load(p.PRIVATE/'data-before.json');after=p.snapshot(state,'premutation-current-resumed-data');updated=0
for table,rows in before.items():
 expected=copy.deepcopy(rows)
 if table=='mp_job':
  byid={r['id']:r for r in after[table]}
  for old in expected:
   new=byid[old['id']];changed={k for k in old if old[k]!=new[k]};assert changed=={'claim_generation','dispatch_generation'}
   assert old['state']==new['state']=='completed' and new['claim_generation']==old['claim_generation']+1 and new['dispatch_generation']==ready['control']['generation']
   old.update({k:new[k] for k in changed});updated+=1
 assert expected==after[table],table
assert updated==1 and p.worker(native,'premutation-current-resumed-worker')==p.load(p.PRIVATE/'worker-before.json')
files=json.loads(p.f.command('premutation-current-resumed-files',['docker','exec',native.config['worker_id'],'/venv/bin/python','-c',p.FILE_OBSERVATION,state['active_db']]))
assert files==p.load(p.PRIVATE/'files-before.json')
catalog=p.Catalog(native.catalog_root,native.validator,readonly=True).snapshot()
published=native.observer.state(native.observer.read(),catalog)['state'];assert published==p.load(p.PRIVATE/'published-before.json')
fixture=p.load(p.LOCAL/'fixtures.json');p.r1_probe.r1.r0.LOCAL=p.LOCAL
for actor,scope in [('alice','A'),('bob','B')]:
 client=p.r1_probe.Client(state,fixture,actor);assert len(client.call('list',dict(limit=25),scope)['items'])==1
 views=client.native('get_views',workspace=scope,kwargs=dict(views=[[False,'list'],[False,'form']],options={}));assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
 release=client.request('/api/v1/client-release')[1]['data'];assert release['generation']==5 and release['inventory_digest']==state['inventory_digest'] and release['release_digest']==published['release_digest']
status=native.store.status(record['operation_id']);assert status['state']=='failed_before_mutation' and status['phase']=='unchanged_traffic_resumed' and status['traffic_resumed'] and not status['mutation_started']
with native.store._connect() as connection:assert connection.execute('SELECT 1 FROM revocations WHERE operation_id=?',(record['operation_id'],)).fetchone()
args=p.prefix()+['plugin','apply',record['operation_id']]+p.options(native)
replay=subprocess.run(args,capture_output=True,timeout=120)
(p.PRIVATE/'replay.stdout').write_bytes(replay.stdout);(p.PRIVATE/'replay.stderr').write_bytes(replay.stderr)
assert replay.returncode and native.store.status(record['operation_id'])==status
assert native._inspect(native.config['worker_id'])['State']['Running'] and native._inspect(state['project']+'-edge-1')['State']['Running']
assert p.snapshot(state,'premutation-current-final-data')==after;p.f.guard(state)
record['state']='qualified_unchanged_release_resumed';p.write(p.PRIVATE/'state.json',record)
p.save('qualification.json',dict(result='passed_current_MIG01_checkpointed_unchanged_release_recovery',acceptance=['MIG-01'],operation_id=record['operation_id'],image_id=state['image_id'],configuration_generation=5,base_release_exact=True,base_published_state_exact=True,old_files_exact=len(files),all17tables_exact_except_one_terminal_job_claim_dispatch_fence=True,terminal_job_epoch_updates=updated,dispatch_generations=dict(before=initial['control']['generation'],ready=ready['control']['generation'],enabled=enabled['after']['control']['generation']),terminal_outcome_payload_actor_attempts_exact=True,independent_worker_identity_image_key_publication_exact=True,main_container_image_config_exact_and_restarted=True,database_restore=False,worker_replaced=False,scoped_native_list_form_and_client_release_pass=True,wrong_resume_hash_denied=True,failed_plan_revoked_and_replay_refused=True,replay_exit_code=replay.returncode,live_execution_handle=None,limits=['Actual checkpointed failure before mutation and separately reviewed unchanged resume on current reference-worker profile. One completed job receives declared claim/dispatch fencing epochs only; no business outcome replay.','No fresh database/filestore restore or OPS02/MIG09 completion claim here. Retained checkpoint/current authority are kept for independently reviewed later recovery.','Original working host/performance realm and independent worker remain untouched; native plugins trusted, no generic remote-effect rollback claim.']))
print(json.dumps(dict(result='MIG01_current_passed',configuration=5,dispatch=enabled['after']['control']['generation'],files=len(files),replay_refused=True)))
