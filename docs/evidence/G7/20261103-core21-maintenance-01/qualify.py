"""Bind normal installed upgrade/current regressions; no whole-G7 claim."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
read=lambda name:json.loads((OUT/name).read_text())
preserved=read('preservation.json');retired=read('retirement.json');native=read('core21-installed-native-results.json');http=read('post-http/http-matrix.json')
two=read('HTTP-qualified.json');remote=read('remote-job.json');guards=read('gateway-startup-guards.json');extra=read('extra-guards.json');canvas=read('canvas-paths.json')
assert preserved['configuration_generation']==30 and preserved['dispatch_generation']==135
assert native['successful'] and native['tests']==63 and http['result']=='passed' and len(http['checks'])==31
assert len(two['worker_ids'])==2 and two['worker_ids'][0]!=two['worker_ids'][1] and len(two['checks'])==5
assert remote['attempts']==1 and remote['idempotent_gateway_replay'] and remote['statistics_match_saved_note_revision']
assert guards['stale_exit']==1 and extra['changed_input_conflicts409'] and extra['legacy_jsonrpc_omitted404']
assert canvas['result']=='passed' and len(retired['retired'])==13
operator_paths=['operator_store.py','approval_validation.py','operator_os.py','contracts.py']
retained={}
for name in operator_paths:
 path='packages/platform_sdk/modular_platform/'+name
 previous=subprocess.check_output(['git','show','d837aba6:'+path]);actual=(ROOT/path).read_bytes();assert previous==actual
 retained[path]=hashlib.sha256(actual).hexdigest()
acceptance={
 'BOOT-03':'Current selected base/web guarded workers and actual omitted legacy /jsonrpc404; same image policy.',
 'BOOT-04':'Strict full native module state matches baseline except core version, installed native set17 remains exact allowed image graph; no ERP activation.',
 'BOOT-05':'Actual current image rejects injected writable data-dir addon before native import; exact inventoried source/startup readers unchanged.',
 'BOOT-06':'Actual old31 image refused before native import/serving; current two guarded workers start without initialization/migration flags and schema stays exact.',
 'ID-01':'Actual native63/HTTP31 and two-worker positive CRUD/private workspace isolation; captured originals preserved.',
 'ID-02':'Actual forged uid/su/database/company/private frames/workspace inputs denied in two-worker and native regressions.',
 'ID-03':'Actual native export/import/binary/token/id-only/cache/job paths and current HTTP31/Canvas reference guards.',
 'ID-04':'Actual service cookie/native technical identity cannot map to implicit administrator authority; current job guards.',
 'ID-05':'Committed demotion/removal/restoration honored on first warmed/new requests on both distinct guarded workers; pending/cache read guard regressions.',
 'ID-06':'Workspace administrator actual manager API403 and native installation read/create AccessError; exact OS-approved operator path preserved.',
 'ID-07':'Current direct native RPC/model and suspension/cache guard checks; strict image inventory entrypoint.',
 'ID-09':'Same actual Alice temporarily editorA/viewerB with native/API checks; global native groups and original authority restored exactly.',
 'ID-10':'Both actual guarded worker container IDs warm reads, then deny after committed demotion/revocation; source actor scope counters remain monotonic.',
 'API-01':'Actual declared methods work, undeclared sudo404, forbidden authority field400; native registered bound chain/DTO validation regressions.',
 'API-02':'Actual remote analyze same-key response replay returns identical outcome; changed same-key input returns409 without extra job.',
 'API-04':'Current public validation/not-found/forbidden responses, normalized native errors and typed DTO checks; no debug/traceback in tested wire denial.',
 'MIG-08':'Actual previous image refuses current release inventory; old33job claims advance epoch, all previous outcomes/inputs/attempts preserved, readiness/drain generation132→135.',
 'SEC-07':'Same exact independently reconstructed new Python diff approved/applied; current8new source cases cover rehashed review omission/forgery. Host authority implementation exactly matches180host/65Linux qualified revision16, retaining expiry/revoke/stale/replay vectors; no claim all old runtime cases rerun.'}
report=dict(result='passed_installed_core21_normal_upgrade_and_bounded_current_backend_requalification',utc=datetime.now(timezone.utc).isoformat(),image_id=preserved['image_id'],inventory_digest=preserved['inventory_digest'],configuration_generation=30,dispatch_generation=135,
 operation_id=preserved['operation_id'],native_tests=63,http_cases=31,two_actual_guarded_workers=two['worker_ids'],remote_once_job=remote['job_id'],retired_helpers=13,
 final_counts=retired['counts'],original_files_exact=50,acceptance_requalified=acceptance,unchanged_qualified_host_authority_sha256=retained,
 retained_source_checks='docs/evidence/G7/20261103-python-maintenance-source-01/qualification.json and linux-consumers02.json',
 current_coverage_limits=['Not dependency-changing post-commit fault/fresh restore/resume, full fresh release, final security/provenance/network/secrets/runbooks or updated worker runtime qualification.',
 'ID08 real browser revalidation and UI09 remain separate; no frontend or Canvas expansion.',
 'Synthetic test history is intentionally retained: one new completed job, six producer events, A policy+4 and original membership audit timestamp. All other captured data exact.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],acceptance_requalified=len(acceptance),native=63,http=31,helpers_retired=13)))
