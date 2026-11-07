"""Admitted 180-second hot/distributed load with paired stock Odoo HTTP."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import hashlib
import copy
from pathlib import Path
from threading import Barrier,Event,Thread
import time

from background_load import BrowserConnection,Sampler,summary
from background_site import load,write
from background_sustained import native
from background_web_capacity import listen
from background_workers import Probe,docker
from background_workload import workload
from modular_platform.capacity_advisor import advise


SEED="""
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from modular_platform.durable import JobSchedule
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
import json
anchor=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=100)
actors={};jobs={};plans=[]
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
    when=anchor+timedelta(seconds=0 if BURST else index*2.5)
    cost=[250000,1000000,5000000][index//4%3]
    short=index%4!=0 if BURST else index%4==3
    handler='org.example.background:load' if short else 'org.example.background:report'
    inputs=dict(iterations=cost) if short else dict(first=row['first'],last=row['last'])
    plan=dict(workspace=label,handler=handler,input=inputs,version=1 if short else 2,
        run_at=when.isoformat(),expires_at=(when+timedelta(seconds=180)).isoformat(),key=KEYTAG+'-bulk-'+str(index))
    plans.append(plan)
    if not LIVE:
        job=enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs',handler,inputs,plan['key'],
            schedule=JobSchedule(when,when+timedelta(seconds=180),20),version=plan['version'])
        jobs[job]=dict(pool='bulk',workspace=label,handler=handler,input=inputs)
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(anchor=anchor.isoformat(),committed=datetime.now(timezone.utc).isoformat(),jobs=jobs,plans=plans)))
"""

LIVE_PRODUCER="""
from datetime import datetime,timezone
from odoo import api
from odoo.service.model import retrying
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
import json,time
env.cr.commit()
jobs={};commits=[]
for plan in PLANS:
    when=datetime.fromisoformat(plan['run_at'])
    while datetime.now(timezone.utc)<when:
        time.sleep(max(0,min(.25,(when-datetime.now(timezone.utc)).total_seconds())))
    row=DATA[plan['workspace']]
    with env.registry.cursor() as cr:
        metadata=api.Environment(cr,1,{})
        def enqueue():
            actor=scoped_environment(api.Environment(cr,FIXTURE['users'][row['user']]['id'],{}),row['public_id'])
            return enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs',plan['handler'],plan['input'],plan['key'],
                schedule=JobSchedule(when,datetime.fromisoformat(plan['expires_at']),20),version=plan['version'])
        job=retrying(enqueue,metadata)
        cr.execute('SELECT created_at FROM mp_job WHERE public_id=%s',[job]);created,=cr.fetchone()
    jobs[job]=dict(pool='bulk',workspace=plan['workspace'],handler=plan['handler'],input=plan['input'])
    commits.append(dict(job=job,nominal=when.isoformat(),created_at=created.replace(tzinfo=timezone.utc).isoformat(),
        committed_at=datetime.now(timezone.utc).isoformat()))
