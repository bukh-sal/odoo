"""Versioned ID03 core20/identity1.5 correction retaining current worker and all data."""
import argparse,copy,hashlib,json,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerPlanningReader
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular_platform.plans import data_digest
f=j.f;f.OUTPUT=OUT;MARKER=j.LOCAL/'core20-upgrade-01.json';PRIVATE=j.LOCAL/'core20-upgrade'
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation',
    'mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership',
    'mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    return state,StagedNativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',
        j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))

def snapshot(state,label):
    query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT jsonb_build_object('
    query+=','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)
    return json.loads(f.sql(state,label,query+'); ROLLBACK;'))

def schema(state,label):
    query="""BEGIN READ ONLY; SELECT encode(sha256(convert_to(jsonb_agg(v ORDER BY v::text)::text,'UTF8')),'hex') FROM (
      SELECT jsonb_build_array(c.relname,c.relkind,a.attname,a.atttypid::regtype::text,a.attnotnull) v
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
      WHERE n.nspname='public' AND c.relkind IN ('r','p','S')) s; ROLLBACK;"""
    return f.sql(state,label,query).decode().strip()

def worker(native,label):
    op=WorkerPlanningReader(native.store,native.target_path,native.target_path.with_name('worker-target.json'))
    publication=op.publisher._document();scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope']
    endpoint=next(e for e in publication['endpoints'] if e['descriptor']['installation_id']==scope['installation_id'])
    public=op.publisher._key_digest(endpoint['descriptor']);attested=op.observer(endpoint['descriptor'],public,endpoint['key_id'])
    info=json.loads(f.command(label,['docker','inspect',attested['container_id']]))[0];assert info['State']['Running']
    return dict(container_id=info['Id'],image=info['Image'],started_at=info['State']['StartedAt'],restart_count=info['RestartCount'],
        mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],public_digest=public,publication_digest=data_digest(publication))

