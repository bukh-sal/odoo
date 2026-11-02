"""Required Notes closure and optional metadata provider lifecycle with connector."""
import argparse,copy,hashlib,json,sys,tarfile
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-notes-stats-remote-01'))
import remote as positive
base,f,j=positive.base,positive.f,positive.j
from modular import configuration
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.contracts import validate_operations_view
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'worker-image-upgrade-01';MARKER=PRIVATE/'cycle.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    assert native.config['generation']==20
    return state,native
def phase(cycle,mode,value):cycle[mode]['state']=value;f.write(MARKER,cycle)
def client(state,actor='operator'):return positive.r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),actor)

def baseline(mode):
    state,native=context()
    if mode=='suspend':
        assert not PRIVATE.exists();protect_directory(PRIVATE);cycle=dict(scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope'])
    else:
        cycle=f.load(MARKER);assert cycle['suspend']['state']=='probe_verified' and mode not in cycle
    before=base.snapshot(state,'image-transition-'+mode+'-before');assert len(before['mp_job'])==29
    assert all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    f.write(PRIVATE/(mode+'-data-before.json'),before)
    f.write(PRIVATE/(mode+'-worker-before.json'),base.worker(native,'image-transition-'+mode+'-worker-before'))
    f.write(PRIVATE/(mode+'-schema-before.json'),dict(digest=base.schema(state,'image-transition-'+mode+'-schema-before')))
    modules=json.loads(f.sql(state,'image-transition-'+mode+'-modules-before','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'))
    f.write(PRIVATE/(mode+'-modules-before.json'),modules)
    cycle[mode]=dict(state='baseline_captured');f.write(MARKER,cycle);print(mode+': fresh populated terminal-history baseline captured',flush=True)

def request(mode):
    state,native=context();cycle=f.load(MARKER);assert cycle[mode]['state']=='baseline_captured';c=client(state);scope=cycle['scope']
    def prepare(plugin,cascade=False):
        return c.request('/api/v1/operations/prepare',dict(schema_version=1,operation='prepare',operation_type='suspend' if mode=='suspend' else 'enable',plugin_id=plugin,site_id=scope['site_id'],workspace_ids=[scope['workspace_id']],cascade=cascade),headers={'X-CSRFToken':c.csrf})
    phase(cycle,mode,'requesting')
    code,response=prepare('org.example.document_stats');assert code==200,(code,response.get('error',{}).get('code'))
    preview=validate_operations_view(response['data'])
    assert preview['targets']==[dict(**scope,plugin_id='org.example.document_stats',action=mode)] and preview['restart_required'] and not preview['native_trusted_code']
    cycle[mode].update(operation_id=preview['operation_id'],plan_hash=preview['plan_hash']);phase(cycle,mode,'http_prepared');f.save(mode+'-preview.json',preview)
    code,response=c.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=preview['operation_id'],plan_hash=preview['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':c.csrf});assert code==200
    view=validate_operations_view(response['data']);assert view['state']=='awaiting_operator_approval' and view['source']=='application_request'
    code,response=c.request('/api/v1/operations/bundle/'+preview['operation_id']);assert code==200
    bundle=response['data'];assert bundle['plan_hash']==preview['plan_hash'] and bundle['operation_lock']['release']==native.config['published_release']
    assert bundle['plan']['backup']['required'];f.save(mode+'-bundle.json',bundle)
    assert base.snapshot(state,'image-transition-'+mode+'-after-request')==f.load(PRIVATE/(mode+'-data-before.json'))
    assert base.worker(native,'image-transition-'+mode+'-worker-after-request')==f.load(PRIVATE/(mode+'-worker-before.json'))
    phase(cycle,mode,'manager_requested');print(mode+': exact normal manager request; optional provider targets one complete suspended scope, native connector retained',flush=True)

