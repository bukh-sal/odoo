"""Bound the qualified native/plugin prerequisite, without closing G6."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
from activate import context,j,f,ROOT
from modular_platform.dispatch_operator import DispatchMaintenance
from secret_scan import Scanner
state,record,native=context();assert state['phase']=='notes7_native_qualified_needs_host' and native.config['generation']==8
assert native.config['image_id']==record['image_id']==state['image_id']
batch=f.load(OUT/'native-batch-01.json');assert batch['successful'] and batch['tests']==10 and batch['installed_source'] and not batch['source_substitution']
assert hashlib.sha256((OUT/'native_batch.py').read_bytes()).hexdigest()==batch['test_sha256']
assert f.load(OUT/'completed.json')['state']=='completed' and f.load(OUT/'completed.json')['traffic_resumed']
assert f.load(OUT/'preservation.json')['exact_checkpoint_rows']==dict(mp_example_note=25,mp_example_canvas_board=0,mp_example_note_event_summary=3,mp_outbox=42)
current=DispatchMaintenance(native).inspect();assert current['control']['state']=='enabled' and current['control']['generation']==37 and current['job_states']==dict(completed=3,dead_letter=2)
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
build=f.load(ROOT/'docs/evidence/G6/20261101-notes7-candidate-01/candidate-build.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
f.guard(state)
values={k:base64.b64decode(v) for k,v in f.load(ROOT/'.local/g5-secret-scan/known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
raw=subprocess.check_output(['docker','exec',state['project']+'-db-1','psql','-U','postgres','-d',state['active_db'],'-Atc',"SELECT password FROM res_users WHERE password IS NOT NULL AND password<>'' ORDER BY id"],timeout=30)
for index,value in enumerate(raw.splitlines()):
    if len(value)>=16:values['current-native-password-hash-'+str(index)]=value
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0');paths=[ROOT/p.decode() for p in names if p and (ROOT/p.decode()).is_file()]
findings=[hit for path in paths for hit in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())];f.write(j.LOCAL/'notes7-checkpoint-private-findings.json',findings);assert not findings
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
result=dict(result='passed_bounded_native_plugin_upgrade_prerequisite',utc=datetime.now(timezone.utc).isoformat(),operation_id=record['operation_id'],plan_hash=record['plan_hash'],image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=8,dispatch_generation=37,native_batch_cases=10,installed_source=True,source_base=build['git_base'],all_runtime_build_inputs_exact=True,freeze_files=94,protected_configurations=9,privacy=dict(public_files=len(paths),known_values=len(values),findings=0),evidence=['candidate-validation.json','completed.json','native-batch-01.json','preservation.json','preservation-attempt-01.json'],acceptance_counts_unchanged=dict(passed=88,not_run=11,invalidated=0,failed=0,excluded_R2=5),rough_weighted_progress_percent=87,limits=['F-01e1 remains active: deployed host facade/native bus/browser proof next.','No blanket ID-03/EVT/JOB-03/SVC/UI-09/G6 pass; external managed worker/effects/credential reconciliation and G7 required.'],next_action='Use existing deployed Shell1.9 host facade and native bus on this same populated fixture; verify actual browser delivery/dedup/disposal/current workspace limits without altering Canvas product source. A test-only page wrapper may exercise the existing custom-page seam. Preserve native Odoo default views.')
f.save('qualification.json',result);f.guard(state)
print('Bounded actual plugin upgrade/native batch/preservation/source/freeze/privacy checkpoint passed. G6/goal stay active.')
