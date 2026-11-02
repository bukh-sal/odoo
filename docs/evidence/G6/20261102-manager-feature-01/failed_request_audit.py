"""Audit the failed real browser nomination without deleting or approving it."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import OUT,PRIVATE,MARKER,context,f,base
state,native=context();cycle=f.load(MARKER)
rows=json.loads((jpath:=PRIVATE.parent/'logs/manager-suspend-failed-request-rows.stdout').read_bytes())
new=[r for r in rows if r['operation_id'] not in cycle['before_request_ids']];assert new==[]
assert base.snapshot(state,'manager-suspend-data-after-failed-request')==f.load(PRIVATE/'suspend-data-before.json')
assert base.worker(native,'manager-suspend-worker-after-failed-request')==f.load(PRIVATE/'worker-before.json')
report=dict(result='failed_preview_rolled_back_app_draft',drafts=new,all17tables_and_independent_worker_exact=True,
    cause='Prepared restart description mismatch in frozen operations-view validator',
    boundary='Existing HTTP exception rollback preserves app request table; no request or independent authority granted',
    next='Align canonical host-restart derivation and prepared-view validation; coherent versioned runtime required')
f.save('failed-request-audit.json',report)
cycle.update(state='runtime_preview_fix_required',failed_browser_drafts=new);cycle['suspend']['state']='preview_failed_rolled_back';f.write(MARKER,cycle)
print(json.dumps(dict(result=report['result'],unrequested_drafts=0,original_data_worker_unchanged=True,independent_apply_not_invoked=True)))
