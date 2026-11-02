"""Independent post-restore endpoint revocation, stale-review refusal and key rotation."""
import argparse,copy,hashlib,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from recovery import ROOT,context,base,f,j,OUT,PRIVATE,MARKER,phase
from modular_platform.worker_operator import WorkerOperator
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.operator_os import OperatorError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
AUTH=PRIVATE/'authority.json'

def op(native):return WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')
def cli(native):return base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]
def save(record,state):record['state']=state;f.write(AUTH,record)
def physical(native,record,label):
    operator=op(native);endpoint=f.load(PRIVATE/'authority-before.json')['endpoints']
    entry=next(e for e in endpoint if e['descriptor']['installation_id']==record['scope']['installation_id'])
    observed=operator.observer(entry['descriptor'],operator.publisher._key_digest(entry['descriptor']),entry['key_id'])
    info=json.loads(f.command(label,['docker','inspect',observed['container_id']]))[0]
    return dict(container_id=info['Id'],image=info['Image'],started_at=info['State']['StartedAt'],restart_count=info['RestartCount'],mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],public_digest=observed['public_digest'])

def revoke():
    state,native=context();recovery=f.load(MARKER);assert recovery['state']=='resume_reviewed' and not AUTH.exists()
    operator=op(native);publication=operator.publisher._document();assert publication['generation']==5
    entry=next(e for e in publication['endpoints'] if e['descriptor']['installation_id']==recovery['scope']['installation_id'])
    assert entry['descriptor']['generation']==3 and entry['descriptor']['state']=='enabled'
    record=dict(scope=recovery['scope'],container_id=f.load(PRIVATE/'worker-before.json')['container_id'],key_id=entry['key_id'])
    f.write(PRIVATE/'authority-before.json',publication);f.write(PRIVATE/'authority-data-before.json',base.snapshot(state,'reference-authority-before'))
    f.write(PRIVATE/'authority-worker-before.json',physical(native,record,'reference-authority-worker-before'))
    endpoint=copy.deepcopy(entry['descriptor']);endpoint.update(generation=4,state='revoked');f.write(PRIVATE/'revoked-endpoint.json',endpoint);save(record,'preparing_revocation')
    review=json.loads(f.command('reference-authority-revoke-prepare',cli(native)+['prepare','--endpoint',str(PRIVATE/'revoked-endpoint.json'),'--key-id',record['key_id']]))
    assert json.loads(f.command('reference-authority-revoke-review',cli(native)+['review',review['plan']['operation_id']]))==review
    f.save('revocation-review.json',review);record.update(operation_id=review['plan']['operation_id'],plan_hash=review['plan_hash']);save(record,'publishing_revocation')
    result=json.loads(f.command('reference-authority-revoke-publish',cli(native)+['publish',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive']))
    assert result['generation']==6 and result['state']=='revoked';f.save('revocation-publication.json',result)
    assert physical(native,record,'reference-authority-worker-after-revoke')==f.load(PRIVATE/'authority-worker-before.json')
    assert base.snapshot(state,'reference-authority-after-revoke')==f.load(PRIVATE/'authority-data-before.json')
    save(record,'revoked6');print('Separately reviewed publication6/endpoint4 revoked after closed restore; physical worker/data unchanged',flush=True)

def reject_stale_resume():
    state,native=context();record=f.load(AUTH);recovery=f.load(MARKER);assert record['state']=='revoked6' and recovery['state']=='resume_reviewed'
    decision=PRIVATE/'resume-decision.json';seal=f.load(decision.with_suffix('.hash.json'))
    old=f.load(decision);assert datetime.now(timezone.utc)<datetime.fromisoformat(old['review']['expires_at'].replace('Z','+00:00'))
    current=RestoreExecutor(native)._resume_state(recovery['operation_id']);payload=copy.deepcopy(old);payload.pop('review')
    changed={k for k in payload if payload[k]!=current[k]};assert changed and changed<={'effects','restored_observation_digest'},changed
    try:RecoveryReviews(native.store).verify(old,exact_hash=seal['decision_hash'],current_payload=current)
    except OperatorError as error:assert str(error)=='Recovery target, checkpoint, authority or actual state changed since review'
    else:raise AssertionError('Old review wrongly accepted changed current publication')
    args=base.prefix()+['plugin','recover','resume',recovery['operation_id']]+base.options(native)+['--decision',str(decision),'--decision-hash',seal['decision_hash'],'--noninteractive']
    save(record,'testing_old_resume_refusal')
    result=subprocess.run(args,capture_output=True,cwd=ROOT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    (PRIVATE/'old-resume.stdout').write_bytes(result.stdout);(PRIVATE/'old-resume.stderr').write_bytes(result.stderr)
    assert result.returncode==2,'Inspect exact old decision and journal; never retry it'
    status=native.store.status(recovery['operation_id']);assert status['state']=='revoked' and status['phase']=='restore_verified' and not status['traffic_resumed']
    assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
    assert base.snapshot(state,'reference-authority-after-old-resume')==f.load(PRIVATE/'authority-data-before.json')
    assert op(native).publisher._document()['generation']==6
    f.save('stale-resume-refusal.json',dict(result='passed_actual_post_review_revocation_invalidates_old_resume',old_resume_decision_hash=seal['decision_hash'],old_review_unexpired=True,changed_review_fields=sorted(changed),direct_verifier_rejects_changed_current_state=True,exit_code=2,current_publication_generation=6,endpoint_generation=4,traffic_and_dispatch_stay_closed=True,old28jobs_and_all17tables_exact=True,revoked_approval_not_restored_from_checkpoint=True))
    save(record,'old_resume_refused');print('Old exact resume review refused after independent endpoint revocation; target remains closed/data exact',flush=True)

def rotate_runtime():
    state,native=context();record=f.load(AUTH);assert record['state']=='old_resume_refused';operator=op(native)
    assert operator.publisher._document()['generation']==6
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    record.update(new_issuer_ref='recovery19_issuer',new_public_ref='recovery19_public',new_key_id='recovery19-key',new_public_digest=hashlib.sha256(public).hexdigest());save(record,'provisioning_new_immutable_key_refs')
    operator.publisher.provision_keypair(record['new_issuer_ref'],record['new_public_ref'],private,public)
    record['private_material_transferred_to_worker']=False;save(record,'operator_stopping_worker_for_public_config5')
    f.command('reference-authority-stop-config3',['docker','stop','--time','20',record['container_id']],timeout=40)
    info=json.loads(f.command('reference-authority-stopped-config3',['docker','inspect',record['container_id']]))[0]
    assert not info['State']['Running'] and info['State']['ExitCode']==0 and info['Image']==f.load(PRIVATE/'worker-before.json')['image']
    volume=operator.config['runtime']['public_config_volume'];v=json.loads(f.command('reference-authority-volume',['docker','volume','inspect',volume]))[0]
    assert v['Labels']['com.modular.disposable']==operator.config['runtime']['project']
    code="""import hashlib,json,os,pathlib,sys
r=pathlib.Path('/config');v=json.load(sys.stdin);assert {p.name for p in r.iterdir()}=={'config.json','public.pem'}
assert hashlib.sha256((r/'public.pem').read_bytes()).hexdigest()==v['old_public_digest']
c=json.loads((r/'config.json').read_text());assert c==dict(v['scope'],public_key_file='/run/worker/public.pem',key_id=v['old_key_id'],endpoint_generation=3)
assert hashlib.sha256(v['public'].encode()).hexdigest()==v['new_public_digest']
public=r/'public.next';public.write_text(v['public']);public.chmod(0o444)
config=r/'config.next';config.write_text(json.dumps(dict(v['scope'],public_key_file='/run/worker/public.pem',key_id=v['new_key_id'],endpoint_generation=5)));config.chmod(0o444)
os.replace(public,r/'public.pem');os.replace(config,r/'config.json');print('Exact public-only config3/key13 advanced to config5/new key; no issuer material')
"""
    old=f.load(PRIVATE/'authority-worker-before.json');payload=dict(scope=record['scope'],old_key_id=record['key_id'],old_public_digest=old['public_digest'],new_key_id=record['new_key_id'],new_public_digest=record['new_public_digest'],public=public.decode())
    save(record,'operator_writing_public_config5')
    f.command('reference-authority-update-public-config5',['docker','run','--rm','-i','--name',state['project']+'-reference-public-config5','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/config','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code],input=json.dumps(payload).encode())
    save(record,'operator_starting_public_config5');f.command('reference-authority-start-config5',['docker','start',record['container_id']])
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        info=json.loads(subprocess.check_output(['docker','inspect',record['container_id']],timeout=10))[0]
        if info['State'].get('Health',{}).get('Status')=='healthy':break
        time.sleep(1)
    endpoint=f.load(PRIVATE/'revoked-endpoint.json');endpoint.update(generation=5,state='enabled',issuer_key_ref=record['new_issuer_ref'],public_key_ref=record['new_public_ref']);f.write(PRIVATE/'new-key-endpoint.json',endpoint)
    observed=operator.observer(endpoint,record['new_public_digest'],record['new_key_id']);assert observed['container_id']==record['container_id']
    assert info['Image']==old['image'] and info['Mounts']==old['mounts']
    assert base.snapshot(state,'reference-authority-after-runtime-key')==f.load(PRIVATE/'authority-data-before.json')
    assert operator.publisher._document()['generation']==6
    save(record,'public_config5_new_key_attested');print('Separate operator changed public config/key and restarted same worker/image; host still closed and approval still revoked6',flush=True)

def publish_current():
    state,native=context();record=f.load(AUTH);assert record['state']=='public_config5_new_key_attested';save(record,'preparing_new_key_publication')
    review=json.loads(f.command('reference-authority-new-key-prepare',cli(native)+['prepare','--endpoint',str(PRIVATE/'new-key-endpoint.json'),'--key-id',record['new_key_id']]))
    assert json.loads(f.command('reference-authority-new-key-review',cli(native)+['review',review['plan']['operation_id']]))==review
    f.save('new-key-review.json',review);record.update(new_operation_id=review['plan']['operation_id'],new_plan_hash=review['plan_hash']);save(record,'publishing_current_key')
    result=json.loads(f.command('reference-authority-new-key-publish',cli(native)+['publish',record['new_operation_id'],'--plan-hash',record['new_plan_hash'],'--noninteractive']))
    assert result['generation']==7 and result['state']=='enabled';f.save('new-key-publication.json',result)
    fresh=base.worker(native,'reference-authority-new-key-worker');assert fresh['container_id']==record['container_id'] and fresh['public_digest']==record['new_public_digest'];f.write(PRIVATE/'worker-current.json',fresh)
    assert base.snapshot(state,'reference-authority-after-new-publication')==f.load(PRIVATE/'authority-data-before.json')
    assert not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
    recovery=f.load(MARKER);phase(recovery,'restored_verified');save(record,'current_key_published7')
    f.save('key-rotation.json',dict(result='passed_actual_independent_revocation_and_fresh_key_publication_before_resume',publication_before=5,revoked_publication=6,current_publication=7,endpoint_generation_before=3,current_endpoint_generation=5,
        old_key_id=record['key_id'],current_key_id=record['new_key_id'],same_worker_container_image_mounts_and_scope=True,explicit_separate_operator_stop_public_update_start=True,public_only_worker_configuration=True,private_issuer_only_in_operator_store=True,
        metadata_installer_did_not_control_worker=True,all17tables_and28jobs_exact=True,host_still_closed_requires_fresh_resume_review=True,new_images=0,new_volumes=0))
    print('Fresh independently reviewed publication7/endpoint5/new key enabled; host still closed, fresh resume review required',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['revoke','reject_stale_resume','rotate_runtime','publish_current']);a=p.parse_args();globals()[a.action]()
