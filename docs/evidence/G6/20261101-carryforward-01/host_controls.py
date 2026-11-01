"""Actual OS stale-enable denial and uniquely correlated review preview."""
import hashlib,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError
from modular_platform.dispatch_operator import DispatchMaintenance
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='carryforward_tests_verified'
marker=j.LOCAL/'carryforward-host-controls-01.json';assert not marker.exists()
operation=str(uuid4());review=str(uuid4());directory=j.LOCAL/'operator/dispatch-control-probes'/operation
f.write(marker,dict(state='running',operation_id=operation,review_id=review))
native=NativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'));adapter=DispatchMaintenance(native)
before=adapter.inspect_current();assert before['control']['state']=='paused' and before['control']['generation']==18
denied=False
try:adapter.run('enable',operation,directory/'stale-enable',release_digest=before['release_digest'],expected_digest='sha256:'+'0'*64)
except OperatorError:denied=True
assert denied,'Inspect actual control immediately; unexpected enable must never be treated as a passing denial'
prospective=adapter.reconcile_jobs(operation,directory/'preview',previous_release=before['release_digest'],release_digest=before['release_digest'],inventory_digest=state['inventory_digest'],preview=True,review_id=review)
after=adapter.inspect_current();assert before==after
assert prospective['dispatch_enabled'] is False and prospective['requires_independent_resume']
record=f.load(directory/'preview/preview.json');assert record['mutation_committed'] is False
assert record['child'].endswith('dispatch-preview-'+review.replace('-',''))
paths=['platform_addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/dispatch_lifecycle.py','packages/platform_sdk/modular_platform/dispatch_operator.py','packages/platform_sdk/modular_platform/dispatch_maintenance.py','packages/platform_sdk/modular_platform/dispatch_jobs_maintenance.py']
result=dict(result='passed_host_controls',operation_id=operation,review_id=review,image_id=state['image_id'],wrong_snapshot_enable_refused=True,review_correlated_preview_rolled_back=True,full_dispatch_snapshot_unchanged=True,control_generation=18,observed=after,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},limits=['Direct disposable test of helper controls; no actual approved upgrade/restore/final-resume workflow or enable mutation exercised.','Original fixed-function host preview retained; this new probe covers changed control-tag inspection/enable and review-specific child identity.'])
f.save('host-controls.json',result);f.write(marker,dict(state='completed',result='passed',operation_id=operation,review_id=review));f.phase(state,'carryforward_host_controls_verified');f.guard(state)
print('OS stale snapshot enable refused; review-correlated native preview rolled back; dispatch remains paused18.')
