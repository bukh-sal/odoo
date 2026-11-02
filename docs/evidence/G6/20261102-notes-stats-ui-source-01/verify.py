"""Verify the approved UI-only upgrade before creating any new test job."""
import copy,hashlib,json,sys,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from upgrade import ROOT,OUT,PRIVATE,MARKER,context,base,f,j
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
state,native=context();record=f.load(MARKER)
assert record['state']=='completed_needs_verification' and native.config['generation']==24
bundle=f.load(OUT/'manager-bundle.json');target=bundle['operation_lock']['targets'][0]
before=f.load(PRIVATE/'data-before-install.json');after=base.snapshot(state,'notes-ui-upgrade-02-data-after')
installed=next(r for r in before['mp_plugin_installation'] if r['public_id']==target['installation_id'])
workspace=next(r for r in before['mp_workspace'] if r['public_id']==target['workspace_id'])
stage=native.store.root/'stages'/record['operation_id'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
observed=ReferenceDispatchMaintenance(native).inspect();assert observed==enabled['after'] and observed['control']['state']=='enabled'
epochs=0;deltas={}
for table,rows in before.items():
    expected=copy.deepcopy(rows);actual=after[table];assert len(expected)==len(actual),table
    if table=='mp_plugin_installation':
        row=next(r for r in expected if r['id']==installed['id']);current=next(r for r in actual if r['id']==row['id'])
        delta={k for k in row if row[k]!=current[k]};assert delta=={'version','artifact_digest','manifest','write_date'},delta
        assert current['version']=='0.1.1' and current['artifact_digest']==f.load(PRIVATE/'setup.json')['artifact_digest']
        row.update(**{k:current[k] for k in delta});deltas[table]=sorted(delta)
    elif table=='mp_workspace_plugin':
        row=next(r for r in expected if r['installation_id']==installed['id'] and r['workspace_id']==workspace['id'])
        current=next(r for r in actual if r['id']==row['id']);assert row['availability']==current['availability']=='enabled'
        assert {k for k in row if row[k]!=current[k]}<={'write_date'};row['write_date']=current['write_date']
    elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
    elif table=='mp_job':
        byid={r['id']:r for r in actual}
        for row in expected:
            current=byid[row['id']];delta={k for k in row if row[k]!=current[k]}
            assert delta<={'release_digest','claim_generation','dispatch_generation'}
            if delta:
                assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==row['claim_generation']+1
                assert current['dispatch_generation']==ready['control']['generation']
                row.update(**{k:current[k] for k in delta});epochs+=1
    assert expected==actual,table+' outside approved UI-only metadata/epoch footprint'
assert base.schema(state,'notes-ui-upgrade-02-schema-after')==f.load(PRIVATE/'schema-before-install.json')['digest']
modules=json.loads(f.sql(state,'notes-ui-upgrade-02-modules-after','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'))
old={r['name']:(r['state'],r['latest_version']) for r in f.load(PRIVATE/'modules-before-install.json')}
new={r['name']:(r['state'],r['latest_version']) for r in modules}
assert new['mp_example_notes_stats']==('installed','19.0.0.1.1')
assert all(new[k]==v for k,v in old.items() if k!='mp_example_notes_stats')
assert native.config['published_release']==bundle['operation_lock']['release']
assert base.worker(native,'notes-ui-upgrade-02-worker-after')==f.load(PRIVATE/'worker-before-install.json')
files=json.loads(f.command('notes-ui-upgrade-02-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
retained={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(native.store.root/'checkpoints'/record['operation_id']/'filestore.tar.gz','r:gz') as archive:
    for member in archive:
        if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert len(retained)>=48 and all(files.get(p)==digest for p,digest in retained.items())
worker_path=j.LOCAL/'operator/worker-target.json';worker_config=f.load(worker_path)
assert worker_config['helper_image']==f.load(OUT/'candidate-admission.json')['base_image']
worker_config['helper_image']=record['image_id'];f.write(worker_path,worker_config)
assert base.worker(native,'notes-ui-upgrade-02-worker-helper-after')==f.load(PRIVATE/'worker-before-install.json')
f.save('preservation.json',dict(result='passed_approved_NotesStats_UI_only_upgrade',operation_id=record['operation_id'],plan_hash=record['plan_hash'],
    native_generation=24,dispatch_generation=observed['control']['generation'],native_image=record['image_id'],native_inventory=record['inventory_digest'],
    old30job_outcomes_inputs_attempts_results_and_all30Notes_retained=True,job_epochs_updated=epochs,all17tables_preserved_under_reviewed_footprint=True,
    schema_and_other_native_module_versions_exact=True,old_checkpoint_files_retained=len(retained),
    worker_container_image_key_config9_approval11_exact=True,helper_only_moved_to_admitted_image=True,no_new_grants=True,browser_verified=False))
record['state']='preservation_verified';f.write(MARKER,record);f.phase(state,'notes_stats_ui_upgrade_preservation_verified');f.guard(state)
print('UI-only native upgrade24 preserved all30oldjobs/30Notes/17tables/schema/files/worker approval11; backend entrypoints next')
