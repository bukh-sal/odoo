"""Real unsupported-state start and late-readiness refusal under OS reviews."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-dispatch'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.plans import data_digest
from modular import configuration
import modular_platform.restore_executor as module
import queues


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['queued-start','prepare-late','late']);args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');target=LOCAL/'operator/target.json';config=load(target);assert config['generation']==20 and config['project']=='mp-r0-r1dispefb95a06d78f'
    op=load(LOCAL/'dispatch-fault.json')['operation_id'];store=OperatorStore(LOCAL/'operator/control');trust=ROOT/state['operator_trust_config'];catalog=ROOT/state['operator_catalog'];native=NativeExecutor(store,target,catalog,configuration(trust));recovery=RestoreExecutor(native);before=store.status(op)
    assert before['phase']=='restore_verified' and not before['traffic_resumed']
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    if args.action=='queued-start':
        old=load(OUTPUT/'old-clean-review.json');decision=OUTPUT/'old-clean-decision.json';assert not decision.exists();decision.write_text(json.dumps(old['decision'],indent=2)+'\n',encoding='utf8')
        command=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust),'plugin','recover','resume',op,'--decision',str(decision),'--decision-hash',old['decision_hash'],'--noninteractive','--store',str(store.root),'--deployment-config',str(target),'--catalog',str(catalog)]
        r=subprocess.run(command,capture_output=True,timeout=120);(LOCAL/'queued-resume.stderr').write_bytes(r.stderr)
        assert r.returncode!=0 and b'require reconciliation; traffic must remain closed' in r.stderr
        reason='unsupported restored effects rejected before decision/traffic execution'
    elif args.action=='prepare-late':
        envelope=recovery.prepare_resume(op);write('late-review.json',dict(decision=envelope,decision_hash=data_digest(envelope)));assert not any(envelope['effects'].values())
        print(json.dumps(dict(state='late_boundary_independently_reviewed_not_executed',decision_hash=data_digest(envelope),profile=envelope['recovery_profile'])));return
    else:
        envelope=load(OUTPUT/'late-review.json');decision=envelope['decision'];assert data_digest(decision)==envelope['decision_hash']
        app=native.observer._container('app');original=module._run;injected=[]
        def late_work(arguments,**kwargs):
            result=original(arguments,**kwargs)
            if arguments[:3]==['docker','exec',app] and 'urllib.request' in arguments[-1]:
                assert not injected;injected.append(queues.seed('late'))
            return result
        with patch.object(module,'_run',side_effect=late_work):
            try:recovery.resume(decision,exact_hash=envelope['decision_hash'],noninteractive=True)
            except OperatorError as error:assert 'require reconciliation; traffic must remain closed' in str(error);reason=str(error)
            else:raise AssertionError('Late work passed the final traffic boundary')
        assert len(injected)==1;write('late-injection.json',dict(result='injected_after_real_HTTP_readiness_before_final_traffic_fence',queue=injected[0]))
        recovery.revoke_review(decision,exact_hash=envelope['decision_hash'])
    assert store.status(op)==before and not native._inspect(native.observer._container('edge',stopped=True))['State']['Running']
    receipt_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in queues.receipts().glob('*.json')}
    write(args.action+'-refused.json',dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),operation_id=op,reason=reason,journal_unchanged=True,traffic_fence_not_recorded=True,edge_still_stopped=True,external_receipt_hashes=receipt_hashes,private_review_revoked=args.action=='late',limits=['Synthetic fixture queued work and durable local external receipt; no real job adapter or network delivery.']))
    print(json.dumps(dict(result='passed',case=args.action,traffic_closed=True)))


if __name__=='__main__':main()
