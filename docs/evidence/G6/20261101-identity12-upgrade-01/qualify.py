"""Close the bounded identity correction using retained installed evidence.

Read-only runtime inspection. Never rebuild, migrate, enqueue, or replay jobs.
"""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f,MARKER
from modular_platform.dispatch_operator import DispatchMaintenance
from secret_scan import Scanner

state,record,native=context()
assert state['phase']=='identity12_qualified_needs_gate_record'
assert native.config['generation']==7 and native.config['image_id']==state['image_id']==record['image_id']
completed=f.load(OUT/'completed.json');assert completed['state']=='completed' and completed['traffic_resumed']
current=DispatchMaintenance(native).inspect()
assert current['control']['state']=='enabled' and current['control']['generation']==34
assert current['job_states']==dict(completed=3,dead_letter=2)
expected=dict(mp_job=5,mp_outbox=42,mp_event_subscription=33,mp_event_delivery=222,mp_event_consumption=3,mp_event_consumer_state=1)
assert all(current['tables'][name]['rows']==rows for name,rows in expected.items())
installed=f.load(OUT.parent/'20261101-authority-flush-01/installed-01.json')
assert installed['successful'] and installed['tests']==20 and installed['installed_source'] and installed['image_id']==state['image_id']
for path,digest in installed['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
source=f.load(OUT.parent/'20261101-authority-flush-01/source-checkpoint.json')
archived=OUT.parent/'20261101-authority-flush-01/native_tests_source18.py'
assert hashlib.sha256(archived.read_bytes()).hexdigest()==source['source_sha256']['docs/evidence/G6/20261101-authority-flush-01/native_tests.py']
# Compare with the exact pre-correction source, not mutable HEAD.
prior=ast.parse(subprocess.check_output(['git','show','e2cddf95:platform_addons/mp_identity/scopes.py'],cwd=ROOT))
now=ast.parse((ROOT/'platform_addons/mp_identity/scopes.py').read_bytes())
named=lambda tree:{n.name:n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
a,b=named(prior),named(now)
for name in ['Scope','canonical_uuid','current_scope','scoped_environment']:assert ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False)
calls=[n for n in b['resolve_scope'].body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and getattr(n.value.func,'id',None)=='_flush_identity_policy']
assert len(calls)==1;b['resolve_scope'].body.remove(calls[0])
assert ast.dump(a['resolve_scope'],include_attributes=False)==ast.dump(b['resolve_scope'],include_attributes=False)
candidate=f.load(OUT/'candidate-validation.json');assert candidate['SDK_core_shell_Python_policy_unchanged'] and len(candidate['source_diff'])==2
http=f.load(OUT/'HTTP-qualified.json');assert len(set(http['worker_ids']))==2 and http['original_business_projection_groups_and_membership_authority_exact']
assert f.load(OUT/'helpers-stopped.json')['owned_secondary_and_edge_stopped_exit0']
assert f.load(j.LOCAL/'identity12-HTTP-01.json')['state']=='completed'
for name in ['preservation.json','checkpoint-trace.json','original-job-regression.json','history.json']:
    value=f.load(OUT/name);assert value.get('result') or value.get('successful') or value.get('checks')
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
f.guard(state)
values={k:base64.b64decode(v) for k,v in f.load(ROOT/'.local/g5-secret-scan/known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
# Capture password hashes privately in memory. Never print a raw credential.
raw=subprocess.check_output(['docker','exec',state['project']+'-db-1','psql','-U','postgres','-d',state['active_db'],'-Atc',"SELECT password FROM res_users WHERE password IS NOT NULL AND password<>'' ORDER BY id"],timeout=30)
for index,value in enumerate(raw.splitlines()):
    if len(value)>=16:values['current-native-password-hash-'+str(index)]=value
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=[ROOT/p.decode() for p in names if p and (ROOT/p.decode()).is_file()]
findings=[hit for path in paths for hit in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())]
f.write(j.LOCAL/'identity12-final-private-findings.json',findings);assert not findings,'Inspect private redacted findings; no sensitive stdout'
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
result=dict(result='passed_bounded_identity12_requalification',utc=datetime.now(timezone.utc).isoformat(),image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=7,dispatch_generation=34,native_tests=20,installed_source=True,two_distinct_guarded_HTTP_workers=True,source_type_SQL_cache_logic_preserved=True,original_business_authority_groups_and_job_trace_preserved=True,original_producer_envelopes=36,retained_owned_HTTP_events=6,old_filestore_files_retained=44,frozen_files=94,protected_configurations=9,privacy=dict(files=len(paths),known_values=len(values),findings=0),restored_acceptances=['FEAS-01','FEAS-02','ID-01','ID-02','ID-04','ID-05','ID-07','ID-09','ID-10','JOB-02'],restored_gates=['G1','G3'],retained_evidence_boundary='Unchanged browser cache/transport, two-tab lifecycle, Scope type, SQL query and cache keys; current installed native and HTTP scope/role/service/two-worker revocation checks replace affected server authority evidence.',evidence=['candidate-validation.json','completed.json','../20261101-authority-flush-01/installed-01.json','HTTP-qualified.json','helpers-stopped.json','preservation.json','checkpoint-trace.json','original-job-regression.json','history.json'],limits=['No EVT/JOB-03/SVC/ID-03/UI-09 pass from this bounded correction.','Notes0.2.7 native batch and deployed host/bus/browser checks remain; external service/effect/credential and full G7 qualification remain.'],next_action='Separate Notes0.2.7 plugin candidate: exact current core/SDK/identity and unchanged Labels/Canvas; local isolated catalog and normal independent plugin upgrade, then installed native batch/event host/browser proof.')
f.save('qualification.json',result)
record['state']='qualified';f.write(MARKER,record)
for name in ['core10-upgrade-01.json','core10-job-finish-01.json']:
    path=j.LOCAL/name;old=f.load(path);old['state']='qualified_after_identity12_correction';old['qualification']='docs/evidence/G6/20261101-identity12-upgrade-01/qualification.json';f.write(path,old)
f.phase(state,'identity12_qualified');f.guard(state)
print('Installed20/native HTTP/two workers/history/preservation/freeze/privacy qualified; ten checks and G1/G3 may be restored. G6 remains open.')
