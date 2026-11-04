"""Actual checkpointed failure before mutation and independently reviewed base resume."""
import argparse,hashlib,json,sys,subprocess
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-premutation-recovery-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context as original_context,snapshot,worker,LOCAL,prefix,options,validation
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_os import protect_directory
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular_platform.contracts import validate_operations_view
from modular_platform.catalog import Catalog
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
import r1_probe
f.OUTPUT=OUT
def load(path):return json.loads(path.read_bytes())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def save(name,value):
 with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def context():return original_context('register')
def mark(record,phase):record['state']=phase;write(PRIVATE/'state.json',record)
def prepare():
 state,native=context();assert native.config['generation']==5 and not PRIVATE.exists();protect_directory(PRIVATE)
 record=dict(state='observing',configuration=load(native.target_path));write(PRIVATE/'state.json',record)
 before=snapshot(state,'premutation-current-before');assert len(before['mp_job'])==1 and before['mp_job'][0]['state']=='completed' and not before['mp_service_credential']
 write(PRIVATE/'data-before.json',before);write(PRIVATE/'worker-before.json',worker(native,'premutation-current-worker-before'))
 files=json.loads(f.command('premutation-current-files-before',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
 write(PRIVATE/'files-before.json',files);write(PRIVATE/'dispatch-before.json',ReferenceDispatchMaintenance(native).inspect())
 catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot();write(PRIVATE/'published-before.json',native.observer.state(native.observer.read(),catalog)['state'])
 fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'operator')
 body=dict(schema_version=1,operation='prepare',operation_type='suspend',plugin_id='org.example.document_stats',site_id=fixture['site_id'],workspace_ids=[fixture['workspaces']['A']['public_id']],cascade=False)
 status,value=client.request('/api/v1/operations/prepare',body,headers={'X-CSRFToken':client.csrf});assert status==200
 view=validate_operations_view(value['data']);record.update(operation_id=view['operation_id'],plan_hash=view['plan_hash']);mark(record,'prepared')
 status,value=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=record['operation_id'],plan_hash=record['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert status==200
 status,value=client.request('/api/v1/operations/bundle/'+record['operation_id']);assert status==200;bundle=value['data'];assert bundle['plan_hash']==record['plan_hash'] and bundle['plan']['backup']['required'] and len(bundle['plan']['targets'])==1
 save('bundle.json',bundle);ops=prefix()+['operations','--store',str(native.store.root)]
 save('import.json',json.loads(f.command('premutation-current-import',ops+['import-request',record['operation_id']]+validation(native))))
 review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];save('independent-review.json',review)
 native._runtime_preflight(bundle)
 f.command('premutation-current-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+validation(native))
 mark(record,'approved');f.guard(state)
 print(json.dumps(dict(result='exact_metadata_suspend_approved_fault_not_run',operation_id=record['operation_id'],configuration=5)),flush=True)
class InjectedBeforeMutation(RuntimeError):pass
def fault():
 state,native=context();record=load(PRIVATE/'state.json');assert record['state']=='approved' and load(native.target_path)==record['configuration']
 mark(record,'applying_pre_mutation_fault')
 with patch.object(native.store,'before_mutation',side_effect=InjectedBeforeMutation('Owned current release fault after checkpoint, before mutation reservation')):
  try:native.apply(record['operation_id'])
  except InjectedBeforeMutation:pass
  else:raise AssertionError('Expected checkpointed fault not reached')
 status=native.store.status(record['operation_id']);assert status['state']=='failed_before_mutation' and status['phase']=='checkpointed' and not status['mutation_started'] and not status['traffic_resumed']
 assert load(native.target_path)==record['configuration'] and snapshot(state,'premutation-current-failed-data')==load(PRIVATE/'data-before.json')
 assert worker(native,'premutation-current-failed-worker')==load(PRIVATE/'worker-before.json')
 assert not native._inspect(native.observer._container('app'))['State']['Running'] and not native._inspect(native.observer._container('edge'))['State']['Running']
 dispatch=ReferenceDispatchMaintenance(native).inspect();assert dispatch['control']['state']=='paused'
 save('fault.json',dict(result='passed_actual_current_checkpointed_failure_before_mutation',operation_id=record['operation_id'],status=status,configuration_unchanged=True,all17tables_worker_exact=True,traffic_and_dispatch_closed=True,dispatch=dispatch))
 mark(record,'failed_before_mutation_verified');f.guard(state);print(json.dumps(dict(result='fault_before_mutation_verified',phase='checkpointed',base_configuration=5)),flush=True)
def recover(action):
 state,native=context();record=load(PRIVATE/'state.json');assert load(native.target_path)==record['configuration']
 expected='failed_before_mutation_verified' if action=='prepare' else 'unchanged_resume_reviewed';assert record['state']==expected
 args=prefix()+['plugin','recover','prepare-unchanged-resume' if action=='prepare' else 'resume-unchanged',record['operation_id']]+options(native)
 if action=='resume':
  seal=load(OUT/'resume-decision.json');args+=['--decision',str(OUT/'resume-decision.json'),'--decision-hash',seal['decision_hash'],'--noninteractive']
 mark(record,'preparing_unchanged_resume' if action=='prepare' else 'resuming_unchanged')
 result=json.loads(f.command('premutation-current-'+action,args,timeout=240))
 save('resume-decision.json' if action=='prepare' else 'resume-result.json',result)
 if action=='prepare':
  assert result['decision']['operation_id']==record['operation_id'];record['decision_hash']=result['decision_hash'];mark(record,'unchanged_resume_reviewed')
 else:
  assert result['state']=='unchanged_release_resumed' and not result['database_restore'] and not result['worker_replaced'];mark(record,'resumed_needs_verification')
 f.guard(state);print(json.dumps(dict(result='unchanged_resume_reviewed' if action=='prepare' else 'unchanged_resume_completed')),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','fault','prepare-resume','resume']);args=parser.parse_args()
 if args.action in ['prepare','fault']:globals()[args.action]()
 else:recover('prepare' if args.action=='prepare-resume' else 'resume')
