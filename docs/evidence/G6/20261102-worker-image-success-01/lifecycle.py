"""NEW normal metadata upgrade/enable after the original plan was recovered."""
import argparse,copy,hashlib,json,sys,tarfile
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from approve_runtime import ROOT,OUT,PRIVATE,context,op,base,f,j,previous
from modular_platform.contracts import validate_operations_view
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
s=previous.s
def path(action):return PRIVATE/(action+'.json')
def phase(record,value,action):record['state']=value;f.write(path(action),record)

def prepare(action):
    state,native=context();assert not path(action).exists() and action in ('upgrade','enable')
    assert native.config['generation']==(22 if action=='upgrade' else 23)
    runtime=f.load(PRIVATE/'runtime.json');assert runtime['state']=='current_image_published11'
    old=f.load(j.LOCAL/'worker-image-upgrade-01/metadata.json');assert native.store.status(old['operation_id'])['state']=='revoked'
    if action=='enable':assert f.load(path('upgrade'))['state']=='verified'
    before=base.snapshot(state,'image-final-'+action+'-before');assert len(before['mp_job'])==29
    f.write(PRIVATE/(action+'-before.json'),before);f.write(PRIVATE/(action+'-worker-before.json'),base.worker(native,'image-final-'+action+'-worker-before'))
    f.write(PRIVATE/(action+'-schema-before.json'),dict(digest=base.schema(state,'image-final-'+action+'-schema-before')))
    f.write(PRIVATE/(action+'-modules-before.json'),json.loads(f.sql(state,'image-final-'+action+'-modules-before','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;')))
    scope=old['scope'];record=dict(scope=scope,state='requesting',base_generation=native.config['generation'],retired_operation=old['operation_id']);phase(record,'requesting',action)
    client=s.client(state);nomination=dict(schema_version=1,operation='prepare',operation_type=action,plugin_id='org.example.document_stats',site_id=scope['site_id'],workspace_ids=[scope['workspace_id']],cascade=False)
    if action=='upgrade':nomination.update(artifact_version='0.1.2',artifact_digest=old['digest'])
    code,response=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf});assert code==200,(code,response)
    view=validate_operations_view(response['data']);assert view['targets']==[dict(**scope,plugin_id='org.example.document_stats',action=action)]
    assert view['restart_required'] and not view['native_trusted_code'] and view['operation_id']!=old['operation_id']
    record.update(operation_id=view['operation_id'],plan_hash=view['plan_hash']);phase(record,'prepared',action);f.save(action+'-preview.json',view)
    code,response=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=record['operation_id'],plan_hash=record['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf});assert code==200
    code,response=client.request('/api/v1/operations/bundle/'+record['operation_id']);assert code==200;bundle=response['data'];f.save(action+'-bundle.json',bundle)
    assert bundle['plan_hash']==record['plan_hash'] and not bundle['plan']['permission_changes'] and bundle['plan']['backup']['required']
    assert bundle['operation_lock']['release']['generation']==23
    canonical=[e for e in op(native).planning_state()['endpoints'] if all(e[k]==scope[k] for k in ['site_id','workspace_id','installation_id'])]
    assert bundle['operation_lock']['endpoints']==canonical and len(canonical)==1 and canonical[0]['generation']==9
    assert base.snapshot(state,'image-final-'+action+'-after-request')==before
    phase(record,'manager_requested',action);print(action+': NEW normal manager request captures current endpoint9/image548202; original plan stays revoked',flush=True)

def approve(action):
    state,native=context();record=f.load(path(action));assert record['state']=='manager_requested'
    ops=base.prefix()+['operations','--store',str(native.store.root)];phase(record,'importing_and_reviewing',action)
    f.save(action+'-import.json',json.loads(f.command('image-final-'+action+'-import',ops+['import-request',record['operation_id']]+base.validation(native))))
    review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];f.save(action+'-review.json',review)
    native._runtime_preflight(native.store.bundle(record['operation_id']))
    f.command('image-final-'+action+'-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+base.validation(native))
    phase(record,'approved',action);print(action+': exact new HTTP request independently reconstructed/reviewed/approved',flush=True)

def apply(action):
    state,native=context();record=f.load(path(action));assert record['state']=='approved';phase(record,'applying',action)
    f.phase(state,'image_final_'+action+'_applying')
    result=json.loads(f.command('image-final-'+action+'-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600))
    assert result['state']=='completed' and result['traffic_resumed'];f.save(action+'-completed.json',result)
    assert f.load(native.target_path)['generation']==23
    phase(record,'completed_needs_verification',action);print(action+': ordinary approved executor completed; exact preservation verification next',flush=True)

def verify(action):
    state,native=context();record=f.load(path(action));assert record['state']=='completed_needs_verification' and native.config['generation']==23
    before=f.load(PRIVATE/(action+'-before.json'));after=base.snapshot(state,'image-final-'+action+'-after');scope=record['scope']
    installation=next(r for r in before['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==scope['workspace_id'])
    bundle=f.load(OUT/(action+'-bundle.json'));stage=native.store.root/'stages'/record['operation_id'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    helper=ReferenceDispatchMaintenance(native);observed=helper.inspect();assert observed==enabled['after']
    assert helper.policy_for(observed)['profile']=='r1-reference-stateless-v1'
    changed_jobs=0
    for table,rows in before.items():
        expected=copy.deepcopy(rows);actual=after[table];assert len(expected)==len(actual)
        if table=='mp_plugin_installation' and action=='upgrade':
            row=next(r for r in expected if r['id']==installation['id']);current=next(r for r in actual if r['id']==row['id'])
            assert {k for k in row if row[k]!=current[k]}=={'version','artifact_digest','manifest'}
            assert current['version']=='0.1.2' and current['artifact_digest']==f.load(j.LOCAL/'worker-image-upgrade-01/metadata.json')['digest']
            row.update(**{k:current[k] for k in ['version','artifact_digest','manifest']})
        elif table=='mp_workspace_plugin':
            row=next(r for r in expected if r['installation_id']==installation['id'] and r['workspace_id']==workspace['id']);current=next(r for r in actual if r['id']==row['id'])
            assert row['availability']=='suspended' and current['availability']==('enabled' if action=='enable' else 'suspended')
            row.update(availability=current['availability'],write_date=current['write_date'])
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        elif table=='mp_job':
            byid={r['id']:r for r in actual}
            for row in expected:
                current=byid[row['id']];changed={k for k in row if row[k]!=current[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
                if changed:
                    assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==row['claim_generation']+1 and current['dispatch_generation']==ready['control']['generation']
                    row.update(**{k:current[k] for k in changed});changed_jobs+=1
        assert expected==actual,table+' outside reviewed metadata/feature/policy/queue footprint'
    assert base.schema(state,'image-final-'+action+'-schema-after')==f.load(PRIVATE/(action+'-schema-before.json'))['digest']
    modules=json.loads(f.sql(state,'image-final-'+action+'-modules-after','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'))
    assert modules==f.load(PRIVATE/(action+'-modules-before.json'))
    assert base.worker(native,'image-final-'+action+'-worker-after')==f.load(PRIVATE/(action+'-worker-before.json'))
    assert op(native).publisher._document()['generation']==11
    files=json.loads(f.command('image-final-'+action+'-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(native.store.root/'checkpoints'/record['operation_id']/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert len(retained)>=48 and all(files.get(p)==digest for p,digest in retained.items())
    assert native.store.status(record['retired_operation'])['state']=='revoked'
    f.save(action+'-preservation.json',dict(result='passed_actual_new_changed_image_metadata_'+action,operation_id=record['operation_id'],configuration_generation=23,
        dispatch_generation=observed['control']['generation'],old29job_outcomes_inputs_attempts_results_exact=True,changed_job_epochs=changed_jobs,
        all30Notes_other_native_data_auth_history_exact=True,schema_native_modules_exact=True,checkpoint_files_preserved=len(retained),
        current_worker_image_container_start_key_mount_network_publication11_exact=True,strict_default_reference_profile_restored=True,
        provider_feature='enabled' if action=='enable' else 'suspended',original_failed_plan_still_revoked=True,no_remote_process_control=True))
    phase(record,'verified',action);f.phase(state,'image_final_'+action+'_verified');print(action+': actual metadata/feature/native/jobs/files/current worker preservation verified; strict default profile active',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['upgrade','enable']);p.add_argument('step',choices=['prepare','approve','apply','verify']);a=p.parse_args();globals()[a.step](a.action)
