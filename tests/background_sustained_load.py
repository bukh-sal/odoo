"""Admitted 180-second hot/distributed load with paired stock Odoo HTTP."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import hashlib
from pathlib import Path
from threading import Barrier,Event,Thread
import time

from background_load import BrowserConnection,Sampler,summary
from background_site import load,write
from background_sustained import native
from background_web_capacity import listen
from background_workers import Probe,docker
from background_workload import workload


SEED="""
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from modular_platform.durable import JobSchedule
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
import json
anchor=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=100)
actors={};jobs={}
for label,row in DATA.items():
    actors[label]=scoped_environment(api.Environment(env.cr,FIXTURE['users'][row['user']]['id'],{}),row['public_id'])
for workspace,label in [(0,'A'),(1,'B')]:
    actor=actors[label];model=actor['mp.background.task']
    env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users'][DATA[label]['user']]['principal_id']])
    assignee,=env.cr.fetchone()
    values=[dict(name=KEYTAG+' reminder '+str(n),points=n%13,assignee_id=assignee,
        due_at=(anchor+timedelta(seconds=row['offset_seconds'])).replace(tzinfo=None))
        for n,row in enumerate(WORKLOAD['reminders']) if row['workspace']==workspace]
    tasks=model.create(values)
    for task in tasks:
        job=task._queue_current();assert job
        jobs[job]=dict(pool='urgent',workspace=label,task=task.public_id)
