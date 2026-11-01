"""Exact corrective checkpoint, original failed regression and installed history."""
import hashlib,json,re,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f,MARKER
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
state,record,native=context();assert state['phase']=='identity12_HTTP_qualified' and native.config['generation']==7
operation=record['operation_id'];checkpoint=native.store.root/'checkpoints'/operation;stage=native.store.root/'stages'/operation
manifest=f.load(checkpoint/'manifest.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert manifest['dispatch_profile']==fence['after'] and fence['after']['control']['generation']==32 and ready['control']['generation']==33
assert enabled['before']==ready and enabled['after']['control']['generation']==34
current=DispatchMaintenance(native).inspect();assert current['control']==enabled['after']['control'] and current['job_states']==dict(completed=3,dead_letter=2)
for name in ['mp_job','mp_event_consumption','mp_event_consumer_state','mp_event_delivery','mp_event_subscription']:
    assert current['tables'][name]==enabled['after']['tables'][name]
args,_=native._child(operation,'fixture-files-after',network=False)
files=json.loads(f.command('identity12-files-after-01',args+['-c',FILE_OBSERVATION,state['active_db']]))
expected={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for item in archive:
        if item.isfile() and item.name.startswith(prefix):expected[item.name[len(prefix):]]=hashlib.sha256(archive.extractfile(item).read()).hexdigest()
assert len(expected)>=42 and all(files.get(name)==digest for name,digest in expected.items())
baseline=f.load(j.LOCAL/'identity12-HTTP-baseline-01.json')
def copy_rows(raw,table):
    match=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S);assert match
    return match[1],sorted(l for l in match[2].splitlines() if l)
business=[]
for table in ['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary']:
    old=f.command('identity12-checkpoint-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    new=f.command('identity12-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    a,b=copy_rows(old,table),copy_rows(new,table);assert a==b
    business.append(dict(table=table,rows=len(a[1]),checkpoint_COPY_exact=True,sha256=hashlib.sha256(a[0]+b'\n'+b'\n'.join(a[1])).hexdigest()))
# Revisit only the original read/rollback regression on the installed fix.
# The real runner/job remains terminal and is never launched again.
code='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nSEED='+repr(f.load(j.LOCAL/'core10-seed-01.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+"\nPHASE='after'\n"
source=(ROOT/'docs/evidence/G6/20261101-core10-upgrade-01/job_native.py').read_text();assert "('enabled',31)" in source
code+=source.replace("('enabled',31)","('enabled',34)",1)
raw=f.native(state,'identity12-original-job-regression-01',[],code);rows=[json.loads(l.split('MP_CORE10_JOB=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE10_JOB=')];assert len(rows)==1
f.save('original-job-regression.json',dict(**rows[0],installed_image_id=state['image_id'],dispatch_generation=34,previous_failed_probe='../20261101-core10-upgrade-01/job_native_attempt01.py',only_fixture_control_generation_assertion_adapted=True,job_runner_replayed=False))
history='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nSEED='+repr(f.load(j.LOCAL/'core10-seed-01.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'+(ROOT/'docs/evidence/G6/20261101-core10-upgrade-01/history_native.py').read_text()
raw=f.native(state,'identity12-history-01',[],history);rows=[json.loads(l.split('MP_CORE10_HISTORY=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE10_HISTORY=')];assert len(rows)==1;f.save('history.json',dict(**rows[0],image_id=state['image_id']))
f.save('preservation.json',dict(result='passed_identity12_corrective_upgrade_preservation',generation=7,operation_id=operation,dispatch_generations=[31,32,33,34],same_database=True,business_checkpoint_COPY_exact=business,all_old_filestore_hashes_retained=len(expected),all_five_terminal_jobs_first_trace_actor_input_key_budget_and_result_preserved=True,original_producer_rows_retained_and_six_HTTP_fixture_events_added=True,consumer_history_and_projection_retained=True,original_failed_pending_role_regression_now_passed=True,actual_installed_history_replay_and_consumer_dedup_passed=True,HTTP_test_helpers_stopped=True,limits=['Notes0.2.7 pending-revision native batch fix and actual host/bus/browser/current event acceptance/external work remain required.']))
record['state']='qualified_needs_gate_record';f.write(MARKER,record);f.phase(state,'identity12_qualified_needs_gate_record');f.guard(state)
print('Corrective same-DB preservation, original pending-role regression and installed event history/dedup pass; no runner replay.')
