"""Continue the existing manager request; targets live in operation_lock."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import probe as p
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='prepared'
fixture=p.load(p.LOCAL/'fixtures.json');p.r1_probe.r1.r0.LOCAL=p.LOCAL;client=p.r1_probe.Client(state,fixture,'operator')
status,value=client.request('/api/v1/operations/bundle/'+record['operation_id']);assert status==200;bundle=value['data']
assert bundle['plan_hash']==record['plan_hash'] and bundle['plan']['backup']['required'] and len(bundle['operation_lock']['targets'])==1
assert bundle['plan']['operation_type']=='suspend' and all(a['runtime']=='external_service' for a in bundle['plan']['artifacts'])
p.save('bundle.json',bundle);ops=p.prefix()+['operations','--store',str(native.store.root)]
p.save('import.json',json.loads(p.f.command('premutation-current-import',ops+['import-request',record['operation_id']]+p.validation(native))))
review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];p.save('independent-review.json',review)
native._runtime_preflight(bundle)
p.f.command('premutation-current-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+p.validation(native))
p.mark(record,'approved');p.f.guard(state)
print(json.dumps(dict(result='existing_exact_metadata_suspend_approved',operation_id=record['operation_id'],configuration=5)))
