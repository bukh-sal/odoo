"""Bind current carry-forward/source hooks and the real populated install proof."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from secret_scan import Scanner
from modular_platform.operator_store import OperatorStore
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='carryforward_scoped_install_qualified'
first=f.load(OUT/'native-01.json');assert first['tests']==11 and not first['errors'] and first['failures']==['g6_carryforward_native.CarryForwardTests.test_api_major_change_is_held_not_adopted']
names=['native-02.json','native-03.json','native-04.json','restored-fence-01.json','enable-01.json','unknown-enable-02.json','compatible-current-01.json']
assert all(f.load(OUT/name)['successful'] and f.load(OUT/name)['tests']==1 for name in names)
for name in ['host-preview.json','host-controls.json','legacy-host-revalidation.json','scoped-install-qualification.json']:
    assert f.load(OUT/name)['result'].startswith('passed')
legacy=f.load(OUT/'legacy-host-revalidation.json');assert legacy['tests']==43
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in legacy['source_sha256'].items()),'Changed shared legacy boundary requires targeted revalidation'
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
install=f.load(OUT/'scoped-install-qualification.json');config=f.load(j.LOCAL/'operator/target.json');assert config['generation']==3 and config['image_id']==state['image_id']
status=OperatorStore(j.LOCAL/'operator/control').status(install['operation_id']);assert status['state']=='completed' and status['traffic_resumed']
assert f.load(j.LOCAL/'lifecycle-C-HTTP-verification.json')['state']=='completed'
for name in ['native-01.json',*names]:
    record=f.load(OUT/name)
    for p,h in record['source_sha256'].items():
        if p.endswith('/job_dispatch.py') or p.endswith('/durable.py'):assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
queue=json.loads(f.sql(state,'carryforward-checkpoint-state-01',"SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'job_states',(SELECT jsonb_object_agg(state,n) FROM (SELECT state,count(*) n FROM mp_job GROUP BY state) q),'notes',(SELECT count(*) FROM mp_example_note),'outbox',(SELECT count(*) FROM mp_outbox),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'deliveries',(SELECT count(*) FROM mp_event_delivery),'consumptions',(SELECT count(*) FROM mp_event_consumption),'consumer_states',(SELECT count(*) FROM mp_event_consumer_state),'control_state',(SELECT state FROM mp_dispatch_control),'control_generation',(SELECT generation FROM mp_dispatch_control),'active_subscriptions',(SELECT count(*) FROM mp_event_subscription WHERE state='active' AND expires_at>timezone('UTC',clock_timestamp())),'leased_deliveries',(SELECT count(*) FROM mp_event_delivery WHERE state='leased'));"))
assert queue==dict(jobs=3,job_states={'completed':1,'dead_letter':2},notes=23,outbox=32,subscriptions=31,deliveries=216,consumptions=3,consumer_states=1,control_state='enabled',control_generation=21,active_subscriptions=0,leased_deliveries=0)
old=ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in f.load(old/'known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
pg=['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',state['active_db'],'-v','ON_ERROR_STOP=1']
native=json.loads(subprocess.check_output(pg,input=b'SELECT jsonb_agg(password) FROM res_users WHERE password IS NOT NULL;'))
for i,value in enumerate(native):
    if len(value)>=16:values['current-native-'+str(i)]=value.encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values);names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=[ROOT/name.decode() for name in names if name and (ROOT/name.decode()).is_file()]
findings=[r for path in paths for r in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())];f.write(j.LOCAL/'carryforward-checkpoint-private-findings.json',findings);assert not findings,'Inspect redacted findings privately'
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
source=['platform_addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/dispatch_lifecycle.py','packages/platform_sdk/modular_platform/dispatch_maintenance.py','packages/platform_sdk/modular_platform/dispatch_jobs_maintenance.py','packages/platform_sdk/modular_platform/dispatch_operator.py','packages/platform_sdk/modular_platform/native_executor.py','packages/platform_sdk/modular_platform/restore_executor.py','packages/platform_sdk/modular_platform/unchanged_recovery.py','tests/test_native_dispatch_resume.py']
record=dict(result='partial_integrated_native_lifecycle_qualification',utc=datetime.now(timezone.utc).isoformat(),previous_goal_turn='progress',current_goal_turn='progress',image_unchanged=state['image_id'],inventory_unchanged=state['inventory_digest'],deployment_generation=3,actual_operation_id=install['operation_id'],actual_operation_completed=True,carry_forward_distinct_native_source_cases=13,additional_restore_enable_native_source_cases=3,positive_rechecked_after_helper_change=True,host_guarded_preview_and_stale_enable_negative_passed=True,shared_legacy_and_native_resume_orchestration_tests=43,legacy_five_cases_revalidated=True,actual_normal_install_and_backup_business_trace_scope_proof='scoped-install-qualification.json',queue_snapshot=queue,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source},frozen_files=94,protected_configurations=9,privacy=dict(public_files_scanned=len(paths),known_values=len(values),findings=0),rough_progress_percent=85,acceptance_counts=dict(passed=88,not_run=11,failed=0,invalidated=0,excluded_R2=5),limits=['New native failure/fresh-restore/separate-resume and pre-mutation unchanged resume paths are wired but not yet exercised by a real native populated fault.','Same-image scoped installation does not qualify a new-image upgrade or old a337 timer/history/batch defects; core/platform0.1.10, Notes0.2.7 and Shell1.9 remain undeployed.','No EVT/SVC/JOB03 acceptance, external runtime/effect/credential reconciliation or complete G6/G7 claim.'],next_action='Seed bounded owned native job claim and event lease; independently approve a new scoped Labels-C install and inject a post-native-commit failure once. Reconcile journal/source, then use the existing exact reviewed fresh restore and separate resume workflow. Do not replay completed Notes-C install. After native recovery, qualify separate versioned core/plugin image upgrades and actual host/bus/browser/native batch fixes, then external worker and full R1.')
f.save('checkpoint.json',record);f.guard(state);print(json.dumps(dict(result=record['result'],generation=3,dispatch='enabled21',native_source_cases=16,actual_install_completed=True,privacy_findings=0)))
