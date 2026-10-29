"""Old committed read-only resume observation versus real restored queued state."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-dispatch'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.operator_os import OperatorError
from modular import configuration


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['baseline','reproduce']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'));target=LOCAL/'operator/target.json';state=load(LOCAL/'state.json');config=load(target)
    assert config['project']=='mp-r0-r1dispefb95a06d78f' and config['generation']==20
    op=load(LOCAL/'dispatch-fault.json')['operation_id'];store=OperatorStore(LOCAL/'operator/control');native=NativeExecutor(store,target,ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']))
    source=subprocess.check_output(['git','show','2adbdbde:packages/platform_sdk/modular_platform/restore_executor.py'])
    namespace=dict(__name__='modular_platform._qualification_old_restore',__package__='modular_platform',__file__=str(ROOT/'packages/platform_sdk/modular_platform/restore_executor.py'))
    exec(compile(source,'<committed pre-fix read-only resume observer>','exec'),namespace)
    old=namespace['RestoreExecutor'](native);payload=old._resume_state(op);current=RestoreExecutor(native)
    if args.action=='baseline':
        path=OUTPUT/'old-clean-review.json';assert not path.exists()
        current_payload=current._resume_state(op);assert not any(current_payload['effects'].values())
        decision=RecoveryReviews(store).issue(payload)
        path.write_text(json.dumps(dict(payload=payload,decision=decision,decision_hash=data_digest(decision),source_commit='2adbdbde',source_sha256=hashlib.sha256(source).hexdigest(),old_mutative_resume_executed=False),indent=2)+'\n',encoding='utf8')
        print(json.dumps(dict(result='old_clean_observer_recorded_current_fixed_profile_clear',generation=20)));return
    baseline=load(OUTPUT/'old-clean-review.json');assert payload==baseline['payload']
    RecoveryReviews(store).verify(baseline['decision'],exact_hash=baseline['decision_hash'],current_payload=payload)
    try:current.prepare_resume(op)
    except OperatorError as error:assert 'require reconciliation' in str(error);reason=str(error)
    else:raise AssertionError('Current guard permitted pending restored work')
    assert store.status(op)['phase']=='restore_verified' and not store.status(op)['traffic_resumed']
    edge=native.observer._container('edge',stopped=True);assert not native._inspect(edge)['State']['Running']
    RecoveryReviews(store).revoke(baseline['decision'],exact_hash=baseline['decision_hash'])
    report=dict(result='real_restored_queue_counterexample_and_fix_verified',source_commit='2adbdbde',source_sha256=hashlib.sha256(source).hexdigest(),old_clean_review_still_valid_with_queued_work=True,old_observation_digest_unchanged=True,old_mutative_resume_executed=False,current_prepare_resume_refused=True,current_reason=reason,journal_still_closed=True,edge_still_stopped=True,old_private_review_revoked=True)
    (OUTPUT/'old-counterexample.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))


if __name__=='__main__':main()
