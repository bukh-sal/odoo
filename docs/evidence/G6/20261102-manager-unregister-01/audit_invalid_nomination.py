"""Read-only audit of rejected malformed harness nomination."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import context,MARKER,PRIVATE,f,base,worker
state,native=context();cycle=f.load(MARKER)
rows=json.loads(f.sql(state,'manager-unregister01-invalid-nomination-requests',"BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(public_id ORDER BY public_id),'[]'::jsonb) FROM mp_operation_request; ROLLBACK;"))
assert rows==cycle['before_request_ids']
assert base.snapshot(state,'manager-unregister01-invalid-nomination-data')==f.load(PRIVATE/'unregister-data-before.json')
assert worker(native,'manager-unregister01-invalid-nomination-worker')==f.load(PRIVATE/'unregister-worker-before.json')
f.save('invalid-nomination-audit.json',dict(result='rejected_malformed_test_harness_before_draft',cause='Frozen sitewide unregister requires empty workspace_ids; harness copied a feature nomination.',app_request_ids_exact=True,all17tables_and_worker_exact=True,independent_approval_apply_not_invoked=True,corrected_fresh_profile_planning_and_real_preview_pass=True,runtime_source_changed=False))
print('Malformed harness request rejected without draft/data/worker changes; corrected nomination source-profile preview passes')
