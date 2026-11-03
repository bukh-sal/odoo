"""Reconcile exact committed outcomes, remove owned records and fault helpers."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-request-faults-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker,LOCAL
import r1_probe,rfc8785
f.OUTPUT=OUT
def load(path):return json.loads(path.read_bytes())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
state,native=context('connector');record=load(PRIVATE/'state.json');assert record['state']=='checks_verified_cleanup_pending' and native.config['generation']==5
assert len(record['owned'])==3
before=load(PRIVATE/'data-before.json');fixture=load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture)
keys=[item['key'] for item in record['owned']];assert all(k.replace('-','').isalnum() for k in keys)
query="BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('key',key,'state',state,'result',result,'input_digest',input_digest,'actor_id',actor_id,'workspace_id',workspace_id,'service_id',service_id,'method',method) ORDER BY key) FROM mp_service_outcome WHERE key IN ("+','.join("'"+k+"'" for k in keys)+");ROLLBACK;"
outcomes=json.loads(f.sql(state,'request-fault-outcomes',query));assert len(outcomes)==3
for item in record['owned']:
 row=next(r for r in outcomes if r['key']==item['key'])
 assert row['state']=='completed' and row['result']==item['note'] and row['actor_id']==fixture['users']['alice']['principal_id'] and row['workspace_id']==fixture['workspaces']['A']['public_id']
 assert row['input_digest']==hashlib.sha256(rfc8785.dumps(item['values'])).hexdigest() and row['service_id']=='org.example.notes.documents' and row['method']=='create'
assert len({item['note']['id'] for item in record['owned']})==3
record['state']='cleaning_owned_records';write(PRIVATE/'state.json',record)
for item in record['owned']:
 item['cleanup_state']='deleting';write(PRIVATE/'state.json',record)
 result=client.call('delete',dict(note_id=item['note']['id'],expected_revision=item['note']['revision']),key='cleanup-'+item['key']);assert result['deleted']
 item['cleanup_state']='deleted';write(PRIVATE/'state.json',record)
after=snapshot(state,'request-fault-final-data');owned={item['note']['id'] for item in record['owned']}
for table,rows in before.items():
 if table=='mp_outbox':
  assert after[table][:len(rows)]==rows;new=after[table][len(rows):];assert len(new)==6 and {e['aggregate_id'] for e in new}==owned
  assert all(e['topic']=='org.example.notes.changed' and e['plugin_id']=='org.example.notes' for e in new)
  for ident in owned:assert [e['aggregate_sequence'] for e in new if e['aggregate_id']==ident]==[1,2]
 else:assert after[table]==rows,table
assert worker(native,'request-fault-final-worker')==load(PRIVATE/'worker-before.json');f.guard(state)
main=json.loads(subprocess.check_output(['docker','inspect',native.config['worker_id']]))[0]
assert main['State']['Running'] and not any(v.startswith('MP_R1_FAULT_FILE=') for v in main['Config']['Env']) and not any(m['Destination']=='/run/mp-fault' for m in main['Mounts'])
retired=[]
for name in [record['edge'],record['secondary']]:
 item=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 assert item['Config']['Labels']['com.modular.disposable']==state['project'] and item['Id']!=native.config['worker_id']
 (PRIVATE/(name+'-inspect.json')).write_text(json.dumps(item,indent=2)+'\n')
 subprocess.run(['docker','stop','--time','10',item['Id']],capture_output=True,check=True,timeout=30)
 stopped=json.loads(subprocess.check_output(['docker','inspect',item['Id']]))[0];assert not stopped['State']['Running']
 subprocess.run(['docker','rm',item['Id']],capture_output=True,check=True,timeout=20)
 gone=subprocess.run(['docker','inspect','--type','container',item['Id']],capture_output=True,timeout=20);assert gone.returncode and b'no such' in gone.stderr.lower()
 retired.append(dict(name=name,id=item['Id'],exit_code=stopped['State']['ExitCode'],removed=True))
for label in ['secondary.stdout','secondary.stderr','cancel.stdout','cancel.stderr']:
 assert (PRIVATE/label).exists()
record['state']='backend_qualified_helpers_retired';write(PRIVATE/'state.json',record)
result=dict(result='passed_current_API03_API05_request_outcomes',acceptance=['API-03','API-05'],image_id=state['image_id'],configuration_generation=5,request_results='request-results.json',durable_outcomes=outcomes,owned_records_deleted=sorted(owned),all17original_tables_exact_except_six_owned_outbox_events=True,old_notes_Canvas_jobs_authority_worker_primary_runtime_exact=True,counts={k:len(v) for k,v in after.items()},cleanup=dict(retired=retired,containers_removed=2,volumes_networks_images_created_or_removed=0,main_fault_environment_mount_absent=True),native_fault_source_sha256=hashlib.sha256((ROOT/'tests/fixtures/addons/v1/mp_r1_fault/controllers.py').read_bytes()).hexdigest(),SDK_source_sha256=hashlib.sha256((ROOT/'platform_addons/mp_shell/static/src/host.js').read_bytes()).hexdigest(),limits=['Secondary explicit operator-only native fixture profile uses exact release image plus existing non-installed fault addon; normal guarded main runtime/worker unchanged. No public arming endpoint/default activation.','Actual unchanged SDK json/callService methods and release fence run in Node against real HTTP, with manual test-session Cookie transport and server-observed postcommit trigger. This is backend/SDK cancellation qualification, not rendered browser/accessibility/ID08 proof.','Eight concurrent same-key writes, real postcommit worker exit86/lost response and actual postcommit abort each preserve one same-database outcome; not arbitrary external-effect exactly-once or rollback guarantees.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],owned_notes_removed=3,expected_outbox_events=6,containers_removed=2,worker_primary_unchanged=True)))
