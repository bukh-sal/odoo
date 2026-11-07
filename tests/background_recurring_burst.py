"""BX-04: recurring distributed reports through the reviewed native producer."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from threading import Barrier
import time

from background_load import BrowserConnection, summary
from background_recurrence import PROVISION, API_PROBE
from background_site import load, write
from background_sustained import native
from background_web_capacity import listen
from background_workers import Probe, docker, wait


def main():
    probe=Probe('bx-04-capacity-01');path=probe.site.local/'bx04-recurring-burst.json'
    assert not path.exists() and not probe.operator._lanes()
    setup=load(probe.site.local/'bx04-sustained-setup.json');labels=sorted(setup['data'])[:10]
    anchor=(datetime.now(timezone.utc)+timedelta(seconds=90)).replace(microsecond=0)
    record=dict(phase='provisioning',image=probe.state['image_id'],anchor=anchor.isoformat());write(path,record)
    source=PROVISION.replace("for label in ('A','B'):","for label in LABELS:")
    source=source.replace("workspace=FIXTURE['workspaces'][label]","workspace=DATA[label]")
    source=source.replace("'bx03-service-'","'bx04-burst-service-'")
    source=source.replace('datetime.now(timezone.utc).replace(microsecond=0),60,3600,5',
                          'datetime.fromisoformat(ANCHOR),30,120,20')
    source=source.replace('dict(first=1,last=1)',"dict(first=workspace['first'],last=workspace['last'])")
    services=native(probe,'bx04-recurring-services',source.replace('BX03_RESULT=','BX04_RESULT='),
        LABELS=labels,DATA=setup['data'],ANCHOR=anchor.isoformat())
    assert len(services)==10
    record.update(phase='provisioned',services=services);write(path,record)
    # Review the new exact credential footprint while every role is stopped.
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2,producer_lanes=1,paused=True)
    assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='paused'
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2,producer_lanes=1)
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    actor_source='SERVICES='+repr(services)+'\n'+API_PROBE.split('def row(',1)[0]
    def change(action):
        code=actor_source+"\nresult={}\nfor label,row in SERVICES.items():\n"
        code+="    env.cr.execute('SELECT config_version FROM mp_job_schedule WHERE public_id=%s',[row['schedule']])\n"
        code+="    revision,=env.cr.fetchone()\n"
        code+="    result[label]=recurring."+action+"_schedule(actor(label),row['schedule'],revision)\n"
        code+="env.cr.commit()\nprint('BX04_RESULT='+json.dumps(result))\n"
        return native(probe,'bx04-recurring-'+action,code)
    active=change('resume')
    assert time.time()<anchor.timestamp()-20
    record.update(phase='ready',approval=review['approval'],activation=active);write(path,record)
    notes=probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")
    ids=','.join("'"+row['schedule']+"'" for row in services.values())
    query="""SELECT jsonb_build_object('at',extract(epoch FROM clock_timestamp()),
        'receipts',(SELECT count(*) FROM mp_job_occurrence WHERE schedule_id IN ("""+ids+""")),
        'duplicate_nominals',(SELECT count(*) FROM (SELECT schedule_id,nominal_at FROM mp_job_occurrence
            WHERE schedule_id IN ("""+ids+""") GROUP BY schedule_id,nominal_at HAVING count(*)>1) d),
        'overlap',(SELECT count(*) FROM (SELECT o.schedule_id FROM mp_job_occurrence o JOIN mp_job j ON j.public_id=o.job_public_id
            WHERE o.schedule_id IN ("""+ids+""") AND j.state IN ('pending','running','retry','held','outcome_unknown')
            GROUP BY o.schedule_id HAVING count(*)>1) d),
        'connections',(SELECT count(*) FROM pg_stat_activity),'max_connections',current_setting('max_connections')::int,
        'lock_wait_seconds',COALESCE((SELECT max(extract(epoch FROM clock_timestamp()-query_start))
            FROM pg_stat_activity WHERE wait_event_type='Lock'),0))"""
    probe.site.state=lambda:dict(probe.state)
    clients=[BrowserConnection(probe.site,'alice') for _ in range(20)]
    note=int(probe.sql("SELECT id FROM mp_example_note WHERE title='BG benchmark 00100' ORDER BY id LIMIT 1"))
    def batch(pool,kind):
        barrier=Barrier(20)
        def request(client):
            barrier.wait(timeout=12);start=time.monotonic()
            if kind=='list':
                result=client.native('mp.example.note','web_search_read',kwargs=dict(domain=[],offset=0,limit=80,
                    specification={name:{} for name in ('title','revision','write_date')}))
                assert len(result['records'])==80
            else:
                result,=client.native('mp.example.note','web_read',[[note]],dict(specification={name:{} for name in ('title','body','revision')}))
                assert result['id']==note
            return (time.monotonic()-start)*1000
        return list(pool.map(request,clients))
    def cpu():
        raw=dict(row.split() for row in docker('exec',probe.project+'-db-1','cat','/sys/fs/cgroup/cpu.stat').decode().splitlines())
        return time.time(),int(raw['usage_usec'])
    observations=[];cpus=[];idle={'list':[],'detail':[]};mixed={'list':[],'detail':[]}
    listening=listen(probe)
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            for kind in idle:batch(pool,kind);time.sleep(1.2)
            for _ in range(10):
                for kind in idle:idle[kind].extend(batch(pool,kind));time.sleep(1.2)
            while time.time()<anchor.timestamp()-5:time.sleep(min(1,max(0,anchor.timestamp()-5-time.time())))
            for kind in idle:batch(pool,kind);time.sleep(1.2)
            while time.time()<anchor.timestamp():time.sleep(.1)
            record.update(phase='measuring',idle={key:summary(values) for key,values in idle.items()});write(path,record)
            previous=cpu()
            for index in range(90):
                reading=json.loads(probe.sql(query));observations.append(reading)
                assert reading['duplicate_nominals']==reading['overlap']==0,reading
                if index%9==0:
                    for kind in mixed:mixed[kind].extend(batch(pool,kind));time.sleep(1.2)
                if time.time()-previous[0]>=10:
                    current=cpu();cpus.append(dict(seconds=current[0]-previous[0],fraction=(current[1]-previous[1])/1e6/(current[0]-previous[0])/4));previous=current
                until=anchor.timestamp()+(index+1)*2
                while time.time()<until:time.sleep(min(.5,until-time.time()))
        paused=change('pause')
        count=int(probe.sql('SELECT count(*) FROM mp_job_occurrence WHERE schedule_id IN ('+ids+')'))
        time.sleep(2)
        assert int(probe.sql('SELECT count(*) FROM mp_job_occurrence WHERE schedule_id IN ('+ids+')'))==count
        def settled():
            return probe.sql("SELECT count(*) FROM mp_job_occurrence o JOIN mp_job j ON j.public_id=o.job_public_id WHERE o.schedule_id IN ("+ids+") AND j.state<>'completed'")=='0'
        wait(settled,60)
        rows=json.loads(probe.sql("""SELECT jsonb_agg(jsonb_build_object('job',j.public_id,'state',j.state,
            'attempts',j.attempts,'result',j.result,'workspace',j.workspace_id,'nominal',o.nominal_at))
            FROM mp_job_occurrence o JOIN mp_job j ON j.public_id=o.job_public_id WHERE o.schedule_id IN ("""+ids+')'))
        assert 60<=len(rows)<=70
        assert all(row['attempts']==1 and row['result']['count']==10 and row['result']['points']==45 for row in rows),rows[:1]
        telemetry=[]
        for name in probe.operator._lanes():telemetry.extend(probe.logs(name,lines='2000'))
        jobs={row['job'] for row in rows}
        claims={row['job_id']:row for row in telemetry if row.get('event')=='claimed' and row.get('job_id') in jobs}
        assert set(claims)==jobs
        starts=summary([row['start_delay_ms'] for row in claims.values()])
        after=listen(probe);delta={key:after[key]-value for key,value in listening.items()}
        checks=dict(start_p95=starts['p95_ms']<=60000,
            web=all(summary(mixed[key])['p95_ms']<500 and summary(mixed[key])['p95_ms']<=1.25*summary(idle[key])['p95_ms'] for key in mixed),
            connections=max(row['connections']/row['max_connections'] for row in observations)<=.7,
            locks=max(row['lock_wait_seconds'] for row in observations)<=2,
            cpu=bool(cpus) and all(row['fraction']<=.85 for row in cpus),listener=not any(delta.values()))
        assert notes==probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")
        record.update(phase='passed' if all(checks.values()) else 'targets_missed',checks=checks,rows=rows,starts=starts,
            observations=observations,cpu=cpus,notes_unchanged=True,listen_delta=delta,pause=paused,
            mixed={key:summary(values) for key,values in mixed.items()},drain=probe.operator.run('drain'))
        assert record['drain']['state']=='paused' and not probe.operator._lanes()
        write(path,record);print(json.dumps(dict(phase=record['phase'],jobs=len(rows),checks=checks)),flush=True)
        assert all(checks.values()),checks
    finally:
        for client in clients:client.connection.close()


if __name__=='__main__':main()
