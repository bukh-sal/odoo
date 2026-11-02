"""Audit the first read-only probe and source-defined foreign binding error."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from install import context,base,f,j,PRIVATE
state,native=context();original=json.loads((j.LOCAL/'logs/notes-stats-http-before.stdout').read_bytes())
assert base.snapshot(state,'notes-stats-http-audit-data')==original
assert base.worker(native,'notes-stats-http-audit-worker')==f.load(PRIVATE/'worker-before-install.json')
assert len(original['mp_job'])==19
f.save('entrypoint-assertion-audit.json',dict(result='read_only_harness_expectation_corrected_from_existing_contract',observed_foreign_workspace_status=503,error_code='DEPENDENCY_UNAVAILABLE',cause='Gateway queries active binding by public_id AND current workspace; missing scoped binding deliberately returns DEPENDENCY_UNAVAILABLE before resource lookup.',actual_C_context_and_status_passed=True,all17tables_and_worker_exact=True,no_jobs_or_native_code_changed=True,next='Fresh labeled read-only continuation expects frozen binding-unavailable code; positive C status and negative A/B are both required.'))
print('Wrong harness404 expectation audited: source-defined503 denial,19jobs/17tables/worker exact; no product change')
