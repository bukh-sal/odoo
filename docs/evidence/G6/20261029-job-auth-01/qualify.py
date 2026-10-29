"""Source-bound F-01b1 qualification; events/external lifecycle remain open."""
import base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_job_fixture as j
j.select_profile('runner');f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state)
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.catalog import Catalog
from modular_platform.native_executor import NativeExecutor
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.operator_store import OperatorStore
from modular import configuration
from secret_scan import Scanner

assert state['phase']=='job_processes_and_kernel_verified'
assert f.load(OUT/'source-checks.json')['result']=='passed'
second=f.load(OUT/'jobs-backend-02.json');third=f.load(OUT/'jobs-backend-03.json')
assert second['tests']==12 and not second['failures'] and second['errors']==[
    'g6_native_authorized.AuthorizedJobTests.test_foreign_and_missing_records_share_not_found (resource=True)',
    'g6_native_authorized.AuthorizedJobTests.test_foreign_and_missing_records_share_not_found (resource=False)']
assert third['successful'] and third['tests']==1
for name in ['process-checks.json','kernel-regression.json','protected-audit.json','HTTP-native-regression.json']:
    assert f.load(OUT/name)['result']=='passed'
process=f.load(OUT/'process-checks.json');assert process['image_id']==state['image_id']
assert process['actual_exit_code']==137 and process['business_revision_at_death']==1 and process['reclaimed_business_revision']==2
for label in ['job-runner-bad-pin','job-runner-normal','job-runner-killed','job-runner-reclaim']:
    child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-'+label]))[0]
    assert not child['State']['Running'] and child['HostConfig']['LogConfig']['Type']=='none'
    assert child['HostConfig']['ReadonlyRootfs'] and child['Config']['User']=='10001:10001'

runtime=inspect_image(state['image_id']);old=inspect_image(second['image_id'])
assert runtime['inventory_digest']==state['inventory_digest'] and runtime['platform_version']=='0.1.8'
assert runtime['inventory']['artifacts']==old['inventory']['artifacts']
files=runtime['inventory']['files'];oldfiles=old['inventory']['files']
differences={name for name in set(files)|set(oldfiles) if files.get(name)!=oldfiles.get(name)}
assert differences=={'packages/platform_sdk/modular_platform/job_runner.py'}
paths=['packages/platform_sdk/modular_platform/job_runner.py','packages/platform_sdk/modular_platform/durable.py','packages/platform_sdk/modular_platform/projection.py','packages/platform_sdk/modular_platform/deployment.py','platform_addons/mp_core/job_dispatch.py','platform_addons/mp_core/dispatch.py','platform_addons/mp_core/__manifest__.py','platform_addons/mp_example_notes/jobs.py','platform_addons/mp_example_notes/services.py','platform_addons/mp_example_notes/models.py','platform_addons/mp_identity/scopes.py','platform_addons/mp_identity/release.py']
for path in paths:
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==files[path.replace('platform_addons/','addons/')]
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==87
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in freeze['files'].items())

auth=ROOT/'.local/g6-jobs';authstate=f.load(auth/'state.json')
assert authstate['phase']=='job_authorization_verified_runner_startup_failed'
auth_config=f.load(auth/'operator/target.json');authcatalog=Catalog(auth/'operator/catalog',configuration(auth/'operator/trust.json'),readonly=True)
observer=DockerObserver(auth_config);observed=observer.state(observer.read(),authcatalog.snapshot())['state']
assert observed==f.load(OUT/'site/installed-state.json')

