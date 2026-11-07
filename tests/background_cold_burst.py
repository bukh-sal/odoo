"""A physical cold start cannot rescue an already short validity window."""
from datetime import datetime, timezone
import json
import time

from background_load import BrowserConnection, summary
from background_site import load, write
from background_sustained import native
from background_workers import Probe, docker, wait


SEED="""
from datetime import datetime,timedelta,timezone
import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
when=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=15)
jobs=[]
for index,label in enumerate(sorted(DATA)[:20]):
    row=DATA[label];actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][row['user']]['id'],{}),row['public_id'])
    jobs.append(enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:load',
        dict(iterations=250000),'bx04-cold-burst-'+str(index),version=1,
        schedule=JobSchedule(when,when+timedelta(seconds=10),1)))
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(jobs=jobs,anchor=when.isoformat(),deadline=(when+timedelta(seconds=10)).isoformat())))
"""


def main():
    probe=Probe('bx-04-capacity-01');path=probe.site.local/'bx04-cold-burst.json'
    assert not path.exists() and not probe.operator._lanes()
    record=dict(phase='starting',image=probe.state['image_id']);write(path,record)
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=0)
    assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='ready'
    probe.site.state=lambda:dict(probe.state);client=BrowserConnection(probe.site,'alice')
    def cpu():
        raw=dict(line.split() for line in docker('exec',probe.project+'-db-1','cat','/sys/fs/cgroup/cpu.stat').decode().splitlines())
        return time.time(),int(raw['usage_usec'])
    previous=cpu();reads=[]
    while time.time()-previous[0]<10:
        start=time.monotonic()
        result=client.native('mp.example.note','web_search_read',kwargs=dict(domain=[],offset=0,limit=80,
            specification={name:{} for name in ('title','revision','write_date')}))
        assert len(result['records'])==80
        reads.append((time.monotonic()-start)*1000);time.sleep(.5)
    current=cpu();client.connection.close()
    measured_health=dict(observed_at=datetime.now(timezone.utc).isoformat(),web_p95_ms=summary(reads)['p95_ms'],
        db_cpu_fraction=(current[1]-previous[1])/1e6/(current[0]-previous[0])/4,lock_wait_seconds=0)
    seed=native(probe,'bx04-cold-burst-seed',SEED,DATA=load(probe.site.local/'bx04-sustained-setup.json')['data'])
    record.update(phase='seeded',seed=seed);write(path,record)
    while time.time()<datetime.fromisoformat(seed['anchor']).timestamp():time.sleep(.1)
    observation=probe.operator.run('capacity');observation['health']=measured_health
    assert sum(row['ready'] for row in observation['groups'] if row['pool']=='bulk')==20
    policy=dict(protocol=1,maximum_age_seconds=60,startup_seconds=15,drain_seconds=60,
        pools=dict(urgent=dict(minimum=1,maximum=1,start_target_seconds=3),bulk=dict(minimum=1,maximum=6,start_target_seconds=3)),
        handlers={'org.example.background:load:1':dict(pool='bulk',default_seconds=.5,arrival_per_second=0)},
        headroom=dict(web_p95_ms=500,db_cpu_fraction=.85,connection_fraction=.7,lock_wait_seconds=2))
    observation_path=probe.site.local/'bx04-cold-burst-observation.json';write(observation_path,observation)
    policy_path=probe.site.local/'bx04-cold-burst-policy.json';write(policy_path,policy)
    advice=probe.operator.run('advise',observation=observation_path,policy=policy_path)
    assert advice['state']=='advised' and not advice['mutation_authorized'],advice
    constraints=advice['pools']['bulk']['constraints']
    assert 'reactive_start_too_late' in constraints and 'reactive_start_after_expiry' in constraints,constraints
    # Separate manual review is still required; advice carries no approval.
    began=datetime.now(timezone.utc).isoformat()
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    record.update(phase='growing',observation=observation,advice=advice,growth_began=began,approval=review['approval']);write(path,record)
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    ready=datetime.now(timezone.utc).isoformat()
    assert datetime.fromisoformat(ready)>datetime.fromisoformat(seed['deadline'])
    wait(lambda:all(probe.row(job)['state']=='dead_letter' for job in seed['jobs']),45)
    rows=[probe.row(job) for job in seed['jobs']]
    assert all(row['attempts']==0 and row['error']=='DEADLINE_EXCEEDED' for row in rows)
    record.update(phase='passed',ready_at=ready,cold_growth_seconds=(datetime.fromisoformat(ready)-datetime.fromisoformat(began)).total_seconds(),
        expired_before_any_claim=20,drain=probe.operator.run('drain'))
    assert record['drain']['state']=='paused' and not probe.operator._lanes()
    write(path,record);print(json.dumps(dict(phase='passed',expired=20,cold_growth_seconds=record['cold_growth_seconds'])),flush=True)


if __name__=='__main__':main()
