"""Independent revocation invalidates a different-image recovery resume review."""
import argparse,copy,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from recover import ROOT,context,base,f,j,OUT,PRIVATE,MARKER,phase
from modular_platform.worker_operator import WorkerOperator
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.operator_os import OperatorError
AUTH=PRIVATE/'recovery-authority.json'

def op(native):return WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')
def cli(native):return base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]
def save(record,state):record['state']=state;f.write(AUTH,record)
def physical(native,record,label):
    operator=op(native);endpoint=f.load(PRIVATE/'image-authority-before.json')['endpoints']
    entry=next(e for e in endpoint if e['descriptor']['installation_id']==record['scope']['installation_id'])
    observed=operator.observer(entry['descriptor'],operator.publisher._key_digest(entry['descriptor']),entry['key_id'])
    info=json.loads(f.command(label,['docker','inspect',observed['container_id']]))[0]
    return dict(container_id=info['Id'],image=info['Image'],started_at=info['State']['StartedAt'],restart_count=info['RestartCount'],mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],public_digest=observed['public_digest'])

def revoke():
    state,native=context();recovery=f.load(MARKER);assert recovery['state']=='resume_reviewed' and not AUTH.exists()
    operator=op(native);publication=operator.publisher._document();assert publication['generation']==9
    entry=next(e for e in publication['endpoints'] if e['descriptor']['installation_id']==recovery['scope']['installation_id'])
    assert entry['descriptor']['generation']==7 and entry['descriptor']['state']=='enabled'
    record=dict(scope=recovery['scope'],container_id=f.load(PRIVATE/'upgrade-worker-before.json')['container_id'],key_id=entry['key_id'])
    f.write(PRIVATE/'image-authority-before.json',publication);f.write(PRIVATE/'image-authority-data-before.json',base.snapshot(state,'image-authority-before'))
    f.write(PRIVATE/'image-authority-worker-before.json',physical(native,record,'image-authority-worker-before'))
    endpoint=copy.deepcopy(entry['descriptor']);endpoint.update(generation=8,state='revoked');f.write(PRIVATE/'image-authority-revoked-endpoint.json',endpoint);save(record,'preparing_revocation')
    review=json.loads(f.command('image-authority-revoke-prepare',cli(native)+['prepare','--endpoint',str(PRIVATE/'image-authority-revoked-endpoint.json'),'--key-id',record['key_id']]))
    assert json.loads(f.command('image-authority-revoke-review',cli(native)+['review',review['plan']['operation_id']]))==review
    f.save('recovery-revocation-review.json',review);record.update(operation_id=review['plan']['operation_id'],plan_hash=review['plan_hash']);save(record,'publishing_revocation')
    result=json.loads(f.command('image-authority-revoke-publish',cli(native)+['publish',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive']))
    assert result['generation']==10 and result['state']=='revoked';f.save('recovery-revocation-publication.json',result)
    assert physical(native,record,'image-authority-worker-after-revoke')==f.load(PRIVATE/'image-authority-worker-before.json')
    assert base.snapshot(state,'image-authority-after-revoke')==f.load(PRIVATE/'image-authority-data-before.json')
    save(record,'revoked10');print('Separately reviewed publication10/endpoint8 revoked after closed restore; physical worker/data unchanged',flush=True)

def reject_stale_resume():
    state,native=context();record=f.load(AUTH);recovery=f.load(MARKER);assert record['state']=='revoked10' and recovery['state']=='resume_reviewed'
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
    assert base.snapshot(state,'image-authority-after-old-resume')==f.load(PRIVATE/'image-authority-data-before.json')
    assert op(native).publisher._document()['generation']==10
    f.save('stale-resume-refusal.json',dict(result='passed_actual_post_review_revocation_invalidates_old_resume',old_resume_decision_hash=seal['decision_hash'],old_review_unexpired=True,changed_review_fields=sorted(changed),direct_verifier_rejects_changed_current_state=True,exit_code=2,current_publication_generation=10,endpoint_generation=8,traffic_and_dispatch_stay_closed=True,old29jobs_and_all17tables_exact=True,revoked_approval_not_restored_from_checkpoint=True))
    phase(recovery,'restored_verified');f.phase(state,'image_recovery_old_resume_refused_requires_fresh_review')
    save(record,'old_resume_refused');print('Old exact resume review refused after independent endpoint revocation; target remains closed/data exact',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['revoke','reject_stale_resume']);a=p.parse_args();globals()[a.action]()
