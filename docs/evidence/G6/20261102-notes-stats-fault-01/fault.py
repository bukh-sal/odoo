"""Bounded actual canonical worker outages; each mutation has a durable marker."""
import argparse,json,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-notes-stats-remote-01'))
import remote as positive
context,base,f,j=positive.context,positive.base,positive.f,positive.j
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerPlanningReader
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'notes-stats-fault-01'

def marker(mode):return PRIVATE/(mode+'.json')
def save(mode,record,phase):
    record['state']=phase;f.write(marker(mode),record)
def inspect(mode,phase,record):
    info=json.loads(f.command('stats-fault-'+mode+'-'+phase,['docker','inspect',record['container_id']]))[0]
    assert info['Id']==record['container_id'] and info['Image']==record['worker']['image']
    assert info['Config']['Labels']['com.docker.compose.project']=='mp-disposable-document-stats-05'
    assert info['HostConfig']['RestartPolicy']['Name']=='no'
    return info
def reader(native):return WorkerPlanningReader(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')

def baseline(mode):
    state,native=context();assert native.config['generation']==18 and not marker(mode).exists()
    if not PRIVATE.exists():protect_directory(PRIVATE)
    if mode=='crash':assert f.load(marker('timeout'))['state']=='verified'
    data=base.snapshot(state,'stats-fault-'+mode+'-before')
    assert len(data['mp_job'])==(20 if mode=='timeout' else 21)
    assert all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
    worker=base.worker(native,'stats-fault-'+mode+'-worker-before')
    original=f.load(j.LOCAL/'notes-stats-remote-01/positive.json');assert original['state']=='verified'
    record={k:original[k] for k in ('note_id','revision','jobs_binding')}
    record.update(container_id=worker['container_id'],worker=worker,gateway_key='fault-'+mode+'-'+uuid4().hex)
    inspect(mode,'inspect-before',record)
    f.write(PRIVATE/(mode+'-data-before.json'),data)
    save(mode,record,'baseline_captured');print(mode+': fresh terminal baseline and exact owned running worker captured',flush=True)

def fault(mode):
    state,native=context();record=f.load(marker(mode));assert record['state']=='baseline_captured'
    info=inspect(mode,'before-fault',record);assert info['State']['Running'] and not info['State']['Paused']
    save(mode,record,'pausing' if mode=='timeout' else 'killing')
    args=['docker','pause',record['container_id']] if mode=='timeout' else ['docker','kill','--signal','KILL',record['container_id']]
    f.command('stats-fault-'+mode+'-inject',args)
    info=inspect(mode,'after-fault',record)
    assert info['State']['Paused'] if mode=='timeout' else not info['State']['Running'] and info['State']['ExitCode']==137
    save(mode,record,'fault_injected');print(mode+': exact owned worker '+('paused' if mode=='timeout' else 'SIGKILL confirmed exit137'),flush=True)

def enqueue(mode):
    state,native=context();record=f.load(marker(mode));assert record['state']=='fault_injected'
    c=positive.client(state);save(mode,record,'requesting')
    result=positive.call(c,record,'analyze',dict(note_id=record['note_id'],expected_revision=record['revision']),record['gateway_key'])
    assert result['job']['state']=='pending';record['job_id']=result['job']['id'];save(mode,record,'enqueued')
    f.save(mode+'-enqueue.json',result);print(mode+': one original-actor job pending',flush=True)

def run(mode):
    state,native=context();record=f.load(marker(mode));assert record['state']=='enqueued'
    save(mode,record,'running');start=time.monotonic()
    args=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    result=json.loads(f.command('stats-fault-'+mode+'-run-once',args,timeout=180))
    elapsed=time.monotonic()-start;f.save(mode+'-run.json',dict(result=result,elapsed_seconds=elapsed))
    record['runner_elapsed_seconds']=elapsed;save(mode,record,'runner_terminal');print(mode+': ordinary runner terminal after %.2fs'%elapsed,flush=True)

def host(native,state,record,mode,phase,expected):
    c=positive.client(state)
    for workspace in ['A','B','C']:
        views=c.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=workspace)
        assert set(views['views'])=={'list','form'} and '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
    assert c.call('get',dict(note_id=record['note_id']),workspace='C')['revision']==record['revision']
    status,response=c.request('/api/v1/context?plugin_id=org.example.notes_stats',workspace='C');assert status==200
    job=positive.call(c,record,'status',dict(note_id=record['note_id']))['job']
    assert job['id']==record['job_id'] and job['state']=='dead_letter' and job['attempts']==1 and job['result'] is None
    assert job['error_code']==('DEADLINE_EXCEEDED' if mode=='timeout' else 'DEPENDENCY_UNAVAILABLE'),job['error_code']
    native.observer.external_reader=reader(native).planning_state
    f.save(mode+'-'+phase+'-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
    operator=positive.r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),'operator')
    status,response=operator.request('/api/v1/operations/installed');assert status==200
    row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
    assert row['health']['state']==expected,(expected,row['health'])
    assert row['features'][0]['availability']=='enabled'
    f.save(mode+'-'+phase+'-host.json',dict(job=job,provider_health=row['health'],native_A_B_C_list_form=True,notes_readable=True,connector_context200=True,browser_rendering_tested=False))
    before=f.load(PRIVATE/(mode+'-data-before.json'));after=base.snapshot(state,'stats-fault-'+mode+'-'+phase+'-after')
    for table in before:
        actual=after[table]
        if table=='mp_job':actual=[r for r in actual if r['public_id']!=record['job_id']]
        assert actual==before[table],table
    return job

