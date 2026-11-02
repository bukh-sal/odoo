"""Reconcile the actual failed apply before any fix or retry."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import context,MARKER,PRIVATE,OUT,base,f,worker,ReferenceDispatchMaintenance
from modular_platform.operator_os import OperatorError
state,native=context();cycle=f.load(MARKER);record=cycle['install'];assert record['state']=='applying'
status=native.store.status(record['operation_id']);assert status['state']=='failed_before_mutation' and not status['mutation_started'] and not status['traffic_resumed']
assert base.snapshot(state,'manager-reregister01-failed-data')==f.load(PRIVATE/'register-data-before.json')
assert worker(native,'manager-reregister01-failed-worker')==f.load(PRIVATE/'register-worker-before.json')
assert base.schema(state,'manager-reregister01-failed-schema')==f.load(PRIVATE/'schema-before.json')['digest']
modules=json.loads(f.sql(state,'manager-reregister01-failed-modules','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'));assert modules==f.load(PRIVATE/'modules-before.json')
try:ReferenceDispatchMaintenance(native).reference_policy(native.config)
except OperatorError as e:assert str(e)=='Retained reference metadata has active availability or endpoint approval'
else:raise AssertionError('Expected exact source reproduction')
stage=native.store.root/'stages'/record['operation_id'];assert set(p.name for p in stage.iterdir())=={'bundle.json','configuration.json'}
edge=native._inspect(native.observer._container('edge',stopped=True));app=native._inspect(native.observer._container('app'));assert not edge['State']['Running'] and app['State']['Running']
f.save('failed-apply-audit.json',dict(result='verified_failed_before_mutation_reference_preregistration_guard',operation_id=record['operation_id'],plan_hash=record['plan_hash'],journal_state=status['state'],phase=status['phase'],mutation_started=False,traffic_resumed=False,ingress_stopped_application_and_db_retained=True,all17tables_fullmodules_schema_stoppedworker_exact=True,configuration_generation=15,dispatch_generation=76,publication_generation=5,endpoint_generation=3,no_dispatch_fence_checkpoint_or_metadata_child=True,cause='Removed reference tombstone rejects independently approved enabled endpoint before suspended re-registration; absent first-registration already allows this.',next='Qualify a bounded inert-tombstone pre-registration observation with exact same-image/scopes/no approved grants or active bindings, then fresh reviewed unchanged-release recovery and immutable rollout. Never replay failed operation.'))
record['state']='failed_before_mutation_reference_guard';f.write(MARKER,cycle);f.phase(state,'manager_reregister01_failed_before_mutation_reference_guard');f.guard(state)
print('Failed apply reconciled: metadata/data/schema/jobs/modules/stoppedworker exact; ingress fenced, no dispatch or metadata mutation')
