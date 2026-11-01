"""Two new pre-native faults and exact reviewed unchanged-release resumes."""
import argparse,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
import r1_probe
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.restore_continuation import FILE_OBSERVATION
f=j.f;f.OUTPUT=OUT

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=NativeExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    assert native.config['generation']==5 and native.config['sites'][0]['database']==state['active_db']
    return state,native

def marker(mode):return j.LOCAL/('native-unchanged-'+mode+'-01.json')

def business(state,label):
    tables=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary']
    query='SELECT jsonb_build_object('+','.join("'"+t+"',(SELECT jsonb_build_object('rows',count(*),'sha256',encode(sha256(convert_to(COALESCE(string_agg(to_jsonb(t)::text,'' ORDER BY id),''),'UTF8')),'hex')) FROM "+t+' t)' for t in tables)+');'
    return json.loads(f.sql(state,label,query))

def files(state,native,operation,label):
    args,_=native._child(operation,label,network=False)
    return json.loads(f.command(label,args+['-c',FILE_OBSERVATION,state['active_db']]))

def prepare(mode):
    state,native=context();assert not marker(mode).exists()
    assert state['phase']==('native_recovery_qualified' if mode=='paused' else 'native_unchanged_paused_qualified')
    reader=native.observer;catalog=Catalog(native.catalog_root,native.validator,readonly=True);snapshot=catalog.snapshot();obs=reader.read();document=reader.state(obs,snapshot)
    fixture=f.load(j.LOCAL/'fixtures.json');operation=str(uuid4());workspace=fixture['workspaces']['C']['public_id']
    targets=[dict(installation_id=installation_id(obs['sites'][0],'org.example.notes_labels'),site_id=state['site_id'],workspace_id=workspace,plugin_id='org.example.notes_labels',action='install')]
    bundle=prepare_current_install_targets(document,obs['sites'],snapshot,activation_targets=targets,operation_id=operation,created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    f.save(mode+'-bundle.json',bundle);f.save(mode+'-before.json',document['state'])
    jobs=json.loads(f.sql(state,'native-unchanged-'+mode+'-jobs-before-01','SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j;'))
    baseline=dict(configuration=native.config,business=business(state,'native-unchanged-'+mode+'-business-before-01'),dispatch=DispatchMaintenance(native).inspect(),jobs=jobs,authority=RestoreExecutor(native)._authority(state['active_db'])[0])
    if mode=='enabled':baseline['filestore']=files(state,native,operation,'native-unchanged-enabled-files-before-01')
    assert baseline['dispatch']['control']['state']=='enabled'
    f.write(j.LOCAL/('native-unchanged-'+mode+'-baseline-01.json'),baseline)
    f.write(marker(mode),dict(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash']))
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'operations','--store',str(native.store.root)];options=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    f.command('native-unchanged-'+mode+'-register-01',prefix+['register','--bundle',str(OUT/(mode+'-bundle.json'))]+options)
    f.command('native-unchanged-'+mode+'-approve-01',prefix+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+options)
    f.write(marker(mode),dict(state='approved',operation_id=operation,plan_hash=bundle['plan_hash']));f.phase(state,'native_unchanged_'+mode+'_approved')

class BeforeNativeFault(RuntimeError):pass

def fault(mode):
    state,native=context();record=f.load(marker(mode));operation=record['operation_id']
    assert record['state']=='approved' and state['phase']=='native_unchanged_'+mode+'_approved'
    method='_checkpoint' if mode=='paused' else '_topology';original=getattr(native,method)
    def fail(*args,**kwargs):
        result=original(*args,**kwargs)
        if mode=='paused':assert result==operation
        f.write(j.LOCAL/('native-unchanged-'+mode+'-fault-01.json'),dict(state='injected_before_native_mutation',method=method,operation_id=operation))
        raise BeforeNativeFault('Owned before-native fault after '+method)
    record['state']='applying';f.write(marker(mode),record);f.phase(state,'native_unchanged_'+mode+'_fault_running')
    with patch.object(native,method,side_effect=fail):
        try:native.apply(operation)
        except BeforeNativeFault:pass
        else:raise AssertionError('Expected before-native fault did not occur')
    status=native.store.status(operation);assert status['state']=='failed_before_mutation' and not status['mutation_started'] and not status['traffic_resumed']
    stage=native.store.root/'stages'/operation;assert not (stage/'native.log').exists() and not (stage/'worker-replacement.json').exists()
    observed=DispatchMaintenance(native).inspect();baseline=f.load(j.LOCAL/('native-unchanged-'+mode+'-baseline-01.json'))
    if mode=='paused':
        assert observed['control']['state']=='paused' and observed['control']['generation']==26
        manifest=f.load(native.store.root/'checkpoints'/operation/'manifest.json');assert manifest['dispatch_profile']==observed
    else:assert observed==baseline['dispatch']
    assert f.load(native.target_path)==baseline['configuration']
    f.save(mode+'-fault.json',dict(result='expected_pre_native_failure',operation_id=operation,status=status,mode=mode,dispatch=observed,configuration_unchanged=True,native_child_launched=False))
    record['state']='failed_before_mutation';f.write(marker(mode),record);f.phase(state,'native_unchanged_'+mode+'_requires_review');f.guard(state)
    print('New '+mode+' failure verified before native mutation; original config/database retained.')

def recovery(mode,action):
    state,native=context();record=f.load(marker(mode));assert record['state']=='failed_before_mutation'
    assert state['phase']=='native_unchanged_'+mode+('_requires_review' if action=='review' else '_reviewed')
    cli='prepare-unchanged-resume' if action=='review' else 'resume-unchanged';decision=j.LOCAL/('native-unchanged-'+mode+'-decision-01.json')
    args=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'plugin','recover',cli,record['operation_id'],'--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
    if action=='resume':args+=['--decision',str(decision),'--decision-hash',f.load(decision.with_suffix('.hash'))['decision_hash'],'--noninteractive']
    f.phase(state,'native_unchanged_'+mode+'_'+action+'_running')
    result=json.loads(f.command('native-unchanged-'+mode+'-'+action+'-01',args,timeout=600))
    if action=='review':
        expected='reconcile_paused' if mode=='paused' else 'enabled_unchanged';assert result['decision']['dispatch']['mode']==expected
        f.write(decision,result['decision']);f.write(decision.with_suffix('.hash'),dict(decision_hash=result['decision_hash']))
        f.save(mode+'-review.json',dict(result='exact_private_unchanged_review',operation_id=record['operation_id'],decision_hash=result['decision_hash'],review=result['decision']['review'],mode=expected,database_restore=False))
        f.phase(state,'native_unchanged_'+mode+'_reviewed')
    else:
        assert result['state']=='unchanged_release_resumed' and result['database_restore'] is False and result['worker_replaced'] is False and result['generation']==5
        f.save(mode+'-resumed.json',result);f.phase(state,'native_unchanged_'+mode+'_resumed')

def verify(mode):
    state,native=context();assert state['phase']=='native_unchanged_'+mode+'_resumed'
    baseline=f.load(j.LOCAL/('native-unchanged-'+mode+'-baseline-01.json'));record=f.load(marker(mode));operation=record['operation_id']
    assert f.load(native.target_path)==baseline['configuration']
    after=DispatchMaintenance(native).inspect();assert after['control']['state']=='enabled' and after['control']['generation']==28
    if mode=='enabled':assert after==baseline['dispatch']
    for name in ['mp_outbox','mp_event_consumption','mp_event_consumer_state','mp_event_subscription','mp_event_delivery']:
        assert after['tables'][name]==baseline['dispatch']['tables'][name]
    assert business(state,'native-unchanged-'+mode+'-business-after-01')==baseline['business']
    assert RestoreExecutor(native)._authority(state['active_db'])[0]==baseline['authority']
    actual_files=files(state,native,operation,'native-unchanged-'+mode+'-files-after-01')
    if mode=='paused':
        expected_files={};prefix='filestore/'+state['active_db']+'/'
        with tarfile.open(native.store.root/'checkpoints'/operation/'filestore.tar.gz','r:gz') as archive:
            for member in archive:
                if member.isfile() and member.name.startswith(prefix):expected_files[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        assert actual_files==expected_files
    else:assert actual_files==baseline['filestore']
    current=json.loads(f.sql(state,'native-unchanged-'+mode+'-jobs-after-01','SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j;'))
    assert len(current)==len(baseline['jobs'])==4
    for old,new in zip(baseline['jobs'],current):
        for key in ['public_id','site_id','actor_id','workspace_id','installation_id','handler','handler_version','effect_mode','input_digest','idempotency_key','payload','state','result','attempts','max_attempts','deadline_at','finished_at','error_code']:
            assert old[key]==new[key],key
    status=native.store.status(operation);assert status['phase']=='unchanged_traffic_resumed' and status['state']=='failed_before_mutation' and not status['mutation_started'] and status['traffic_resumed']
    assert not (native.store.root/'recoveries'/operation).exists()
    r1_probe.r1.r0.LOCAL=j.LOCAL;fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture)
    views=client.native('get_views',workspace='C',kwargs=dict(views=[[False,'list'],[False,'form']],options=dict(toolbar=False)));assert {'list','form'}<=set(views['views'])
    owned=f.load(j.LOCAL/'native-recovery-seed-01.json')['note_id'];assert client.call('get',dict(note_id=owned),workspace='C')['revision']==2
    client.call('get',dict(note_id=owned),workspace='A',expect=404,code='NOT_FOUND')
    proof=dict(result='passed_actual_'+mode+'_unchanged_native_resume',operation_id=operation,generation=5,image_unchanged=state['image_id'],database_unchanged=state['active_db'],configuration_and_worker_exact=True,no_database_restore_or_native_maintenance=True,original_jobs_actor_input_trace_outcome_deadline_and_attempts_preserved=True,business_and_producer_consumer_history_exact=True,current_native_authority_exact=True,filestore_exact_files=len(actual_files),native_Odoo_list_form_and_scoped_HTTP=True,dispatch_generation=28,enabled_profile_no_dispatch_mutation=(mode=='enabled'),status=status,dispatch=after)
    f.save(mode+'-qualification.json',proof);record['state']='qualified';f.write(marker(mode),record);f.phase(state,'native_unchanged_'+mode+'_qualified');f.guard(state)
    print('Actual '+mode+' unchanged native resume qualified; same config5/DB/worker, business/trace exact.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['paused','enabled']);parser.add_argument('action',choices=['prepare','fault','review','resume','verify']);args=parser.parse_args()
    if args.action in {'review','resume'}:recovery(args.mode,args.action)
    else:globals()[args.action](args.mode)
