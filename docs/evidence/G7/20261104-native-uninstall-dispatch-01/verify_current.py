"""Current R1 native uninstall feasibility, read-only before any approval/mutation."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-uninstall-dispatch-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular_platform.uninstall_planning import prepare_current_image_uninstall
from modular_platform.resolution import PlanningError
f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==5 and not PRIVATE.exists();protect_directory(PRIVATE)
before=snapshot(state,'uninstall-dispatch-before');identity=worker(native,'uninstall-dispatch-worker-before')
catalog=Catalog(native.catalog_root,native.validator,readonly=True);observation=native.observer.read();document=native.observer.state(observation,catalog.snapshot())
impact=native.observer.native_impact(observation,catalog,site_id=state['site_id'],requested=['mp_example_notes_labels'])
targets=[dict(installation_id=p['installation_id'],site_id=impact['site_id'],workspace_id=w,plugin_id=p['plugin_id'],action='uninstall') for p in impact['plugins'] for w in p['workspace_ids']]
assert impact['dispatch']['state']=='unsupported' and set(impact['dispatch']['tables'])=={'mp_job','mp_outbox'}
assert {p['plugin_id'] for p in impact['plugins']}=={'org.example.notes_labels'} and len(targets)==2
try:prepare_current_image_uninstall(document,observation['sites'],catalog.snapshot(),impact=impact,targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
except PlanningError as error:assert str(error)=='Native uninstall requires the G6 durable dispatch drain adapter';refusal=str(error)
else:raise AssertionError('Expected legacy dispatch refusal not observed')
assert snapshot(state,'uninstall-dispatch-after')==before and worker(native,'uninstall-dispatch-worker-after')==identity;f.guard(state)
(PRIVATE/'observed-document.json').write_text(json.dumps(document,indent=2)+'\n')
(PRIVATE/'data-before.json').write_text(json.dumps(before,indent=2)+'\n')
paths=['packages/platform_sdk/modular_platform/uninstall_planning.py','packages/platform_sdk/modular_platform/native_uninstall.py','packages/platform_sdk/modular_platform/lifecycle_impact.py']
result=dict(result='confirmed_current_R1_native_uninstall_dispatch_gap',image_id=state['image_id'],configuration_generation=5,impact=impact,targets=targets,planner_refusal=refusal,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},one_completed_reference_job=True,all17tables_worker_original_configs_exact=True,plan_registered=False,approval_created=False,mutation_started=False,required_fix='Connect native uninstall to existing typed dispatch fencing/checkpoint/reconciliation; preserve queue rows during native cleanup, refuse unknown profiles, and verify actual native uninstall/restore on existing disposable realm.',limits=['Read-only feasibility counterexample; earlier G5 native uninstall remains proven only before durable dispatch schema. Current integrated R1 profile needs implementation/qualification.','No new plugin/library/frontend, destructive action or native import during impact inspection.'])
with (OUT/'gap.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],target_scopes=2,planner_refused=True,all17tables_worker_exact=True)))
