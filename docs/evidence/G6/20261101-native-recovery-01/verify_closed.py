"""Read-only fresh-restore preservation before separate resume approval."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from lifecycle import context,j,f,MARKER,RestoreExecutor
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.deployment import DockerObserver
from modular_platform.catalog import Catalog
state,config,native=context();assert state['phase']=='native_restored_closed'
record=f.load(MARKER);operation=record['operation_id'];seed=f.load(j.LOCAL/'native-recovery-seed-01.json')
assert state['active_db']!=record['original_database'] and config['generation']==5
checkpoint=native.store.root/'checkpoints'/operation;manifest=f.load(checkpoint/'manifest.json')
directory=native.store.root/'recoveries'/operation;result=f.load(directory/'result.json')
current=DispatchMaintenance(native).inspect();assert current==result['dispatch']
assert current['control']['state']=='paused' and current['job_states']==dict(completed=1,dead_letter=2,pending=1)
assert current['tables']['mp_outbox']==manifest['dispatch_profile']['tables']['mp_outbox']
for name in ['mp_event_consumption','mp_event_consumer_state']:
    assert current['tables'][name]==manifest['dispatch_profile']['tables'][name]
recovery=RestoreExecutor(native)
failed_auth,failed_private=recovery._authority(record['original_database'])
restored_auth,restored_private=recovery._authority(state['active_db'])
assert failed_auth==restored_auth and failed_private==restored_private

def rows(raw,table):
    match=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S)
    assert match
    return match[1],sorted(l for l in match[2].splitlines() if l)

business=[]
for table in ['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary']:
    before=f.command('native-recovery-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    after=f.command('native-recovery-restored-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    a,b=rows(before,table),rows(after,table);assert a==b
    business.append(dict(table=table,rows=len(a[1]),sha256=hashlib.sha256(a[0]+b'\n'+b'\n'.join(a[1])).hexdigest(),checkpoint_data_exact=True))
query="SELECT jsonb_build_object('job',(SELECT to_jsonb(j) FROM mp_job j WHERE public_id='"+seed['job_id']+"'),'note',(SELECT jsonb_build_object('title',title,'body',body,'revision',revision,'write_uid',write_uid) FROM mp_example_note WHERE public_id='"+seed['note_id']+"'),'receipt',(SELECT jsonb_build_object('state',state,'generation',generation,'receipt_cleared',receipt IS NULL) FROM mp_event_delivery WHERE public_id='"+seed['receipt']['delivery_id']+"'),'subscription',(SELECT state FROM mp_event_subscription WHERE public_id='"+seed['subscription_id']+"'),'within_original_deadline',(SELECT deadline_at>timezone('UTC',clock_timestamp()) FROM mp_job WHERE public_id='"+seed['job_id']+"'));"
actual=json.loads(f.sql(state,'native-recovery-closed-state-01',query))
f.write(j.LOCAL/'native-recovery-closed-state-01.json',actual)
job=actual['job'];old=seed['job']
for key in ['public_id','site_id','workspace_id','actor_id','installation_id','handler','handler_version','effect_mode','idempotency_key','attempts','max_attempts','deadline_at','payload','input_digest','result']:
    assert job[key]==old[key],key
assert job['state']=='pending' and job['claim_generation']>old['claim_generation'] and job['lease_owner'] is None
assert actual['within_original_deadline'] and actual['note']['revision']==1 and actual['note']['title']=='Owned  restored  native job'
assert actual['subscription']=='closed' and actual['receipt']['receipt_cleared'] and actual['receipt']['generation']>seed['receipt']['generation'] and actual['receipt']['state']!='acknowledged'
counts=json.loads(f.sql(state,'native-recovery-closed-leases-01',"SELECT jsonb_build_array((SELECT count(*) FROM mp_event_subscription WHERE state='active'),(SELECT count(*) FROM mp_event_delivery WHERE state='leased'));"))
assert counts==[0,0]
catalog=Catalog(native.catalog_root,native.validator,readonly=True);reader=DockerObserver(config);observed=reader.state(reader.read(),catalog.snapshot())['state']
before=f.load(OUT/'before.json')
assert observed['installations']==before['installations'] and observed['bindings']==before['bindings']
status=native.store.status(operation);assert status['state']=='revoked' and status['phase']=='restore_verified' and not status['traffic_resumed']
assert not native._inspect(reader._container('edge',stopped=True))['State']['Running']
proof=dict(result='passed_closed_fresh_native_restore',operation_id=operation,generation=5,failed_database_retained=True,business_COPY_exact=business,original_actor_input_key_trace_attempts_deadline_and_result_preserved=True,job_requeued_within_original_budget=True,obsolete_claim_generation_advanced=True,obsolete_receipt_cleared_and_subscription_closed=True,current_native_authority_and_private_auth_exact=True,original_installations_and_bindings_exact=True,producer_and_consumer_history_exact=True,dispatch='paused',traffic_closed=True,requires_separate_reviewed_resume=True)
f.save('closed-preservation.json',proof);f.phase(state,'native_restored_closed_verified');f.guard(state)
print('Fresh restore verified while closed: exact business/history/authority and original job budget; separate resume still required.')
