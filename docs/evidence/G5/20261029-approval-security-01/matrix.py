"""Real CLI denial matrix against an owned live site; no DB mutation."""
from datetime import datetime,timezone
import copy,json,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-approval-security';sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.approval_validation import IndependentValidator
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperationLocks,OperatorError,protect_directory
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql

def main():
 assert not LOCAL.exists() and not (OUTPUT/'cli-matrix.json').exists(),'Inspect state before continuation; never replay setup'
 protect_directory(LOCAL);target=json.loads((ROOT/'.local/g5-httpsecurity/operator/target.json').read_text());assert target['project']=='mp-r0-r1http9669f0969d1d';(LOCAL/'target.json').write_bytes((ROOT/'.local/g5-httpsecurity/operator/target.json').read_bytes());original=ROOT/'.local/g5-lifecycle/operator/permission-upgrade';shutil.copyfile(original/'trust.json',LOCAL/'trust.json');shutil.copytree(original/'catalog',LOCAL/'catalog',copy_function=shutil.copyfile)
 catalog=Catalog(LOCAL/'catalog',configuration(LOCAL/'trust.json'),readonly=True);snapshot=catalog.snapshot();assert len(snapshot)==8;reader=DockerObserver(target);observation=reader.read();document=reader.state(observation,snapshot);before=document['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));write=lambda name,value:(OUTPUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
 for name,value in [('state-before',before),('business-before',business),('schema-before',schema)]:write(name+'.json',value)
 prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'trust.json')];options=['--deployment-config',str(LOCAL/'target.json'),'--catalog',str(LOCAL/'catalog')];control=LOCAL/'control';checks=[]
 def cli(args,ok=True,contains=None):
  r=subprocess.run(prefix+args,capture_output=True,timeout=120,cwd=ROOT)
  if (r.returncode==0)!=ok:
   (LOCAL/'unexpected.stdout').write_bytes(r.stdout);(LOCAL/'unexpected.stderr').write_bytes(r.stderr);raise AssertionError('Unexpected CLI outcome; inspect private captures before continuation')
  data=json.loads(r.stdout if ok else r.stderr)
  if contains:assert contains in data.get('message',''),data.get('message')
  return data
 def record(case,**details):
  checks.append(dict(case=case,result='passed',**details));write('cli-progress.json',dict(state='in_progress',checks=checks));print(json.dumps(dict(case=case,result='passed')),flush=True)
 def ops(args,**kwargs):return cli(['operations','--store',str(control)]+args,**kwargs)
 ops(['init-store','--deployment-config',str(LOCAL/'target.json'),'--allow-noninteractive-disposable']);store=OperatorStore(control)
 def row(op):
  with sqlite3.connect(control/'control.sqlite3') as db:return db.execute('SELECT plan_hash,bundle,approval,phase,state,mutation_started,traffic_resumed FROM operations WHERE operation_id=?',(op,)).fetchone(),db.execute('SELECT count(*) FROM events WHERE operation_id=?',(op,)).fetchone()[0]
 def prepare(case,workspace):
  installation=next(r for r in before['installations'] if r['plugin_id']=='org.example.notes_labels' and r['workspace_id']==workspace);t={k:installation[k] for k in ['installation_id','site_id','workspace_id','plugin_id']};t['action']='suspend';bundle=prepare_current_feature(document,observation['sites'],snapshot,targets=[t],operation_type='suspend',operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'));path=LOCAL/(case+'-bundle.json');path.write_text(json.dumps(bundle),encoding='utf8');ops(['register','--bundle',str(path)]+options);return bundle['plan']['operation_id'],bundle
 workspaces=sorted({r['workspace_id'] for r in before['installations']});a,ba=prepare('approved-A',workspaces[0]);b,bb=prepare('unapproved-B',workspaces[1]);approve=lambda op,bundle:ops(['approve',op,'--plan-hash',bundle['plan_hash'],'--noninteractive']+options)
 def deny(case,op,contains=None):
  old=row(op);error=cli(['plugin','apply',op,'--store',str(control)]+options,ok=False,contains=contains);assert row(op)==old and not (control/'stages'/op).exists();record(case,error_code=error['error'],message=error['message'],journal_exact=True,no_stage_or_mutation=True)
 old=row(a);error=ops(['approve',a,'--plan-hash','sha256:'+'0'*64,'--noninteractive']+options,ok=False,contains='Exact reviewed');assert row(a)==old;record('wrong_exact_hash_denied',journal_exact=True)
 approved=approve(a,ba);assert approved['state']=='approved';first=row(a);approval=json.loads(first[0][2]);assert (datetime.fromisoformat(approval['expires_at'].replace('Z','+00:00'))-datetime.fromisoformat(approval['issued_at'].replace('Z','+00:00'))).total_seconds()==900
 assert approve(a,ba)['approval_expires_at']==approved['approval_expires_at'] and row(a)==first;record('CLI_default900_exact_targets_idempotent_no_extension',operation_id=a,plan_hash=ba['plan_hash'],expires_at=approval['expires_at'])
 old=row(b);ops(['approve',b,'--plan-hash',ba['plan_hash'],'--noninteractive']+options,ok=False,contains='Exact reviewed');assert row(b)==old and row(a)==first;record('cross_operation_workspace_hash_replay_denied',both_journals_exact=True)
 deny('unapproved_other_operation_apply_denied',b,'without reconciliation')
 policy=control/'policy.json';policy_raw=policy.read_bytes()
 for label,key,value,contains in [('policy_version','policy_version',store.policy['policy_version']+1,'generation changed'),('operator_generation','authorization_generation',store.policy['authorization_generation']+1,'generation changed'),('deployment_allowlist','deployments',{},'outside the OS operator')]:
  data=json.loads(policy_raw);data[key]=value
  try:policy.write_text(json.dumps(data),encoding='utf8');deny('stale_'+label+'_apply_denied',a,contains)
  finally:policy.write_bytes(policy_raw)
 target_path=LOCAL/'target.json';target_raw=target_path.read_bytes()
 for label,change in [('worker',dict(worker_id='f'*64)),('image',dict(image_id='sha256:'+'f'*64)),('generation',dict(generation=target['generation']+1)),('site',dict(sites=[dict(site_id=str(uuid4()),database=target['sites'][0]['database'])]))]:
  changed=copy.deepcopy(target);changed.update(change)
  try:target_path.write_text(json.dumps(changed),encoding='utf8');deny('stale_'+label+'_target_apply_denied',a)
  finally:target_path.write_bytes(target_raw)
 trust_path=LOCAL/'trust.json';trust_raw=trust_path.read_bytes();trust=json.loads(trust_raw);trust['generation']+=1
 try:trust_path.write_text(json.dumps(trust),encoding='utf8');deny('changed_trust_generation_apply_denied',a)
 finally:trust_path.write_bytes(trust_raw)
 blob=catalog.path(snapshot[0]['digest']);blob_raw=blob.read_bytes()
 try:blob.write_bytes(blob_raw[:-1]+bytes([blob_raw[-1]^1]));deny('changed_exact_artifact_bytes_apply_denied',a,'digest mismatch')
 finally:blob.write_bytes(blob_raw)
 # Real wall-clock expiry under an explicit owned one-second start policy.
 policy_data=json.loads(policy_raw);policy_data['maximum_start_lifetime']=1;policy.write_text(json.dumps(policy_data),encoding='utf8');c,bc=prepare('expiry-C',workspaces[0]);expired=approve(c,bc);expiry=datetime.fromisoformat(expired['approval_expires_at'].replace('Z','+00:00'))
 while datetime.now(timezone.utc)<expiry:time.sleep(.1)
 deny('actual_wall_clock_expiry_before_start_denied',c,'Approval unavailable');assert ops(['show',c])['state']=='expired';policy.write_bytes(policy_raw)
 # Reserve with the real validator/locks; revoke before any child can launch.
 d,bd=prepare('reserved-D',workspaces[0]);approve(d,bd);validation=IndependentValidator(target,LOCAL/'catalog',configuration(LOCAL/'trust.json'))
 with OperationLocks(control/'locks',target['deployment_id'],[s['site_id'] for s in target['sites']]) as held:
  store.reserve(d,held,validation);store.advance(d,held,'staged');ops(['revoke-approval',d]);old=row(d)
  try:store.before_mutation(d,held,validation)
  except OperatorError as error:assert 'revoked' in str(error)
  else:raise AssertionError('Revoked pre-mutation approval accepted')
  assert row(d)==old and not store.status(d)['mutation_started'];record('revoked_reserved_approval_before_mutation_denied',operation_id=d,journal_exact=True,no_database_mutation=True)
 ops(['revoke-approval',a]);deny('revoked_original_apply_denied',a,'revoked');old=row(a);ops(['approve',a,'--plan-hash',ba['plan_hash'],'--noninteractive']+options,ok=False,contains='revocation is final');assert row(a)==old;record('revoked_operation_cannot_be_reapproved')
 for op in [b,c]:ops(['revoke-approval',op])
 after=reader.state(reader.read(),Catalog(LOCAL/'catalog',configuration(LOCAL/'trust.json'),readonly=True).snapshot())['state'];assert after==before and json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema
 statuses=[store.status(op) for op in [a,b,c,d]];assert all(r['state']=='revoked' and not r['mutation_started'] for r in statuses);assert all(not (control/'stages'/op).exists() for op in [a,b,c,d]);write('final-statuses.json',statuses);write('state-after.json',after)
 result=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),checks=checks,live_project=target['project'],live_generation=target['generation'],all_four_operations_revoked=True,all_journals_premutation=True,exact_state_business_schema_retained=True,limits=['Real CLI and independent validator read actual immutable image/PostgreSQL state. Only separate private control/catalog/config fixtures change.','Pre-mutation boundary uses actual store/validator/process locks directly; no metadata/native child executed.','Staleness injection affects owned operator inputs, not protected DB/deployment files. Pure digest-field/consumption/after-mutation matrices are separate source checks.'])
 write('cli-matrix.json',result);print(json.dumps(dict(result='passed',checks=len(checks),database_mutations=False,operations_retired=4)),flush=True)
if __name__=='__main__':main()
