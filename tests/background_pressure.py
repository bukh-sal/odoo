"""Owned native connection-pressure and genuinely aged telemetry qualification."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from threading import Thread
import time

from background_load import BrowserConnection, summary
from background_site import load, write
from background_sustained import native
from background_workers import Probe, docker, wait


PRESSURE = """
import json,time,psycopg2
from odoo.tools import config
connections=[]
try:
    env.cr.execute("SELECT current_setting('max_connections')::int,count(*) FROM pg_stat_activity")
    maximum,used=env.cr.fetchone()
    count=max(1,int(maximum*.75)-used)
    assert count<=75
    for _ in range(count):
        connection=psycopg2.connect(env.cr._cnx.dsn,password=config['db_password'],application_name=TAG)
        connections.append(connection)
    time.sleep(65)
finally:
    for connection in connections:connection.close()
print('BX04_RESULT='+json.dumps(dict(connections=len(connections),closed=True)))
"""

SEED = """
from datetime import datetime,timedelta,timezone
import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
row=DATA['A'];actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),row['public_id'])
jobs=[]
now=datetime.now(timezone.utc)
for index in range(20):
    jobs.append(enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:report',
        dict(first=row['first'],last=row['last']),TAG+'-report-'+str(index),version=2,
        schedule=JobSchedule(now,now+timedelta(seconds=180),20)))
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(jobs=jobs)))
"""


def main(attempt):
    tag='bx04-pressure-'+str(attempt).zfill(2)
    probe=Probe('bx-04-capacity-01');path=probe.site.local/(tag+'.json')
    assert not path.exists() and not probe.operator._lanes()
    record=dict(phase='starting',image=probe.state['image_id']);write(path,record)
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='ready'
    before={key:value['Id'] for key,value in probe.operator._lanes().items()}
    notes=probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")
    probe.site.state=lambda:dict(probe.state)
    client=BrowserConnection(probe.site,'alice')
    def read():
        start=time.monotonic()
        result=client.native('mp.example.note','web_search_read',kwargs=dict(domain=[],offset=0,limit=80,
            specification={name:{} for name in ('title','revision','write_date')}))
        assert len(result['records'])==80
        return (time.monotonic()-start)*1000
    def cpu():
        values=dict(line.split() for line in docker('exec',probe.project+'-db-1','cat','/sys/fs/cgroup/cpu.stat').decode().splitlines())
        return time.monotonic(),int(values['usage_usec'])
    results=[];errors=[]
    def pressure():
        try:results.append(native(probe,tag+'-connections',PRESSURE,TAG=tag))
        except BaseException as error:errors.append(str(error))
    thread=Thread(target=pressure,daemon=True);thread.start()
    try:
        wait(lambda:errors or probe.sql("SELECT count(*)>current_setting('max_connections')::int*.7 AND count(*) FILTER (WHERE application_name='"+tag+"')>0 FROM pg_stat_activity")=='t',30)
        assert not errors,errors
        seed=native(probe,tag+'-seed',SEED,TAG=tag,DATA=load(probe.site.local/'bx04-sustained-setup.json')['data'])
        record.update(phase='pressure_active',seed=seed,approval=review['approval']);write(path,record)
        start,usage=cpu();reads=[read() for _ in range(10)]
        time.sleep(max(0,10-(time.monotonic()-start)))
        end,finish=cpu()
        observation=probe.operator.run('capacity')
        observation['health']=dict(observed_at=datetime.now(timezone.utc).isoformat(),web_p95_ms=summary(reads)['p95_ms'],
            db_cpu_fraction=(finish-usage)/1e6/(end-start)/4,lock_wait_seconds=observation['database']['longest_lock_wait_seconds'])
        assert observation['database']['connections']>observation['database']['max_connections']*.7
        policy=dict(protocol=1,maximum_age_seconds=30,startup_seconds=15,drain_seconds=60,
            pools=dict(urgent=dict(minimum=1,maximum=1,start_target_seconds=3),bulk=dict(minimum=1,maximum=6,start_target_seconds=60)),
            handlers={'org.example.background:report:2':dict(pool='bulk',default_seconds=2,arrival_per_second=0)},
            headroom=dict(web_p95_ms=500,db_cpu_fraction=.85,connection_fraction=.7,lock_wait_seconds=2))
        policy_path=probe.site.local/(tag+'-policy.json');write(policy_path,policy)
        def advice(label,value,expected):
            observation_path=probe.site.local/(tag+'-'+label+'.json');write(observation_path,value)
            result=probe.operator.run('advise',observation=observation_path,policy=policy_path)
            assert result['state']=='hold' and expected in result['reasons'],result
            assert all(row['advised_lanes'] is None for row in result['pools'].values())
            return result
        pressured=advice('observed',observation,'headroom_connections')
        missing=deepcopy(observation);missing.pop('health')
        missing_result=advice('missing',missing,'missing_headroom')
        # Age the real observation rather than manufacture an old timestamp.
        policy['maximum_age_seconds']=1;write(policy_path,policy);time.sleep(2)
        stale=advice('stale',observation,'stale_or_future_observation')
        assert 'stale_or_future_headroom' in stale['reasons']
        record.update(phase='holds_verified',observation=observation,web=summary(reads),pressure=pressured,
            missing=missing_result,stale=stale);write(path,record)
    finally:
        thread.join(timeout=90)
    assert not thread.is_alive() and not errors,(errors,results)
    assert len(results)==1 and 0<results[0]['connections']<=75 and results[0]['closed']
    assert probe.sql("SELECT count(*) FROM pg_stat_activity WHERE application_name='"+tag+"'")=='0'
    wait(lambda:all(probe.row(job)['state']=='completed' for job in seed['jobs']),90)
    assert all(probe.row(job)['attempts']==1 for job in seed['jobs'])
    assert before=={key:value['Id'] for key,value in probe.operator._lanes().items()}
    assert notes==probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")
    record.update(phase='passed',pressure_helper=results[0],connections_closed=True,no_resize=True,jobs_completed_once=20,
        notes_unchanged=True,drain=probe.operator.run('drain'))
    assert record['drain']['state']=='paused' and not probe.operator._lanes()
    write(path,record);print(json.dumps(dict(phase='passed',reasons=pressured['reasons'],jobs=20)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--attempt',type=int,required=True,choices=range(1,10))
    main(parser.parse_args().attempt)
