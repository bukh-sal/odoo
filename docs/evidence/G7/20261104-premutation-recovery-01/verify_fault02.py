"""Verify the completed fault using pinned IDs; running-only observer is inappropriate."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import probe as p
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='applying_pre_mutation_fault'
status=native.store.status(record['operation_id']);assert status['state']=='failed_before_mutation' and status['phase']=='checkpointed' and not status['mutation_started'] and not status['traffic_resumed']
assert p.load(native.target_path)==record['configuration']
assert p.load(p.LOCAL/'logs/premutation-current-failed-data.stdout')==p.load(p.PRIVATE/'data-before.json')
assert p.worker(native,'premutation-current-verify02-worker')==p.load(p.PRIVATE/'worker-before.json')
assert not native._inspect(native.config['worker_id'])['State']['Running']
assert not native._inspect(state['project']+'-edge-1')['State']['Running']
dispatch=p.ReferenceDispatchMaintenance(native).inspect();assert dispatch['control']['state']=='paused'
p.save('fault.json',dict(result='passed_actual_current_checkpointed_failure_before_mutation',operation_id=record['operation_id'],status=status,configuration_unchanged=True,all17tables_worker_exact=True,traffic_and_dispatch_closed=True,dispatch=dispatch,verification_continuation='Fault completed correctly; first verifier incorrectly used running-only _container to locate expected-stopped app. Pinned worker_id/project edge IDs used without replay.'))
p.mark(record,'failed_before_mutation_verified');p.f.guard(state)
print(json.dumps(dict(result='fault_before_mutation_verified',phase='checkpointed',base_configuration=5)))
