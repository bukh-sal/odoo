"""Actual browser-created metadata feature requests and independent handoff."""
import argparse,copy,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core14-upgrade-01'))
import activate as base
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
j=base.j;f=base.f;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'manager-feature-01';MARKER=PRIVATE/'cycle.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    assert native.config['generation']==14 and native.config['image_id']==f.load(ROOT/'docs/evidence/G6/20261102-core14-candidate-01/candidate-build.json')['image_id']
    return state,native

def baseline():
    state,native=context();assert not PRIVATE.exists();protect_directory(PRIVATE)
    before=base.snapshot(state,'manager-suspend-data-before')
    assert len(before['mp_job'])==19 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    assert not any(r['state']=='leased' for r in before['mp_event_delivery'])
    f.write(PRIVATE/'suspend-data-before.json',before)
    f.write(PRIVATE/'schema-before.json',dict(digest=base.schema(state,'manager-feature-schema-before')))
    f.write(PRIVATE/'worker-before.json',base.worker(native,'manager-feature-worker-before'))
    modules=json.loads(f.sql(state,'manager-feature-modules-before','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'))
    f.write(PRIVATE/'modules-before.json',modules)
    requests=json.loads(f.sql(state,'manager-feature-requests-before',"BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(public_id ORDER BY public_id),'[]'::jsonb) FROM mp_operation_request; ROLLBACK;"))
    setup=f.load(j.LOCAL/'provider-registration/setup.json');scope=setup['scope']
    inst=next(r for r in before['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
    feature=next(r for r in before['mp_workspace_plugin'] if r['installation_id']==inst['id']);assert feature['availability']=='enabled'
    observation=native.observer.read();current=native.observer.state(observation,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
    f.save('suspend-state-before.json',current)
    f.write(MARKER,dict(state='baseline_captured',scope=scope,before_request_ids=requests,baseline_at=datetime.now(timezone.utc).isoformat(),suspend=dict(state='awaiting_browser_request')))
    f.guard(state);print('Exact terminal-history baseline captured before browser nomination; no operation prepared yet')

def capture_request():
    state,native=context();cycle=f.load(MARKER);assert cycle['suspend']['state']=='awaiting_browser_request'
    rows=json.loads(f.sql(state,'manager-suspend-app-request',"""BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'operation_id',r.public_id,'plan_hash',r.plan_hash,'requested',r.requested,'request_id',r.request_id,'user_id',p.user_id,
        'bundle',r.bundle,'base_state',r.base_state) ORDER BY r.id),'[]'::jsonb) FROM mp_operation_request r
        JOIN mp_principal p ON p.id=r.requested_by; ROLLBACK;"""))
    new=[r for r in rows if r['operation_id'] not in cycle['before_request_ids']];assert len(new)==1
    row=new[0];bundle=row['bundle'];scope=cycle['scope'];fixture=f.load(j.LOCAL/'fixtures.json')
    assert row['requested'] and row['request_id'] and row['user_id']==fixture['users']['operator']['id']
    assert bundle['plan']['operation_type']=='suspend' and bundle['plan_hash']==row['plan_hash']
    assert bundle['operation_lock']['targets']==[dict(**scope,plugin_id='org.example.document_stats',action='suspend')]
    assert bundle['display']['restart_required'] and not bundle['display']['native_code_requires_trust']
    assert bundle['plan']['backup']['required'] and bundle['operation_lock']['release']==native.config['published_release']
    assert base.snapshot(state,'manager-suspend-data-after-nomination')==f.load(PRIVATE/'suspend-data-before.json')
    assert base.worker(native,'manager-suspend-worker-after-nomination')==f.load(PRIVATE/'worker-before.json')
    f.save('suspend-browser-bundle.json',bundle);f.write(PRIVATE/'suspend-app-row.json',row)
    cycle['suspend'].update(state='browser_requested',operation_id=row['operation_id'],plan_hash=row['plan_hash']);f.write(MARKER,cycle)
    f.save('suspend-browser-request.json',dict(result='passed_actual_browser_manager_request',operation_id=row['operation_id'],plan_hash=row['plan_hash'],
        existing_operator_uid=row['user_id'],exact_metadata_C_scope=True,host_restart_required=True,native_code_execution_requested=False,
        only_app_nomination_created=True,all17tables_and_independent_worker_unchanged=True,independent_approval_and_apply_not_performed=True))
    print('Exact browser-created request captured; original data/worker unchanged; independent authority still required')

def approve():
    state,native=context();cycle=f.load(MARKER);record=cycle['suspend'];assert record['state']=='browser_requested'
    prefix=base.prefix();validation=base.validation(native);ops=prefix+['operations','--store',str(native.store.root)]
    imported=json.loads(f.command('manager-suspend-import',ops+['import-request',record['operation_id']]+validation));f.save('suspend-import.json',imported)
    status=native.store.status(record['operation_id']);assert status['state']=='awaiting_operator_approval' and not status['mutation_started']
    review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];f.save('suspend-independent-review.json',review)
    native._runtime_preflight(native.store.bundle(record['operation_id']))
    f.command('manager-suspend-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+validation)
    record['state']='approved';f.write(MARKER,cycle);f.phase(state,'manager_metadata_suspend_approved');f.guard(state)
    print('Same browser request imported and independently reconstructed/reviewed/exact approved; no feature mutation yet')

def apply():
    state,native=context();cycle=f.load(MARKER);record=cycle['suspend'];assert record['state']=='approved'
    record['state']='applying';f.write(MARKER,cycle);f.phase(state,'manager_metadata_suspend_applying')
    completed=json.loads(f.command('manager-suspend-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600))
    assert completed['state']=='completed' and completed['traffic_resumed'];f.save('suspend-completed.json',completed)
    record['state']='completed_needs_verification';f.write(MARKER,cycle);f.phase(state,'manager_metadata_suspend_needs_verification')
    print('Same manager-created suspension completed through independent checkpointed executor; verification follows')

def verify():
    state,native=context();cycle=f.load(MARKER);record=cycle['suspend'];assert record['state']=='completed_needs_verification'
    before=f.load(PRIVATE/'suspend-data-before.json');after=base.snapshot(state,'manager-suspend-data-after');scope=cycle['scope']
    inst=next(r for r in before['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==scope['workspace_id']);updated=0
    bundle=f.load(OUT/'suspend-browser-bundle.json');cutoff=datetime.fromisoformat(bundle['plan']['created_at'].replace('Z','+00:00'))
    for table in before:
        expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
        if table=='mp_workspace_plugin':
            old=next(r for r in expected if r['installation_id']==inst['id'] and r['workspace_id']==workspace['id']);current=next(r for r in actual if r['id']==old['id'])
            assert old['availability']=='enabled' and current['availability']=='suspended'
            assert cutoff<=datetime.fromisoformat(current['write_date']).replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc)
            old.update(availability='suspended',write_date=current['write_date'])
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        elif table=='mp_job':
            byid={r['public_id']:r for r in actual}
            for old in expected:
                current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]};assert changed<={'claim_generation','dispatch_generation'}
                if changed:
                    assert current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==66
                    old.update(**{k:current[k] for k in changed});updated+=1
        assert expected==actual,table+' changed beyond exact suspension/policy/epoch effects'
    assert base.schema(state,'manager-feature-schema-after-suspend')==f.load(PRIVATE/'schema-before.json')['digest']
    modules=json.loads(f.sql(state,'manager-feature-modules-after-suspend','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'))
    assert modules==f.load(PRIVATE/'modules-before.json')
    assert base.worker(native,'manager-feature-worker-after-suspend')==f.load(PRIVATE/'worker-before.json')
    stage=native.store.root/'stages'/record['operation_id'];checkpoint=native.store.root/'checkpoints'/record['operation_id']
    ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert ready['control']['generation']==66 and enabled['after']['control']['generation']==67 and ready['external_installations']==1
    assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
    assert native.config['published_release']==bundle['operation_lock']['release']
    assert f.load(stage/'metadata.log')==dict(metadata_published=True,operation_id=record['operation_id'],native_maintenance=False,runtime_control=False)
    files=json.loads(f.command('manager-suspend-files-after',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};path_prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(path_prefix):retained[member.name[len(path_prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    f.save('suspend-preservation.json',dict(result='passed_actual_browser_requested_metadata_suspend',operation_id=record['operation_id'],plan_hash=record['plan_hash'],
        configuration_generation=14,dispatch_generation=67,release_unchanged=True,native_module_rows_and_schema_exact=True,
        external_worker_identity_image_start_restart_mounts_network_key_publication_exact=True,
        all17table_original_rows_preserved_under_exact_feature_policy_epoch_changes=True,old_job_outcomes_inputs_attempts_exact=19,jobs_epoch_updated=updated,
        old_checkpoint_files_preserved=len(retained),metadata_child_has_no_native_or_external_runtime_control=True,
        limits=['Terminal-history queues only; no in-flight remote race or external effects recovery.','Post-suspension browser/host invocation checks and enable/unregister remain separate.']))
    record['state']='preservation_verified';f.write(MARKER,cycle);f.phase(state,'manager_metadata_suspend_verified');f.guard(state)
    print('Actual manager suspension preserved native/data/jobs/files and independent worker; only scoped feature/policy/epochs changed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','capture_request','approve','apply','verify']);args=p.parse_args();globals()[args.action]()
