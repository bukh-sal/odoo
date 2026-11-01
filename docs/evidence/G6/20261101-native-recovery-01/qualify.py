"""Bind actual native fault/recovery/runner evidence and final privacy audit."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from lifecycle import context,f,j,MARKER
from secret_scan import Scanner
state,config,native=context();assert state['phase']=='native_recovery_qualified' and config['generation']==5
operation=f.load(MARKER)['operation_id'];status=native.store.status(operation)
assert operation=='8090a1a8-13ee-42e2-9980-9369a79bd78a' and status['phase']=='restore_traffic_resumed' and status['state']=='revoked' and status['traffic_resumed']
assert f.load(j.LOCAL/'native-recovery-finish-01.json')['state']=='completed'
for name in ['closed-preservation.json','resumed-native-job.json','guarded-runner.json','resumed-HTTP.json','restore-revalidation.json','continuation-inspection.json']:
    assert f.load(OUT/name)['result'].startswith('passed')
revalidation=f.load(OUT/'restore-revalidation.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in revalidation['source_sha256'].items())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in revalidation['unchanged_source_sha256'].items())
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
query="SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'job_states',(SELECT jsonb_object_agg(state,n) FROM (SELECT state,count(*) n FROM mp_job GROUP BY state) q),'notes',(SELECT count(*) FROM mp_example_note),'outbox',(SELECT count(*) FROM mp_outbox),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'deliveries',(SELECT count(*) FROM mp_event_delivery),'consumptions',(SELECT count(*) FROM mp_event_consumption),'consumer_states',(SELECT count(*) FROM mp_event_consumer_state),'control_state',(SELECT state FROM mp_dispatch_control),'control_generation',(SELECT generation FROM mp_dispatch_control),'active_subscriptions',(SELECT count(*) FROM mp_event_subscription WHERE state='active'),'leased_deliveries',(SELECT count(*) FROM mp_event_delivery WHERE state='leased'));"
queue=json.loads(f.sql(state,'native-recovery-checkpoint-01',query))
assert queue==dict(jobs=4,job_states={'completed':2,'dead_letter':2},notes=24,outbox=34,subscriptions=32,deliveries=220,consumptions=3,consumer_states=1,control_state='enabled',control_generation=25,active_subscriptions=0,leased_deliveries=0)
assert not subprocess.check_output(['docker','ps','-q','--filter','label=com.modular.operation='+operation]).strip()
runner=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-native-recovery-real-runner-01']))[0]
assert runner['State']['ExitCode']==0 and not runner['State']['Running']
directory=native.store.root/'recoveries'/operation
assert not (directory/'dispatch-fence/fence.json').exists()
continued=f.load(j.LOCAL/'native-continuation-decision-01.json')
assert continued['continuation']['replay_database_dump'] is False and continued['continuation']['reapply_native_auth'] is False
assert len(list((directory/'continuations').iterdir()))==1
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
f.write(j.LOCAL/'native-recovery-private-findings-01.json',findings);assert not findings,'Inspect only redacted private findings'
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
source=['packages/platform_sdk/modular_platform/restore_executor.py','packages/platform_sdk/modular_platform/restore_continuation.py','packages/platform_sdk/modular_platform/dispatch_operator.py','packages/platform_sdk/modular_platform/dispatch_lifecycle.py','platform_addons/mp_core/job_dispatch.py','tests/test_restore_continuation.py']
proof=dict(result='passed_populated_native_fault_restore_and_separate_resume',utc=datetime.now(timezone.utc).isoformat(),gate='G6 partial F-01e1; not a gate pass',source_commit_before_change=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),operation_id=operation,image_unchanged=state['image_id'],inventory_digest_unchanged=state['inventory_digest'],generation_before=3,generation_after=5,failed_database=f.load(MARKER)['original_database'],restored_database=state['active_db'],queue_snapshot=queue,normal_scoped_install_proof='../20261101-carryforward-01/scoped-install-qualification.json',native_fault='Real exact approved Labels-C native child exit0, controlled host exception before metadata/traffic; original operation retired after verified restore.',restore='Fresh DB/dump/42files/currentauth overlay completed once. Retained Docker helper-name collision before restored fence; new review-specific names plus newly exact reviewed pre-fence continuation completed only remaining setup on SAME target. Separate fresh final-resume review.',closed_business_authority_budget_proof='closed-preservation.json',actual_inventoried_runner_proof='guarded-runner.json',original_actor_effect_and_obsolete_token_proof='resumed-native-job.json',native_views_and_scoped_HTTP_proof='resumed-HTTP.json',source_checks=dict(current=21,retained_unchanged=28,total_distinct=49,evidence='restore-revalidation.json'),source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source},frozen_files=94,protected_configurations=9,privacy=dict(public_files_scanned=len(paths),known_values=len(values),findings=0),rough_progress_percent=85,acceptance_counts=dict(passed=88,not_run=11,invalidated=0,failed=0,excluded_R2=5),goal_turn='progress',limits=['Physical business/producer/dedup history preserved; compatible old-release event delivery remains unqualified until actual versioned core fix.','Event lease expired during this real reviewed workflow; old receipt denial/cleared token/advanced generation/closed subscription supplement the earlier within-lease native fence test.','Fixture explicitly enqueued one new job with one-hour native scheduling policy; production120-second default and all stored deadlines/attempt budgets unchanged.','Pre-native unchanged-release recovery and normal populated new-image core/plugin upgrades remain required F-01e1.','Native-only profile refuses external/live credentials/uncertain effects pending F-01e2; managed worker/effect-ledger/credential integration and JOB03/SVC/full G6/G7 remain.','No Canvas/UI expansion, production/public deployment, global Python change or unknown data reset.'],next_action='New same-image Labels-C pre-native failure then exact reviewed unchanged-release resume on current config5/fresh DB; preserve existing rows/operations. Then distinct versioned core-only and Notes upgrades plus actual host/bus/browser/native batch/event-history fixes; external worker/effects/credentials and full R1 remain.')
f.save('qualification.json',proof);f.guard(state)
print(json.dumps(dict(result=proof['result'],generation=5,dispatch='enabled25',guarded_runner='completed_attempt2_original_user',privacy_findings=0,rough_progress=85,acceptance='88/99 unchanged')))
