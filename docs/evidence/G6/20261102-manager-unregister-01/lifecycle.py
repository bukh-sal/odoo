"""Actual HTTP manager metadata feature requests and independent handoff."""
import argparse,copy,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core15-upgrade-01'))
import activate as base
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
j=base.j;f=base.f;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'manager-unregister-01';MARKER=PRIVATE/'cycle.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    assert native.config['generation']==15 and native.config['image_id']==f.load(ROOT/'docs/evidence/G6/20261102-core15-candidate-01/candidate-build.json')['image_id']
    return state,native

def worker(native,label):
    from revoke import physical,operator
    from modular_platform.plans import data_digest
    return physical(native,label)|dict(publication_digest=data_digest(operator(native).publisher._document()))


def baseline():
    state,native=context();assert f.load(PRIVATE/'revocation.json')['state']=='verified' and not MARKER.exists()
    before=base.snapshot(state,'manager-unregister01-unregister-data-before')
    assert len(before['mp_job'])==19 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    assert not any(r['state']=='leased' for r in before['mp_event_delivery'])
    f.write(PRIVATE/'unregister-data-before.json',before)
    f.write(PRIVATE/'schema-before.json',dict(digest=base.schema(state,'manager-unregister01-feature-schema-before')))
    f.write(PRIVATE/'unregister-worker-before.json',worker(native,'manager-unregister01-feature-worker-before'))
    modules=json.loads(f.sql(state,'manager-unregister01-feature-modules-before','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'))
    f.write(PRIVATE/'modules-before.json',modules)
    requests=json.loads(f.sql(state,'manager-unregister01-feature-requests-before',"BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(public_id ORDER BY public_id),'[]'::jsonb) FROM mp_operation_request; ROLLBACK;"))
    setup=f.load(j.LOCAL/'provider-registration/setup.json');scope=setup['scope']
    inst=next(r for r in before['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
    feature=next(r for r in before['mp_workspace_plugin'] if r['installation_id']==inst['id']);assert feature['availability']=='enabled'
    observation=native.observer.read();current=native.observer.state(observation,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
    f.save('unregister-state-before.json',current)
    f.write(MARKER,dict(state='baseline_captured',scope=scope,before_request_ids=requests,baseline_at=datetime.now(timezone.utc).isoformat(),unregister=dict(state='awaiting_manager_request')))
    f.guard(state);print('Exact terminal-history baseline captured before manager HTTP nomination; no operation prepared yet')

def nominate_http():
    import r1_probe
    from uuid import uuid4
    from modular_platform.contracts import validate_operations_view
    r1_probe.r1.r0.LOCAL=j.LOCAL
    state,native=context();cycle=f.load(MARKER);assert cycle['unregister']['state']=='awaiting_manager_request'
    client=r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),'operator')
    nomination=dict(schema_version=1,operation='prepare',operation_type='unregister',plugin_id='org.example.document_stats',
        site_id=cycle['scope']['site_id'],workspace_ids=[],cascade=False)
    status,response=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf})
    assert status==200,dict(status=status,error=response.get('error',{}).get('code'))
    preview=validate_operations_view(response['data']);assert preview['restart_required'] and not preview['native_trusted_code']
    assert preview['targets']==[dict(**cycle['scope'],plugin_id='org.example.document_stats',action='unregister')]
    f.save('unregister-http-preview.json',preview)
    cycle['unregister'].update(state='http_prepared',operation_id=preview['operation_id'],plan_hash=preview['plan_hash']);f.write(MARKER,cycle)
    status,response=client.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=preview['operation_id'],
        plan_hash=preview['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':client.csrf})
    assert status==200
    requested=validate_operations_view(response['data']);assert requested['state']=='awaiting_operator_approval' and requested['source']=='application_request'
    f.save('unregister-http-request-status.json',requested)
    cycle['unregister']['state']='http_requested';f.write(MARKER,cycle)
    print('Installed manager HTTP preview and request succeed with truthful restart; no independent approval yet')

