"""Actual installed UI crash/restart complement to the timeout proof."""
import argparse,json,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import lifecycle as d
from modular_platform.operator_os import protect_directory
base,f,j=d.base,d.f,d.j;OUT=d.OUT;PRIVATE=j.LOCAL/'headless-ui-05';MARKER=PRIVATE/'operator.json'
def phase(r,v):r['state']=v;f.write(MARKER,r)
def signal(v):f.write(PRIVATE/'operator-phase.json',dict(state=v))
def node(v):assert f.load(PRIVATE/'node-phase.json')['state']==v
def info(r,label):
    value=json.loads(f.command(label,['docker','inspect',r['container_id']]))[0]
    assert value['Id']==r['container_id'] and value['Image']==r['worker']['image']
    assert value['Config']['Labels']['com.docker.compose.project']=='mp-disposable-document-stats-06'
    return value
def prepare():
    s,n=d.context();assert not PRIVATE.exists();protect_directory(PRIVATE);protect_directory(PRIVATE/'profile')
    data=base.snapshot(s,'headless-crash-before');assert len(data['mp_job'])==34 and all(r['state'] in ('completed','dead_letter','cancelled') for r in data['mp_job'])
    target=next(r for r in data['mp_example_note'] if r['public_id']=='5df6a1b5-8ae0-4bf6-978d-464dae38ff7c')
    assert not any(r['handler']=='org.example.notes_stats:analyze' and r['payload']['input']['note_id']==target['public_id'] for r in data['mp_job'])
    worker=base.worker(n,'headless-crash-worker-before');f.write(PRIVATE/'data-before.json',data)
    target={k:target[k] for k in ['public_id','title','revision','body']};target['statistics']=dict(characters=len(target['body']),words=len(target['body'].split()),lines=len(target['body'].splitlines()));del target['body']
    f.write(PRIVATE/'targets.json',dict(outage=target));f.write(MARKER,dict(state='prepared',worker=worker,container_id=worker['container_id'],jobs=[]))
    print('Fresh34terminal baseline/currentworker captured; existing no-analysis Note selected for actual crash UI proof')
def run(mode):
    s,n=d.context();r=f.load(MARKER);node(mode+'_waiting_runner');assert r['state']==('prepared' if mode=='crash' else 'worker_recovered')
    target=f.load(PRIVATE/'targets.json')['outage'];job=d.pending(s,target,'headless-'+mode+'-05-pending');r[mode+'_job_id']=job['public_id']
    if mode=='crash':
        before=info(r,'headless-crash-before-kill');assert before['State']['Running'] and not before['State']['Paused']
        phase(r,'killing_worker');f.command('headless-crash-kill',['docker','kill','--signal','KILL',r['container_id']])
        after=info(r,'headless-crash-after-kill');assert not after['State']['Running'] and after['State']['ExitCode']==137
    phase(r,mode+'_running')
    args=base.prefix()+['worker','--store',str(n.store.root),'--deployment-config',str(n.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    runner=json.loads(f.command('headless-'+mode+'-05-runner',args,timeout=180));f.save(mode+'-05-runner.json',runner)
    data=base.snapshot(s,'headless-'+mode+'-05-terminal');actual=next(a for a in data['mp_job'] if a['public_id']==job['public_id']);assert actual['attempts']==1
    if mode=='crash':assert actual['state']=='dead_letter' and actual['error_code']=='DEPENDENCY_UNAVAILABLE' and actual['result'] is None
    else:assert actual['state']=='completed' and actual['result']==dict(note_id=target['public_id'],revision=target['revision'],statistics=target['statistics'])
    r['jobs'].append(job['public_id']);phase(r,mode+'_completed');signal(mode+'_completed')
    f.save(mode+'-05-job.json',dict(result='passed_actual_browser_'+mode+'_job',job_id=job['public_id'],state=actual['state'],attempts=1,error_code=actual['error_code'],result_value=actual['result']))
    print(mode+': actual browser job terminal once; UI continuation signalled')
def crash():run('crash')
def recovery():run('recovery')
def start():
    s,n=d.context();r=f.load(MARKER);assert r['state']=='crash_completed';node('crash_UI_verified')
    value=info(r,'headless-crash-before-start');assert not value['State']['Running'] and value['State']['ExitCode']==137
    phase(r,'starting_worker');f.command('headless-crash-start',['docker','start',r['container_id']]);phase(r,'worker_started_waiting_health')
    end=time.monotonic()+45
    while time.monotonic()<end:
        value=json.loads(subprocess.check_output(['docker','inspect',r['container_id']],timeout=10))[0]
        if value['State'].get('Health',{}).get('Status')=='healthy':break
        time.sleep(1)
    assert value['State']['Running'] and value['State']['Health']['Status']=='healthy'
    actual=base.worker(n,'headless-crash-worker-recovered')
    assert all(actual[k]==v for k,v in r['worker'].items() if k not in ('started_at','networks'))
    assert actual['started_at']!=r['worker']['started_at']
    for network,values in r['worker']['networks'].items():
        for k in ['NetworkID','IPAddress','GlobalIPv6Address']:assert actual['networks'][network][k]==values[k]
    phase(r,'worker_recovered');signal('worker_recovered');f.write(PRIVATE/'worker-after.json',actual)
    print('Same worker container/image/key/config9/pub11 restarted healthy; only allowed start/network endpoint metadata changes')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','crash','start','recovery']);globals()[p.parse_args().action]()
