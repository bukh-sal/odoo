"""Verify the one approved upgrade; no apply/fault replay or new operation."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT))
import activate as m
from modular_platform.catalog import Catalog
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular_platform.worker_operator import WorkerPlanningReader
from modular_platform.plans import data_digest

f=m.f;f.OUTPUT=OUT;state,native=m.context('connector');r=f.load(m.PRIVATE/'state.json')
assert r['state']=='completed_needs_verification' and native.config['generation']==6
stage=native.store.root/'stages'/r['operation_id'];checkpoint=native.store.root/'checkpoints'/r['operation_id']
bundle=f.load(OUT/'bundle.json')
fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json')
enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert [fence['before']['control']['generation'],fence['after']['control']['generation'],ready['control']['generation'],enabled['after']['control']['generation']]==[18,19,20,21]
assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
before=f.load(m.PRIVATE/'data-before.json');after=m.snapshot(state,'core23-data-after');updated=0
for table,oldrows in before.items():
    expected=copy.deepcopy(oldrows);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual),table
    if table=='mp_job':
        byid={row['public_id']:row for row in actual}
        for old in expected:
            new=byid[old['public_id']];changed={key for key in old if old[key]!=new[key]}
            assert changed<={'release_digest','claim_generation','dispatch_generation'},changed
            if changed:
                assert new['release_digest']==bundle['plan']['target_release_digest']
                assert new['claim_generation']==old['claim_generation']+1 and new['dispatch_generation']==20
                old.update({key:new[key] for key in changed});updated+=1
    assert expected==actual,table
reader=WorkerPlanningReader(native.store,native.target_path,m.LOCAL/'operator/worker-target.json')
entry=reader.publisher._document()['endpoints'][0]
observed=reader.observer(entry['descriptor'],reader.publisher._key_digest(entry['descriptor']),entry['key_id'])
info=json.loads(subprocess.check_output(['docker','inspect',observed['container_id']]))[0]
worker_after=dict(id=info['Id'],image=info['Image'],started=info['State']['StartedAt'],restarts=info['RestartCount'],
    mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],publication=data_digest(reader.publisher._document()))
assert worker_after==f.load(m.PRIVATE/'worker-before.json')
modules=json.loads(f.sql(state,'core23-modules-after',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"))
expected=f.load(m.PRIVATE/'modules-before.json')
for row in expected:
    if row['name']=='mp_core':
        assert row['version']=='19.0.0.1.22';row['version']='19.0.0.1.23'
assert modules==expected
files=json.loads(f.command('core23-files-after',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
oldfiles=f.load(m.PRIVATE/'files-before.json');retained={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for member in archive:
        if member.isfile() and member.name.startswith(prefix):
            retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert retained==oldfiles and all(files.get(name)==digest for name,digest in oldfiles.items())
catalog=Catalog(native.catalog_root,native.validator,readonly=True)
observation=native.observer.read();current=native.observer.state(observation,catalog.snapshot())['state']
baseline=f.load(OUT/'state-before.json')
assert all(current[key]==baseline[key] for key in ['installations','bindings','endpoints'])
impact=native.observer.native_impact(observation,catalog,site_id=state['site_id'],requested=['mp_example_notes_labels'])
assert impact['dispatch']['state']=='present_requires_fence' and len(impact['plugins'])==1 and len(impact['plugins'][0]['workspace_ids'])==2
f.save('installed-impact.json',impact);f.save('state-after.json',current)
path=m.LOCAL/'operator/worker-target.json';cfg=f.load(path);previous=copy.deepcopy(cfg)
assert cfg['helper_image']==baseline['image_id'];cfg['helper_image']=r['image_id'];f.write(path,cfg)
assert {key:value for key,value in previous.items() if key!='helper_image'}=={key:value for key,value in cfg.items() if key!='helper_image'}
assert m.worker(native,'core23-worker-after-helperpin')==f.load(m.PRIVATE/'worker-before.json')
f.save('preservation.json',dict(result='passed_actual_core23_maintenance_preservation',operation_id=r['operation_id'],
    image_id=r['image_id'],inventory_digest=r['inventory_digest'],configuration_generation=6,dispatch_generation=21,
    table_counts={name:len(rows) for name,rows in after.items()},all17tables_exact_except_reviewed_terminal_job_epochs=True,
    terminal_job_epoch_updates=updated,native_modules_exact_except_core22_to23=True,old_files_exact=len(oldfiles),
    checkpoint_files_exact=True,installations_bindings_endpoints_exact=True,worker_identity_image_key_publication_exact=True,
    worker_helper_only_advanced_to_approved_image=True,installed_readonly_uninstall_impact_scopes=2,
    limits=['Actual upgrade/preservation/read-only operator preview only; HTTP native views, app preview and actual uninstall/recovery still required.']))
r['state']='preservation_verified';f.write(m.PRIVATE/'state.json',r);f.phase(state,'core23_preservation_verified');f.guard(state)
print(json.dumps(dict(result='core23_preservation_passed',configuration=6,dispatch=21,files=len(oldfiles),jobs_updated=updated)))