def capture_request():
    state,native=context();cycle=f.load(MARKER);assert cycle['unregister']['state']=='http_requested'
    rows=json.loads(f.sql(state,'manager-unregister01-unregister-app-request',"""BEGIN READ ONLY; SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'operation_id',r.public_id,'plan_hash',r.plan_hash,'requested',r.requested,'request_id',r.request_id,'user_id',p.user_id,
        'bundle',r.bundle,'base_state',r.base_state) ORDER BY r.id),'[]'::jsonb) FROM mp_operation_request r
        JOIN mp_principal p ON p.id=r.requested_by; ROLLBACK;"""))
    new=[r for r in rows if r['operation_id'] not in cycle['before_request_ids']];assert len(new)==1
    row=new[0];bundle=row['bundle'];scope=cycle['scope'];fixture=f.load(j.LOCAL/'fixtures.json')
    assert row['requested'] and row['request_id'] and row['user_id']==fixture['users']['operator']['id']
    assert bundle['plan']['operation_type']=='unregister' and bundle['plan_hash']==row['plan_hash']
    assert bundle['operation_lock']['targets']==[dict(**scope,plugin_id='org.example.document_stats',action='unregister')]
    assert bundle['display']['restart_required'] and not bundle['display']['native_code_requires_trust']
    assert bundle['plan']['backup']['required'] and bundle['operation_lock']['release']==native.config['published_release']
    assert base.snapshot(state,'manager-unregister01-unregister-data-after-nomination')==f.load(PRIVATE/'unregister-data-before.json')
    assert worker(native,'manager-unregister01-unregister-worker-after-nomination')==f.load(PRIVATE/'unregister-worker-before.json')
    f.save('unregister-manager-bundle.json',bundle);f.write(PRIVATE/'unregister-app-row.json',row)
    cycle['unregister'].update(state='manager_requested',operation_id=row['operation_id'],plan_hash=row['plan_hash']);f.write(MARKER,cycle)
    f.save('unregister-manager-request.json',dict(result='passed_actual_http_manager_request',operation_id=row['operation_id'],plan_hash=row['plan_hash'],
        existing_operator_uid=row['user_id'],exact_metadata_C_scope=True,host_restart_required=True,native_code_execution_requested=False,
        only_app_nomination_created=True,all17tables_and_independent_worker_unchanged=True,independent_approval_and_apply_not_performed=True,browser_rendering_tested=False))
    print('Exact HTTP manager request captured; original data/worker unchanged; independent authority still required')

def approve():
    state,native=context();cycle=f.load(MARKER);record=cycle['unregister'];assert record['state']=='manager_requested'
    prefix=base.prefix();validation=base.validation(native);ops=prefix+['operations','--store',str(native.store.root)]
    imported=json.loads(f.command('manager-unregister01-unregister-import',ops+['import-request',record['operation_id']]+validation));f.save('unregister-import.json',imported)
    status=native.store.status(record['operation_id']);assert status['state']=='awaiting_operator_approval' and not status['mutation_started']
    review=native.store.review(record['operation_id'],native._validate());assert review['plan_hash']==record['plan_hash'];f.save('unregister-independent-review.json',review)
    native._runtime_preflight(native.store.bundle(record['operation_id']))
    f.command('manager-unregister01-unregister-approve',ops+['approve',record['operation_id'],'--plan-hash',record['plan_hash'],'--noninteractive','--ack-trust']+(['--ack-destructive'] if native.store.bundle(record['operation_id'])['plan']['destructive'] else [])+validation)
    record['state']='approved';f.write(MARKER,cycle);f.phase(state,'manager_unregister01_metadata_unregister_approved');f.guard(state)
    print('Same HTTP manager request imported and independently reconstructed/reviewed/exact approved; no feature mutation yet')

def apply():
    state,native=context();cycle=f.load(MARKER);record=cycle['unregister'];assert record['state']=='approved'
    record['state']='applying';f.write(MARKER,cycle);f.phase(state,'manager_unregister01_metadata_unregister_applying')
    completed=json.loads(f.command('manager-unregister01-unregister-apply',base.prefix()+['plugin','apply',record['operation_id']]+base.options(native),timeout=600))
    assert completed['state']=='completed' and completed['traffic_resumed'];f.save('unregister-completed.json',completed)
    record['state']='completed_needs_verification';f.write(MARKER,cycle);f.phase(state,'manager_unregister01_metadata_unregister_needs_verification')
    print('Same manager-unregister01-created unregistration completed through independent checkpointed executor; verification follows')


