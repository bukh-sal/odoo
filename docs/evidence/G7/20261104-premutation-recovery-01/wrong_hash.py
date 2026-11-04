"""Wrong recovery hash cannot reopen or change the failed operation."""
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import probe as p
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='unchanged_resume_reviewed'
before=native.store.status(record['operation_id'])
args=p.prefix()+['plugin','recover','resume-unchanged',record['operation_id']]+p.options(native)+['--decision',str(p.OUT/'resume-decision.json'),'--decision-hash','sha256:'+'0'*64,'--noninteractive']
result=subprocess.run(args,capture_output=True,timeout=90)
(p.PRIVATE/'wrong-hash.stdout').write_bytes(result.stdout);(p.PRIVATE/'wrong-hash.stderr').write_bytes(result.stderr)
assert result.returncode and b'Exact reviewed recovery hash' in result.stderr
assert native.store.status(record['operation_id'])==before
assert not native._inspect(native.config['worker_id'])['State']['Running'] and not native._inspect(state['project']+'-edge-1')['State']['Running']
p.save('wrong-hash.json',dict(result='denied_wrong_exact_recovery_hash',exit_code=result.returncode,journal_unchanged=True,traffic_workers_remain_closed=True))
print(json.dumps(dict(result='wrong_hash_denied_no_state_change')))
