"""Full bounded EVT qualification: retained exact code plus actual new-image proof."""
import ast,base64,hashlib,json,re,socket,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.dispatch_operator import DispatchMaintenance
from secret_scan import Scanner
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='host_events_current_native_verified'
native=StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
assert native.config['generation']==8 and native.config['image_id']==state['image_id']
browser=f.load(OUT/'browser-observation.json');assert len(browser['checks'])==4 and not browser['failures'] and browser['actual_host_facade'] and browser['native_Odoo_default'] and browser['bus_payload_minimized']
assert browser['counts']['callbacks']==29 and browser['counts']['wakes']>=1 and browser['disposals']==1 and len(browser['notes'])==2
assert f.load(j.LOCAL/'host-event-proxy-01.json')['state']=='stopped' and f.load(j.LOCAL/'host-event-proxy-metrics.json')['websocket_tunnels']>=1
with socket.socket() as probe:probe.settimeout(1);assert probe.connect_ex(('127.0.0.1',18089))!=0
current_native=f.load(OUT/'native-current.json');assert current_native['result']=='passed' and len(current_native['checks'])==3 and not current_native['source_substitution']
assert hashlib.sha256((OUT/'native_current.py').read_bytes()).hexdigest()==current_native['test_sha256']
current=DispatchMaintenance(native).inspect();assert current['control']['state']=='enabled' and current['control']['generation']==37 and current['job_states']==dict(completed=3,dead_letter=2)
expected=dict(mp_job=5,mp_outbox=44,mp_event_subscription=35,mp_event_delivery=251,mp_event_consumption=3,mp_event_consumer_state=1)
assert all(current['tables'][name]['rows']==rows for name,rows in expected.items())
leases=f.command('host-event-final-stream-state',['docker','exec',state['project']+'-db-1','psql','-U','postgres','-d',state['active_db'],'-Atc',"SELECT jsonb_build_array((SELECT count(*) FROM mp_event_subscription WHERE state='active'),(SELECT count(*) FROM mp_event_delivery WHERE state='leased'))"])
assert json.loads(leases)==[0,0]

def parse(raw,table):
    m=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S);assert m
    return m[1].decode().split(', '),[line.decode().split('\t') for line in m[2].splitlines() if line]
