"""Coordinate real browser-triggered jobs and one exact owned worker outage."""
import argparse,importlib.util,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('ui_release',OUT.parent/'20261102-notes-stats-ui-source-01/upgrade.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from modular_platform.operator_os import protect_directory
base,f,j=m.base,m.f,m.j;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'headless-ui-04';MARKER=PRIVATE/'operator.json'

def context():
    state,native=m.context();assert native.config['generation']==24
    return state,native
def phase(record,value):record['state']=value;f.write(MARKER,record)
def signal(value):f.write(PRIVATE/'operator-phase.json',dict(state=value))
def node(value):assert f.load(PRIVATE/'node-phase.json')['state']==value
def info(record,label):
    value=json.loads(f.command(label,['docker','inspect',record['container_id']]))[0]
    assert value['Id']==record['container_id'] and value['Image']==record['worker']['image']
    assert value['Config']['Labels']['com.docker.compose.project']=='mp-disposable-document-stats-06'
    return value

def prepare():
    state,native=context();assert not PRIVATE.exists();protect_directory(PRIVATE);protect_directory(PRIVATE/'profile')
    before=base.snapshot(state,'headless-lifecycle-before');assert len(before['mp_job'])==31 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    worker=base.worker(native,'headless-lifecycle-worker-before');f.write(PRIVATE/'data-before.json',before)
    notes=before['mp_example_note'];nav=next(r for r in notes if r['public_id']=='a31c7960-2ebc-4d73-9c98-70292275ecad')
    outage=next(r for r in notes if r['public_id']=='70374666-2199-4c99-897b-980518dc6b98')
    assert not any(r['handler']=='org.example.notes_stats:analyze' and r['payload']['input']['note_id']==outage['public_id'] for r in before['mp_job'])
    targets={}
    for name,row in [('navigation',nav),('outage',outage)]:
        targets[name]={k:row[k] for k in ['public_id','title','revision']}
        targets[name]['statistics']=dict(characters=len(row['body']),words=len(row['body'].split()),lines=len(row['body'].splitlines()))
    f.write(PRIVATE/'targets.json',targets);f.write(MARKER,dict(state='prepared',worker=worker,container_id=worker['container_id'],jobs=[]))
    print('31terminal baseline captured; two existing Notes identified by immutable ID; isolated browser profile prepared')

def pending(state,target,label):
    rows=base.snapshot(state,label)['mp_job'];active=[r for r in rows if r['state'] not in ('completed','dead_letter','cancelled')]
    assert len(active)==1 and active[0]['state']=='pending' and active[0]['attempts']==0
    job=active[0];assert job['handler']=='org.example.notes_stats:analyze' and job['payload']['input']==dict(note_id=target['public_id'],expected_revision=target['revision'])
    return job

def run_job(mode):
    state,native=context();record=f.load(MARKER);node(mode+'_waiting_runner')
    expected={'navigation':'prepared','outage':'navigation_completed','recovery':'worker_recovered'}[mode]
    assert record['state']==expected
    target=f.load(PRIVATE/'targets.json')['navigation' if mode=='navigation' else 'outage']
    job=pending(state,target,'headless-'+mode+'-pending');record[mode+'_job_id']=job['public_id']
    if mode=='outage':
        value=info(record,'headless-outage-before-pause');assert value['State']['Running'] and not value['State']['Paused']
        phase(record,'pausing_worker_for_UI_proof');f.command('headless-outage-pause',['docker','pause',record['container_id']])
        assert info(record,'headless-outage-after-pause')['State']['Paused']
    phase(record,mode+'_running')
    args=base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    runner=json.loads(f.command('headless-'+mode+'-runner',args,timeout=180));f.save(mode+'-runner.json',runner)
    after=base.snapshot(state,'headless-'+mode+'-terminal');actual=next(r for r in after['mp_job'] if r['public_id']==job['public_id'])
    assert actual['attempts']==1
    if mode=='outage':assert actual['state']=='dead_letter' and actual['error_code']=='DEADLINE_EXCEEDED' and actual['result'] is None
    else:assert actual['state']=='completed' and actual['result']==dict(note_id=target['public_id'],revision=target['revision'],statistics=target['statistics'])
    record['jobs'].append(job['public_id']);phase(record,mode+'_completed')
    f.save(mode+'-job.json',dict(result='passed_real_browser_enqueued_'+mode+'_job',job_id=job['public_id'],state=actual['state'],attempts=1,error_code=actual['error_code'],
        result_value=actual['result'],native_generation=24,actor_original=True,browser_triggered=True))
    signal(mode+'_completed');print(mode+': actual browser job terminal once; browser continuation signalled')

def navigation():run_job('navigation')
def outage():run_job('outage')
def recovery():run_job('recovery')

def unpause():
    state,native=context();record=f.load(MARKER);assert record['state']=='outage_completed';node('outage_UI_verified')
    assert info(record,'headless-outage-before-unpause')['State']['Paused']
    phase(record,'unpausing_worker');f.command('headless-outage-unpause',['docker','unpause',record['container_id']])
    assert base.worker(native,'headless-outage-recovered-worker')==record['worker']
    phase(record,'worker_recovered');signal('worker_recovered');print('Same owned worker unpaused; image/start/key/config9/publication11 exact')

def attest():
    state,native=context();record=f.load(MARKER);assert record['state']=='unpausing_worker';node('outage_UI_verified')
    value=info(record,'headless-outage-post-unpause-health')
    assert value['State']['Running'] and not value['State']['Paused'] and value['State']['Health']['Status']=='healthy'
    assert base.worker(native,'headless-outage-recovered-worker-02')==record['worker']
    phase(record,'worker_recovered');signal('worker_recovered');print('Fresh healthy heartbeat attested after completed unpause; no repeated mutation')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','navigation','outage','unpause','attest','recovery']);globals()[p.parse_args().action]()