def verify():
    state,native=context();cycle=f.load(MARKER);record=cycle['unregister'];assert record['state']=='completed_needs_verification'
    before=f.load(PRIVATE/'unregister-data-before.json');after=base.snapshot(state,'manager-unregister01-data-after');scope=cycle['scope']
    installation=next(r for r in before['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==scope['workspace_id']);updated=0
    bundle=f.load(OUT/'unregister-manager-bundle.json')
    assert bundle['operation_lock']['release']==native.config['published_release']
    assert not any(r['descriptor']['provider_installation_id']==scope['installation_id'] or r['descriptor']['consumer_installation_id']==scope['installation_id'] for r in before['mp_service_binding'])
    for table in before:
        expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
        if table=='mp_plugin_installation':
            old=next(r for r in expected if r['id']==installation['id']);assert old['state']=='installed';old['state']='removed'
        elif table=='mp_workspace_plugin':
            old=next(r for r in expected if r['installation_id']==installation['id'] and r['workspace_id']==workspace['id'])
            current=next(r for r in actual if r['id']==old['id']);assert old['availability']=='enabled' and current['availability']=='suspended'
            assert current['write_date']>=old['write_date'];old.update(availability='suspended',write_date=current['write_date'])
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        elif table=='mp_plugin_grant':
            for old in expected:
                if old['installation_id']==installation['id'] and old['state']=='approved':
                    assert old['workspace_id']==workspace['id'];old.update(state='revoked',policy_version=bundle['plan']['policy_version'])
        elif table=='mp_service_credential':
            for old in expected:
                if old['installation_public_id']==scope['installation_id'] and old['state']=='active':old['state']='revoked'
        elif table=='mp_job':
            byid={r['public_id']:r for r in actual}
            for old in expected:
                current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]};assert changed<={'claim_generation','dispatch_generation'}
                if changed:
                    assert current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==75
                    old.update(**{k:current[k] for k in changed});updated+=1
        assert expected==actual,table+' changed outside exact unregister effects'
    assert base.schema(state,'manager-unregister01-schema-after')==f.load(PRIVATE/'schema-before.json')['digest']
    modules=json.loads(f.sql(state,'manager-unregister01-modules-after','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'))
    assert modules==f.load(PRIVATE/'modules-before.json')
    assert worker(native,'manager-unregister01-worker-after')==f.load(PRIVATE/'unregister-worker-before.json')
    stage=native.store.root/'stages'/record['operation_id'];checkpoint=native.store.root/'checkpoints'/record['operation_id']
    ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert ready['control']['generation']==75 and enabled['after']['control']['generation']==76
    assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
    assert f.load(stage/'metadata.log')==dict(metadata_published=True,operation_id=record['operation_id'],native_maintenance=False,runtime_control=False)
    files=json.loads(f.command('manager-unregister01-files-after',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    f.save('unregister-preservation.json',dict(result='passed_actual_http_manager_requested_metadata_unregister',operation_id=record['operation_id'],plan_hash=record['plan_hash'],
        configuration_generation=15,dispatch_generation=76,release_unchanged=True,metadata_retained_removed_feature_suspended=True,
        native_module_rows_and_schema_exact=True,independent_worker_physical_identity_public_key_and_revoked_publication4_exact=True,
        all17table_original_rows_preserved_under_exact_metadata_feature_grant_policy_epoch_changes=True,
        old_job_outcomes_inputs_attempts_exact=19,jobs_epoch_updated=updated,old_checkpoint_files_preserved=len(retained),
        metadata_child_has_no_native_or_external_runtime_control=True,
        limits=['No native required consumer installed yet; closure refusal has source coverage only.','No remote/in-flight/recovery/changedimage/browser qualification.']))
    record['state']='preservation_verified';f.write(MARKER,cycle);f.phase(state,'manager_unregister01_metadata_unregister_verified');f.guard(state)
    print('Actual metadata unregister preserves native/data/jobs/files and separately running worker; only approved metadata/grants/policy/epochs change')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','nominate_http','capture_request','approve','apply','verify']);args=p.parse_args();globals()[args.action]()