notes_record=f.load(j.LOCAL/'notes7-upgrade-01.json');checkpoint=native.store.root/'checkpoints'/notes_record['operation_id']
def pair(table):
    old=f.command('host-event-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    new=f.command('host-event-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    a,b=parse(old,table),parse(new,table);assert a[0]==b[0];return a,b
for table in ['mp_example_note','mp_outbox']:
    a,b=pair(table);cols=a[0];index=cols.index('public_id');old={row[index]:row for row in a[1]};new={row[index]:row for row in b[1]}
    assert all(new.get(key)==value for key,value in old.items())
    assert len(new)==len(old)+2
    if table=='mp_example_note':assert set(new)-set(old)==set(browser['notes']) and len(old)==25
    else:
        assert len(old)==42;aggregate=cols.index('aggregate_id');assert {row[aggregate] for key,row in new.items() if key not in old}==set(browser['notes'])
for table in ['mp_example_canvas_board','mp_example_note_event_summary','mp_membership','mp_principal','mp_plugin_grant','mp_service_binding']:
    a,b=pair(table);assert sorted(a[1])==sorted(b[1])
a,b=pair('mp_job');allowed={'release_digest','claim_generation','dispatch_generation'};cols=a[0]
canonical=lambda rows:sorted([{k:v for k,v in zip(cols,row) if k not in allowed} for row in rows],key=lambda row:row['public_id'])
assert canonical(a[1])==canonical(b[1]) and len(a[1])==5

# Retain only evidence whose implementation boundary is independently exact.
oldbuild=f.load(ROOT/'docs/evidence/G6/20261029-events-candidate-01/candidate-build.json');exact=[]
for path in ['platform_addons/mp_core/event_models.py','platform_addons/mp_core/async_models.py','platform_addons/mp_core/controllers.py','platform_addons/mp_core/dispatch.py','platform_addons/mp_example_notes_labels/event_projection.py','platform_addons/mp_example_notes_labels/models.py','platform_addons/mp_identity/models/scoped.py']:
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==oldbuild['source_sha256'][path];exact.append(path)
def named(tree):return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
changes={}
for path,allowed in [('platform_addons/mp_core/events.py',{'_subscription','dispatch'}),('packages/platform_sdk/modular_platform/event_store.py',{'candidates'}),('packages/platform_sdk/modular_platform/durable.py',{'enqueue'})]:
    old=subprocess.check_output(['git','show','5daaf201:'+path],cwd=ROOT);assert hashlib.sha256(old).hexdigest()==oldbuild['source_sha256'][path]
    a,b=named(ast.parse(old)),named(ast.parse((ROOT/path).read_bytes()));assert a.keys()==b.keys();changed={n for n in a if a[n]!=b[n]};assert changed==allowed;changes[path]=sorted(changed)
oldnotes=ast.parse(subprocess.check_output(['git','show','5daaf201:platform_addons/mp_example_notes/models.py'],cwd=ROOT));newnotes=ast.parse((ROOT/'platform_addons/mp_example_notes/models.py').read_bytes())
method=lambda tree,name:next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='Note' for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
assert ast.dump(method(oldnotes,'_emit_change'),include_attributes=False)==ast.dump(method(newnotes,'_emit_change'),include_attributes=False)
previous=f.load(ROOT/'docs/evidence/G6/20261029-events-01/checkpoint-20261101.json')
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in previous['source_sha256'].items())
for name in ['native-backend-01.json','native-binding-01.json','native-technical-01.json','HTTP-qualified.json']:assert f.load(ROOT/'docs/evidence/G6/20261029-events-01'/name)['result']=='passed'
for name in ['preservation.json','history.json']:assert f.load(ROOT/'docs/evidence/G6/20261101-identity12-upgrade-01'/name)['result'].startswith('passed')
assert f.load(ROOT/'docs/evidence/G6/20261101-notes7-upgrade-01/qualification.json')['native_batch_cases']==10
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
build=f.load(ROOT/'docs/evidence/G6/20261101-notes7-candidate-01/candidate-build.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
assets=f.load(j.LOCAL/'host-event-proxy-assets.json');assert len(assets)>=2 and all(v['response_unchanged'] for v in assets.values())
f.save('served-assets.json',assets)
values={k:base64.b64decode(v) for k,v in f.load(ROOT/'.local/g5-secret-scan/known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
raw=subprocess.check_output(['docker','exec',state['project']+'-db-1','psql','-U','postgres','-d',state['active_db'],'-Atc',"SELECT password FROM res_users WHERE password IS NOT NULL AND password<>'' ORDER BY id"],timeout=30)
for index,value in enumerate(raw.splitlines()):
    if len(value)>=16:values['current-native-hash-'+str(index)]=value
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0');paths=[ROOT/p.decode() for p in names if p and (ROOT/p.decode()).is_file()]
findings=[hit for path in paths for hit in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())];f.write(j.LOCAL/'host-event-final-private-findings.json',findings);assert not findings
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
result=dict(result='passed_scoped_native_events_and_deployed_host',utc=datetime.now(timezone.utc).isoformat(),image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=8,dispatch_generation=37,acceptances=['EVT-01','EVT-02','EVT-03'],native_original_retained_cases=14,current_native_cases=3,retained_HTTP_checks=9,frontend_source_cases=13,retained_corrected_source_browser_cases=7,current_actual_host_browser_checks=4,actual_Odoo_WebSocket_bus=True,actual_host_facade=True,current_served_bundles_unchanged=True,producer_hook_AST_exact=True,retained_byte_exact_paths=exact,changed_functions_and_covered_new_behavior=changes,changed_function_evidence='Actual core10/identity12 history/replay/paused close/retained consumer tombstone duplicate; original-user semantic job retry; current rollback/scope and browser actual replay/dispose; Notes.7 native batch10. Identity1.2 native20/HTTPtwo-worker requalification retained.',original_business_authority_bindings_jobs_and_42_envelopes_preserved=True,retained_browser_notes=browser['notes'],counts=dict(jobs=5,notes=27,events=44,subscriptions=35,deliveries=251,consumptions=3,consumer_states=1,active_subscriptions=0,leased_deliveries=0),freeze_files=94,protected_configurations=9,privacy=dict(public_files=len(paths),known_values=len(values),findings=0,screenshot_visually_reviewed=True),helpers='proxy36997 intentionally interrupted after four successful browser checks; finally marker stopped and port18089 closed; created browser tab closed; primary remains live',limits=['Native-only populated lifecycle prerequisite F-01e1 and scoped events F-01b2 complete; full G6 remains open for deterministic external worker/artifact/endpoint/scoped credentials/outage and non-idempotent effect/credential reconciliation.','ID-03 broader native-path audit/UI-09/final G7 qualification still required.','Earlier real native/HTTP/browser evidence is retained only with the explicitly audited source boundary; no new browser login-UI or production deployment claim.'],next_action='F-01c: inspect frozen worker request/response/token and endpoint lifecycle contracts plus existing scoped service gateway, implement minimal deterministic independently operated reference worker. No Canvas/product UI work.')
f.save('qualification.json',result);f.phase(state,'events_native_host_qualified');f.guard(state)
print('EVT01/02/03 qualified with actual deployed host/native bus and source-bound retained integration; G6/external/G7 remain open.')
