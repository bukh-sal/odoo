"""Paired stock WebClient benchmark with the frozen BG-01 workload."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import math
from statistics import median
import sys
from threading import Barrier,Event,Thread
import time

from background_lifecycle import shell
from background_site import write
from background_workers import Probe,docker,wait
from background_workload import workload,verify_profile
from check_reference import Client


SEED="""
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
from uuid import uuid4
assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
anchor=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=12)
rows={}
models={}
jobs={}
for index,who,workspace in [(0,'alice','A'),(1,'bob','B')]:
    actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][who]['id'],{}),
                              FIXTURE['workspaces'][workspace]['public_id'])
    model=actor['mp.background.task']
    models[index]=model
    if RANGES:
        rows[index]=model.search([('id','>=',RANGES[index][0]),('id','<=',RANGES[index][1])],order='id')
        assert len(rows[index])==500
        continue
    env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users'][who]['principal_id']])
    assignee=env.cr.fetchone()[0]
    schedule={row['task']:row['offset_seconds'] for row in WORKLOAD['reminders'] if row['workspace']==index}
    values=[]
    for row in WORKLOAD['tasks']:
        if row['workspace']!=index:continue
        data=dict(name='BG workload '+str(row['task']),points=row['points'])
        if row['task'] in schedule:
            data.update(assignee_id=assignee,
                due_at=(anchor+timedelta(seconds=schedule[row['task']])).replace(tzinfo=None))
        values.append(data)
    rows[index]=model.create(values)
    for number in schedule:
        job=rows[index][number-1]._queue_current()
        assert job
        jobs[job]='urgent'
for value in WORKLOAD['reports']:
    index=value['workspace']
    picked=rows[index]
    assert len(picked)==500 and picked[-1].id-picked[0].id==499
    when=anchor if not RANGES else datetime.now(timezone.utc)
    job=enqueue_scheduled(models[index]._job_env(),'jobs','org.example.background:report',
        dict(first=picked[0].id,last=picked[-1].id),str(uuid4()),version=2,
        schedule=JobSchedule(when,when+timedelta(seconds=value['expires_after_seconds']),value['attempt_seconds']))
    jobs[job]='bulk'
env.cr.commit()
print('BG_LOAD='+json.dumps(dict(anchor=anchor.isoformat(),jobs=jobs,
    ranges={index:[picked[0].id,picked[-1].id] for index,picked in rows.items()})))
