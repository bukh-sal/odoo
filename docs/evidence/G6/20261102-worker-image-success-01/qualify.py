"""Audit SVC05 evidence plus current installed source/data/authority; no gate shortcut."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from approve_runtime import ROOT,OUT,PRIVATE,context,op,base,f,j
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.plans import data_digest
OLD=OUT.parent/'20261102-worker-image-upgrade-01'
def read(name):return f.load(name)
state,native=context();assert native.config['generation']==23
assert read(PRIVATE/'remote-job.json')['state']=='verified' and read(PRIVATE/'credentials-marker.json')['state']=='verified'
for action in ['upgrade','enable']:
    record=read(PRIVATE/(action+'.json'));assert record['state']=='verified'
    status=native.store.status(record['operation_id']);assert status['state']=='completed' and status['traffic_resumed']
    result=read(OUT/(action+'-preservation.json'));assert result['old29job_outcomes_inputs_attempts_results_exact'] and result['checkpoint_files_preserved']>=48
    assert result['current_worker_image_container_start_key_mount_network_publication11_exact'] and result['strict_default_reference_profile_restored']
retired=read(j.LOCAL/'worker-image-upgrade-01/metadata.json');assert native.store.status(retired['operation_id'])['state']=='revoked'
assert len({retired['operation_id'],read(PRIVATE/'upgrade.json')['operation_id'],read(PRIVATE/'enable.json')['operation_id']})==3
assert read(OLD/'unapproved-image-manager-refusal.json')['status']==400
refusals=read(OLD/'runtime-refusals.json')['cases'];assert {r['case'] for r in refusals}=={'old_image','third_image','ordinary_old_metadata_new_image'} and all(r['result']=='refused' for r in refusals)
proof=read(OLD/'reviewed-transition-native.json');assert proof['policy']['profile']=='r1-reference-stateless-transition-v1'
assert proof['policy']['worker_transition']['base_image']!=proof['policy']['worker_transition']['target_image']
assert read(OLD/'upgrade-fault.json')['actual_metadata_child_exit0']
restored=read(OLD/'closed-preservation.json');assert restored['old_metadata_0_1_1_and_suspended_feature_restored'] and restored['new_worker_image_548202_not_rolled_back'] and restored['all29job_outcomes_inputs_keys_attempts_deadlines_results_preserved']
stale=read(OLD/'stale-resume-refusal.json');assert stale['old_review_unexpired'] and stale['exit_code']==2 and stale['current_publication_generation']==10
assert read(OLD/'resumed-http.json')['current_OS_publication10_revocation_preserved']
credentials=read(OUT/'current-credentials.json');assert credentials['publication_generation']==11 and credentials['endpoint_generation']==9
assert {r['name']:r['status'] for r in credentials['cases']}==dict(current=200,old_endpoint7=403,wrong_audience=401,foreign_workspace=403,retired_key_current_kid=401)
job=read(OUT/'ordinary-remote-job.json')['job'];assert job['state']=='completed' and job['attempts']==1 and job['error_code'] is None
assert read(OUT/'unknown-effect-refusal.json')['rollback_restored_exact_native_dispatch_state']
data=base.snapshot(state,'image-success-qualification-current');assert len(data['mp_job'])==30 and len(data['mp_example_note'])==30
assert all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
assert {k:sum(r['state']==k for r in data['mp_job']) for k in ['completed','dead_letter','cancelled']}==dict(completed=12,dead_letter=16,cancelled=2)
operator=op(native);publication=operator.publisher._document();assert publication['generation']==11
scope=read(PRIVATE/'runtime.json')['scope'];entry=next(e for e in publication['endpoints'] if all(e['descriptor'][k]==scope[k] for k in ['installation_id','site_id','workspace_id']))
endpoint=entry['descriptor'];assert endpoint['generation']==9 and endpoint['state']=='enabled'
worker=base.worker(native,'image-success-qualification-worker');assert worker==read(PRIVATE/'worker-current.json')
runtime=native.observer.read()['runtime'];assert runtime['platform_version']=='0.1.17' and runtime['native_manifests']['mp_core']['version']=='19.0.0.1.17'
names=['worker_transition','reference_dispatch','reference_recovery','external_planning','external_metadata','metadata_executor','dispatch_lifecycle',
    'worker_operator','worker_publication','worker_authority','worker_dispatch','job_runner','tokens','projection','operator_store','plans']
source={}
for name in names:
    path='packages/platform_sdk/modular_platform/'+name+'.py';digest=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    assert runtime['inventory']['files'][path]==digest;source[path]=digest
helper=ReferenceDispatchMaintenance(native);snapshot=helper.inspect();helper.require_profile(snapshot)
assert helper.policy_for(snapshot)['profile']=='r1-reference-stateless-v1' and snapshot['uncertain_jobs']==0 and snapshot['active_credentials']==0 and snapshot['api_keys']==0
registration=helper.policy_for(snapshot)['registrations'][0];assert registration['version']=='0.1.2' and registration['features']==[dict(workspace_id=scope['workspace_id'],feature_state='enabled')]
build=read(OLD/'worker-build.json');assert worker['image']==build['image_id']==endpoint['expected_image_digest']
images=json.loads(subprocess.check_output(['docker','image','inspect',build['base_image_id'],build['image_id']],timeout=20))
assert images[0]['RootFS']==images[1]['RootFS'] and {k:v for k,v in images[0]['Config'].items() if k!='Labels'}=={k:v for k,v in images[1]['Config'].items() if k!='Labels'}
records=[OLD/p for p in ['metadata-curation.json','unapproved-image-manager-refusal.json','runtime-refusals.json','reviewed-transition-native.json','upgrade-fault.json','closed-preservation.json','stale-resume-refusal.json','resumed-http.json','source-checks.json','retirement.json']]
records += [OUT/p for p in ['public-config9.json','runtime-publication.json','upgrade-preservation.json','enable-preservation.json','current-credentials.json','ordinary-remote-job.json','unknown-effect-refusal.json']]
f.save('qualification.json',dict(result='passed_SVC05_for_R1_reference_stateless_profile',utc=datetime.now(timezone.utc).isoformat(),
    acceptance=['SVC-05'],spec_sections=['14.6','10.5','11.6','23'],git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    native_generation=23,dispatch_generation=snapshot['control']['generation'],native_image=native.config['image_id'],native_inventory=runtime['inventory_digest'],
    worker_image=worker['image'],worker_container=worker['container_id'],publication_generation=11,endpoint_generation=9,metadata_version='0.1.2',
    current_ordinary_original_actor_job=job['id'],counts={t:len(rows) for t,rows in data.items()},source_sha256=source,
    records={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in records},
    limits=['Compatible worker release-label image; original runtime code/OS/Python layers are exact. No API-major or storage migration claim.',
        'Stateless reference only; no automatic external rollback or arbitrary effect reconciliation. Actual non-idempotent crash/unknown evidence remains JOB03.',
        'Independent revocation was injected after the closed SQL restore; the stale resume was rejected and fresh current review required.',
        'Native HTTP and backend checks only. SVC02/browser/UI09/full G6/G7 remain.']))
f.write(PRIVATE/'qualification-marker.json',dict(state='qualified_SVC05',generation=23,job_id=job['id']))
print('SVC05 qualified: actual changed image/independent approval/new exact upgrade+enable/ordinary remote job/current credentials/recovery fences; G6 remains open',flush=True)