# Old primitive fixture stays byte/data compatible; no lifecycle mutation.
primitive=f.load(ROOT/'.local/g6/state.json')
private_pg=['docker','exec','-i',primitive['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',primitive['active_db'],'-v','ON_ERROR_STOP=1']
query="SELECT jsonb_build_object('states',(SELECT jsonb_object_agg(state,n) FROM (SELECT state,count(*) n FROM mp_job GROUP BY state) q),'outbox',(SELECT count(*) FROM mp_outbox),'notes',(SELECT count(*) FROM mp_example_note),'dispatch',(SELECT state FROM mp_dispatch_control),'generation',(SELECT generation FROM mp_dispatch_control));"
preserved=json.loads(f.command('verify-primitive-fixture',private_pg,input=query.encode()))
assert preserved==dict(states=dict(held=4,dead_letter=2,completed=1,cancelled=1,outcome_unknown=1),outbox=1,notes=11,dispatch='paused',generation=4)
for name in ['trust.json','catalog/catalog.sqlite3']:
    assert (ROOT/'.local/operator'/name).read_bytes()==(ROOT/'.local/g6/operator'/name).read_bytes()

current=json.loads(f.sql(state,'final-job-counts',query))
assert current['dispatch']=='paused' and current['states'].get('running',0)==current['states'].get('pending',0)==0

knownroot=ROOT/'.local/g5-secret-scan';values={key:base64.b64decode(value) for key,value in f.load(knownroot/'known-values.json').items()}
for folder in [j.LOCAL,auth,ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and (path.name.endswith('password') or path.name.endswith('secret') or path.name=='service-token'):
            value=path.read_bytes().strip()
            if len(value)>=16:values[folder.name+'/'+path.name]=value
    authority=RestoreExecutor(NativeExecutor(OperatorStore(folder/'operator/control'),folder/'operator/target.json',folder/'operator/catalog',configuration(folder/'operator/trust.json')))._authority(f.load(folder/'state.json')['active_db'])[1]
    for user in authority['users']:
        for field in ['password','totp_secret']:
            if user[field] and len(user[field])>=16:values[folder.name+'/native/'+str(user['id'])+'/'+field]=user[field].encode()
scanner=Scanner((knownroot/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
public=[ROOT/name.decode() for name in names if name and (ROOT/name.decode()).is_file()]
logs=[p for folder in [j.LOCAL,auth] for p in (folder/'logs').iterdir() if p.is_file()]
findings=[finding for path in public+logs for finding in scanner.inspect_file(path,path.name)]
assert not findings,'Private scanner findings require redacted review; no raw values'
record=dict(result='passed',work_item='F-01b1',utc=datetime.now(timezone.utc).isoformat(),source_commit_before_change=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],database=state['active_db'],native_authorization_cases=12,source_tests=47,native_processes=4,actual_SIGKILL_exit=137,real_native_PostgreSQL_regression_tests=11,Linux_input_tests=4,HTTP_native_CRUD_denials=12,native_list_form_contexts=3,frozen_files=87,protected_target_configs=8,protected_G5_audit=True,old_G6_counts_exact=preserved,old_authorization_site_metadata_exact=True,global_catalog_and_trust_exact=True,current_counts=current,source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},only_candidate02_to03_runtime_change=sorted(differences),same_exact_package_artifacts=True,public_files_scanned=len(public),private_diagnostics_scanned=len(logs),known_credential_sources=len(values),credential_findings=0,acceptance=['JOB-01','JOB-02'],limits=['F-01b2 scoped producer/delivery/dedup/status event contracts remain open; no EVT acceptance passed.','Non-idempotent supported reconciliation and external worker/metadata lifecycle remain pending; JOB-03/SVC checks not passed.','G5 no-dispatch recovery still rejects populated queues. No populated-G6 upgrade/restore claim; F-01e remains required.','Candidate01 compatibility gap and candidate02 runner namespace defect retained. Corrected candidate03 tested on a distinct fresh site, no old database reset/upgrade bypass.','One test-helper context error and one private exception assertion correction are retained; source-bound eleven+one results, no full suite replay after runtime passed.','Native CRUD uses Odoo list/form views; Canvas and frontend remain unchanged.'])
path=OUT/'qualification.json';assert not path.exists();f.write(path,record)
f.guard(state);print(json.dumps(dict(result='passed',work_item='F-01b1',acceptance=record['acceptance'],known_credential_sources=len(values),credential_findings=0)))
