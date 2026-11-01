"""Actual normal CLI bootstrap from current independent authority, no DB mutation.

Retain one authority volume for the next normal integrated job profile. Do not
restart the retired publication fixture or reset its revoked generation2 mirror.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PRIVATE=protect_directory(ROOT/'.local/document-stats/operator-05');MARKER=PRIVATE/'state.json'
assert not MARKER.exists(),'Inspect exact prior bootstrap intent/volume; never replay setup'
native=json.loads((ROOT/'.local/g6-events/state.json').read_text());operator=ROOT/'.local/g6-events/operator'
protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*native['protected_configurations'],'.local/g6-events/operator/target.json']}
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def command(label,args,*,expect=0):
    stdout=PRIVATE/(label+'.stdout');stderr=PRIVATE/(label+'.stderr');assert not stdout.exists()
    with stdout.open('xb') as out,stderr.open('xb') as err:
        result=subprocess.run(args,stdout=out,stderr=err,cwd=ROOT,timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert result.returncode==expect,'Inspect exact diagnostics without replay: '+label
    return stdout.read_bytes(),stderr.read_bytes()
volume=native['project']+'_worker_authority'
assert not command('authority-volume-absent',['docker','volume','ls','-q','--filter','name=^'+volume+'$'])[0].strip()
record=dict(state='creating_normal_authority_volume',volume=volume,project=native['project']);write(MARKER,record)
command('create-authority',['docker','volume','create','--label','com.modular.worker-authority='+native['deployment_id'],
    '--label','com.modular.disposable='+native['project'],volume])
lock=json.loads((ROOT/'services/document_stats/image.lock.json').read_text())
config=dict(schema_version=1,deployment_id=native['deployment_id'],site_id=native['site_id'],authority_volume=volume,helper_image=native['image_id'],
    runtime=dict(project='mp-disposable-document-stats-05',service='document-stats',network=native['project']+'_runtime',public_config_volume='mp-disposable-document-stats-05-public-config',image=lock['reference'],destination='http://document-stats:8080'))
config_path=operator/'worker-target.json';assert not config_path.exists();write(config_path,config)
cli=[str(ROOT/'.venv/Scripts/python.exe'),'-X','utf8','tools/modular.py','--config',str(operator/'trust.json'),'worker',
    '--store',str(operator/'control'),'--deployment-config',str(operator/'target.json'),'--worker-config',str(config_path)]
review=json.loads(command('prepare-bootstrap',cli+['prepare-bootstrap'])[0]);plan=review['plan']
assert plan['kind']=='bootstrap' and plan['document']['generation']==2
assert all(e['descriptor']['state']=='revoked' for e in plan['document']['endpoints'])
record.update(state='bootstrap_prepared',operation_id=plan['operation_id'],plan_hash=review['plan_hash']);write(MARKER,record)
shown=json.loads(command('review-bootstrap',cli+['review',plan['operation_id']])[0]);assert shown==review
command('wrong-hash-refused',cli+['publish',plan['operation_id'],'--plan-hash','sha256:'+'0'*64,'--noninteractive'],expect=2)
result=json.loads(command('publish-bootstrap',cli+['publish',plan['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive'])[0])
assert result['state']=='bootstrapped' and result['generation']==2
record['state']='bootstrapped_current_authority';write(MARKER,record)
command('bootstrap-replay-refused',cli+['publish',plan['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive'],expect=2)
command('nonempty-bootstrap-refused',cli+['prepare-bootstrap'],expect=2)
script="import json,pathlib;v=json.loads(pathlib.Path('/run/worker-authority/authority.json').read_text());assert v['generation']==2 and all(e['descriptor']['state']=='revoked' for e in v['endpoints']);print('Current independent revocation/generation retained')"
command('verify-runtime-current-authority',['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL',
    '--mount','type=volume,source='+volume+',target=/run/worker-authority,readonly','--entrypoint','/venv/bin/python',native['image_id'],'-c',script])
_,error=command('old-runner-image-refused-before-claim',cli+['run-job-once'],expect=2)
refusal=json.loads(error);assert 'current runner/authority source' in refusal['message']
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
assert not command('no-job-runtime-created',['docker','ps','-aq','--filter','label=com.modular.job_operation'])[0].strip()
record.update(state='qualified_normal_volume_retained',native_unchanged=True);write(MARKER,record)
qualification=dict(result='passed_normal_operator_bootstrap_prerequisite',generation=2,revocation_preserved=True,normal_cli_exact_hash_and_review=True,wrong_hash_replay_and_nonempty_refused=True,old_runner_refused_before_claim=True,
    new_images=0,temporary_helpers_auto_removed=True,retained_authority_volume=volume,retention_reason='Normal integration target for next immutable core/connector and committed job; current independent generation2 retained',protected_configurations=len(protected),
    source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/modular.py','packages/platform_sdk/modular_platform/worker_operator.py','packages/platform_sdk/modular_platform/worker_projection.py','packages/platform_sdk/modular_platform/worker_publication.py']},
    limits=['Current installed core1.10/runner refused; current core1.11 immutable rollout and actual committed Notes job remain required.','No external provider registered/launched, no runtime metadata lifecycle or external recovery acceptance credit.'])
write(OUT/'qualification.json',qualification);print('Normal CLI current-authority bootstrap and negative gates passed; authority volume retained for integration')
