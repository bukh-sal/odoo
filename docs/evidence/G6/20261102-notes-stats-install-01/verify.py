"""Exact native connector installation footprint, existing data and worker."""
import copy,hashlib,json,sys,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from install import ROOT,OUT,PRIVATE,MARKER,context,base,f,j
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION

state,native=context();record=f.load(MARKER);assert record['state']=='completed_needs_verification' and native.config['generation']==18
bundle=f.load(OUT/'manager-bundle.json');target=bundle['operation_lock']['targets'][0]
before=f.load(PRIVATE/'data-before-install.json');after=base.snapshot(state,'notes-stats-install-data-after')
old_ids={r['public_id'] for r in before['mp_plugin_installation']}
new_rows=[r for r in after['mp_plugin_installation'] if r['public_id'] not in old_ids];assert len(new_rows)==1
installed=new_rows[0]
assert (installed['public_id'],installed['plugin_id'],installed['runtime'],installed['state'],installed['version'],installed['artifact_digest'])==(target['installation_id'],'org.example.notes_stats','native','installed','0.1.0',f.load(PRIVATE/'setup.json')['artifact_digest'])
workspace=next(r for r in before['mp_workspace'] if r['public_id']==target['workspace_id'])
features=[r for r in after['mp_workspace_plugin'] if r['installation_id']==installed['id']]
assert len(features)==1 and features[0]['availability']=='enabled' and features[0]['workspace_id']==workspace['id']
grants=[r for r in after['mp_plugin_grant'] if r['installation_id']==installed['id']]
assert len(grants)==2 and sorted(r['capability'] for r in grants)==['org.example.document_stats:analysis.run','org.example.notes:notes.read']
assert all(r['state']=='approved' and r['workspace_id']==workspace['id'] and r['policy_version']==bundle['plan']['policy_version'] for r in grants)
bindings=[r for r in after['mp_service_binding'] if r['consumer_id']==installed['id']]
assert len(bindings)==3 and {r['alias'] for r in bindings}=={'documents','jobs','stats'}
locked={r['binding_id']:r for r in bundle['operation_lock']['bindings']}
assert all(r['descriptor']==locked[r['public_id']] and r['workspace_id']==workspace['id'] and r['state']=='active' for r in bindings)
stats=next(r['descriptor'] for r in bindings if r['alias']=='stats');assert stats['provider_plugin_id']=='org.example.document_stats'
assert all(r['descriptor']['provider_plugin_id']=={'documents':'org.example.notes','jobs':'org.example.notes_stats','stats':'org.example.document_stats'}[r['alias']] for r in bindings)
updated=0
for table in before:
    expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table])
    if table=='mp_plugin_installation':actual=[r for r in actual if r['id']!=installed['id']]
    elif table in ('mp_workspace_plugin','mp_plugin_grant'):actual=[r for r in actual if r['installation_id']!=installed['id']]
    elif table=='mp_service_binding':actual=[r for r in actual if r['consumer_id']!=installed['id']]
    elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
    elif table=='mp_job':
        byid={r['public_id']:r for r in actual};assert len(byid)==19
        for old in expected:
            current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
            if changed:
                assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==87
                old.update(**{k:current[k] for k in changed});updated+=1
    assert expected==actual,table+' changed beyond exact approved connector footprint'
assert base.schema(state,'notes-stats-install-schema-after')==f.load(PRIVATE/'schema-before-install.json')['digest']
modules=json.loads(f.sql(state,'notes-stats-install-modules-after','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'))
old_modules={r['name']:(r['state'],r['latest_version']) for r in f.load(PRIVATE/'modules-before-install.json')}
current={r['name']:(r['state'],r['latest_version']) for r in modules};assert current['mp_example_notes_stats']==('installed','19.0.0.1.0')
assert all(current[n]==v for n,v in old_modules.items() if n!='mp_example_notes_stats')
assert base.worker(native,'notes-stats-install-worker-after')==f.load(PRIVATE/'worker-before-install.json')
stage=native.store.root/'stages'/record['operation_id'];checkpoint=native.store.root/'checkpoints'/record['operation_id']
ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert ready['control']['generation']==87 and enabled['after']['control']['generation']==88
assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
assert native.config['published_release']==bundle['operation_lock']['release']
files=json.loads(f.command('notes-stats-install-files-after',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
retained={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for member in archive:
        if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained and all(files.get(p)==digest for p,digest in retained.items())
worker_path=j.LOCAL/'operator/worker-target.json';worker_config=f.load(worker_path);old_helper=worker_config['helper_image'];assert old_helper==f.load(ROOT/'docs/evidence/G6/20261102-core16-candidate-01/candidate-build.json')['image_id']
worker_config['helper_image']=record['image_id'];f.write(worker_path,worker_config)
assert base.worker(native,'notes-stats-install-worker-after-helper-update')==f.load(PRIVATE/'worker-before-install.json')
f.save('preservation.json',dict(result='passed_actual_approved_native_connector_C_install',operation_id=record['operation_id'],plan_hash=record['plan_hash'],configuration_generation=18,dispatch_generation=88,
    image_id=record['image_id'],inventory_digest=record['inventory_digest'],new_metadata_rows=dict(installations=1,features=1,grants=2,bindings=3),
    native_connector_installed_only_C=True,no_new_business_table_or_note_field=True,old_module_state_versions_and_core_sdk16_exact=True,
    all17original_tables_preserved_under_exact_new_footprint_policy_epoch_changes=True,old_job_outcomes_inputs_attempts_preserved=19,jobs_epoch_updated=updated,
    old_checkpoint_files_preserved=len(retained),independent_worker_config3_publication5_physical_identity_key_exact=True,helper_only_moved_to_admitted_image=True,
    limits=['Installed native footprint only; original-actor service/job/actual remote/degraded/in-flight and recovery qualification follows.']))
record['state']='preservation_verified';f.write(MARKER,record);f.phase(state,'notes_stats_native_install_preservation_verified');f.guard(state)
print('Native connector C installed with exact1installation/1feature/2grants/3bindings; old data/jobs/files/schema/worker preserved')
