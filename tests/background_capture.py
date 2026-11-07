"""Read-only lane log capture for an already running owned BX-04 case."""
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

from background_site import load,write,ROOT
from background_workers import docker


def main():
    local=ROOT/'.local/background-qualification/bx-04-capacity-01'
    target=load(local/'operator/target.json');project=target['project']
    case=load(local/'bx04-sustained-many-live.json')
    assert case['live_enqueue'] and case['phase'] in {'preloaded','idle_measured'}
    directory=local/'many-live-worker-trace';assert not directory.exists();directory.mkdir()
    names=[project+'-job-'+pool+'-'+str(index) for pool,index in [('urgent',1),('bulk',1),('bulk',2)]]
    owned=json.loads(docker('inspect',*names))
    for row in owned:
        labels=row['Config']['Labels']
        assert labels['com.modular.deployment']==target['deployment_id']
        assert labels['com.modular.job_site']==target['sites'][0]['site_id']
        assert row['Image']==target['image_id'] and row['State']['Running']
    write(directory/'intent.json',dict(state='capturing',image=target['image_id'],
        lanes=[dict(id=row['Id'],name=row['Name']) for row in owned],case_hash=hashlib.sha256((local/'bx04-sustained-many-live.json').read_bytes()).hexdigest()))
    def capture(row):
        pool=row['Config']['Labels']['com.modular.job_pool'];name=row['Name'].rsplit('-',1)[1]
        output=directory/(pool+'-'+name+'.stdout');error=directory/(pool+'-'+name+'.stderr')
        with output.open('xb') as out,error.open('xb') as err:
            process=subprocess.Popen(['docker','logs','--follow','--tail','2000',row['Id']],stdout=out,stderr=err,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:code=process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=5);code=124
        return dict(name=row['Name'],exit_code=code,stdout_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                    stderr_sha256=hashlib.sha256(error.read_bytes()).hexdigest())
    with ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(capture,owned))
    write(directory/'result.json',dict(state='complete' if all(row['exit_code']==0 for row in result) else 'incomplete',lanes=result))
    print(json.dumps(dict(lanes=len(result),exit_codes=[row['exit_code'] for row in result])),flush=True)


if __name__=='__main__':main()
