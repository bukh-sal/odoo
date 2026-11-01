"""Actual reviewed metadata registration; independently operated worker untouched."""
import argparse,copy,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from setup import ROOT,OUT,j,f,PRIVATE,MARKER,command
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerOperator
from modular_platform.restore_continuation import FILE_OBSERVATION
from modular_platform.plans import data_digest
from uuid import uuid4
REGISTRATION=PRIVATE/'registration.json'
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation',
    'mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership',
    'mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),
        j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,native

def snapshot(state,label):
    query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT jsonb_build_object("
    query+=','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)
    return json.loads(f.sql(state,label,query+'); ROLLBACK;'))

def schema(state,label):
    query="""BEGIN READ ONLY; SELECT encode(sha256(convert_to(jsonb_agg(v ORDER BY v::text)::text,'UTF8')),'hex') FROM (
      SELECT jsonb_build_array(c.relname,c.relkind,a.attname,a.atttypid::regtype::text,a.attnotnull) v
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
      WHERE n.nspname='public' AND c.relkind IN ('r','p','S')
    ) s; ROLLBACK;"""
    return f.sql(state,label,query).decode().strip()

def worker(native,label):
    op=WorkerOperator(native.store,native.target_path,native.target_path.with_name('worker-target.json'))
    publication=op.publisher._document();setup=f.load(MARKER)
    endpoint=next(e for e in publication['endpoints'] if e['descriptor']['installation_id']==setup['scope']['installation_id'])
    public_digest=op.publisher._key_digest(endpoint['descriptor'])
    attested=op.observer(endpoint['descriptor'],public_digest,endpoint['key_id'])
    info=json.loads(command(label,['docker','inspect',attested['container_id']]))[0]
    stable=dict(container_id=info['Id'],image=info['Image'],started_at=info['State']['StartedAt'],restart_count=info['RestartCount'],
        mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],public_digest=public_digest,publication_digest=data_digest(publication))
    assert info['State']['Running'];return stable