def verify_down(mode,phase='down'):
    state,native=context();record=f.load(marker(mode));assert record['state']=='runner_terminal'
    info=inspect(mode,'verify-'+phase,record)
    assert info['State']['Paused'] if mode=='timeout' else not info['State']['Running']
    host(native,state,record,mode,phase,'degraded')
    save(mode,record,'down_verified');print(mode+': bounded job failure, healthy native host and unavailable provider API verified',flush=True)

def verify_down_continuation(mode):verify_down(mode,'down-continuation')

def recover(mode):
    state,native=context();record=f.load(marker(mode));assert record['state']=='down_verified'
    save(mode,record,'unpausing' if mode=='timeout' else 'starting')
    f.command('stats-fault-'+mode+'-recover',['docker','unpause' if mode=='timeout' else 'start',record['container_id']])
    save(mode,record,'runtime_resumed');print(mode+': same worker separately resumed; fresh attestation still required',flush=True)

def verify_up(mode):
    state,native=context();record=f.load(marker(mode));assert record['state']=='runtime_resumed'
    actual=base.worker(native,'stats-fault-'+mode+'-worker-after');before=record['worker']
    for key in before:
        if mode=='crash' and key in ('started_at','networks'):continue
        assert actual[key]==before[key],key
    if mode=='crash':
        assert actual['started_at']!=before['started_at']
        for network,values in before['networks'].items():
            for key in ('NetworkID','IPAddress','GlobalIPv6Address'):
                assert actual['networks'][network][key]==values[key],key
    host(native,state,record,mode,'up','healthy')
    f.save(mode+'-qualification.json',dict(result='passed_actual_worker_'+mode+'_host_survival_and_same_worker_recovery',configuration_generation=18,dispatch_generation=88,
        job_id=record['job_id'],old_terminal_jobs=20 if mode=='timeout' else 21,all_old_jobs_and_other16tables_exact=True,
        same_worker_image_key_publication5_config3_addresses=True,one_terminal_failed_attempt_no_late_host_result=True,
        native_A_B_C_view_definitions_and_original_actor_note_status=True,provider_unavailable_then_healthy=True,
        elapsed_runner_seconds=record['runner_elapsed_seconds'],limits=['Backend/API evidence; degraded UI rendering and complete SVC02 acceptance still pending.']))
    save(mode,record,'verified');f.phase(state,'notes_stats_'+mode+'_verified');f.guard(state)
    print(mode+': unchanged worker authority freshly attested; failed job stable, all old data exact, host/provider healthy',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['timeout','crash']);p.add_argument('action',choices=['baseline','fault','enqueue','run','verify_down','verify_down_continuation','recover','verify_up']);a=p.parse_args();globals()[a.action](a.mode)
