"""Existing independent status publication and actual authorized manager readback."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parent));import probe as p
state,native=p.context();record=p.load(p.PRIVATE/'state.json')
assert record['state']=='qualified_native_uninstall_fresh_restore_resumed'
before=p.snapshot(state,'native-uninstall-current-mirror-before')
result=json.loads(p.f.command('native-uninstall-current-mirror',p.prefix()+['operations','--store',str(native.store.root),
    'mirror-status',record['operation_id']]+p.validation(native)))
fixture=p.load(p.LOCAL/'fixtures.json');p.r1_probe.r1.r0.LOCAL=p.LOCAL
client=p.r1_probe.Client(state,fixture,'operator')
code,value=client.request('/api/v1/operations/status/'+record['operation_id']);assert code==200
mirror=value['data'];assert mirror['operation_id']==record['operation_id'] and mirror['plan_hash']==record['plan_hash']
assert not mirror['stale'] and mirror['state']=='revoked'
assert p.snapshot(state,'native-uninstall-current-mirror-after')==before
p.save('manager-status.json',dict(result='passed_current_independent_status_mirror_readback',publication=result,manager_status=mirror,
    current_state='revoked',all17tables_exact=True,limits=['Existing explicit operator mirror-status command, no frontend code/rendering change.']))
p.f.guard(state);print('Current independent revoked/recovered operation status published and read through authorized manager API',flush=True)
