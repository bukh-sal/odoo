"""Close the bounded reference storage defect, leaving G7 qualification open."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('canvas4_qualified',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();record=f.load(m.MARKER)
assert native.config['generation']==27 and record['state']=='preservation_verified'
admission=f.load(OUT/'candidate-admission.json');assert admission['image_id']==state['image_id']==native.config['image_id']
build=f.load(OUT.parent/'20261102-canvas4-candidate-01/candidate-build.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
tests=f.load(OUT/'native-results.json');http=f.load(OUT/'http-results.json');preservation=f.load(OUT/'preservation.json');cleanup=f.load(OUT/'retirement.json')
assert tests['successful'] and tests['tests']==9 and tests['actual_installed_source']
assert http['result']=='passed_actual_empty_board_clear_reload_restore' and all(r['passed'] for r in http['checks'])
assert f.load(m.PRIVATE/'http-marker.json')['state']=='owned_fixture_restored_revision3'
assert preservation['configuration_generation']==27 and preservation['dispatch_generation']==126 and preservation['only_native_version_delta']==['mp_example_canvas','19.0.0.1.3','19.0.0.1.4']
assert cleanup['counts']['native_tests']==3 and cleanup['all17tables_current_worker_app_checkpoint_images_volumes_preserved']
assert f.load(OUT/'compiler-retirement.json')['current_and_checkpoint_retained']
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==97 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
f.save('qualification.json',dict(result='passed_minimal_Canvas_empty_array_storage_correction',work_item='G-01d1',spec_sections=['22.3','22.5','25.5 G'],configuration_generation=27,dispatch_generation=126,image=state['image_id'],inventory=state['inventory_digest'],Canvas='0.1.4',core='19.0.0.1.19',identity='19.0.0.1.4',native_tests=9,http_checks=len(http['checks']),
 actual_approved_Canvas_only_upgrade=True,one_nonempty_preupgrade_board_preserved=True,actual_default_and_explicit_empty_JSON_persistence=True,public_get_save_empty_array_and_fresh_client_reload=True,strict_input_CAS_role_workspace_Note_reference_guards_preserved=True,existing_Notes_use_native_Odoo_list_form=True,
 old36jobs_30Notes_other16tables_worker_preserved=True,owned_test_board_final_revision=3,owned_test_board_original_cards_restored=True,only_column_schema_delta='Canvas cards NOTNULL removed; native SQLNULL normalizes to public[]',no_frontend_source_change=True,contracts_97_exact=True,removed_containers=cleanup['removed_containers'],compiler_retired=True,
 limits=['Reference compatibility correction only, no Canvas feature expansion or new acceptance credit.','ID03 remains passed by exact unchanged core19/identity1.4/other native paths and the new Canvas scope checks.','Full G7 still requires UI09, performance, current full release/security/license/network/provenance, fresh install/recovery/runbooks/handoff and obsolete owned Docker fixture retention cleanup.']))
record['state']='qualified';f.write(m.MARKER,record);f.phase(state,'canvas4_qualified');f.guard(state)
print('Minimal Canvas empty persistence qualified on actual27/126; full G7 remains open')
