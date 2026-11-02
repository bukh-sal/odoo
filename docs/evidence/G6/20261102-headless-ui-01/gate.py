"""Finish exact helper cleanup and audit G6 exit against current evidence."""
import gzip,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import lifecycle as d
from modular_platform.operator_os import protect_directory
ROOT,OUT,base,f,j=d.ROOT,d.OUT,d.base,d.f,d.j
state,native=d.context();assert not (OUT/'gate-G6.json').exists()
ui=f.load(OUT/'qualification.json');assert ui['acceptance']==['SVC-02']
assert ui['actual_paused_worker_timeout_degraded_UI'] and ui['actual_SIGKILL137_worker_crash_degraded_UI']
assert ui['actual_post_navigation_computation_no_late_notice'] and ui['explicit_post_recovery_real_results_visible']
for name,digest in ui['records'].items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest
backend_path=OUT.parent/'20261102-current-backend-audit-01/coverage.json';backend=f.load(backend_path)
for path,digest in backend['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
for path,digest in backend['checked_record_sha256'].items():assert hashlib.sha256((OUT.parent/path).read_bytes()).hexdigest()==digest
expected={'JOB-01','JOB-02','JOB-03','EVT-01','EVT-02','EVT-03','SVC-01','SVC-02','SVC-03','SVC-04','SVC-05'}
assert {r['acceptance'] for r in backend['coverage']}==expected
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert freeze['revision']==15 and len(freeze['files'])==97 and len(freeze['contracts'])==8
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
assert hashlib.sha256((ROOT/'planning/modular_platform_spec.md').read_bytes()).hexdigest()=='c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201'

# Only exited, exact-deployment, same-image observers with durable receipts.
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
selected={}
for line in call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines():
    ident,name=line.split();prefix=state['project']+'-op-';suffix='-dispatch-observe'
    if not name.startswith(prefix) or not name.endswith(suffix):continue
    operation=name[len(prefix):-len(suffix)];receipt=native.store.root/'dispatch-inspections'/operation/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0]
    if info['Image']!=native.config['image_id']:continue
    labels=info['Config']['Labels'];value=f.load(receipt)
    assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id']
    assert value['child']==name and value['action']=='observe' and not info['State']['Running'] and info['State']['ExitCode']==0
    assert info['HostConfig']['LogConfig']['Type']=='none';selected[ident]=info
archive=protect_directory(ROOT/'.local/retired-docker-20261102/headless-ui')
for ident,info in selected.items():
    path=archive/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    call(['docker','rm',ident])
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split());assert not selected.keys()&remaining

pids=[];retained=[]
for number in range(1,6):
    directory=j.LOCAL/f'headless-ui-0{number}';process=f.load(directory/'process.json')
    assert process['state']=='stopped' and process['exit']['code']==0;pids.append(process['pid'])
    profile=directory/'profile';assert profile.is_dir()
    retained.append(dict(role='protected_owned_test_browser_profile',name=profile.parent.name,bytes=sum(p.stat().st_size for p in profile.rglob('*') if p.is_file())))
query='@(Get-Process -Id '+','.join(map(str,pids))+' -ErrorAction SilentlyContinue).Count'
assert call(['pwsh','-NoProfile','-Command',query]).decode().strip()=='0'
f.save('cleanup.json',dict(result='retired_exact_terminal_observers_all_owned_browsers_stopped',containers_removed=len(selected),
    new_images=0,new_volumes=0,personal_browser_touched=False,owned_browser_processes_still_running=0,
    profiles_retained=retained,profile_removal='Automatic approval review rejected deleting the five owned profiles: blocked by policy; no specific reason supplied. No deletion ran and no alternate deletion method was attempted.',
    profiles_protected_and_excluded_from_release=True,current_host_worker_database_public_authority_and_checkpoint_roles_preserved=True,no_global_prune=True))

worker=base.worker(native,'g6-gate-current-worker');assert worker==f.load(j.LOCAL/'headless-ui-05/worker-after.json')
data=base.snapshot(state,'g6-gate-current-data');assert len(data['mp_job'])==36 and len(data['mp_example_note'])==30
assert all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
original=f.load(j.LOCAL/'headless-ui-02/data-before.json')
new={r['public_id'] for r in data['mp_job']}-{r['public_id'] for r in original['mp_job']};assert len(new)==6
for table,rows in original.items():assert ([r for r in data[table] if r['public_id'] not in new] if table=='mp_job' else data[table])==rows
records={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in [backend_path,OUT/'qualification.json',OUT/'cleanup.json']}
records.update({'docs/evidence/G6/'+p:hashlib.sha256((OUT.parent/p).read_bytes()).hexdigest() for p in backend['checked_record_sha256']})
f.save('gate-G6.json',dict(gate='G6',result='passed',utc=datetime.now(timezone.utc).isoformat(),
    spec_version='1.1',spec_sha256='c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201',
    native_generation=24,dispatch_generation=117,image=state['image_id'],inventory=state['inventory_digest'],
    worker_image=worker['image'],worker_container=worker['container_id'],worker_config_generation=9,worker_authority_publication=11,
    contract_freeze_revision=15,contract_files=97,contract_rows=8,
    acceptance={ident:'passed' for ident in sorted(expected)},evidence_sha256=records,
    native_jobs_claim_reclaim_authority_and_uncertainty_proven=True,scoped_events_and_dedup_native_consumer_host_proven=True,
    independent_worker_scoped_tokens_lifecycle_image_recovery_proven=True,actual_timeout_crash_degraded_UI_and_native_survival_proven=True,
    all30original_jobs_and_other16tables_exact_under6explicit_new_UI_test_jobs=True,terminal_jobs=36,notes=30,
    no_R2_sandbox_or_automatic_external_rollback_claim=True,
    retained_operational_note='Five closed protected disposable browser profiles retained after automatic deletion-policy rejection; no new Docker image/volume assets.',
    next_gate='G7',remaining_R1=['ID-03 complete native transport/path audit','UI-09 keyboard/contrast/zoom/RTL',
        'Current full acceptance audit, fresh reinstall/recovery/runbooks, security/dependency/license/provenance checks, performance and release evidence bundle'],
    goal_complete=False))
f.phase(state,'G6_jobs_events_services_qualified');f.guard(state)
print('G6 PASSED:11JOB/EVT/SVC checks current-source qualified;36terminaljobs/30Notes/current worker healthy; G7/fullR1 still required')
