"""Bind completed actual evidence; no lifecycle action or new business record."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parent));import probe as p
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='ordinary_job_verified'
files=['approved.json','fault.json','closed-preservation.json','resumed-http.json','ordinary-job.json','retirement.json',
       'restore-wrong-hash.json','resume-wrong-hash.json','required-provider-preview.json']
evidence={name:p.load(p.OUT/name) for name in files}
assert all(value['result'].startswith(('passed','installed','refused')) for value in evidence.values())
assert p.load(p.PRIVATE/'ordinary-job-state.json')['state']=='verified'
status=native.store.status(record['operation_id']);assert status['state']=='revoked' and status['traffic_resumed']
assert p.snapshot(state,'native-uninstall-qualified-final-data')==p.load(p.PRIVATE/'data-final.json')
assert p.worker(native,'native-uninstall-qualified-worker')==p.load(p.PRIVATE/'worker-before.json')
result=dict(result='passed_current_native_uninstall_fresh_restore_separate_resume',acceptance=['LIFE-03','LIFE-04','OPS-02','MIG-09'],
    specification_sections=['9.3','9.4','9.5','10.5','24.4'],operation_id=record['operation_id'],plan_hash=record['plan_hash'],
    host_image=native.config['image_id'],configuration_generation=native.config['generation'],
    failed_database_retained=record['configuration']['sites'][0]['database'],fresh_database=state['active_db'],
    manager_sitewide_uninstall_scopes=2,native_uninstall_commit_and_real_column_loss=True,
    missing_destructive_ACK_refused=True,coordinated_checkpoint_and_native_dispatch_history_preserved=True,
    fresh_restore_schema_values_files_current_auth_verified=True,separate_exact_restore_and_resume_reviews=True,
    wrong_restore_and_resume_hashes_denied=True,old_sessions_and_client_pins_refused=True,revoked_plan_replay_refused=True,
    original_worker_process_image_key_publication_preserved=True,ordinary_original_actor_job_completed_after_resume=True,
    required_provider_closure_plugins=4,required_provider_closure_scopes=8,required_cascade_false_refused=True,
    current_business_counts=dict(notes=2,canvas_boards=1,canvas_revision=2,outbox=11,jobs=2,completed_jobs=2),
    private_state='qualified_native_uninstall_fresh_restore_resumed',live_execution_handle=None,evidence=files,
    limits=['Actual current disposable outbound-stateless reference profile; unknown/non-idempotent effects remain independently reconciled or closed under retained JOB03 evidence.',
            'One unrequested Notes application preview demonstrates four-plugin/eight-scope required closure; it is not imported, approved or executed.',
            'The deliberate fault occurs after native child success and before metadata/traffic. Full native-only normal uninstall/reinstall/source-removal evidence remains retained at its unchanged source boundaries.',
            'No browser/accessibility/performance, final license/advisory/provenance, release-kit or complete G7 claim.'])
p.save('qualification.json',result)
record['state']='qualified_native_uninstall_fresh_restore_resumed';p.write(p.PRIVATE/'state.json',record)
p.f.phase(state,'core23_native_recovery_qualified');p.f.guard(state)
print(json.dumps(dict(result=result['result'],acceptance=result['acceptance'],configuration=native.config['generation'])),flush=True)
