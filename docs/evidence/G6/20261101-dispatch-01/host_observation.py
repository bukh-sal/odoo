"""Read-only end-to-end host adapter on the unchanged populated fixture."""
import hashlib,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.plans import data_digest
from modular import configuration
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='dispatch_fence_verified'
dest=OUT/'host-observation.json';assert not dest.exists()
native=NativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
operation=str(uuid4());scope=data_digest(native.config['published_release'])
observed=DispatchMaintenance(native).run('observe',operation,j.LOCAL/'operator/dispatch-inspections'/operation,release_digest=scope)
assert observed['control']['state']=='paused' and observed['control']['generation']==18
assert observed['tables']['mp_job']['rows']==3 and observed['tables']['mp_outbox']['rows']==29
assert observed['tables']['mp_event_delivery']['rows']==216
paths=['packages/platform_sdk/modular_platform/dispatch_lifecycle.py','packages/platform_sdk/modular_platform/dispatch_maintenance.py','packages/platform_sdk/modular_platform/dispatch_operator.py']
f.write(dest,dict(result='passed_readonly_host_adapter',operation_id=operation,image_id=state['image_id'],observed=observed,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},limits=['Host owns the helper source and exact current site/database/release; no image patched or backend mutation.','Not yet wired into apply/checkpoint/reconciliation/restore/resume; existing no-dispatch recovery refusal remains.']))
f.guard(state);print('Read-only OS host adapter passed on the populated event fixture.')
