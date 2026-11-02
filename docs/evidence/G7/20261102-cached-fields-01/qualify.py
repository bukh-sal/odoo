"""Bind installed ID03 results and retained unchanged adapters; not G7 pass."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('qualify_core19',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context()
assert native.config['generation']==26 and f.load(m.MARKER)['state']=='preservation_verified'
admission=f.load(OUT/'candidate-admission.json');assert admission['image_id']==state['image_id']==native.config['image_id']
build=f.load(OUT.parent/'20261102-core19-candidate-01/candidate-build.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
checks=f.load(OUT/'installed-native-results.json');http=f.load(OUT/'post-http/http-matrix.json');preserved=f.load(OUT/'preservation.json');canvas=f.load(OUT/'canvas-paths.json')
assert checks['successful'] and checks['tests']==40 and checks['installed_correction']
assert http['result']=='passed' and len(http['checks'])==29 and not http['failed']
assert preserved['configuration_generation']==26 and preserved['dispatch_generation']==123 and preserved['old_jobs_outcomes_inputs_attempts_preserved']==36
assert canvas['result']=='passed' and canvas['native_generation']==26
assert f.load(OUT/'retirement.json')['removed_containers']==18 and f.load(OUT/'compiler-retirement.json')['current_and_checkpoint_retained']
prior=OUT.parent/'20261102-native-paths-01'
assert f.load(prior/'http-binary.json')['result']=='passed_actual_legacy_public_binary_HTTP_denials'
for filename in ['server-actions.json','canvas-paths.json']:
 assert f.load(prior/filename)['result']=='passed',filename
core18=f.load(prior/'candidate-admission.json');delta={r['path'] for r in admission['source_diff']}
assert delta=={'addons/mp_core/__manifest__.py','addons/mp_identity/__manifest__.py','addons/mp_identity/models/scoped.py','packages/platform_sdk/modular_platform/projection.py'}
mapping={
 'search/autocomplete/aggregate/native list and reads':'post-http/http-matrix.json:29 current HTTP positive/negative cases, both workspaces, viewer and missing/forged scope',
 'export/import':'installed-native-results.json: NativePathTests, authorized export permission only in rollback fixture, own export and foreign/mixed/id-only denials; native import create/CAS and viewer/ownership denials',
 'attachments':'installed-native-results.json: actual public/ordinary token/limited-field token/direct stream denials and unrelated public-asset positives. Prior http-binary.json: real anonymous/own/foreign download bytes denied. Binary adapter and upstream HTTP route unchanged by exact core19 four-path delta; newly changed target guard is covered by current native tests.',
 'batch and pending revisions':'installed-native-results.json:10 NativeBatchTests plus import/web_save mixed/role cases',
 'jobs':'installed-native-results.json:12 CurrentJobGuards preserve original actor and recheck scope, membership, feature, bindings, grants, technical credentials, role/revision/status; unchanged registered handlers and guarded durable runner retain passed G6 workflow evidence',
 'warmed fields/virtual origins':'installed-native-results.json:10 NativeCacheTests, scalar/subscript/mapped/relational fields, own/viewer/new positives and workspace/principal/missing scope/revocation/action/feature/actor/foreign-origin denials',
 'Canvas scope and JSON Note references':'canvas-paths.json: actual installed nonempty boards, own/foreign/mixed/missing native reads, viewer-write and own/foreign/missing Note-reference checks, all rolled back',
 'server actions and native cron inventory':'../20261102-native-paths-01/server-actions.json: actual native run retains UID/non-sudo both group variants, own success and foreign denial; no workspace native crons. Native server-action implementation and registry inventory unchanged by core19, generic read guard covered by current installed cases. Trusted native code is not sandboxed.'}
f.save('qualification.json',dict(result='passed_ID03_supported_R1_native_paths',acceptance='ID-03',spec_sections=['11.4','11.7','23'],configuration_generation=26,dispatch_generation=123,image=state['image_id'],inventory=state['inventory_digest'],core='19.0.0.1.19',identity='19.0.0.1.4',native_tests=40,http_cases=29,coverage=mapping,
 all36terminaljobs_other16tables_files_schema_worker_authority_preserved=True,all_current_source_build_inputs_exact=True,contract_freeze_files=97,contract_rows=8,
 limits=['This closes the supported R1 native scope-path audit, not G7 or the complete release.','No new HTTP cache leak claim or native/sudo sandbox claim. Distinct workspace/principal units of work still require distinct transactions.','Canvas valid-empty-array persistence remains a separate required release defect; no Canvas product expansion.','UI09/performance/current full release/security-license-network-provenance/fresh install-recovery/runbooks/handoff remain.']))
print('ID03 supported native-path audit qualified on actual26/123; full G7 remains open')
