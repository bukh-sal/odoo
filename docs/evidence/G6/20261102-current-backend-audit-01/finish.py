"""Close backend coverage against actual installed bytes, leaving UI/gate open."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import audit as d
ROOT,OUT,f,j=d.ROOT,d.OUT,d.f,d.j
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
state,native=d.current.context();assert native.config['generation']==24
assert f.load(d.MARKER)['state']=='native_guards_verified'
guards=f.load(OUT/'native-guards.json');assert guards['successful'] and guards['tests']==12
boundaries=f.load(OUT/'source-boundaries.json')

# Bind the real executable tree, not only the local checkout, to this audit.
observation=native.observer.read();runtime=observation['runtime']
assert runtime['inventory_digest']=='sha256:e9240b4fece52ade7af8c06fa6a46c0cdd888008cd6601d1faeb5c8352e55da2'
paths={r['path'] for r in boundaries['qualified_to_current']}|set(boundaries['event_paths'])
paths|={'platform_addons/mp_shell/static/src/host.js','platform_addons/mp_shell/static/src/native_interactions.js',
        'platform_addons/mp_example_notes/models.py','platform_addons/mp_core/external_authority.py',
        'platform_addons/mp_example_notes_stats/jobs.py','platform_addons/mp_example_notes_stats/services.py',
        'platform_addons/mp_example_notes_stats/models.py','platform_addons/mp_example_notes_stats/contracts.py'}
actual={}
for path in sorted(paths):
    digest=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    image_path=path.replace('platform_addons/','addons/',1)
    assert runtime['inventory']['files'][image_path]==digest,path
    actual[path]=digest

old_events=f.load(OUT.parent/'20261101-notes7-candidate-01/candidate-build.json')['source_sha256']
for path in ['platform_addons/mp_shell/static/src/host.js','platform_addons/mp_shell/static/src/native_interactions.js','platform_addons/mp_example_notes/models.py']:
    assert actual[path]==old_events[path],path

# The post-remote authorization changes supersede the old native12 bridge.
authority=f.load(OUT.parent/'20261102-installed-authority-01/qualification.json')
assert len(authority['cases'])==8 and authority['actual_remote_computed'] and authority['all8negative_case_writes_rolled_back']
matrix_paths=['platform_addons/mp_core/external_job.py','platform_addons/mp_core/external_authority.py',
              'platform_addons/mp_core/job_dispatch.py','platform_addons/mp_example_notes_stats/jobs.py',
              'platform_addons/mp_example_notes_stats/services.py','platform_addons/mp_example_notes_stats/contracts.py']
for path in matrix_paths:
    raw=subprocess.check_output(['git','show',authority['source_commit']+':'+path],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==actual[path],path

success=f.load(OUT.parent/'20261102-worker-image-success-01/qualification.json')
assert all(actual[p]==h for p,h in success['source_sha256'].items())
for path,digest in success['records'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
job03=f.load(OUT.parent/'20261102-job03-01/qualification.json')
assert job03['actual_external_counter_committed_once_without_response'] and job03['actual_native_producer_SIGKILL_exit137']
assert job03['native_status_outcome_unknown_LEASE_EXPIRED_no_result'] and job03['two_subsequent_actual_runner_passes_idle_no_external_retry']
for path,digest in job03['evidence_sha256'].items():assert hashlib.sha256((OUT.parent/'20261102-job03-01'/path).read_bytes()).hexdigest()==digest,path
drift=next(r for r in boundaries['qualified_to_current'] if r['evidence'].startswith('20261102-job03') and not r['byte_exact'])
assert drift['path']=='packages/platform_sdk/modular_platform/dispatch_lifecycle.py' and drift['changed_definitions']==['_reference']
unknown=f.load(OUT.parent/'20261102-worker-image-success-01/unknown-effect-refusal.json')
assert unknown['profile']=='r1-reference-stateless-v1' and unknown['rollback_restored_exact_native_dispatch_state'] and unknown['no_external_effect_or_job_dispatch']

adapter=ReferenceDispatchMaintenance(native);control=adapter.inspect()
assert control['control']['state']=='enabled' and control['control']['generation']==117
assert adapter.policy_for(control)['profile']=='r1-reference-stateless-v1'
assert d.base.snapshot(state,'current-backend-final-data')==f.load(d.PRIVATE/'data-before.json')
worker=d.base.worker(native,'current-backend-final-worker');assert worker==f.load(d.PRIVATE/'worker-before.json')
assert native.store.status('854da573-1cfe-4749-9580-98da27d9b20a')['state']=='completed'
assert native.store.status('5edcfc97-6477-48a4-ad2b-ba36252834fc')['state']=='revoked'

rows=[
 ('JOB-01','backend_covered',['20261101-core12-runner-01/qualification.json','20261101-core12-runner-01/source-boundaries.json','20261102-current-backend-audit-01/native-guards.json']),
 ('JOB-02','backend_covered',['20261102-current-backend-audit-01/native-guards.json','20261102-installed-authority-01/qualification.json','20261102-remote-role-01/qualification.json','20261102-remote-revision-01/qualification.json']),
 ('JOB-03','backend_covered',['20261102-job03-01/qualification.json','20261102-worker-image-success-01/unknown-effect-refusal.json']),
 ('EVT-01','backend_and_retained_host_covered',['20261101-host-events-01/qualification.json']),
 ('EVT-02','backend_and_retained_host_covered',['20261101-host-events-01/qualification.json']),
 ('EVT-03','backend_and_retained_host_covered',['20261101-host-events-01/qualification.json']),
 ('SVC-01','backend_covered',['20261102-worker-image-success-01/qualification.json']),
 ('SVC-02','backend_covered_actual_UI_pending',['20261102-notes-stats-fault-01/timeout-qualification.json','20261102-notes-stats-fault-01/crash-qualification.json','20261102-notes-stats-ui-source-01/entrypoints.json']),
 ('SVC-03','backend_covered',['20261102-worker-scope-01/qualification.json','20261102-worker-image-success-01/current-credentials.json']),
 ('SVC-04','backend_covered',['20261102-connector-lifecycle-01/qualification.json','20261102-manager-unregister-01/qualification.json','20261102-manager-reregister-02/qualification.json']),
 ('SVC-05','backend_covered',['20261102-worker-image-success-01/qualification.json'])]
records={}
for _,_,names in rows:
    for name in names:
        path=OUT.parent/name;proof=f.load(path)
        assert proof['result'].startswith('passed'),name
        records[name]=hashlib.sha256(path.read_bytes()).hexdigest()
f.save('coverage.json',dict(result='passed_current_G6_backend_coverage_audit_not_gate',utc=datetime.now(timezone.utc).isoformat(),
    git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    native_generation=24,dispatch_generation=117,image=state['image_id'],inventory=runtime['inventory_digest'],
    source_sha256=actual,event_and_host_paths_exact=len(boundaries['event_paths'])+3,current_native_guards=12,
    external_matrix_six_executable_files_byte_exact=True,successor_image_transition_sixteen_SDK_files_byte_exact=True,
    job03_only_changed_definition='_reference; current native default unknown guard covered by later installed SVC05 evidence',
    checked_record_sha256=records,coverage=[dict(acceptance=a,state=s,evidence=e) for a,s,e in rows],
    all30jobs_and_other16tables_and_current_worker_authority_preserved=True,
    remaining_G6=['SVC-02 actual UI healthy/degraded result and scope/navigation retirement proof','Final G6 review after that UI proof; no gate-G6 yet'],
    limits=['Twelve tests exercise real installed native job guards; fixture reuses an existing Bob membership within rollback only.',
            'Source equality carries forward the explicitly identified prior tests; it does not widen their scope.',
            'Browser deferred per user. No new acceptance pass, G6 gate pass, G7 start, external rollback or universal exactly-once claim.']))
f.write(d.MARKER,dict(f.load(d.MARKER),state='backend_coverage_verified'))
f.phase(state,'current_backend_coverage_verified_browser_pending');f.guard(state)
print('Current installed backend coverage verified:12native guards,14event/host paths exact,6matrix files exact,16SDK successor files exact; SVC02 UI/G6/G7 remain')
