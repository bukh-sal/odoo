"""Source/evidence/privacy checkpoint for the incomplete native lifecycle slice."""
import ast,base64,hashlib,json,subprocess,sys,tomllib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from secret_scan import Scanner
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='dispatch_job_repeat_source_verified'
proof=f.load(OUT/'fence-02.json');commit=f.load(OUT/'drain-commit-01.json');assert proof['successful'] and proof['tests']==9 and commit['successful'] and commit['tests']==1
helper='packages/platform_sdk/modular_platform/dispatch_lifecycle.py';assert proof['helper_sha256']==commit['helper_sha256']==hashlib.sha256((ROOT/helper).read_bytes()).hexdigest()
for filename in ['history-source-02.json','job-repeat-source.json']:
    record=f.load(OUT/filename);assert record['result']=='passed'
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in record['source_sha256'].items())
host=f.load(OUT/'host-observation.json');assert host['result']=='passed_readonly_host_adapter'
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in host['source_sha256'].items())
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
assert tomllib.loads((ROOT/'plugins/notes/plugin.toml').read_text())['plugin']['version']=='0.2.7'
assert tomllib.loads((ROOT/'plugins/notes/plugin.toml').read_text())['compatibility']['platform']=='>=0.1.10,<0.2'
snapshot=json.loads(f.sql(state,'dispatch-checkpoint-state-01',"SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'events',(SELECT count(*) FROM mp_outbox),'notes',(SELECT count(*) FROM mp_example_note),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'deliveries',(SELECT count(*) FROM mp_event_delivery),'consumptions',(SELECT count(*) FROM mp_event_consumption),'consumer_states',(SELECT count(*) FROM mp_event_consumer_state),'control_state',(SELECT state FROM mp_dispatch_control),'control_generation',(SELECT generation FROM mp_dispatch_control),'active_subscriptions',(SELECT count(*) FROM mp_event_subscription WHERE state='active' AND expires_at>timezone('UTC',clock_timestamp())),'leased_deliveries',(SELECT count(*) FROM mp_event_delivery WHERE state='leased'));"))
assert snapshot==dict(jobs=3,events=29,notes=23,subscriptions=31,deliveries=216,consumptions=3,consumer_states=1,control_state='paused',control_generation=18,active_subscriptions=0,leased_deliveries=0)
labels=['dispatch-counterexamples-01','dispatch-fence-01','dispatch-drain-concurrency-01','dispatch-drain-reconcile-01','dispatch-history-source-01','dispatch-fence-02','dispatch-drain-commit-01','dispatch-history-source-02','dispatch-job-repeat-counterexample-01','dispatch-job-repeat-source-01','op-'+host['operation_id']+'-dispatch-observe']
children=[]
for label in labels:
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-'+label]))[0]
    assert not child['State']['Running'] and child['HostConfig']['LogConfig']['Type']=='none' and child['HostConfig']['ReadonlyRootfs']
    children.append(dict(name=child['Name'],exit_code=child['State']['ExitCode']))
old=ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in f.load(old/'known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
pg=['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',state['active_db'],'-v','ON_ERROR_STOP=1']
native=json.loads(subprocess.check_output(pg,input=b'SELECT jsonb_agg(password) FROM res_users WHERE password IS NOT NULL;'))
for index,value in enumerate(native):
    if len(value)>=16:values['native-current-'+str(index)]=value.encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0');paths=[ROOT/n.decode() for n in names if n and (ROOT/n.decode()).is_file()]
findings=[finding for path in paths for finding in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())];f.write(j.LOCAL/'dispatch-checkpoint-private-findings.json',findings);assert not findings,'Inspect redacted private findings'
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
source=[helper,'packages/platform_sdk/modular_platform/dispatch_maintenance.py','packages/platform_sdk/modular_platform/dispatch_operator.py','packages/platform_sdk/modular_platform/durable.py','packages/platform_sdk/modular_platform/event_store.py','packages/platform_sdk/modular_platform/projection.py','platform_addons/mp_core/job_dispatch.py','platform_addons/mp_core/events.py','platform_addons/mp_core/__manifest__.py','platform_addons/mp_example_notes/models.py','platform_addons/mp_example_notes/__manifest__.py','plugins/notes/plugin.toml']
result=dict(result='partial_native_lifecycle_qualification',utc=datetime.now(timezone.utc).isoformat(),previous_goal_turn='progress',current_goal_turn='progress',image_unchanged=state['image_id'],inventory_unchanged=state['inventory_digest'],native_fence_cases=10,corrected_job_retry_scenarios=5,corrected_history_and_paused_close_source=True,readonly_OS_host_adapter=True,source_Platform_version='0.1.10',source_Notes_version='0.2.7',source_Shell_version='19.0.0.1.9',new_image_built=False,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source},planning_cli_checks=dict(passed=5,observed_tool_chunk='5a5256',command=['.venv/Scripts/python.exe','-X','utf8','-m','unittest','discover','-s','tests','-p','test_planning_cli.py']),queue_snapshot=snapshot,children=children,privacy=dict(public_files_scanned=len(paths),known_values=len(values),findings=0),frozen_files=94,protected_configurations=9,rough_progress_percent=84,acceptance_counts=dict(passed=88,not_run=11,failed=0,invalidated=0,excluded_R2=5),limits=['Helpers/source tests are not a working independently reviewed upgrade/restore/resume path; current refusals unchanged.','Pending Note revision source fix still needs versioned immutable native upgrade and batch qualification.','No external effects/credentials reconciliation, complete EVT qualification or G6/G7 pass claimed.','Other prior sites/configurations left untouched; no new full live-data audit.'],next_action='Implement current-authority compatible job carry-forward preserving semantic dedup/first trace and held/unknown outcomes. Then wire this helper into the existing approved executor/checkpoint/restore/unchanged/final-resume paths; qualify a populated controlled upgrade and fresh recovery before new-image event acceptance.')
f.save('checkpoint.json',result);f.guard(state);print(json.dumps(dict(result=result['result'],native_fence_cases=10,job_retry_scenarios=5,privacy_findings=0,dispatch='paused',generation=18)))
