"""Check actual lifecycle checkpoint, retained data, trace and native HTTP path."""
import hashlib,json,re,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
import r1_probe
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular import configuration
f=j.f;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=j.LOCAL
state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='carryforward_scoped_install_completed'
result=f.load(OUT/'scoped-install-result.json');operation=result['operation_id'];target=j.LOCAL/'operator/target.json';config=f.load(target)
store=OperatorStore(j.LOCAL/'operator/control');status=store.status(operation);assert status['state']=='completed' and status['traffic_resumed'] and status['mutation_started']
stage=store.root/'stages'/operation;checkpoint=store.root/'checkpoints'/operation
manifest=f.load(checkpoint/'manifest.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result'];reconciled=f.load(stage/'dispatch-reconcile/reconcile.json')
assert manifest['dispatch_profile']==fence['after'] and manifest['dispatch_profile']['control']['state']=='paused'
assert reconciled['mutation_committed'] and reconciled['result']['resume_allowed'] and reconciled['result']['dispatch_enabled'] is False
assert enabled['before']==ready and enabled['after']['control']['state']=='enabled' and enabled['after']['control']['generation']==21
native=NativeExecutor(store,target,j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'));actual=DispatchMaintenance(native).inspect();assert actual==enabled['after']
for table in ['mp_outbox','mp_event_consumption','mp_event_consumer_state']:
    assert actual['tables'][table]==manifest['dispatch_profile']['tables'][table]

def copy_data(raw,table):
    match=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S)
    assert match,'Exact COPY data block missing; inspect private utility output, never execute it'
    return match[1],sorted(line for line in match[2].splitlines() if line)
def table_pair(table):
    old=f.command('lifecycle-C-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    new=f.command('lifecycle-C-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    return copy_data(old,table),copy_data(new,table)
business=[]
for table in ['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary']:
    old,new=table_pair(table);assert old==new
    business.append(dict(table=table,rows=len(old[1]),same_checkpoint_COPY_data=True,sha256=hashlib.sha256(old[0]+b'\n'+b'\n'.join(old[1])).hexdigest()))
old,new=table_pair('mp_job');assert old[0]==new[0]
columns=[c.strip() for c in old[0].decode().split(',')]
def records(rows):return {parts[columns.index('public_id')]:dict(zip(columns,parts)) for parts in [line.decode().split('\t') for line in rows]}
before,after=records(old[1]),records(new[1]);assert before.keys()==after.keys()
for ident,a in before.items():
    b=after[ident]
    for key in ['actor_id','workspace_id','installation_id','idempotency_key','attempts','max_attempts','deadline_at','result','state']:assert a[key]==b[key]
    # Reference envelopes contain canonical ASCII IDs/scopes, not escape-heavy
    # user content; refuse an unknown COPY encoding rather than guessing it.
    assert '\\' not in a['payload'] and '\\' not in b['payload']
    original,current=json.loads(a['payload']),json.loads(b['payload'])
    assert original['input']==current['input']
    for key in ['request_id','trace_id','credential_id','authenticated_installation_id','allowed_actions']:assert original['context'][key]==current['context'][key]
    assert {k:v for k,v in original['context']['binding'].items() if k!='generation'}=={k:v for k,v in current['context']['binding'].items() if k!='generation'}

fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture)
for workspace in ['A','B','C']:
    views=client.native('get_views',workspace=workspace,kwargs={'views':[[False,'list'],[False,'form']],'options':{'toolbar':False}});assert {'list','form'}<=set(views['views'])
note=client.call('create',dict(title='Owned lifecycle C HTTP '+uuid4().hex,body='Synthetic scoped normal-path proof'),workspace='C',key=uuid4().hex)
updated=client.call('update',dict(note_id=note['id'],expected_revision=1,title='Verified scoped normal lifecycle'),workspace='C',key=uuid4().hex);assert updated['revision']==2
client.call('update',dict(note_id=note['id'],expected_revision=1,title='Denied stale update'),workspace='C',expect=409,code='CONFLICT')
client.call('get',dict(note_id=fixture['objects']['A']['public_id']),workspace='C',expect=404,code='NOT_FOUND')
client.call('delete',dict(note_id=note['id'],expected_revision=2),workspace='C',key=uuid4().hex)
client.call('get',dict(note_id=note['id']),workspace='C',expect=404,code='NOT_FOUND')
final=DispatchMaintenance(native).inspect();assert final['control']==actual['control'] and final['tables']['mp_job']==actual['tables']['mp_job']
assert final['tables']['mp_outbox']['rows']==32 and final['tables']['mp_event_consumption']==actual['tables']['mp_event_consumption']
proof=dict(result='passed_actual_scoped_install',operation_id=operation,image_id=state['image_id'],inventory_digest=state['inventory_digest'],deployment_generation=3,dispatch_generation=21,dispatch_state='enabled',native_normal_install_with_populated_queues=True,coordinated_dispatch_checkpoint=True,classification_kept_paused_until_effects_fence=True,original_business_data_exact=business,all_three_job_IDs_input_actor_trace_attempts_outcomes_preserved=True,original29events_and_native_dedup_history_exact_before_HTTP=True,native_Odoo_list_form_workspaces=['A','B','C'],new_C_HTTP_CRUD_CAS_and_foreign_A_denial=True,only_suite_owned_new_note_deleted=True,final_dispatch=final,limits=['Same-image scoped install is not actual new-image upgrade or failure/restore qualification.','Old a337 timer/history/Note batch bugs remain until versioned core/plugin upgrades; no EVT acceptance or full G6 pass.','Three new C events retained; existing A/B business data, Canvas and native projections match the coordinated backup exactly.'])
f.save('scoped-install-qualification.json',proof);f.phase(state,'carryforward_scoped_install_qualified');f.guard(state);print('Actual populated scoped install qualified: checkpoint/business/trace exact; native views/CRUD/CAS and scope pass.')