print('BX04_RESULT='+json.dumps(dict(jobs=jobs,commits=commits)))
"""


def run(case,attempt=1,live=False,burst=False,bulk_lanes=2):
    probe=Probe('bx-04-capacity-01')
    setup=load(probe.site.local/'bx04-sustained-setup.json')
    assert setup['phase']=='reference_upgraded'
    assert type(attempt) is int and 1<=attempt<=10
    suffix='' if attempt==1 else '-'+str(attempt).zfill(2)
    assert not (live and burst) and type(bulk_lanes) is int and 1<=bulk_lanes<=6
    tag=case+('-live' if live else '')+('-burst-'+str(bulk_lanes) if burst else '')+suffix
    path=probe.site.local/('bx04-sustained-'+tag+'.json');assert not path.exists()
    assert not probe.operator._lanes()
    duration=60 if burst else 180
    record=dict(phase='starting',case=case,attempt=attempt,live_enqueue=live,burst=burst,bulk_lanes=bulk_lanes,
        image=probe.target['image_id'],seconds=duration,bulk_rate=None if burst else .4,
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    write(path,record)
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=bulk_lanes)
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    record.update(phase='seeding',approval=review['approval']);write(path,record)
    seed=native(probe,'bx04-sustained-seed-'+tag,SEED,DATA=setup['data'],CASE=case,KEYTAG=tag,LIVE=live,BURST=burst,WORKLOAD=workload())
    anchor=datetime.fromisoformat(seed['anchor']).timestamp()
    assert anchor-datetime.fromisoformat(seed['committed']).timestamp()>65
    record.update(phase='preloaded',seed=seed);write(path,record)
    producer_result=[];producer_error=[];producer_thread=None
    producer_name=probe.project+'-bx04-live-producer-'+tag
    if live:
        def produce():
            try:producer_result.append(native(probe,'bx04-live-producer-'+tag,LIVE_PRODUCER,DATA=setup['data'],PLANS=seed['plans']))
            except BaseException as error:producer_error.append(str(error))
        producer_thread=Thread(target=produce,daemon=True);producer_thread.start()
    notes=probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n")
    note=int(probe.sql("SELECT id FROM mp_example_note WHERE title='BG benchmark 00100' ORDER BY id LIMIT 1"))
    probe.site.state=lambda:dict(probe.state)
    clients=[BrowserConnection(probe.site,'alice') for _ in range(20)]
    ids=','.join("'"+job+"'" for job in seed['jobs'])
    selector='(public_id IN ('+ids+") OR idempotency_key LIKE '"+tag+"-bulk-%')" if live else 'public_id IN ('+ids+')'
    query="""SELECT jsonb_build_object('at',extract(epoch FROM clock_timestamp()),
        'completed',count(*) FILTER (WHERE state='completed'),
        'failed',count(*) FILTER (WHERE state IN ('dead_letter','held','cancelled','outcome_unknown')),
        'ready',count(*) FILTER (WHERE state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp())),
        'running',count(*) FILTER (WHERE state='running'),
        'ready_bulk_workspaces',count(DISTINCT workspace_id) FILTER (WHERE handler NOT LIKE '%:remind'
            AND state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp())),
        'connections',(SELECT count(*) FROM pg_stat_activity),
        'max_connections',current_setting('max_connections')::int,
        'lock_wait_seconds',COALESCE((SELECT max(extract(epoch FROM clock_timestamp()-query_start))
            FROM pg_stat_activity WHERE wait_event_type='Lock'),0)) FROM mp_job WHERE """+selector
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
            if burst:
                calibration=load(probe.site.local/'bx04-calibration.json')
                assert calibration['phase']=='passed'
                snapshot=probe.operator.run('capacity')
                assert snapshot['pins']==calibration['snapshot']['pins']
                snapshot['samples']=calibration['snapshot']['samples']
                projected=copy.deepcopy(snapshot)
                projected['observed_at']=seed['anchor']
                ready=0
                for group in projected['groups']:
                    if group['pool']=='bulk' and group['current']:
                        group.update(ready=group['future'],future=0,original_wait_ms=0,retry_wait_ms=0,
                            min_validity_ms=180000 if group['future'] else None)
                        ready+=group['ready']
                assert ready==72
                assert cpus and readings
                projected['health']=dict(observed_at=datetime.fromtimestamp(readings[-1]['at'],timezone.utc).isoformat(),
                    web_p95_ms=max(value['p95_ms'] for value in record['idle'].values()),
                    db_cpu_fraction=cpus[-1]['fraction'],lock_wait_seconds=readings[-1]['lock_wait_seconds'])
                policy=dict(protocol=1,maximum_age_seconds=60,startup_seconds=15,drain_seconds=60,
                    pools=dict(urgent=dict(minimum=1,maximum=1,start_target_seconds=3),
                        bulk=dict(minimum=1,maximum=6,start_target_seconds=60)),
                    handlers={'org.example.background:report:2':dict(pool='bulk',default_seconds=2,arrival_per_second=0),
                        'org.example.background:load:1':dict(pool='bulk',default_seconds=.5,arrival_per_second=0)},
                    headroom=dict(web_p95_ms=500,db_cpu_fraction=.85,connection_fraction=.7,lock_wait_seconds=2))
                weighted=advise(projected,policy,now=datetime.fromisoformat(seed['anchor']),expected_pins=snapshot['pins'])
                count_snapshot=copy.deepcopy(projected);count_snapshot['samples']=[]
                count_policy=copy.deepcopy(policy)
                for value in count_policy['handlers'].values():value['default_seconds']=2
                count=advise(count_snapshot,count_policy,now=datetime.fromisoformat(seed['anchor']),expected_pins=snapshot['pins'])
                assert weighted['state']==count['state']=='advised',(weighted,count)
                record['sizing_comparison']=dict(kind='planned eligibility projection, not a live queue observation',
                    policy=policy,count_policy=count_policy,weighted=weighted,count=count,
                    fixed_bulk_lanes=2,snapshot=projected)
                write(path,record)
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
            while time.time()<anchor+duration or not readings or readings[-1]['completed']<222:
                assert not errors,errors
                assert not producer_error,producer_error
                assert time.time()<anchor+300,'Backlog did not drain within120seconds'
                kind=('list','detail')[index%2];measured=batch(pool,kind);mixed[kind].extend(measured)
                rounds.append(dict(at=time.time(),kind=kind,**summary(measured)));index+=1;time.sleep(1.2)
            record.update(phase='measured',mixed={key:summary(values) for key,values in mixed.items()},web_rounds=rounds,
                final_reading=readings[-1],cpu_intervals=cpus,observations=readings)
            write(path,record)
    finally:
        stop.set();thread.join(timeout=6)
        for client in clients:client.connection.close()
        if producer_thread is not None and producer_thread.is_alive():
            # This is an explicitly owned, bounded test producer. Never leave
            # future enqueueing detached after a failed HTTP measurement.
            row,=json.loads(docker('inspect',producer_name))
            assert row['Config']['Labels']['com.modular.disposable']==probe.project
            docker('stop','--time','5',producer_name)
            producer_thread.join(timeout=10)
    if live:
        assert producer_thread is not None and not producer_thread.is_alive() and not producer_error,producer_error
        result,=producer_result
        assert len(result['jobs'])==72
        seed['jobs'].update(result['jobs'])
        record.update(live_producer=result)
        ids=','.join("'"+job+"'" for job in seed['jobs'])
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
    assert row_checks==dict(reports=18 if burst else 54,loads=54 if burst else 18,repeated_attempts=0),row_checks
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
    if burst:passed['simultaneous_64_plus_workspaces']=max(row['ready_bulk_workspaces'] for row in readings)>=64
    last_bulk=max(datetime.fromisoformat(row['at']).timestamp() for job,row in ends.items() if seed['jobs'][job]['pool']=='bulk')
    record['bulk_drain_seconds']=last_bulk-anchor
    record['post_arrival_bulk_drain_seconds']=max(0,last_bulk-(anchor if burst else anchor+177.5))
    passed['bulk_drain']=record['post_arrival_bulk_drain_seconds']<=120
    record['bulk_lane_seconds_to_drain']=bulk_lanes*(last_bulk-anchor)
    record['bulk_lane_hours_to_drain']=record['bulk_lane_seconds_to_drain']/3600
    record['bulk_lane_seconds_window']=bulk_lanes*(readings[-1]['at']-anchor)
    drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
    record.update(phase='passed' if all(passed.values()) else 'targets_missed',checks=passed,timings=timings,
        per_job_claims=claims,per_job_ends=ends,
        scoped_outputs=row_checks,notifications=notifications,notes_unchanged=True,listen_delta=delta,drain=drained)
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],checks=passed,timings=timings)),flush=True)
    assert all(passed.values()),passed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case',choices=['hot','many'])
    parser.add_argument('--attempt',type=int,default=1)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--burst',action='store_true')
    parser.add_argument('--bulk-lanes',type=int,default=2)
    args=parser.parse_args();run(args.case,args.attempt,args.live,args.burst,args.bulk_lanes)