def prefix():return [sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
def options(native):return ['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def validation(native):return ['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]

def prepare():
    state,native=context();record=f.load(MARKER);assert record['state']=='candidate_validated' and native.config['generation']==27 and not PRIVATE.exists()
    from modular_platform.operator_os import protect_directory
    protect_directory(PRIVATE)
    build=f.load(ROOT/'docs/evidence/G7/20261102-core20-candidate-04/candidate-build.json')
    assert record['image_id']==build['image_id'] and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
    catalog=Catalog(native.catalog_root,native.validator,readonly=True)
    before=native.observer.state(native.observer.read(),catalog.snapshot())['state'];assert len(before['installations'])==9
    f.save('state-before.json',before);f.write(PRIVATE/'data-before.json',snapshot(state,'core20-data-before'))
    f.write(PRIVATE/'schema-before.json',dict(digest=schema(state,'core20-schema-before')))
    f.write(PRIVATE/'worker-before.json',worker(native,'core20-worker-before'))
    modules=json.loads(f.sql(state,'core20-modules-before',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;"))
    f.write(PRIVATE/'modules-before.json',modules)
    data=f.load(PRIVATE/'data-before.json');assert len(data['mp_job'])==36 and all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
    assert not any(r['state']=='leased' for r in data['mp_event_delivery'])
    record['state']='staging';f.write(MARKER,record);f.phase(state,'core20_staging')
    staged=json.loads(f.command('core20-stage',prefix()+['plugin','stage-image','--image-id',record['image_id']]+options(native)));f.save('staged-image.json',staged)
    finish_prepare()

def finish_prepare():
    state,native=context();record=f.load(MARKER);assert record['state']=='staging' and native.config['generation']==27
    before=f.load(OUT/'state-before.json');staged=f.load(OUT/'staged-image.json')
    assert snapshot(state,'core20-data-preplan-check')==f.load(PRIVATE/'data-before.json')
    current=native.observer.state(native.observer.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
    assert current==before,'Staging changed the independently observed preimage; inspect before planning'
    native_plugins={r['plugin_id'] for r in before['release_lock']['plugins'] if r['runtime']=='native'}
    nomination=dict(operation_type='core_upgrade',targets=[{k:r[k] for k in ('installation_id','site_id','workspace_id','plugin_id')}|dict(action='deploy')
        for r in before['installations'] if r['state']=='installed' and r['plugin_id'] in native_plugins])
    assert len(nomination['targets'])==8;f.save('nomination.json',nomination)
    bundle=json.loads(f.command('core20-plan',prefix()+['plugin','plan-staged','--input',str(OUT/'nomination.json')]+options(native)));f.save('bundle.json',bundle)
    changes=f.load(OUT/'candidate-admission.json')['native_changes']
    assert bundle['operation_lock']['native_core_changes']==changes
    assert bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
    assert [p for p in bundle['operation_lock']['release']['plugins'] if p['runtime']=='external_service']==[p for p in before['release_lock']['plugins'] if p['runtime']=='external_service']
    assert bundle['operation_lock']['bindings']==before['bindings'] and bundle['operation_lock']['endpoints']==before['endpoints']
    record.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(MARKER,record)
    ops=prefix()+['operations','--store',str(native.store.root)]
    f.command('core20-register',ops+['register','--bundle',str(OUT/'bundle.json')]+validation(native))
    f.save('independent-review.json',native.store.review(record['operation_id'],native._validate()))
    f.command('core20-approve',ops+['approve',record['operation_id'],'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-destructive']+validation(native))
    record['state']='approved';f.write(MARKER,record);f.phase(state,'core20_approved');f.guard(state)
    print('Core20/current shell10 native-only deployment targets independently reconstructed and approved; external pins retained')

def apply():
    state,native=context();record=f.load(MARKER);assert record['state']=='approved' and native.config['generation']==27
    record['state']='applying';f.write(MARKER,record);f.phase(state,'core20_applying')
    result=json.loads(f.command('core20-apply',prefix()+['plugin','apply',record['operation_id']]+options(native),timeout=600))
    assert result['state']=='completed' and result['traffic_resumed'];f.save('completed.json',result)
    config=f.load(native.target_path);assert config['generation']==28 and config['image_id']==record['image_id'] and config['sites'][0]['database']==state['active_db']
    state.update(image_id=config['image_id'],inventory_digest=record['inventory_digest']);record['state']='completed_needs_verification';f.write(MARKER,record)
    f.phase(state,'core20_completed_needs_verification');f.guard(state)
    print('Reviewed core20/current shell10 upgrade completed; exact populated preservation verification follows')

def verify(attempt='01'):
    state,native=context();record=f.load(MARKER);assert record['state']=='completed_needs_verification' and native.config['generation']==28
    operation=record['operation_id'];stage=native.store.root/'stages'/operation;checkpoint=native.store.root/'checkpoints'/operation
    bundle=f.load(OUT/'bundle.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert fence['before']['control']['generation']==126 and fence['after']['control']['generation']==127
    assert ready['control']['generation']==128 and enabled['after']['control']['generation']==129 and ready['external_installations']==1
    observed=ReferenceDispatchMaintenance(native).inspect();assert observed==enabled['after']
    assert observed['job_states']==dict(completed=15,dead_letter=19,cancelled=2)
    before=f.load(PRIVATE/'data-before.json');after=snapshot(state,'core20-data-after-'+attempt);updated=0;closed=0
    for table in TABLES:
        expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
        if table=='mp_job':
            byid={r['public_id']:r for r in actual}
            for old in expected:
                current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
                if changed:
                    assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==128
                    old.update(**{k:current[k] for k in changed});updated+=1
        elif table=='mp_event_subscription':
            for old in expected:
                if old['state']=='active':old['state']='closed';closed+=1
        assert expected==actual,table+' changed beyond exact release/queue fence effects'
    assert schema(state,'core20-schema-after-'+attempt)==f.load(PRIVATE/'schema-before.json')['digest']
    assert worker(native,'core20-worker-after-'+attempt)==f.load(PRIVATE/'worker-before.json')
    modules=json.loads(f.sql(state,'core20-modules-after-'+attempt,"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module; ROLLBACK;"))
    expected=f.load(PRIVATE/'modules-before.json')
    for row in expected:
        if row['name']=='mp_core':assert row['version']=='19.0.0.1.19';row['version']='19.0.0.1.20'
        if row['name']=='mp_identity':assert row['version']=='19.0.0.1.4';row['version']='19.0.0.1.5'
    assert expected==modules
    files=json.loads(f.command('core20-files-after-'+attempt,['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};path_prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(path_prefix):retained[member.name[len(path_prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    catalog=Catalog(native.catalog_root,native.validator,readonly=True).snapshot();current=native.observer.state(native.observer.read(),catalog)['state']
    base=f.load(OUT/'state-before.json');assert current['installations']==base['installations'] and current['bindings']==base['bindings'] and current['endpoints']==base['endpoints']
    f.save('state-after.json',current)
    cfg=j.LOCAL/'operator/worker-target.json';worker_config=f.load(cfg);previous=copy.deepcopy(worker_config)
    assert worker_config['helper_image']==f.load(OUT/'state-before.json')['image_id']
    worker_config['helper_image']=state['image_id'];f.write(cfg,worker_config)
    assert {k:v for k,v in worker_config.items() if k!='helper_image'}=={k:v for k,v in previous.items() if k!='helper_image'}
    assert worker(native,'core20-worker-after-helperpin-'+attempt)==f.load(PRIVATE/'worker-before.json')
    f.save('preservation.json',dict(result='passed_actual_core20_shell10_upgrade',operation_id=operation,image=state['image_id'],inventory=state['inventory_digest'],
        configuration_generation=28,dispatch_generation=129,counts={t:len(rows) for t,rows in after.items()},schema_columns_exact=True,
        full_native_module_state_versions_preserved_except_reviewed_core=True,all_business_metadata_authority_events_exact=True,
        old_jobs_outcomes_inputs_attempts_preserved=36,jobs_epoch_updated=updated,active_subscriptions_closed=closed,
        retained_checkpoint_files=len(retained),external_metadata_feature_bindings_endpoints_unchanged=True,
        independent_worker_identity_image_start_restart_mounts_network_key_publication_exact=True,helper_image_only_moved_to_approved_image=True,
        limits=['Upgrade/preservation only; installed manager HTTP/browser lifecycle and connector/remote/recovery/image-transition qualification remain.']))
    record['state']='preservation_verified';f.write(MARKER,record);f.phase(state,'core20_preservation_verified');f.guard(state)
    print('Core20/current shell10 preservation verified; external worker/publication, metadata, data/jobs/files intact; helper pin updated')

def verify_readonly():verify('02')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','finish_prepare','apply','verify','verify_readonly']);args=parser.parse_args();globals()[args.action]()
