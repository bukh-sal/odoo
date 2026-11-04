"""Execute the reviewed decision payload, keeping the CLI envelope as evidence."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import probe as p
from modular_platform.plans import data_digest
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='unchanged_resume_reviewed'
seal=p.load(p.OUT/'resume-decision.json');payload=p.load(p.OUT/'resume-payload.json')
assert payload==seal['decision'] and data_digest(payload)==seal['decision_hash'] and payload['operation_id']==record['operation_id']
assert p.load(p.OUT/'wrong-hash.json')['journal_unchanged']
p.mark(record,'resuming_unchanged')
args=p.prefix()+['plugin','recover','resume-unchanged',record['operation_id']]+p.options(native)+['--decision',str(p.OUT/'resume-payload.json'),'--decision-hash',seal['decision_hash'],'--noninteractive']
result=json.loads(p.f.command('premutation-current-resume',args,timeout=240));p.save('resume-result.json',result)
assert result['state']=='unchanged_release_resumed' and not result['database_restore'] and not result['worker_replaced']
p.mark(record,'resumed_needs_verification');p.f.guard(state)
print(json.dumps(dict(result='unchanged_resume_completed',configuration=5,database_restore=False,worker_replaced=False)))
