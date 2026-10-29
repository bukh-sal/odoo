"""Continue after diagnosed ZIP-footer refusal; never repeat setup or passed cases."""
from datetime import datetime,timezone
import json,sqlite3,subprocess,sys,time,zipfile
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-approval-security';sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.approval_validation import IndependentValidator
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperationLocks,OperatorError
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql

def main():
 load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));write=lambda name,value:(OUTPUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');assert not (OUTPUT/'cli-matrix.json').exists();checks=load(OUTPUT/'cli-progress.json')['checks'];assert len(checks)==12;target=load(LOCAL/'target.json');control=LOCAL/'control';store=OperatorStore(control);assert store.policy['maximum_start_lifetime']==900;catalog=Catalog(LOCAL/'catalog',configuration(LOCAL/'trust.json'),readonly=True);snapshot=catalog.snapshot();assert len(snapshot)==8;assert (LOCAL/'trust.json').read_bytes()==(ROOT/'.local/g5-lifecycle/operator/permission-upgrade/trust.json').read_bytes();reader=DockerObserver(target);observation=reader.read();document=reader.state(observation,snapshot);before=load(OUTPUT/'state-before.json');assert document['state']==before
 ba=load(LOCAL/'approved-A-bundle.json');bb=load(LOCAL/'unapproved-B-bundle.json');a=ba['plan']['operation_id'];b=bb['plan']['operation_id'];assert store.status(a)['state']=='approved' and store.status(b)['state']=='awaiting_operator_approval';assert not any((control/'stages'/op).exists() for op in [a,b]);assert not (LOCAL/'expiry-C-bundle.json').exists() and not (LOCAL/'reserved-D-bundle.json').exists()
 prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'trust.json')];options=['--deployment-config',str(LOCAL/'target.json'),'--catalog',str(LOCAL/'catalog')]
 def cli(args,ok=True,contains=None):
  r=subprocess.run(prefix+args,capture_output=True,timeout=120,cwd=ROOT)
  if (r.returncode==0)!=ok:(LOCAL/'unexpected-resume.stdout').write_bytes(r.stdout);(LOCAL/'unexpected-resume.stderr').write_bytes(r.stderr);raise AssertionError('Inspect resume private outcome before continuation')
  data=json.loads(r.stdout if ok else r.stderr)
  if contains:assert contains in data.get('message',''),data.get('message')
  return data
 def ops(args,**kwargs):return cli(['operations','--store',str(control)]+args,**kwargs)
 def row(op):
  with sqlite3.connect(store.database) as db:return db.execute('SELECT plan_hash,bundle,approval,phase,state,mutation_started,traffic_resumed FROM operations WHERE operation_id=?',(op,)).fetchone(),db.execute('SELECT count(*) FROM events WHERE operation_id=?',(op,)).fetchone()[0]
 def record(case,**details):
  checks.append(dict(case=case,result='passed',**details));write('cli-progress.json',dict(state='in_progress',checks=checks));print(json.dumps(dict(case=case,result='passed')),flush=True)
 def deny(case,op,contains=None):
  old=row(op);error=cli(['plugin','apply',op,'--store',str(control)]+options,ok=False,contains=contains);assert row(op)==old and not (control/'stages'/op).exists();record(case,error_code=error['error'],message=error['message'],journal_exact=True,no_stage_or_mutation=True)
 blob=catalog.path(snapshot[0]['digest']);raw=blob.read_bytes()
 with zipfile.ZipFile(blob) as archive:entry=next(e for e in archive.infolist() if not e.is_dir());offset=entry.header_offset+30+len(entry.filename.encode('utf8'))+len(entry.extra);assert offset<len(raw)-22
 try:blob.write_bytes(raw[:offset]+bytes([raw[offset]^1])+raw[offset+1:]);deny('changed_exact_artifact_payload_bytes_apply_denied',a,'digest mismatch')
 finally:blob.write_bytes(raw)
 policy=control/'policy.json';policy_raw=policy.read_bytes();workspaces=sorted({r['workspace_id'] for r in before['installations']})
 def prepare(case):
  item=next(r for r in before['installations'] if r['plugin_id']=='org.example.notes_labels' and r['workspace_id']==workspaces[0]);t={k:item[k] for k in ['installation_id','site_id','workspace_id','plugin_id']};t['action']='suspend';bundle=prepare_current_feature(document,observation['sites'],snapshot,targets=[t],operation_type='suspend',operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'));path=LOCAL/(case+'-bundle.json');path.write_text(json.dumps(bundle),encoding='utf8');ops(['register','--bundle',str(path)]+options);return bundle['plan']['operation_id'],bundle
 approve=lambda op,bundle:ops(['approve',op,'--plan-hash',bundle['plan_hash'],'--noninteractive']+options)
 data=json.loads(policy_raw);data['maximum_start_lifetime']=1;policy.write_text(json.dumps(data),encoding='utf8');c,bc=prepare('expiry-C');expired=approve(c,bc);expiry=datetime.fromisoformat(expired['approval_expires_at'].replace('Z','+00:00'))
 while datetime.now(timezone.utc)<expiry:time.sleep(.1)
 deny('actual_wall_clock_expiry_before_start_denied',c,'Approval unavailable');assert ops(['show',c])['state']=='expired';policy.write_bytes(policy_raw)
 d,bd=prepare('reserved-D');approve(d,bd);validation=IndependentValidator(target,LOCAL/'catalog',configuration(LOCAL/'trust.json'))
 with OperationLocks(control/'locks',target['deployment_id'],[s['site_id'] for s in target['sites']]) as held:
  store.reserve(d,held,validation);store.advance(d,held,'staged');ops(['revoke-approval',d]);old=row(d)
  try:store.before_mutation(d,held,validation)
  except OperatorError as error:assert 'revoked' in str(error)
  else:raise AssertionError('Revoked pre-mutation approval accepted')
  assert row(d)==old and not store.status(d)['mutation_started'];record('revoked_reserved_approval_before_mutation_denied',operation_id=d,journal_exact=True,no_database_mutation=True)
 ops(['revoke-approval',a]);deny('revoked_original_apply_denied',a,'revoked');old=row(a);ops(['approve',a,'--plan-hash',ba['plan_hash'],'--noninteractive']+options,ok=False,contains='revocation is final');assert row(a)==old;record('revoked_operation_cannot_be_reapproved')
 for op in [b,c]:ops(['revoke-approval',op])
 after=reader.state(reader.read(),Catalog(LOCAL/'catalog',configuration(LOCAL/'trust.json'),readonly=True).snapshot())['state'];assert after==before and json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-before.json')
 statuses=[store.status(op) for op in [a,b,c,d]];assert all(s['state']=='revoked' and not s['mutation_started'] for s in statuses);write('final-statuses.json',statuses);write('state-after.json',after)
 result=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),checks=checks,live_project=target['project'],live_generation=target['generation'],all_four_operations_revoked=True,all_journals_premutation=True,exact_state_business_schema_retained=True,initial_diagnosed_attempt='attempt-archive-footer.json',limits=['Actual CLI/independent validator reads immutable image/PostgreSQL state; only separate private control/catalog/config fixtures change.','Pre-mutation revocation uses actual store/validator/process locks directly, no metadata/native child executed.','Staleness injection changes owned operator inputs, not protected DB/deployment files. Pure state-field/consumption/after-mutation cases are separate source tests.'])
 write('cli-matrix.json',result);print(json.dumps(dict(result='passed',checks=len(checks),database_mutations=False,operations_retired=4)))
if __name__=='__main__':main()