def approve(mode):
    state,native=context();cycle=f.load(MARKER);r=cycle[mode];assert r['state']=='manager_requested'
    ops=base.prefix()+['operations','--store',str(native.store.root)];validation=base.validation(native)
    phase(cycle,mode,'importing_and_reviewing')
    f.save(mode+'-import.json',json.loads(f.command('image-transition-'+mode+'-import',ops+['import-request',r['operation_id']]+validation)))
    status=native.store.status(r['operation_id']);assert status['state']=='awaiting_operator_approval' and not status['mutation_started']
    review=native.store.review(r['operation_id'],native._validate());assert review['plan_hash']==r['plan_hash'];f.save(mode+'-review.json',review)
    native._runtime_preflight(native.store.bundle(r['operation_id']))
    f.command('image-transition-'+mode+'-approve',ops+['approve',r['operation_id'],'--plan-hash',r['plan_hash'],'--noninteractive','--ack-trust']+validation)
    phase(cycle,mode,'approved');print(mode+': same HTTP request independently reconstructed/reviewed/exact approved',flush=True)

def apply(mode):
    state,native=context();cycle=f.load(MARKER);r=cycle[mode];assert r['state']=='approved';phase(cycle,mode,'applying')
    f.phase(state,'image_transition_'+mode+'_applying')
    result=json.loads(f.command('image-transition-'+mode+'-apply',base.prefix()+['plugin','apply',r['operation_id']]+base.options(native),timeout=600))
    assert result['state']=='completed' and result['traffic_resumed'];f.save(mode+'-completed.json',result)
    phase(cycle,mode,'completed_needs_verification');print(mode+': normal independently approved executor completed; inspect preservation',flush=True)

