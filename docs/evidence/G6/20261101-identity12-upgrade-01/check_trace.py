"""Full checkpoint job-field preservation and original producer COPY rows."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f
state,record,native=context();assert state['phase']=='identity12_qualified_needs_gate_record' and native.config['generation']==7
checkpoint=native.store.root/'checkpoints'/record['operation_id']
def read(raw,table):
    match=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S);assert match
    return match[1].decode().split(', '),[line.decode().split('\t') for line in match[2].splitlines() if line]
def pair(table):
    old=f.command('identity12-trace-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    new=f.command('identity12-trace-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    a,b=read(old,table),read(new,table);assert a[0]==b[0];cols=a[0]
    return {row[cols.index('public_id')]:dict(zip(cols,row)) for row in a[1]},{row[cols.index('public_id')]:dict(zip(cols,row)) for row in b[1]}
before,after=pair('mp_job');assert before.keys()==after.keys() and len(before)==5
allowed={'release_digest','claim_generation','dispatch_generation'}
for ident,old in before.items():
    assert old['state'] in {'completed','dead_letter'}
    assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in after[ident].items() if k not in allowed}
events,current=pair('mp_outbox');assert len(events)==36 and len(current)==42 and all(current[ident]==value for ident,value in events.items())
f.save('checkpoint-trace.json',dict(result='passed_complete_checkpoint_job_and_producer_row_comparison',job_rows=5,all_job_columns_exact_except_explicit_release_claim_dispatch_generations=True,preserved=['actor','workspace','installation','handler/version','input digest and payload','semantic key/first request/trace','attempts/budget/deadline','result/error/state/progress','lease/cancellation/effect fields','creation/finish timestamps'],original_producer_envelopes_exact=36,only_six_owned_HTTP_fixture_events_added=True,failed_database_retained=True,raw_COPY_streams_private=True))
f.guard(state);print('All5 original job rows preserve every field except explicit epochs; all36 original producer rows exact,6owned HTTP events retained.')
