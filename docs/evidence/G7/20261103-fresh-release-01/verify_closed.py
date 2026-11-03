"""Verify actual restored dependency baseline while ingress/dispatch remain closed."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import ROOT,LOCAL,PRIVATE,MARKER,f,OLD,context,snapshot,schema,FILE_OBSERVATION
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.catalog import Catalog
state,native=context();r=f.load(MARKER);assert r['recovery']['state']=='restored_closed'
assert native.config['image_id']==state['image_id']==OLD and native.config['generation']==4 and state['active_db']!=r['original_database']
directory=native.store.root/'recoveries'/r['operation_id'];result=f.load(directory/'result.json');dispatch=ReferenceDispatchMaintenance(native).inspect()
assert dispatch==result['dispatch'] and dispatch['control']['state']=='paused'
assert native.store.status(r['operation_id'])['state']=='revoked' and not native.store.status(r['operation_id'])['traffic_resumed']
assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
recovery=RestoreExecutor(native);source_auth,source_private=recovery._authority(r['original_database']);restored_auth,restored_private=recovery._authority(state['active_db'])
assert source_auth==restored_auth and source_private==restored_private
before=f.load(PRIVATE/'before.json');after=snapshot(state,'g7-dependency-restored-closed-data');revoked=f.load(PRIVATE/'authority-revocation.json')
changes={}
for table,rows in before.items():
 expected=copy.deepcopy(rows);actual=after[table]
 if table=='mp_membership':
  row=next(x for x in expected if x['id']==revoked['membership_id']);row['state']='revoked'
 elif table=='mp_workspace':
  for row in expected:
   current=next(x for x in actual if x['id']==row['id']);floor=revoked['after']['workspace']['policy_generation'] if row['id']==revoked['workspace_id'] else row['policy_generation']
   assert current['policy_generation']>=floor;changes[str(row['id'])]=[row['policy_generation'],current['policy_generation']];row['policy_generation']=current['policy_generation']
 elif table=='mp_job':
  assert len(expected)==len(actual)==1;changed={k for k in expected[0] if expected[0][k]!=actual[0][k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
  for key in changed:
   if key!='release_digest':assert actual[0][key]>=expected[0][key]
  expected[0].update(**{k:actual[0][k] for k in changed})
 assert expected==actual,table+' differs beyond exact authority/policy/epoch footprint'
assert schema(state,'g7-dependency-restored-closed-schema')==f.load(PRIVATE/'schema.json')['sha256']
modules=json.loads(f.sql(state,'g7-dependency-restored-closed-modules',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"));assert modules==f.load(PRIVATE/'modules.json')
runtime=native.observer.read()['runtime'];baseline=f.load(ROOT/'docs/evidence/G7/20261103-fresh-release-01/site/baseline-and-target.json')
assert runtime['inventory_digest']==baseline['baseline_inventory'] and runtime['python_lock_digest']==baseline['baseline_python_lock'] and runtime['platform_version']=='0.1.20'
files=json.loads(f.command('g7-dependency-restored-closed-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]));old=f.load(PRIVATE/'files.json');assert all(files.get(p)==h for p,h in old.items())
decision=f.load(PRIVATE/'restore-decision.json');assert state['active_db']==decision['fresh_database'] and decision['configuration']['sites'][0]['database']==r['original_database']
# Published lock is compared as data, not to its digest string.
assert decision['restored_release_lock']==native.config['published_release']
f.save('closed-preservation.json',dict(result='passed_actual_dependency_fault_fresh_restore_while_closed',operation_id=r['operation_id'],configuration_generation=4,current_image=OLD,inventory_digest=runtime['inventory_digest'],python_lock_digest=runtime['python_lock_digest'],failed_database_retained=r['original_database'],fresh_database=state['active_db'],native_modules_schema_exact=True,baseline_tables_exact_except_current_BobB_revocation_policy_job_epochs=True,policy_changes=changes,original4Notes_1Canvas_1completed_job_exact=True,current_human_authority_private_native_auth_exact=True,old_approval_revoked=True,filestore_files_retained=len(old),standalone_attachment_sha256=f.load(PRIVATE/'seed.json')['attachment_sha256'],dispatch_paused=True,ingress_closed=True,separate_resume_required=True))
r['recovery']['state']='restored_closed_verified';f.write(MARKER,r);f.phase(state,'g7_dependency_restored_closed_verified');f.guard(state)
print('Fresh old31/core20/Python lock restored; data/schema/files/current BobB revocation preserved; approval revoked; still closed',flush=True)
