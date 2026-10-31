"""Validate and record partial event qualification without claiming deployment."""
import ast,base64,hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
import fixture as j
f=j.f;out=Path(__file__).resolve().parent;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='event_jobs_regression_verified'
for name,count in [('native-backend-01.json',12),('native-technical-01.json',1),('native-binding-01.json',1),('job-origin-regression.json',3)]:
    record=f.load(out/name);assert record['result']=='passed' and record['tests']==count and record['image_id']==state['image_id']
http=f.load(out/'HTTP-qualified.json');assert http['result']=='passed' and len(http['checks'])==9
browser=(out/'browser-source-fix-observation.txt').read_text();assert 'BROWSER TRANSPORT QUALIFICATION PASSED' in browser and browser.count('PASS ')==7 and 'FAIL ' not in browser
freeze=f.load(f.ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94
assert all(hashlib.sha256((f.ROOT/p).read_bytes()).hexdigest()==digest for p,digest in freeze['files'].items())
build=f.load(out.parent/'20261029-events-candidate-01/candidate-build.json')
changed={p for p,h in build['source_sha256'].items() if hashlib.sha256((f.ROOT/p).read_bytes()).hexdigest()!=h}
assert changed=={'platform_addons/mp_shell/__manifest__.py','platform_addons/mp_shell/static/src/event_client.js'},changed
assert ast.literal_eval((f.ROOT/'platform_addons/mp_shell/__manifest__.py').read_text())['version']=='19.0.0.1.9'
source_paths=['platform_addons/mp_shell/static/src/event_client.js','platform_addons/mp_shell/static/src/event_contract.js','platform_addons/mp_shell/__manifest__.py','tests/test_event_client.mjs','docs/evidence/G6/20261029-events-01/browser_harness.html']
source={p:hashlib.sha256((f.ROOT/p).read_bytes()).hexdigest() for p in source_paths}
queue=json.loads(f.sql(state,'checkpoint-event-state-20261101',"SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'job_states',(SELECT jsonb_object_agg(state,n) FROM (SELECT state,count(*) n FROM mp_job GROUP BY state) q),'events',(SELECT count(*) FROM mp_outbox),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'active_subscriptions',(SELECT count(*) FROM mp_event_subscription WHERE state='active' AND expires_at>timezone('UTC',clock_timestamp())),'deliveries',(SELECT count(*) FROM mp_event_delivery),'consumptions',(SELECT count(*) FROM mp_event_consumption),'consumer_states',(SELECT count(*) FROM mp_event_consumer_state),'notes',(SELECT count(*) FROM mp_example_note),'dispatch',(SELECT state FROM mp_dispatch_control),'dispatch_generation',(SELECT generation FROM mp_dispatch_control));"))
assert queue['dispatch']=='paused' and queue['active_subscriptions']==0,queue
# Read-only known-value privacy audit. No credential bytes leave this process.
from secret_scan import Scanner
old=f.ROOT/'.local/g5-secret-scan';values={k:base64.b64decode(v) for k,v in f.load(old/'known-values.json').items()}
for folder in [j.LOCAL,f.ROOT/'.local/g6-jobs-runner',f.ROOT/'.local/g6-jobs',f.ROOT/'.local/g6',f.ROOT/'.local/g5-clean-recovery']:
    for p in folder.iterdir():
        if p.is_file() and p.name.endswith(('password','secret')):
            value=p.read_bytes().strip()
            if len(value)>=16:values[folder.name+'/'+p.name]=value
pg=['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',state['active_db'],'-v','ON_ERROR_STOP=1']
native=json.loads(subprocess.check_output(pg,input=b"SELECT jsonb_agg(password) FROM res_users WHERE password IS NOT NULL;"))
for i,value in enumerate(native):
    if len(value)>=16:values['current-native-'+str(i)]=value.encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=f.ROOT).split(b'\0')
paths=[f.ROOT/n.decode() for n in names if n and (f.ROOT/n.decode()).is_file()]
findings=[finding for path in paths for finding in scanner.inspect_file(path,path.relative_to(f.ROOT).as_posix())]
f.write(j.LOCAL/'checkpoint-20261101-privacy-findings.json',findings);assert not findings,'Inspect redacted private findings before publication'
for p in paths:
    if p.suffix=='.json':json.loads(p.read_bytes())
    if p.suffix=='.py':ast.parse(p.read_bytes())
f.guard(state)
result=dict(result='partial_qualification',utc=datetime.now(timezone.utc).isoformat(),previous_goal_turn='progress',current_goal_turn='progress',image_id=state['image_id'],inventory_digest=state['inventory_digest'],native_event_cases=14,http_checks=9,private_native_CRUD_denials=28,affected_job_cases=3,frontend_source_checks=dict(passed=13,command=['node','tests/test_event_client.mjs'],observed_tool_chunk='194bb4',new_case='Default timer global receiver scheduling and cleanup',no_claim_of_new_immutable_image=True),browser=dict(source_mode='corrected worktree transport against unchanged deployed native backend via loopback-only test proxy',checks=7,initial_deployed_failure='Illegal invocation from unbound browser timer; screenshot retained',fixed='globalThis timer wrappers; Shell source version19.0.0.1.9',fixture_authentication='ordinary server-side native Alice login supplied browser fixture cookie; browser login UI not qualified',Canvas_changed=False,host_facade_native_bus_wiring_browser_qualification='pending after controlled immutable upgrade'),source_sha256=source,queued_state=queue,frozen_files=94,protected_configuration_hashes=9,protected_live_database_audit='not rerun; unrelated prior sites found stopped and left untouched',privacy=dict(public_files=len(paths),known_values=len(values),findings=0),acceptance_credit=False,rough_progress_percent=83,required_remaining=['Queue-aware drain/restore/receipt generation reconciliation and independent resume, before populated fixture upgrade','Deploy new immutable timer fix and versioned native pending-revision fix via ordinary controlled upgrade; requalify host/browser/native batch','Protected data/source audit and full source-bound EVT qualification','External deterministic worker, endpoint/artifact/credential lifecycle, uncertain outcomes and full G6 integration','G7 complete acceptance/accessibility/RTL/performance/provenance/reinstall/recovery/release bundle'])
dest=out/'checkpoint-20261101.json';assert not dest.exists();f.write(dest,result)
print(json.dumps(dict(result='partial_qualification',native_cases=14,http_checks=9,job_cases=3,browser_source_checks=7,privacy_findings=0,dispatch=queue['dispatch'],frozen_files=94)))
