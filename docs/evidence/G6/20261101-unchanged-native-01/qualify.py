"""Bind both actual unchanged recoveries, unchanged source and final audit."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from check import context,f,j,marker
from secret_scan import Scanner
state,native=context();assert state['phase']=='native_unchanged_enabled_qualified'
cases={mode:f.load(OUT/(mode+'-qualification.json')) for mode in ['paused','enabled']}
assert all(proof['result'].startswith('passed') and proof['filestore_exact_files']==42 for proof in cases.values())
assert cases['enabled']['enabled_profile_no_dispatch_mutation'] is True
for mode,proof in cases.items():
    assert f.load(marker(mode))['state']=='qualified'
    assert native.store.status(proof['operation_id'])==proof['status']
    assert not subprocess.check_output(['docker','ps','-q','--filter','label=com.modular.operation='+proof['operation_id']]).strip()
    with native.store._connect() as database:
        approval=json.loads(database.execute('SELECT approval FROM operations WHERE operation_id=?',[proof['operation_id']]).fetchone()[0])
        assert approval['state']=='revoked'
prior=f.load(ROOT/'docs/evidence/G6/20261101-native-recovery-01/qualification.json')
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in prior['source_sha256'].items())
legacy=f.load(ROOT/'docs/evidence/G6/20261101-carryforward-01/legacy-host-revalidation.json')
unchanged='packages/platform_sdk/modular_platform/unchanged_recovery.py'
assert hashlib.sha256((ROOT/unchanged).read_bytes()).hexdigest()==legacy['source_sha256'][unchanged]
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
queue=json.loads(f.sql(state,'native-unchanged-final-state-01',"SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'job_states',(SELECT jsonb_object_agg(state,n) FROM (SELECT state,count(*) n FROM mp_job GROUP BY state) q),'notes',(SELECT count(*) FROM mp_example_note),'outbox',(SELECT count(*) FROM mp_outbox),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'deliveries',(SELECT count(*) FROM mp_event_delivery),'consumptions',(SELECT count(*) FROM mp_event_consumption),'consumer_states',(SELECT count(*) FROM mp_event_consumer_state),'control_state',(SELECT state FROM mp_dispatch_control),'control_generation',(SELECT generation FROM mp_dispatch_control),'active_subscriptions',(SELECT count(*) FROM mp_event_subscription WHERE state='active'),'leased_deliveries',(SELECT count(*) FROM mp_event_delivery WHERE state='leased'));"))
assert queue==dict(jobs=4,job_states={'completed':2,'dead_letter':2},notes=24,outbox=34,subscriptions=32,deliveries=220,consumptions=3,consumer_states=1,control_state='enabled',control_generation=28,active_subscriptions=0,leased_deliveries=0)
old=ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in f.load(old/'known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
native_passwords=json.loads(subprocess.check_output(['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',state['active_db'],'-v','ON_ERROR_STOP=1'],input=b'SELECT jsonb_agg(password) FROM res_users WHERE password IS NOT NULL;'))
for i,value in enumerate(native_passwords):
    if len(value)>=16:values['current-native-'+str(i)]=value.encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=[ROOT/name.decode() for name in names if name and (ROOT/name.decode()).is_file()]
findings=[r for path in paths for r in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())]
f.write(j.LOCAL/'native-unchanged-private-findings-01.json',findings);assert not findings,'Inspect only redacted private findings'
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
proof=dict(result='passed_two_actual_pre_native_unchanged_resume_profiles',utc=datetime.now(timezone.utc).isoformat(),gate='G6 partial F-01e1; no gate pass',source_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),generation=5,image_unchanged=state['image_id'],inventory_unchanged=state['inventory_digest'],database_unchanged=state['active_db'],cases={mode:dict(operation_id=item['operation_id'],evidence=mode+'-qualification.json',mode='reconcile_paused' if mode=='paused' else 'enabled_unchanged') for mode,item in cases.items()},both_original_approvals_revoked=True,same_configuration_worker_business_42files_authority_jobs_trace_budget_and_outcome=True,paused_control_generations=[25,26,27,28],enabled_whole_dispatch_snapshot_unchanged=True,no_native_maintenance_database_restore_or_replacement=True,queue_snapshot=queue,production_source_unchanged_from_prior_qualification=True,source_sha256=prior['source_sha256']|{unchanged:legacy['source_sha256'][unchanged]},prior_source_tests_retained=dict(current_targeted=21,unchanged_retained=28,total_distinct=49,evidence='../20261101-native-recovery-01/restore-revalidation.json'),frozen_files=94,protected_configurations=9,privacy=dict(public_files_scanned=len(paths),known_values=len(values),findings=0),rough_progress_percent=86,acceptance_counts=dict(passed=88,not_run=11,invalidated=0,failed=0,excluded_R2=5),goal_turn='progress',next_build_input_inspection='core-only-input-inspection.json',limits=['Actual native new-image core/plugin upgrade and retained compatible event delivery/native-batch/browser fixes remain before F-01e1 completion.','Current old a337 image still has documented timer/history/batch defects; no EVT/ID03 acceptance from unchanged recovery.','Native-only scope still refuses external/live credentials/uncertain effects pending F-01e2; actual managed worker/effects/credential and JOB03/SVC/G7 remain required.','Readonly retained-source comparison is a build preparation result; no candidate/worktree created and no progress credit for it.','Canvas and standard native Odoo record views remain unchanged; no frontend product expansion.'],next_action='Create isolated Git worktree from current implementation HEAD, restore only12verified old Notes0.2.6 inputs from5daaf201, use existing recorded builder and require exact artifact95d74f8e reproduction; normal independently staged/approved core10 populated upgrade with a newly bounded pending original-user job, then separate Notes0.2.7 upgrade and actual event/host/bus/browser/native batch proof. Preserve all current/failed databases and old operations.')
f.save('qualification.json',proof);f.guard(state)
print(json.dumps(dict(result=proof['result'],generation=5,dispatch='enabled28',privacy_findings=0,rough_progress=86,acceptance='88/99 unchanged')))
