"""Verify real new-image/native commit, then commit one current authority revocation."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import ROOT,LOCAL,PRIVATE,MARKER,f,OLD,NEW,context,snapshot,schema,FILE_OBSERVATION
state,native=context();r=f.load(MARKER);assert r['state']=='recovery_required'
child=json.loads(f.command('g7-dependency-native-child-proof',['docker','inspect',state['project']+'-op-'+r['operation_id']+'-native']))[0]
assert child['Image']==NEW and child['State']['Status']=='exited' and child['State']['ExitCode']==0
assert child['Config']['Labels']['com.modular.operation']==r['operation_id'] and child['Config']['Labels']['com.modular.deployment']==state['deployment_id']
modules=json.loads(f.sql(state,'g7-dependency-postcommit-modules',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"))
expected=copy.deepcopy(f.load(PRIVATE/'modules.json'));core=next(x for x in expected if x['name']=='mp_core');assert core['version']=='19.0.0.1.20';core['version']='19.0.0.1.21';assert modules==expected
assert schema(state,'g7-dependency-postcommit-schema')==f.load(PRIVATE/'schema.json')['sha256']
before=f.load(PRIVATE/'before.json');after=snapshot(state,'g7-dependency-postcommit-data')
for table,rows in before.items():
 expected=copy.deepcopy(rows);actual=after[table]
 if table=='mp_job':
  assert len(actual)==len(expected)==1
  changes={k for k in expected[0] if expected[0][k]!=actual[0][k]};assert changes<={'claim_generation','dispatch_generation'}
  assert actual[0]['claim_generation']>expected[0]['claim_generation'];expected[0].update(**{k:actual[0][k] for k in changes})
 assert expected==actual,table
files=json.loads(f.command('g7-dependency-postcommit-files',['docker','run','--rm','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--entrypoint','/venv/bin/python',OLD,'-c',FILE_OBSERVATION,state['active_db']]))
old=f.load(PRIVATE/'files.json');assert all(files.get(p)==h for p,h in old.items())
f.save('postcommit-proof.json',dict(result='verified_real_new570_native_core21_commit_and_paused_oldmetadata',native_child=child['Id'],actual_child_image=child['Image'],exit_code=0,native_core_version='19.0.0.1.21',metadata_configuration_generation=native.config['generation'],native_schema_exact=True,baseline_tables_exact_except_job_fence_epochs=True,old_files_retained=len(old),original_approval_not_reused=True))
fixture=f.load(LOCAL/'fixtures.json')
# Use actual joined native IDs, never infer principal IDs from user arithmetic.
query="BEGIN READ ONLY;SELECT jsonb_build_object('member',to_jsonb(m),'workspace',to_jsonb(w)) FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id JOIN mp_workspace w ON w.id=m.workspace_id WHERE p.public_id='"+fixture['users']['bob']['principal_id']+"' AND w.public_id='"+fixture['workspaces']['B']['public_id']+"';ROLLBACK;"
prior=json.loads(f.sql(state,'g7-authority-before-revoke',query));assert prior['member']['state']=='active' and prior['member']['role']=='editor'
record=dict(state='revoking',membership_id=prior['member']['id'],workspace_id=prior['workspace']['id'],before=prior);f.write(PRIVATE/'authority-revocation.json',record)
sql="BEGIN;UPDATE mp_membership SET state='revoked' WHERE id="+str(prior['member']['id'])+" AND state='active';UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id="+str(prior['workspace']['id'])+";COMMIT;"
f.sql(state,'g7-authority-commit-revoke',sql)
actual=json.loads(f.sql(state,'g7-authority-after-revoke',query));assert actual['member']==dict(prior['member'],state='revoked') and actual['workspace']==dict(prior['workspace'],policy_generation=prior['workspace']['policy_generation']+1)
record.update(state='verified',after=actual);f.write(PRIVATE/'authority-revocation.json',record)
f.save('current-authority-revocation.json',dict(result='committed_current_failed_source_human_revocation_before_restore_review',actor='bob',workspace='B',state='revoked',before_policy_generation=prior['workspace']['policy_generation'],after_policy_generation=actual['workspace']['policy_generation'],unrelated_membership_fields_exact=True,traffic_remains_closed=True,scope='Only owned qualification realm; original working deployment untouched'))
print('Real570/core21 native commit verified; current BobB revocation committed before independent restore review',flush=True)
