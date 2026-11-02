"""Close the Labels policy gap and bounded read correction, not G7."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('notes8_qualified',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();record=f.load(m.MARKER)
assert native.config['generation']==29 and record['state']=='preservation_verified'
admission=f.load(OUT/'candidate-admission.json');assert admission['image_id']==state['image_id']==native.config['image_id']
build=f.load(OUT.parent/'20261102-notes8-labels4-candidate-03/candidate-build.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
tests=f.load(OUT/'notes8-installed-native-results.json');http=f.load(OUT/'post-http/http-matrix.json');canvas=f.load(OUT/'canvas-paths.json');preservation=f.load(OUT/'preservation.json')
assert tests['successful'] and tests['tests']==63 and tests['installed_correction']
assert http['result']=='passed' and len(http['checks'])==31 and not http['failed'] and http['native_generation']==29
assert canvas['result']=='passed' and canvas['native_generation']==29
assert preservation['configuration_generation']==29 and preservation['dispatch_generation']==132 and preservation['schema_columns_exact'] and preservation['all36jobs_outcomes_inputs_attempts_retained']
assert f.load(OUT/'retirement.json')['counts']['native_tests']==8 and f.load(OUT/'compiler-retirement.json')['current_and_checkpoint_retained']
assert f.load(OUT/'installed-labels3-policy-probe.json')['result']=='counterexample_confirmed'
fixed=f.load(OUT/'corrected-candidate-policy-probe.json');assert fixed['result']=='passed' and len(fixed['checks'])==2
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==97 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
profile=f.load(OUT/'candidate-query-profile.json');queries={r['operation']:[s['sql_queries'] for s in r['samples']] for r in profile['results']}
assert queries['native_list24']==[45]*3 and queries['gateway_list24']==[29]*3
f.save('qualification.json',dict(result='passed_installed_Notes8_Labels4_read_serialization_and_pending_policy_fix',work_item='G-01c2b',acceptance_requalified='ID-03',configuration_generation=29,dispatch_generation=132,image=state['image_id'],inventory=state['inventory_digest'],Notes='0.2.8',Labels='0.2.4',core='19.0.0.1.20',identity='19.0.0.1.5',native_tests=63,http_cases=31,
 actual_installed_pending_policy_cached_field_denied=True,private_policy_bool_cache_expiry_SQL_ORM_and_write_guards_qualified=True,read_v1_v2_DTOs_and_empty_lists_preserved=True,ordinary_curated_independently_reviewed_approved_five_scope_upgrade=True,
 all36jobs_other16tables_schema_files_worker_preserved_except_reviewed_metadata_policy_queue_epochs=True,all_current_source_build_inputs_exact=True,contracts_97_exact=True,
 unchanged_components=['core20','identity1.5','SDK20','shell10','native Notes views','Canvas4','native NotesStats1','external metadataStats2','external worker runtime/credentials/publication'],
 retained_coverage='../20261102-read-window-02/qualification.json maps exact unchanged binary HTTP/server-action/Canvas4 persistence; original55native plus8current Labels/DTO cases now pass against installed plugin code.',
 query_discriminator=dict(candidate_only=True,native24list_before=519,native24list_after=45,gateway24list_before=816,gateway24list_after=29,not_HTTP_or_10k_target=True),
 limits=['Only the read correction and ID03 regression are qualified; no extra performance gate/acceptance credit.','Current real HTTP latency discriminator and isolated10k20concurrent benchmark still required.','UI09/shell/mount cycles/full fresh release/security/license/network/provenance/recovery/runbooks/handoff remain.','Native Python/sudo/SQL remain trusted; the private finite20ms snapshot is not a sandbox.']))
record['state']='qualified';f.write(m.MARKER,record);f.phase(state,'notes8-labels4_read_qualified');f.guard(state)
print('Notes8/Labels4 read correction qualified on actual29/132; ID03 requalified, full performance/G7 remain')
