"""BX-05 supervised process loss, stale apply and exact continuation completion."""
import json
from threading import Thread
import time

from background_chunks import BASIC
from background_site import load,write
from background_sustained import native
from background_workers import Probe,docker,wait


WATCH="""
import json,time
from modular_platform import durable
env.cr.execute("SELECT set_config('application_name','bx05-stale-watch',false)");env.cr.commit()
end=time.monotonic()+90
while time.monotonic()<end:
    with env.registry.cursor() as cr:
        cr.execute('SELECT state,claim_generation FROM mp_job WHERE public_id=%s',[OLD['job']]);state,generation=cr.fetchone()
        if state=='running' and generation>OLD['generation']:
            try:durable.run_fenced(cr,durable.Claim(OLD['job'],OLD['generation'],OLD['owner']),lambda row:(_ for _ in ()).throw(AssertionError('Old apply entered')))
            except durable.ClaimLost:
                cr.rollback()
                print('BX04_RESULT='+json.dumps(dict(stale_apply_denied=True,observed_state=state,generation=generation)))
                break
            else:raise AssertionError('Old claim accepted')
    time.sleep(.05)
else:raise AssertionError('No replacement running claim observed')
"""

VERIFY="""
import hashlib
model=actor('alice','A');row=model._report_row(RUN)
assert row['state']=='completed' and row['cursor']==row['total']==5000 and row['points']==2497500
assert row['snapshot'] is None
env.cr.execute("SELECT payload->'input'->>'cursor',result,attempts FROM mp_job WHERE handler='org.example.background:report_chunk' AND payload->'input'->>'run'=%s ORDER BY (payload->'input'->>'cursor')::int",[RUN])
rows=env.cr.fetchall();assert [int(cursor) for cursor,result,attempts in rows]==list(range(0,5000,100))
assert len(rows)==50 and sum(result['count'] for cursor,result,attempts in rows)==5000
previous='0'*64
for cursor,result,attempts in rows:
    previous=hashlib.sha256(json.dumps([previous,result['digest']],separators=(',',':')).encode()).hexdigest()
assert previous==row['result_digest']
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(count=5000,points=2497500,chunks=50,digest=previous,
    attempts=sum(attempts for cursor,result,attempts in rows),terminal_snapshot_cleared=True)))
"""


def main():
    probe=Probe('bx-05-chunks-01');path=probe.site.local/'bx05-process.json'
    assert not path.exists() and not probe.operator._lanes()
    initial=load(probe.site.local/'bx05-atomicity.json');assert initial['phase']=='passed'
    ident=initial['result']['run']
    query="""SELECT jsonb_build_object('cursor',r.cursor,'state',r.state,'points',r.points,
        'job',j.public_id,'job_state',j.state,'generation',j.claim_generation,'owner',j.lease_owner)
        FROM mp_background_report r JOIN mp_job j ON j.public_id=r.job_public_id WHERE r.public_id='"""+ident+"'"
    def observed():return json.loads(probe.sql(query))
    record=dict(phase='starting',run=ident,image=probe.state['image_id']);write(path,record)
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    record.update(phase='ready',approval=review['approval']);write(path,record)
    def candidate():
        row=observed()
        return row if 100<=row['cursor']<4000 and row['job_state']=='running' else None
    frozen=None;observations=[]
    for _ in range(3):
        row=wait(candidate,25);lane=probe.lane(row['job'],row['generation']);assert lane
        container,=json.loads(docker('inspect',lane))
        assert container['Image']==probe.state['image_id']
        assert container['Config']['Labels']['com.modular.job_site']==probe.state['site_id']
        raw=docker('exec',lane,'/venv/bin/python','-c',
            "import json,os,signal;p=json.load(open('/tmp/mp-job-health.json'));assert p['pool']=='bulk';print(p['pid'],flush=True);os.kill(p['pid'],signal.SIGSTOP)")
        pid=int(raw.decode().strip());after=observed()
        same=after['job_state']=='running' and probe.lane(after['job'],after['generation'])==lane
        observations.append(dict(before=row,after=after,same_lane=same))
        if same:
            frozen=dict(**after,lane=lane,pid=pid,restart_before=container['RestartCount']);break
        docker('exec',lane,'/venv/bin/python','-c','import os,signal;os.kill('+str(pid)+',signal.SIGCONT)')
    assert frozen is not None,observations
    record.update(phase='worker_stopped',frozen=frozen,observations=observations);write(path,record)
    results=[];errors=[]
    def watcher():
        try:results.append(native(probe,'bx05-stale-watch',WATCH,OLD=frozen))
        except BaseException as error:errors.append(str(error))
    thread=Thread(target=watcher,daemon=True);thread.start()
    try:
        wait(lambda:errors or probe.sql("SELECT count(*) FROM pg_stat_activity WHERE application_name='bx05-stale-watch'")=='1',20)
        assert not errors,errors
        record.update(phase='crash_requested');write(path,record)
        docker('exec',frozen['lane'],'/venv/bin/python','-c','import os,signal;os.kill('+str(frozen['pid'])+',signal.SIGKILL)')
        def restarted():
            current,=json.loads(docker('inspect',frozen['lane']))
            return current if current['RestartCount']>frozen['restart_before'] and current['State']['Running'] else None
        restarted_row=wait(restarted,40)
        thread.join(timeout=95)
        assert not thread.is_alive() and not errors and len(results)==1,(errors,results)
        assert results[0]['stale_apply_denied'] and results[0]['observed_state']=='running'
        record.update(phase='stale_denied',watch=results[0],restart_count=restarted_row['RestartCount']);write(path,record)
        wait(lambda:observed()['state']=='completed',150)
        prefix=BASIC.split("model=actor('alice','A');other=actor('bob','B')",1)[0]
        verified=native(probe,'bx05-process-verify',prefix+VERIFY,RUN=ident)
        drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
        record.update(phase='passed',verified=verified,drain=drained);write(path,record)
        print(dict(phase='passed',chunks=50,automatic_restart=True,stale_apply_denied=True),flush=True)
    finally:
        # SIGKILL is safe even if the diagnostic stopped before the planned
        # crash. Never leave the owned worker indefinitely SIGSTOP'ed.
        if record['phase']=='worker_stopped':
            docker('exec',frozen['lane'],'/venv/bin/python','-c','import os,signal;os.kill('+str(frozen['pid'])+',signal.SIGCONT)')


if __name__=='__main__':main()