def verify(mode):
    state,native=context();cycle=f.load(MARKER);r=cycle[mode];assert r['state']=='completed_needs_verification'
    before=f.load(PRIVATE/(mode+'-data-before.json'));after=base.snapshot(state,'image-transition-'+mode+'-after');scope=cycle['scope']
    inst=next(row for row in before['mp_plugin_installation'] if row['public_id']==scope['installation_id']);workspace=next(row for row in before['mp_workspace'] if row['public_id']==scope['workspace_id'])
    stage=native.store.root/'stages'/r['operation_id'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert ready['external_installations']==1 and enabled['after']['control']['generation']==ready['control']['generation']+1
    assert ReferenceDispatchMaintenance(native).inspect()==enabled['after']
    changed_jobs=0
    for table in before:
        expected=copy.deepcopy(before[table]);actual=after[table];assert len(expected)==len(actual)
        if table=='mp_workspace_plugin':
            row=next(row for row in expected if row['installation_id']==inst['id'] and row['workspace_id']==workspace['id']);current=next(row2 for row2 in actual if row2['id']==row['id'])
            assert row['availability']==('enabled' if mode=='suspend' else 'suspended') and current['availability']==('suspended' if mode=='suspend' else 'enabled')
            row.update(availability=current['availability'],write_date=current['write_date'])
        elif table=='mp_workspace':next(row for row in expected if row['id']==workspace['id'])['policy_generation']+=1
        elif table=='mp_job':
            byid={row['id']:row for row in actual}
            for row in expected:
                current=byid[row['id']];changed={k for k in row if row[k]!=current[k]};assert changed<={'claim_generation','dispatch_generation'}
                if changed:
                    assert current['claim_generation']==row['claim_generation']+1 and current['dispatch_generation']==ready['control']['generation'];changed_jobs+=1
                    row.update(**{k:current[k] for k in changed})
        assert expected==actual,table+' outside exact scoped lifecycle footprint'
    assert base.schema(state,'image-transition-'+mode+'-schema-after')==f.load(PRIVATE/(mode+'-schema-before.json'))['digest']
    modules=json.loads(f.sql(state,'image-transition-'+mode+'-modules-after','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'))
    assert modules==f.load(PRIVATE/(mode+'-modules-before.json'))
    assert base.worker(native,'image-transition-'+mode+'-worker-after')==f.load(PRIVATE/(mode+'-worker-before.json'))
    assert native.config['published_release']==f.load(OUT/(mode+'-bundle.json'))['operation_lock']['release']
    assert f.load(stage/'metadata.log')==dict(metadata_published=True,operation_id=r['operation_id'],native_maintenance=False,runtime_control=False)
    files=json.loads(f.command('image-transition-'+mode+'-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(native.store.root/'checkpoints'/r['operation_id']/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    f.save(mode+'-preservation.json',dict(result='passed_actual_optional_provider_'+mode+'_with_connector',operation_id=r['operation_id'],plan_hash=r['plan_hash'],configuration_generation=20,dispatch_generation=enabled['after']['control']['generation'],
        installed_connector_and_other8features_unchanged=True,old_job_outcomes_inputs_attempts_exact=len(before['mp_job']),changed_job_epochs=changed_jobs,
        all17tables_exact_under_feature_policy_job_epoch_changes=True,schema_native_modules_exact=True,old_files_retained=len(retained),same_worker_process_image_key_publication=True,no_remote_runtime_control=True))
    phase(cycle,mode,'preservation_verified');f.phase(state,'image_transition_'+mode+'_verified');print(mode+': full populated native/schema/data/files/jobs/connector/worker preservation verified',flush=True)

def probe(mode):
    state,native=context();cycle=f.load(MARKER);r=cycle[mode];assert r['state']=='preservation_verified'
    alice=client(state,'alice');original=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
    for workspace in ['A','B','C']:
        views=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace);assert set(views['views'])=={'list','form'}
    code,response=alice.request('/api/v1/context?plugin_id=org.example.notes_stats',workspace='C');assert code==200
    before=base.snapshot(state,'image-transition-'+mode+'-before-probe')
    phase(cycle,mode,'probe_requesting')
    response=positive.call(alice,original,'analyze',dict(note_id=original['note_id'],expected_revision=original['revision']),'image-transition-'+mode+'-'+uuid4().hex)
    assert response['job']['state']=='pending';job=response['job']['id'];r['probe_job']=job;phase(cycle,mode,'probe_enqueued')
    args=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    phase(cycle,mode,'probe_running');result=json.loads(f.command('image-transition-'+mode+'-probe-run',args,timeout=180));f.save(mode+'-probe-run.json',result)
    actual=positive.call(alice,original,'status',dict(note_id=original['note_id']))['job'];assert actual['id']==job and actual['attempts']==1
    if mode=='suspend':assert actual['state']=='dead_letter' and actual['error_code']=='PLUGIN_SUSPENDED' and actual['result'] is None
    else:assert actual['state']=='completed' and actual['error_code'] is None and actual['result']==dict(note_id=original['note_id'],revision=original['revision'],statistics=original['expected_statistics'])
    after=base.snapshot(state,'image-transition-'+mode+'-after-probe')
    for table in before:
        actual_rows=[row for row in after[table] if row['public_id']!=job] if table=='mp_job' else after[table]
        assert actual_rows==before[table],table
    assert base.worker(native,'image-transition-'+mode+'-worker-after-probe')==f.load(PRIVATE/(mode+'-worker-before.json'))
    mirror=json.loads(f.command('image-transition-'+mode+'-mirror',base.prefix()+['operations','--store',str(native.store.root),'mirror-status',r['operation_id']]+base.validation(native)));f.save(mode+'-mirror.json',mirror)
    code,response=client(state).request('/api/v1/operations/status/'+r['operation_id']);assert code==200
    view=validate_operations_view(response['data']);assert view['state']=='completed' and view['source']=='operator_journal_mirror' and view['plan_hash']==r['plan_hash']
    f.save(mode+'-probe.json',dict(result='passed_actual_connector_'+mode+'_integration',job=actual,native_A_B_C_views=True,connector_context200_status_readable=True,all_old_data_and_worker_exact=True,same_operation_completed_HTTP_mirror=True,browser_rendering_tested=False))
    phase(cycle,mode,'probe_verified');f.phase(state,'image_transition_'+mode+'_probe_verified');print(mode+': real connector job and preserved native views/status/same-operation completed mirror verified',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['suspend','enable']);p.add_argument('action',choices=['baseline','request','approve','apply','verify','probe']);a=p.parse_args();globals()[a.action](a.mode)