"""


def summary(samples):
    return dict(count=len(samples),median_ms=round(median(samples),3),
        p95_ms=round(sorted(samples)[math.ceil(len(samples)*.95)-1],3),max_ms=round(max(samples),3))


def seed_jobs(probe, label, ranges):
    raw=shell(probe,label,'import json\nFIXTURE='+repr(probe.fixture)+'\nWORKLOAD='+repr(workload())+
              '\nRANGES='+repr(ranges)+'\n'+SEED)
    row,=[json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BG_LOAD=')]
    return row


def observe(probe,jobs):
    ids=','.join("'"+job+"'" for job in jobs)
    return json.loads(probe.sql(f"""SELECT jsonb_build_object('at',extract(epoch FROM clock_timestamp()),
        'ready',count(*) FILTER (WHERE state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp())),
        'oldest_urgent_ms',COALESCE(round(max(extract(epoch FROM timezone('UTC',clock_timestamp())-available_at)*1000)
            FILTER (WHERE handler LIKE '%:remind' AND state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp()))),0),
        'running',count(*) FILTER (WHERE state='running'), 'queued',count(*) FILTER (WHERE state IN ('pending','retry')),
        'completed',count(*) FILTER (WHERE state='completed'),
        'bulk_completed',count(*) FILTER (WHERE handler LIKE '%:report' AND state='completed'),
        'pg_connections',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()),
        'pg_active',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='active'))
        FROM mp_job WHERE public_id IN ({ids});"""))


def run():
    probe=Probe('bg-03-01')
    lifecycle=json.loads((probe.site.local/'bg03-release-queue.json').read_text())
    assert lifecycle['phase']=='passed'
    path=probe.site.local/'bg04-load.json'
    assert not path.exists()
    result=dict(phase='preparing',image=probe.state['image_id'],workload=verify_profile())
    write(path,result)
    a,b=(probe.fixture['workspaces'][key]['id'] for key in ('A','B'))
    alice=probe.fixture['users']['alice']
    bob=probe.fixture['users']['bob']
    assert probe.sql('SELECT count(*) FROM mp_example_note;')=='0'
    for workspace,user,count in ((a,alice,10000),(b,bob,1)):
        probe.sql(f"""INSERT INTO mp_example_note
            (workspace_id,public_id,title,body,author_id,revision,create_uid,write_uid,create_date,write_date)
            SELECT {workspace},gen_random_uuid()::text,'BG benchmark '||lpad(i::text,5,'0'),
            repeat(md5(i::text),300),p.id,1,p.user_id,p.user_id,timezone('UTC',now()),timezone('UTC',now())
            FROM generate_series(1,{count}) i CROSS JOIN mp_principal p WHERE p.public_id='{user['principal_id']}';""")
    probe.sql('ANALYZE mp_example_note; ANALYZE mp_job;')
    def snapshot():
        return probe.sql("SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n;")
    before=snapshot()
    ident=int(probe.sql(f"SELECT id FROM mp_example_note WHERE workspace_id={a} AND title='BG benchmark 00100';"))
    probe.site.state=lambda:dict(probe.state)
    clients=[Client(probe.site,'alice') for _ in range(20)]
    assert clients[0].native('mp.example.note','search_count',[[]])==10000
    assert clients[0].native('mp.example.note','search_count',[[]],workspace='B')==1
    names={'application':probe.target['worker_id'],'postgres':probe.project+'-db-1','edge':probe.project+'-edge-1'}
    for row in probe.operator.run('start')['lanes']:
        names[row['name']]=row['container']
    resources={}
    for role,name in names.items():
        row=json.loads(docker('inspect',name))[0]['HostConfig']
        resources[role]=dict(nano_cpus=row['NanoCpus'],memory_bytes=row['Memory'])
    cpu,memory,driver=docker('info','--format','{{.NCPU}} {{.MemTotal}} {{.Driver}}').decode().split()
    resources['docker']=dict(cpus=int(cpu),memory_bytes=int(memory),storage_driver=driver)

    def request(client,case):
        if case=='list':
            result=client.native('mp.example.note','web_search_read',kwargs=dict(domain=[],offset=0,limit=80,
                specification={name:{} for name in ('title','revision','write_date')}))
            assert len(result['records'])==80 and all(row['title'].startswith('BG benchmark ') for row in result['records'])
        else:
            row,=client.native('mp.example.note','web_read',[[ident]],dict(
                specification={name:{} for name in ('title','body','revision')}))
            assert row['id']==ident and len(row['body'])==9600

    def paired():
        values={'list':[],'detail':[]}
        with ThreadPoolExecutor(max_workers=20) as pool:
            for _ in range(10):
                for case in values:
                    start=Barrier(20)
                    def timed(client):
                        start.wait(timeout=12)
                        now=time.perf_counter()
                        request(client,case)
                        return (time.perf_counter()-now)*1000
                    values[case].extend(pool.map(timed,clients))
                    time.sleep(1.20)
        return {key:summary(samples) for key,samples in values.items()}

    for case in ('list','detail'):
        for _ in range(3):request(clients[0],case)
    time.sleep(1.2)
    idle=paired()
    result.update(phase='idle_measured',idle=idle,resources=resources)
    write(path,result)
    loaded=seed_jobs(probe,'bg04-mixed-seed',{})
    jobs=loaded['jobs']
    assert list(jobs.values()).count('urgent')==150 and list(jobs.values()).count('bulk')==40
    anchor=datetime.fromisoformat(loaded['anchor']).timestamp()
    time.sleep(max(0,anchor-time.time()))
    samples=[]
    sampling_done=Event()
    def sample():
        while not sampling_done.is_set():
            samples.append(observe(probe,jobs))
            if sampling_done.wait(.5):break
    monitor=Thread(target=sample,daemon=True)
    monitor.start()
    try:
        mixed=paired()
        wait(lambda:observe(probe,jobs)['completed']==190,timeout=120)
    finally:
        sampling_done.set()
        monitor.join(timeout=20)
    samples.append(observe(probe,jobs))
    assert not monitor.is_alive() and samples and any(row['running']>=2 for row in samples)
    assert any(row['bulk_completed']<40 and row['running']>=2 for row in samples if row['at']>=anchor+20)
    telemetry=[]
    for pool,count in (('urgent',1),('bulk',2)):
        for index in range(1,count+1):
            telemetry.extend(probe.logs(f'{probe.project}-job-{pool}-{index}',lines='1800'))
    starts={row['job_id']:row['start_delay_ms'] for row in telemetry
            if row.get('event')=='claimed' and row.get('job_id') in jobs}
    assert set(starts)==set(jobs)
    durations={row['job_id']:row['duration_ms'] for row in telemetry
               if row.get('event')=='attempt_end' and row.get('job_id') in jobs}
    assert set(durations)==set(jobs)
    timings={pool:dict(start=summary([starts[job] for job in starts if jobs[job]==pool]),
                      duration=summary([durations[job] for job in durations if jobs[job]==pool]))
             for pool in ('urgent','bulk')}
    bulk_seconds=next((row['at']-anchor for row in samples if row['bulk_completed']==40),None)
    assert bulk_seconds is not None
    oldest=max(row['oldest_urgent_ms'] for row in samples)
    result.update(phase='mixed_measured',mixed=mixed,worker_timings=timings,oldest_urgent_ms=oldest,
                  bulk_drain_seconds=bulk_seconds,bulk_throughput_per_second=40/bulk_seconds,
                  pg_connections_peak=max(row['pg_connections'] for row in samples),
                  pg_active_peak=max(row['pg_active'] for row in samples),
                  queue_peak=max(row['queued'] for row in samples),sample_count=len(samples))
    write(path,result)
    assert all(mixed[key]['p95_ms']<500 and mixed[key]['p95_ms']<=1.25*idle[key]['p95_ms']
               for key in mixed),result['mixed']
    assert timings['urgent']['start']['p95_ms']<=3000 and oldest<=10000 and bulk_seconds<=120
    ids=','.join("'"+job+"'" for job in jobs)
    assert probe.sql(f"""SELECT count(*) FROM mp_job j JOIN mp_outbox e ON e.causation_id=j.public_id
        JOIN mp_background_task t ON t.public_id=e.aggregate_id
        JOIN mp_background_notification n ON n.task_id=t.id AND n.revision=e.aggregate_sequence
        WHERE j.public_id IN ({ids}) AND e.topic='org.example.background.notification'
        AND e.workspace_id=j.workspace_id AND t.workspace_id=j.workspace_id AND n.recipient_id=t.assignee_id;""")=='150'
    expected=sum(index%13 for index in range(1,501))
    assert probe.sql(f"""SELECT count(*) FROM mp_job WHERE public_id IN ({ids}) AND handler LIKE '%:report'
        AND result->>'count'='500' AND result->>'points'='{expected}';""")=='40'
    assert before==snapshot()

    restart=seed_jobs(probe,'bg04-restart-seed',{int(key):value for key,value in loaded['ranges'].items()})
    running=wait(lambda:next((job for job in restart['jobs'] if probe.lane(job)),None))
    mechanism=probe.kill(probe.lane(running))
    recovered=time.monotonic()
    wait(lambda:observe(probe,restart['jobs'])['completed']==40,timeout=120)
    after=time.monotonic()-recovered
    assert after<=120 and before==snapshot()
    probe.operator.run('drain')
    result.update(phase='passed',recovered_after_seconds=round(after,3),restart=mechanism,
                  native_notes_unchanged=True,notifications=150,scoped_reports=40,
                  restart_reports=40)
    write(path,result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    run()
