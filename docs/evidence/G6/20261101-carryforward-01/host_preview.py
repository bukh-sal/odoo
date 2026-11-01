"""Actual guarded OS/native bridge preview on the retained pre-adapter image."""
import hashlib,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.plans import data_digest
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='carryforward_tests_verified'
marker=j.LOCAL/'carryforward-host-preview-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
native=NativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
release=data_digest(native.config['published_release']);operation=str(uuid4());directory=j.LOCAL/'operator/dispatch-job-previews'/operation
adapter=DispatchMaintenance(native)
before=adapter.run('observe',str(uuid4()),directory/'before',release_digest=release)
result=adapter.reconcile_jobs(operation,directory/'preview',previous_release=release,release_digest=release,inventory_digest=state['inventory_digest'],preview=True)
after=adapter.run('observe',str(uuid4()),directory/'after',release_digest=release)
assert before==after and before['control']['generation']==18 and before['control']['state']=='paused'
assert result['dispatch_enabled'] is False and result['requires_independent_resume'] and len(result['jobs'])==3
paths=['platform_addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/dispatch_operator.py','packages/platform_sdk/modular_platform/dispatch_jobs_maintenance.py']
record=dict(result='passed_guarded_host_preview',operation_id=operation,image_id=state['image_id'],inventory_digest=state['inventory_digest'],actual_pre_adapter_retained_image=True,whole_queue_receipt_control_snapshot_exact_before_after=True,current_generation=18,prospective_reconciliation=result,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},limits=['Preview rolls back; no approved apply/restore/resume mutation or new immutable image qualified.','Pinned native runtime validators/handlers are reused; only one fixed host-owned reconciliation function is supplied, never artifact/application Python.'])
f.write(marker,dict(state='completed',result='passed'));f.save('host-preview.json',record);f.phase(state,'carryforward_host_preview_verified');f.guard(state)
print('Guarded OS/native carry-forward preview passed on retained image; full queue/control snapshot unchanged.')
