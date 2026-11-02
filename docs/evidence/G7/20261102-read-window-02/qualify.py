"""Bind actual installed finite-read correction without declaring G7 passed."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('read_window_qualified',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();record=f.load(m.MARKER)
assert native.config['generation']==28 and record['state']=='preservation_verified'
admission=f.load(OUT/'candidate-admission.json');assert state['image_id']==native.config['image_id']==admission['image_id']
build=f.load(OUT.parent/'20261102-core20-candidate-03/candidate-build.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
tests=f.load(OUT/'window2-installed-native-results.json');http=f.load(OUT/'post-http/http-matrix.json');canvas=f.load(OUT/'canvas-paths.json');preservation=f.load(OUT/'preservation.json')
assert tests['successful'] and tests['tests']==55 and tests['installed_correction']
assert http['result']=='passed' and len(http['checks'])==31 and not http['failed'] and http['native_generation']==28
assert canvas['result']=='passed' and canvas['native_generation']==28
assert preservation['configuration_generation']==28 and preservation['dispatch_generation']==129 and preservation['old_jobs_outcomes_inputs_attempts_preserved']==36
assert f.load(OUT/'retirement.json')['counts']['native_tests']==8 and f.load(OUT/'compiler-retirement.json')['current_and_checkpoint_retained']
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==97 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
delta={r['path'] for r in admission['source_diff']}
assert delta=={'addons/mp_core/__manifest__.py','addons/mp_core/models.py','addons/mp_identity/__manifest__.py','addons/mp_identity/models/scoped.py','addons/mp_identity/scopes.py','addons/mp_identity/read_window.py','packages/platform_sdk/modular_platform/projection.py'}
profile=f.load(OUT/'candidate-query-profile.json');queries={r['operation']:[s['sql_queries'] for s in r['samples']] for r in profile['results']}
assert queries['native_list24']==[123]*3 and queries['gateway_list24']==[816]*3
f.save('qualification.json',dict(result='passed_installed_finite_native_read_window_correction',work_item='G-01c2_core_prerequisite',configuration_generation=28,dispatch_generation=129,image=state['image_id'],inventory=state['inventory_digest'],core='19.0.0.1.20',identity='19.0.0.1.5',native_tests=55,http_cases=31,Canvas_scope=canvas['checks'],
 exact_current_source_build_inputs=True,ordinary_independently_reviewed_approved_upgrade=True,all36jobs_other16tables_schema_files_worker_preserved_except_reviewed_queue_epochs=True,contracts_97_exact=True,ID03_retained=True,
 retained_coverage={'binary_HTTP':'../20261102-native-paths-01/http-binary.json: real anonymous/own/foreign denials. Binary adapter/upstream route unchanged by exact seven-path delta; current native attachment suite exercises changed shared guard.',
 'server_actions':'../20261102-native-paths-01/server-actions.json: actual UID/nonsudo groups, own success/foreign denial. Server-action engine unchanged; current native read suite exercises shared guard.',
 'Canvas4_empty_storage':'../20261102-canvas4-source-01/qualification.json: packaged Canvas4 bytes/schema retained; current shared-guard Canvas/reference cases passed.'},
 query_discriminator=dict(candidate_only=True,native24list_before=519,native24list_after=123,gateway24list_unchanged=816,not_HTTP_or_10k_target=True),
 limits=['Core prerequisite only; G-01c2 still requires separate Notes/Labels read serialization adaptation and measured HTTP improvement.','Not a native-code/SQL sandbox. Supported serializers reuse finite validated authority for at most20ms; entries/writes remain fresh.','UI09/10k20concurrent/shell/mount cycles/full fresh release/security/license/network/provenance/recovery/runbooks/handoff remain. No new progress/acceptance credit.']))
record['state']='qualified';f.write(m.MARKER,record);f.phase(state,'core20_read_window_qualified');f.guard(state)
print('Core20 read-window correction qualified on actual28/129; G7/performance remains open')