labels=sorted(DATA) if CASE=='many' else ['A']
for index in range(72):
    label=labels[index%len(labels)];actor=actors[label];row=DATA[label]
    when=anchor+timedelta(seconds=index*2.5)
    cost=[250000,1000000,5000000][index//4%3]
    short=index%4==3
    handler='org.example.background:load' if short else 'org.example.background:report'
    inputs=dict(iterations=cost) if short else dict(first=row['first'],last=row['last'])
    job=enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs',handler,inputs,KEYTAG+'-bulk-'+str(index),
        schedule=JobSchedule(when,when+timedelta(seconds=180),20),version=1 if short else 2)
    jobs[job]=dict(pool='bulk',workspace=label,handler=handler,input=inputs)
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(anchor=anchor.isoformat(),committed=datetime.now(timezone.utc).isoformat(),jobs=jobs)))
"""


def run(case,attempt=1):
    probe=Probe('bx-04-capacity-01')
    setup=load(probe.site.local/'bx04-sustained-setup.json')
    assert setup['phase']=='reference_upgraded'
    assert type(attempt) is int and 1<=attempt<=10
    suffix='' if attempt==1 else '-'+str(attempt).zfill(2)
    tag=case+suffix
    path=probe.site.local/('bx04-sustained-'+tag+'.json');assert not path.exists()
    assert not probe.operator._lanes()
    record=dict(phase='starting',case=case,attempt=attempt,image=probe.target['image_id'],seconds=180,bulk_rate=.4,
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    write(path,record)
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    record.update(phase='seeding',approval=review['approval']);write(path,record)
    seed=native(probe,'bx04-sustained-seed-'+tag,SEED,DATA=setup['data'],CASE=case,KEYTAG=tag,WORKLOAD=workload())
    anchor=datetime.fromisoformat(seed['anchor']).timestamp()
    assert anchor-datetime.fromisoformat(seed['committed']).timestamp()>65
    record.update(phase='preloaded',seed=seed);write(path,record)
    notes=probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")
    note=int(probe.sql("SELECT id FROM mp_example_note WHERE title='BG benchmark 00100' ORDER BY id LIMIT 1"))
    probe.site.state=lambda:dict(probe.state)
    clients=[BrowserConnection(probe.site,'alice') for _ in range(20)]
    ids=','.join("'"+job+"'" for job in seed['jobs'])
    query="""SELECT jsonb_build_object('at',extract(epoch FROM clock_timestamp()),
        'completed',count(*) FILTER (WHERE state='completed'),
        'failed',count(*) FILTER (WHERE state IN ('dead_letter','held','cancelled','outcome_unknown')),
        'ready',count(*) FILTER (WHERE state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp())),
        'running',count(*) FILTER (WHERE state='running'),
        'connections',(SELECT count(*) FROM pg_stat_activity),
        'max_connections',current_setting('max_connections')::int,
        'lock_wait_seconds',COALESCE((SELECT max(extract(epoch FROM clock_timestamp()-query_start))
            FROM pg_stat_activity WHERE wait_event_type='Lock'),0)) FROM mp_job WHERE public_id IN ("""+ids+")"
    readings=[];cpus=[];stop=Event();errors=[]
    def cpu():
        raw=docker('exec',probe.project+'-db-1','cat','/sys/fs/cgroup/cpu.stat').decode().splitlines()
        return dict(at=time.time(),**{key:int(value) for key,value in (line.split() for line in raw)})
    def monitor():
        try:
            with Sampler(probe) as session:
                previous=cpu();last=previous['at']
                while not stop.is_set():
                    readings.append(json.loads(session.sql(query+';')))
                    if time.time()-last>=10:
                        current=cpu();elapsed=current['at']-previous['at']
                        cpus.append(dict(at=current['at'],interval=elapsed,
                            fraction=(current['usage_usec']-previous['usage_usec'])/1e6/elapsed/4,
                            throttled_usec=current['throttled_usec']-previous['throttled_usec']))
                        previous=current;last=current['at']
                    stop.wait(.5)
        except BaseException as error:errors.append(str(error))
    def request(client,kind):
        if kind=='list':
            result=client.native('mp.example.note','web_search_read',kwargs=dict(domain=[],offset=0,limit=80,
                specification={name:{} for name in ('title','revision','write_date')}))
            assert len(result['records'])==80
        else:
            result,=client.native('mp.example.note','web_read',[[note]],dict(specification={name:{} for name in ('title','body','revision')}))
            assert result['id']==note and len(result['body'])==9600
    def batch(pool,kind):
        barrier=Barrier(20)
        def timed(client):
            barrier.wait(timeout=12);start=time.monotonic();request(client,kind)
            return (time.monotonic()-start)*1000
        return list(pool.map(timed,clients))
    listening=listen(probe)
    thread=Thread(target=monitor,daemon=True);thread.start()
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            for kind in ('list','detail'):batch(pool,kind);time.sleep(1.2)
            idle={'list':[],'detail':[]}
            for _ in range(10):
                for kind in idle:idle[kind].extend(batch(pool,kind));time.sleep(1.2)
            assert time.time()<anchor-5,'Preload/warmup consumed the scheduled start window'
            record.update(phase='idle_measured',idle={key:summary(values) for key,values in idle.items()});write(path,record)
            while time.time()<anchor-5:time.sleep(min(.5,anchor-5-time.time()))
            # The scheduled wait can exceed the proxy keepalive lifetime.
            # Reconnect and warm both cases before their eligibility instant.
            for client in clients:client.connection.close()
            for kind in ('list','detail'):batch(pool,kind);time.sleep(1.2)
            assert time.time()<anchor,'Reconnection ran into the scheduled workload'
            record['warm_connections_at_start']=sum(client.connection.sock is not None for client in clients)
            assert record['warm_connections_at_start']==20
            while time.time()<anchor:time.sleep(min(.5,anchor-time.time()))
            mixed={'list':[],'detail':[]};rounds=[];index=0
            while time.time()<anchor+180 or not readings or readings[-1]['completed']<222:
                assert not errors,errors
                assert time.time()<anchor+300,'Backlog did not drain within120seconds'
                kind=('list','detail')[index%2];measured=batch(pool,kind);mixed[kind].extend(measured)
                rounds.append(dict(at=time.time(),kind=kind,**summary(measured)));index+=1;time.sleep(1.2)
            record.update(phase='measured',mixed={key:summary(values) for key,values in mixed.items()},web_rounds=rounds,
                final_reading=readings[-1],cpu_intervals=cpus,observations=readings)
            write(path,record)
    finally:
        stop.set();thread.join(timeout=6)
        for client in clients:client.connection.close()
    assert not thread.is_alive() and not errors,errors
    assert readings[-1]['failed']==0 and readings[-1]['completed']==222
    telemetry=[]
    for name in probe.operator._lanes():telemetry.extend(probe.logs(name,lines='2000'))
    claims={row['job_id']:row for row in telemetry if row.get('event')=='claimed' and row.get('job_id') in seed['jobs']}
    ends={row['job_id']:row for row in telemetry if row.get('event')=='attempt_end' and row.get('job_id') in seed['jobs']}
    assert set(claims)==set(ends)==set(seed['jobs'])
    timings={pool:dict(start=summary([row['start_delay_ms'] for job,row in claims.items() if seed['jobs'][job]['pool']==pool]),
        worker=summary([row['worker_duration_ms'] for job,row in ends.items() if seed['jobs'][job]['pool']==pool])) for pool in ('urgent','bulk')}
    row_checks=json.loads(probe.sql("""SELECT jsonb_build_object('reports',count(*) FILTER (WHERE handler LIKE '%:report'
        AND result->>'count'='10' AND result->>'points'='45'),'loads',count(*) FILTER (WHERE handler LIKE '%:load'
        AND result->>'iterations'=payload->'input'->>'iterations'),
        'repeated_attempts',count(*) FILTER (WHERE attempts<>1)) FROM mp_job WHERE public_id IN ("""+ids+")"))
    assert row_checks==dict(reports=54,loads=18,repeated_attempts=0),row_checks
    notifications=int(probe.sql("""SELECT count(*) FROM mp_job j JOIN mp_outbox e ON e.causation_id=j.public_id
        JOIN mp_background_task t ON t.public_id=e.aggregate_id JOIN mp_background_notification n
        ON n.task_id=t.id AND n.revision=e.aggregate_sequence
        WHERE j.public_id IN ("""+ids+""" ) AND e.workspace_id=j.workspace_id AND t.workspace_id=j.workspace_id
        AND n.recipient_id=t.assignee_id"""))
    assert notifications==150
    assert probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")==notes
    listen_after=listen(probe);delta={key:listen_after[key]-value for key,value in listening.items()}
    passed=dict(web=all(record['mixed'][key]['p95_ms']<500 and record['mixed'][key]['p95_ms']<=1.25*record['idle'][key]['p95_ms'] for key in record['mixed']),
        urgent=timings['urgent']['start']['p95_ms']<=3000,
        oldest_urgent=timings['urgent']['start']['max_ms']<=10000,bulk=timings['bulk']['start']['p95_ms']<=60000,
        connections=max(row['connections']/row['max_connections'] for row in readings)<=.7,
        locks=max(row['lock_wait_seconds'] for row in readings)<=2,
        cpu=all(row['fraction']<=.85 for row in cpus if row['at']>=anchor+10),listener=not any(delta.values()))
    drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
    record.update(phase='passed' if all(passed.values()) else 'targets_missed',checks=passed,timings=timings,
        scoped_outputs=row_checks,notifications=notifications,notes_unchanged=True,listen_delta=delta,drain=drained)
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],checks=passed,timings=timings)),flush=True)
    assert all(passed.values()),passed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case',choices=['hot','many'])
    parser.add_argument('--attempt',type=int,default=1)
    args=parser.parse_args();run(args.case,args.attempt)
