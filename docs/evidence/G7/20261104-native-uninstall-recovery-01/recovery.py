"""Ordinary exact-hash restore and separately reviewed resume; no replay."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).parent));import probe as p
from modular_platform.plans import data_digest

def step(action):
    state,native=p.context();record=p.load(p.PRIVATE/'state.json');operation=record['operation_id']
    mapping={'prepare-restore':('recovery_required_native_committed','restore_reviewed','restore'),
             'restore':('restore_reviewed','restored_verified_traffic_closed','restore'),
             'prepare-resume':('restored_verified_traffic_closed','resume_reviewed','resume'),
             'resume':('resume_reviewed','restored_resumed_needs_verification','resume')}
    expected,finished,stem=mapping[action];assert record['state']==expected
    if action=='prepare-resume':assert record.get('closed_verified') is True
    args=p.prefix()+['plugin','recover',action,operation]+p.options(native)
    if action in ['restore','resume']:
        seal=p.load(p.PRIVATE/(stem+'-envelope.json'));payload=p.load(p.PRIVATE/(stem+'-payload.json'))
        assert data_digest(payload)==seal['decision_hash'] and payload==seal['decision']
        args+=['--decision',str(p.PRIVATE/(stem+'-payload.json')),'--decision-hash',seal['decision_hash'],'--noninteractive']
    p.mark(record,'running_'+action)
    result=json.loads(p.f.command('native-uninstall-current-'+action,args,timeout=600))
    if action.startswith('prepare-'):
        decision=result['decision'];assert decision['operation_id']==operation and data_digest(decision)==result['decision_hash']
        assert decision['action']==('restore_to_fresh_database' if stem=='restore' else 'resume_verified_restore')
        p.write(p.PRIVATE/(stem+'-envelope.json'),result);p.write(p.PRIVATE/(stem+'-payload.json'),decision)
        p.save(action+'.json',dict(result='exact_private_recovery_review',operation_id=operation,
            decision_hash=result['decision_hash'],review=decision['review'],action=decision['action']))
        if stem=='restore':
            assert decision['fresh_database']=='mp_disposable_r0_r1_restore_'+operation.replace('-','')
            assert decision['fresh_database']!=record['configuration']['sites'][0]['database']
            record['fresh_database']=decision['fresh_database']
        before=native.store.status(operation)
        wrong=p.prefix()+['plugin','recover',stem,operation]+p.options(native)+[
            '--decision',str(p.PRIVATE/(stem+'-payload.json')),'--decision-hash','sha256:'+'0'*64,'--noninteractive']
        negative=subprocess.run(wrong,capture_output=True,timeout=120)
        (p.PRIVATE/(stem+'-wrong-hash.stdout')).write_bytes(negative.stdout)
        (p.PRIVATE/(stem+'-wrong-hash.stderr')).write_bytes(negative.stderr)
        assert negative.returncode and native.store.status(operation)==before
        assert b'hash' in negative.stderr.lower()
        p.save(stem+'-wrong-hash.json',dict(result='refused_wrong_exact_hash',exit_code=negative.returncode,journal_unchanged=True))
    else:
        assert result['state']==('restored_verified' if action=='restore' else 'restored_traffic_resumed')
        p.save(action+'.json',result)
        config=p.load(native.target_path)
        assert config['sites'][0]['database']==record['fresh_database'] and config['image_id']==record['configuration']['image_id']
        state.update(active_db=config['sites'][0]['database'],image_id=config['image_id'])
        state['databases']=sorted(set(state['databases']+[state['active_db']]))
        p.f.phase(state,finished)
    p.mark(record,finished);p.f.guard(state)
    print(json.dumps(dict(result=finished,operation_id=operation)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare-restore','restore','prepare-resume','resume'])
    step(parser.parse_args().action)
