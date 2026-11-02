"""Read-only fresh restored reference preservation, before separate resume."""
import copy,hashlib,json,sys,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from recovery import context,base,f,j,OUT,PRIVATE,MARKER,RestoreExecutor,FILE_OBSERVATION,phase
from modular_platform.plans import data_digest

state,native=context();record=f.load(MARKER);assert record['state']=='restored_closed'
operation=record['operation_id'];fresh='mp_disposable_r0_r1_restore_'+operation.replace('-','')
assert state['active_db']==fresh and state['active_db']!=record['original_database'] and native.config['generation']==19
directory=native.store.root/'recoveries'/operation;result=f.load(directory/'result.json')
checkpoint=native.store.root/'checkpoints'/operation;manifest=f.load(checkpoint/'manifest.json')
assert result['state']=='restored_verified' and result['keep_traffic_closed'] and result['configuration']==native.config
assert result['dispatch']['profile']=='r1-reference-stateless-dispatch-v1' and result['dispatch']['control']['state']=='paused'
assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
status=native.store.status(operation);assert status['state']=='revoked' and status['phase']=='restore_verified' and not status['traffic_resumed']
oldlock=copy.deepcopy(manifest['previous_release']['release_lock']);oldlock.update(generation=19,created_at=f.load(OUT/'bundle.json')['plan']['created_at'])
assert native.config['published_release']==oldlock
before=f.load(PRIVATE/'data-before.json');after=base.snapshot(state,'reference-restore-closed-data')
epoch=data_digest(oldlock);changed_jobs=0
for table,rows in before.items():
    expected=copy.deepcopy(rows);actual=after[table];assert len(expected)==len(actual),table
    if table=='mp_workspace':
        for row in expected:row['policy_generation']+=1
    elif table=='mp_job':
        byid={r['id']:r for r in actual}
        for row in expected:
            current=byid[row['id']];changed={k for k in row if row[k]!=current[k]}
            assert changed<={'release_digest','claim_generation','dispatch_generation'},changed
            if changed:
                assert current['release_digest']==epoch and current['claim_generation']==row['claim_generation']+1 and current['dispatch_generation']==result['dispatch']['control']['generation']
                row.update(**{key:current[key] for key in changed});changed_jobs+=1
    assert expected==actual,table+' outside exact security policy/new queue epoch footprint'
assert base.schema(state,'reference-restore-closed-schema')==f.load(PRIVATE/'schema-before.json')['digest']
modules=json.loads(f.sql(state,'reference-restore-closed-modules','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'))
assert modules==f.load(PRIVATE/'modules-before.json')
recovery=RestoreExecutor(native)
failed_auth,failed_private=recovery._authority(record['original_database']);restored_auth,restored_private=recovery._authority(fresh)
assert failed_auth==restored_auth and failed_private==restored_private
assert base.worker(native,'reference-restore-closed-worker')==f.load(PRIVATE/'worker-before.json')
files=json.loads(f.command('reference-restore-closed-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,fresh]))
retained={};prefix='filestore/'+record['original_database']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for member in archive:
        if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert len(retained)>=48 and all(files.get(p)==digest for p,digest in retained.items())
f.write(PRIVATE/'data-closed.json',after)
f.save('closed-preservation.json',dict(result='passed_actual_fresh_reference_restore_while_closed',operation_id=operation,configuration_generation=19,
    fresh_database_derived_from_exact_operation=True,failed_database_retained=True,checkpoint_metadata_native_schema_modules_and_all30notes_exact=True,
    all28job_outcomes_inputs_keys_attempts_deadlines_results_preserved=True,changed_job_epochs=changed_jobs,
    workspace_policy_generation_plus1_security_invalidation=True,current_native_authority_and_private_auth_exact=True,technical_credentials_revoked=True,
    source_checkpoint_feature_restored=True,all49outbox35subscriptions251deliveries_and_consumption_history_exact=True,
    old_files_preserved=len(retained),same_running_external_worker_and_independent_publication5=True,
    dispatch_profile=result['dispatch']['profile'],dispatch_generation=result['dispatch']['control']['generation'],dispatch_paused=True,actual_edge_stopped=True,
    separate_resume_required=True,limits=['No new post-checkpoint OS revocation was injected; current independent publication/key state is unchanged and is not restored from the DB.','Actual non-idempotent external uncertainty/reconciliation remains JOB03, separate from this stateless reference restore.']))
phase(record,'restored_verified');f.phase(state,'reference_restored_verified');f.guard(state)
print('Fresh reference DB19 verified while closed: checkpoint data/history/native/auth/files and independent worker preserved; separate resume required',flush=True)
