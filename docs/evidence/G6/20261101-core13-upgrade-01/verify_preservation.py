"""Actual core13 queues/business/authority/files preservation; no mutation replay."""
import copy,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from activate import ROOT,OUT,j,f,MARKER,context,data_snapshot,TABLES
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION

def main():
    state,native=context();record=f.load(MARKER)
    assert record['state']=='completed_needs_qualification' and native.config['generation']==11
    operation=record['operation_id'];stage=native.store.root/'stages'/operation;checkpoint=native.store.root/'checkpoints'/operation
    fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert fence['before']['control']['generation']==43
    assert fence['after']['control']['generation']==44 and ready['control']['generation']==45 and enabled['after']['control']['generation']==46
    observed=DispatchMaintenance(native).inspect();assert observed==enabled['after']
    assert observed['job_states']==dict(completed=6,dead_letter=10,cancelled=2)
    before=f.load(j.LOCAL/'core13-preservation-before.json');after=data_snapshot(state,'core13-preservation-after')
    allowed_jobs={'release_digest','claim_generation','dispatch_generation'};backfills=[];updated_jobs=0;closed_subscriptions=0
    oldjobs={r['public_id']:r for r in before['mp_job']};newjobs={r['public_id']:r for r in after['mp_job']}
    assert set(oldjobs)==set(newjobs) and len(oldjobs)==18
    cutoff=datetime.fromisoformat(f.load(OUT/'bundle.json')['plan']['created_at'].replace('Z','+00:00'))
    for ident,old in oldjobs.items():
        new=copy.deepcopy(newjobs[ident]);changed={k for k in old if old[k]!=new[k]}
        if 'finished_at' in changed:
            assert ident==f.load(j.LOCAL/'core12-cancel-seed.json')['job_id']
            assert old['state']==new['state']=='cancelled' and old['finished_at'] is None
            stamp=datetime.fromisoformat(new['finished_at']).replace(tzinfo=timezone.utc)
            assert cutoff<=stamp<=datetime.now(timezone.utc)
            new['finished_at']=None;changed.remove('finished_at');backfills.append(ident)
        assert changed<=allowed_jobs
        if changed:
            assert new['release_digest']==f.load(OUT/'bundle.json')['plan']['target_release_digest']
            assert new['claim_generation']==old['claim_generation']+1 and new['dispatch_generation']==45
            updated_jobs+=1
        assert {k:v for k,v in old.items() if k not in allowed_jobs}=={k:v for k,v in new.items() if k not in allowed_jobs}
    for table in TABLES:
        if table=='mp_job':continue
        if table=='mp_event_subscription':
            expected=copy.deepcopy(before[table])
            for row in expected:
                if row['state']=='active':row['state']='closed';closed_subscriptions+=1
            assert after[table]==expected
        else:assert before[table]==after[table],table+' changed'
    assert len(backfills)<=1
    app=native.observer._container('app')
    files=json.loads(f.command('core13-current-files',['docker','exec',app,'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    expected={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):expected[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert expected and all(files.get(name)==digest for name,digest in expected.items())
    sql="BEGIN READ ONLY; SELECT jsonb_build_object('core',(SELECT latest_version FROM ir_module_module WHERE name='mp_core'),'identity',(SELECT latest_version FROM ir_module_module WHERE name='mp_identity'),'shell',(SELECT latest_version FROM ir_module_module WHERE name='mp_shell')); ROLLBACK;"
    versions=json.loads(f.sql(state,'core13-native-versions',sql));assert versions==dict(core='19.0.0.1.13',identity='19.0.0.1.2',shell='19.0.0.1.9')
    cfg=j.LOCAL/'operator/worker-target.json';worker=f.load(cfg);previous_hash=hashlib.sha256(cfg.read_bytes()).hexdigest()
    assert worker['helper_image']==f.load(ROOT/'docs/evidence/G6/20261101-core12-candidate-01/candidate-build.json')['image_id']
    previous=copy.deepcopy(worker);worker['helper_image']=state['image_id'];f.write(cfg,worker)
    assert {k:v for k,v in worker.items() if k!='helper_image'}=={k:v for k,v in previous.items() if k!='helper_image'}
    f.save('preservation.json',dict(result='passed_actual_core13_upgrade_preservation',image=state['image_id'],inventory=state['inventory_digest'],
        configuration_generation=11,dispatch_generation=46,native_versions=versions,same_database=True,
        counts={t:len(rows) for t,rows in after.items()},original_business_metadata_authority_event_rows_exact=True,
        allowed_active_subscriptions_closed=closed_subscriptions,original_jobs_preserved_except_reviewed_epoch_fields=True,
        reconciled_job_epoch_rows=updated_jobs,sanctioned_cancelled_null_timestamp_backfills=len(backfills),
        old_checkpoint_files_preserved=len(expected),all_current_files=len(files),
        worker_helper_update=dict(previous_sha256=previous_hash,current_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),only_field='helper_image'),
        limits=['Native feature and external metadata/connector/remote/lifecycle/recovery still require installed qualification.',
            'No actual external provider or connector is installed by this core-only operation.']))
    record['state']='preservation_verified';f.write(MARKER,record);f.phase(state,'core13_preservation_verified');f.guard(state)
    print('Core13 installed: business/metadata/authority/events/jobs/files preserved; helper pin updated to approved image')

if __name__=='__main__':main()