def prepare():
    state,native=context();setup=f.load(MARKER);assert setup['state']=='worker_published' and not REGISTRATION.exists()
    assert native.config['generation']==11
    nomination=dict(operation_type='install',targets=[dict(**setup['scope'],plugin_id='org.example.document_stats',action='install')],
        selections=[dict(plugin_id='org.example.document_stats',version='0.1.0',digest=setup['artifact_digest'])],
        feature_states=[dict(**setup['scope'],availability='suspended')])
    f.save('register-nomination.json',nomination)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    bundle=json.loads(command('plan-registration',prefix+['plugin','plan-external','--input',str(OUT/'register-nomination.json')]+options))
    native._runtime_preflight(bundle);f.save('register-bundle.json',bundle)
    assert len(bundle['plan']['artifacts'])==1 and bundle['plan']['artifacts'][0]['runtime']=='external_service'
    assert bundle['plan']['artifacts'][0]['native_addon'] is None and not bundle['plan']['permission_changes']
    before=snapshot(state,'provider-register-before');f.write(PRIVATE/'data-before.json',before)
    f.write(PRIVATE/'schema-before.json',dict(digest=schema(state,'provider-register-schema-before')))
    f.write(PRIVATE/'worker-before.json',worker(native,'worker-before-registration'))
    observation=native.observer.read();document=native.observer.state(observation,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())
    f.save('register-state-before.json',document['state'])
    marker=dict(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(REGISTRATION,marker)
    ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    command('register-operation',ops+['register','--bundle',str(OUT/'register-bundle.json')]+validation)
    f.save('register-independent-review.json',native.store.review(marker['operation_id'],native._validate()))
    command('approve-registration',ops+['approve',marker['operation_id'],'--plan-hash',marker['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+validation)
    marker['state']='approved';f.write(REGISTRATION,marker);f.phase(state,'provider_registration_approved');f.guard(state)
    print('Exact suspended metadata registration independently reconstructed/approved; no database mutation yet')

def approve():
    state,native=context();marker=f.load(REGISTRATION);assert marker['state']=='prepared'
    status=native.store.status(marker['operation_id']);assert status['state']=='awaiting_operator_approval' and not status['mutation_started']
    bundle=native.store.bundle(marker['operation_id'])
    declaration=bundle['operation_lock']['declaration_changes']['org.example.document_stats']
    assert set(declaration['target_permissions']['defines'])=={'analysis.run'}
    assert not declaration['target_permissions']['requests'] and not bundle['plan']['permission_changes']
    f.save('register-independent-review-02.json',native.store.review(marker['operation_id'],native._validate()))
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    command('approve-registration-declarations',prefix+['operations','--store',str(native.store.root),'approve',marker['operation_id'],
        '--plan-hash',marker['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions',
        '--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)])
    marker['state']='approved';f.write(REGISTRATION,marker);f.phase(state,'provider_registration_approved');f.guard(state)
    print('Same exact plan freshly reviewed and approved with explicit capability declaration acknowledgement')

def apply():
    state,native=context();marker=f.load(REGISTRATION);assert marker['state']=='approved' and native.config['generation']==11
    marker['state']='applying';f.write(REGISTRATION,marker);f.phase(state,'provider_registration_applying')
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    result=json.loads(command('apply-registration',prefix+['plugin','apply',marker['operation_id'],'--store',str(native.store.root),
        '--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)],timeout=600))
    assert result['state']=='completed';f.save('register-completed.json',result)
    config=f.load(native.target_path);assert config['generation']==12 and config['image_id']==state['image_id']
    marker['state']='completed_needs_verification';f.write(REGISTRATION,marker);f.phase(state,'provider_registration_needs_verification')
    print('Metadata registration committed through reviewed lifecycle; detailed verification follows')

def capture_native_modules():
    state,native=context();assert f.load(REGISTRATION)['state']=='approved' and native.config['generation']==11
    path=PRIVATE/'native-modules-before.json';assert not path.exists()
    rows=json.loads(f.sql(state,'provider-all-native-modules-before',"BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;"))
    f.write(path,rows)
    print('Read-only full native module baseline captured before metadata mutation')

def verify():
    state,native=context();marker=f.load(REGISTRATION);assert marker['state']=='completed_needs_verification'
    setup=f.load(MARKER);bundle=f.load(OUT/'register-bundle.json');operation=marker['operation_id']
    stage=native.store.root/'stages'/operation;checkpoint=native.store.root/'checkpoints'/operation
    assert native.store.status(operation)['state']=='completed' and native.config['generation']==12
    before=f.load(PRIVATE/'data-before.json');after=snapshot(state,'provider-register-after')
    assert schema(state,'provider-register-schema-after')==f.load(PRIVATE/'schema-before.json')['digest']
    assert worker(native,'worker-after-registration')==f.load(PRIVATE/'worker-before.json')
    oldinst={r['public_id'] for r in before['mp_plugin_installation']};newinst=[r for r in after['mp_plugin_installation'] if r['public_id'] not in oldinst]
    assert len(newinst)==1;new=newinst[0]
    assert (new['public_id'],new['plugin_id'],new['version'],new['artifact_digest'],new['runtime'],new['state'])==(
        setup['scope']['installation_id'],'org.example.document_stats','0.1.0',setup['artifact_digest'],'external_service','installed')
    newfeatures=[r for r in after['mp_workspace_plugin'] if r['installation_id']==new['id']]
    assert len(newfeatures)==1 and newfeatures[0]['availability']=='suspended'
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==setup['scope']['workspace_id']);assert newfeatures[0]['workspace_id']==workspace['id']
    ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert ready['profile']=='r1-reference-stateless-dispatch-v1' and ready['external_installations']==1
    assert ready['control']['generation']==54 and enabled['after']['control']['generation']==55
    assert f.load(stage/'dispatch-fence/fence.json')['result']['before']['control']['generation']==52
    updated_jobs=0
    for table in TABLES:
        expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table])
        if table=='mp_plugin_installation':actual=[r for r in actual if r['public_id'] in oldinst]
        elif table=='mp_workspace_plugin':actual=[r for r in actual if r['installation_id']!=new['id']]
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        elif table=='mp_job':
            byid={r['public_id']:r for r in actual};assert len(byid)==len(expected)==19
            for old in expected:
                current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]}
                assert changed<={'release_digest','claim_generation','dispatch_generation'}
                if changed:
                    assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==54
                    old.update(**{k:current[k] for k in changed});updated_jobs+=1
        assert expected==actual,table+' changed beyond exact metadata registration'
    observation=native.observer.read();current=native.observer.state(observation,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
    old=f.load(OUT/'register-state-before.json');assert len(current['installations'])==8
    assert [r for r in current['installations'] if r['plugin_id']!='org.example.document_stats']==old['installations']
    assert current['bindings']==old['bindings'] and current['release_lock']==bundle['operation_lock']['release']
    pin=next(p for p in current['release_lock']['plugins'] if p['runtime']=='external_service');assert pin['native_addon'] is None
    modules=json.loads(f.sql(state,'provider-all-native-modules-after',"BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;"))
    assert modules==f.load(PRIVATE/'native-modules-before.json')
    assert not any('document_stats' in m['addon'] for m in observation['sites'][0]['native_modules'])
    assert f.load(stage/'native-skipped.json')['reason'].startswith('Reviewed metadata publication only')
    assert f.load(stage/'metadata.log')==dict(metadata_published=True,operation_id=operation,native_maintenance=False,runtime_control=False)
    files=json.loads(command('registration-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    f.save('register-state-after.json',current)
    f.save('register-qualification.json',dict(result='passed_actual_suspended_metadata_registration',operation_id=operation,
        image=native.config['image_id'],configuration_generation=12,dispatch_generation=55,publication_generation=3,
        canonical_scope=setup['scope'],artifact_digest=setup['artifact_digest'],native_addon_and_schema_unchanged=True,
        worker_identity_image_start_restart_mounts_network_key_and_publication_exact=True,
        no_runtime_launch_stop_or_remote_erase_by_installer=True,all_original_business_authority_event_metadata_rows_preserved=True,
        original_job_rows_preserved_except_exact_epoch_fields=19,jobs_epoch_updated=updated_jobs,old_checkpoint_files_preserved=len(retained),
        limits=['Registration only, feature suspended. Enable/suspend/upgrade/unregister, connector/remote/degraded and external recovery still required.',
            'Worker is separately operated; no external non-idempotent effect is claimed.']))
    marker['state']='verified';f.write(REGISTRATION,marker);f.phase(state,'provider_registered_suspended_verified');f.guard(state)
    print('Actual suspended metadata registration verified: no native addon/schema/runtime control; original data/files preserved')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','approve','capture_native_modules','apply','verify']);args=parser.parse_args();globals()[args.action]()
