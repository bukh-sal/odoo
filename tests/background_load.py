"""Paired stock WebClient benchmark with the frozen BG-01 workload."""
import atexit
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from http.client import HTTPConnection
from http.cookiejar import CookieJar
import json
import math
from statistics import median
import subprocess
import sys
from threading import Barrier,Event,Thread
import time
from urllib.request import HTTPCookieProcessor

from background_lifecycle import shell
from background_web_capacity import listen
from background_site import ROOT,load,write
from background_workers import Probe,docker,wait
from background_workload import workload,verify_profile
from check_reference import Client


SEED="""
from datetime import datetime,timedelta,timezone
import re
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
from uuid import uuid4
assert env.cr.dbname==EXPECTED_DB and re.fullmatch(r'mp_disposable_r0_r1_(?:release|restore)_[a-f0-9]+',EXPECTED_DB)
anchor=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=ANCHOR_LEAD)
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
print('BG_LOAD='+json.dumps(dict(anchor=anchor.isoformat(),committed=datetime.now(timezone.utc).isoformat(),jobs=jobs,
    ranges={index:[picked[0].id,picked[-1].id] for index,picked in rows.items()})))
"""


def summary(samples):
    return dict(count=len(samples),median_ms=round(median(samples),3),
        p95_ms=round(sorted(samples)[math.ceil(len(samples)*.95)-1],3),max_ms=round(max(samples),3))


def seed_jobs(probe, label, ranges, *, anchor_lead=12):
    raw=shell(probe,label,'import json\nFIXTURE='+repr(probe.fixture)+'\nWORKLOAD='+repr(workload())+
              '\nRANGES='+repr(ranges)+'\nEXPECTED_DB='+repr(probe.state['database'])+
              '\nANCHOR_LEAD='+repr(anchor_lead)+'\n'+SEED)
    row,=[json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BG_LOAD=')]
    return row


def observe(probe,jobs,sql=None):
    ids=','.join("'"+job+"'" for job in jobs)
    return json.loads((sql or probe.sql)(f"""SELECT jsonb_build_object('at',extract(epoch FROM clock_timestamp()),
        'ready',count(*) FILTER (WHERE state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp())),
        'oldest_urgent_ms',COALESCE(round(max(extract(epoch FROM timezone('UTC',clock_timestamp())-available_at)*1000)
            FILTER (WHERE handler LIKE '%:remind' AND state IN ('pending','retry') AND available_at<=timezone('UTC',clock_timestamp()))),0),
        'running',count(*) FILTER (WHERE state='running'), 'queued',count(*) FILTER (WHERE state IN ('pending','retry')),
        'completed',count(*) FILTER (WHERE state='completed'),
        'bulk_completed',count(*) FILTER (WHERE handler LIKE '%:report' AND state='completed'),
        'pg_connections',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()),
        'pg_active',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='active'))
        FROM mp_job WHERE public_id IN ({ids});"""))


class Sampler:
    """One local read-only PSQL session for both paired phases."""
    def __init__(self,probe):
        self.probe=probe

    def __enter__(self):
        self.process=subprocess.Popen(['docker','exec','-i',self.probe.project+'-db-1',
            'psql','-XqAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',self.probe.state['database']],
            text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.process.stdin.write("SET default_transaction_read_only=on; SET statement_timeout='3s';\n")
        self.process.stdin.flush()
        return self

    def sql(self,query):
        self.process.stdin.write(query+'\n')
        self.process.stdin.flush()
        row=self.process.stdout.readline()
        if not row:raise RuntimeError('Live sampling session closed')
        return row

    def __exit__(self,*_):
        self.process.stdin.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


class BrowserConnection(Client):
    """Use one warm loopback HTTP connection per ordinary authenticated session."""
    def __init__(self,reference,actor):
        self.connection=None
        super().__init__(reference,actor)
        jar=next(handler.cookiejar for handler in self.http.handlers if isinstance(handler,HTTPCookieProcessor))
        assert isinstance(jar,CookieJar) and any(cookie.name=='session_id' for cookie in jar)
        self.cookie='; '.join(f'{cookie.name}={cookie.value}' for cookie in jar)
        self.connection=HTTPConnection('127.0.0.1',self.state['port'],timeout=30)

    def request(self,path,payload=None,workspace=None,headers=None):
        if self.connection is None:
            return super().request(path,payload,workspace,headers)
        headers=dict(headers or {},Host=self.state['hostname']+':'+str(self.state['port']),Cookie=self.cookie)
        headers['X-MP-Client-Release']=self.token
        if workspace:headers['X-MP-Workspace']=self.fixture['workspaces'][workspace]['public_id']
        if payload is not None:headers['Content-Type']='application/json'
        self.connection.request('GET' if payload is None else 'POST',path,
                                body=json.dumps(payload) if payload is not None else None,headers=headers)
        with self.connection.getresponse() as response:
            return response.status,json.loads(response.read())


class EdgePeer:
    def __init__(self,probe,note):
        name=probe.project+'-bg-web-peer'
        code=(ROOT/'tests/background_web_peer.py').read_text()
        self.process=subprocess.Popen(['docker','run','--rm','-i','--name',name,'--log-driver','none',
            '--label','com.modular.disposable='+probe.project,'--network',probe.project+'_edge',
            '--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--entrypoint','/venv/bin/python',probe.state['image_id'],'-u','-c',code],
            text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.name=name
        atexit.register(self.close)
        self.reused=0
        actor=probe.fixture['users']['alice']
        value=dict(database=probe.state['database'],host=probe.state['hostname']+':'+str(probe.state['port']),
            login=actor['login'],uid=actor['id'],password=load(probe.site.local/'account-passwords.json')['alice'],
            workspace=probe.fixture['workspaces']['A']['public_id'],note=note)
        assert self.command(json.dumps(value),'ready')['sessions']==20

    def command(self,value,state):
        self.process.stdin.write(value+'\n')
        self.process.stdin.flush()
        raw=self.process.stdout.readline()
        assert raw,'No response from Linux qualification peer'
        row=json.loads(raw)
        assert row['state']==state,row
        return row

    def close(self):
        if self.process.poll() is not None:return
        try:
            self.process.stdin.write('quit\n')
            self.process.stdin.flush()
            self.process.stdin.close()
            self.process.wait(timeout=8)
        except (BrokenPipeError,subprocess.TimeoutExpired):
            subprocess.run(['docker','rm','-f',self.name],capture_output=True,timeout=15)
            if self.process.poll() is None:self.process.kill()
            self.process.wait()


def run(resume_seed=False,tuned=False,scaled=False,aligned=False,linux_peer=False,web_three=False,db_four=False,
        one_urgent=False,run_name='bg-03-01'):
    db_four=db_four or one_urgent
    web_three=web_three or db_four
    aligned=aligned or linux_peer or web_three
    assert run_name in {'bg-03-01','bx-04-capacity-01'}
    probe=Probe(run_name,extra_phase='bg04-mixed-seed' if resume_seed else None)
    lifecycle=json.loads((probe.site.local/('bg03-release-queue.json' if run_name=='bg-03-01' else 'bx04-native.json')).read_text())
    assert lifecycle['phase']=='passed'
    path=probe.site.local/('bg04-load-one-urgent.json' if one_urgent else 'bg04-load-db-four.json' if db_four else 'bg04-load-web-three.json' if web_three else 'bg04-load-linux-peer.json' if linux_peer else 'bg04-load-aligned-02.json' if aligned else 'bg04-load-scaled.json' if scaled else
                           'bg04-load-tuned.json' if tuned else 'bg04-load.json')
    if resume_seed:
        result=json.loads(path.read_bytes())
        assert result['phase']=='idle_measured' and result['image']==probe.state['image_id']
        assert probe.state['phase']=='bg04-mixed-seed'
        assert probe.sql("SELECT count(*) FROM mp_background_task WHERE name LIKE 'BG workload %';")=='0'
        assert not (probe.site.local/'logs/bg04-mixed-seed.stdout').read_bytes()
        probe.state['phase']='background_installed'
        write(probe.site.local/'state.json',probe.state)
    else:
        assert not path.exists()
        result=dict(phase='preparing',image=probe.state['image_id'],workload=verify_profile())
        write(path,result)
    a,b=(probe.fixture['workspaces'][key]['id'] for key in ('A','B'))
    alice=probe.fixture['users']['alice']
    bob=probe.fixture['users']['bob']
    if resume_seed or tuned or scaled or aligned:
        assert probe.sql('SELECT count(*) FROM mp_example_note;')=='10001'
    else:
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
    clients=[(BrowserConnection if aligned and not linux_peer else Client)(probe.site,'alice')
             for _ in range(1 if linux_peer else 20)]
    assert clients[0].native('mp.example.note','search_count',[[]])==10000
    assert clients[0].native('mp.example.note','search_count',[[]],workspace='B')==1
    peer=EdgePeer(probe,ident) if linux_peer else None
    names={'application':probe.target['worker_id'],'postgres':probe.project+'-db-1','edge':probe.project+'-edge-1'}
    urgent_count=2 if (scaled or aligned) and not one_urgent else 1
    from modular_platform.job_fleet import JobFleet
    if JobFleet(probe.operator).desired():
        fleet=probe.operator.run('status')
        assert fleet['state']=='ready' and fleet['pools']['urgent']['desired']==urgent_count and fleet['pools']['bulk']['desired']==2
    else:fleet=probe.operator.run('start',urgent_lanes=urgent_count)
    for row in fleet['lanes']:
        names[row['name']]=row['container']
    resources={}
    for role,name in names.items():
        row=json.loads(docker('inspect',name))[0]['HostConfig']
        resources[role]=dict(nano_cpus=row['NanoCpus'],memory_bytes=row['Memory'])
    cpu,memory,driver=docker('info','--format','{{.NCPU}} {{.MemTotal}} {{.Driver}}').decode().split()
    resources['docker']=dict(cpus=int(cpu),memory_bytes=int(memory),storage_driver=driver)
    listen_before=listen(probe) if web_three else None
    def cpu_stats():
        raw=docker('exec',names['postgres'],'cat','/sys/fs/cgroup/cpu.stat').decode().splitlines()
        return {key:int(value) for key,value in (line.split() for line in raw)}
    cpu_idle=cpu_stats() if db_four else None

    def request(client,case):
        if case=='list':
            result=client.native('mp.example.note','web_search_read',kwargs=dict(domain=[],offset=0,limit=80,
                specification={name:{} for name in ('title','revision','write_date')}))
            assert len(result['records'])==80 and all(row['title'].startswith('BG benchmark ') for row in result['records'])
        else:
            row,=client.native('mp.example.note','web_read',[[ident]],dict(
                specification={name:{} for name in ('title','body','revision')}))
            assert row['id']==ident and len(row['body'])==9600

    def warm_connections():
        if peer:
            peer.command('warm','warm')
            return None
        with ThreadPoolExecutor(max_workers=20) as pool:
            for case in ('list','detail'):
                list(pool.map(lambda client:request(client,case),clients))
                time.sleep(1.20)
        sockets=[client.connection.sock for client in clients]
        assert all(sockets)
        return sockets

    def same_connections(sockets):
        if peer:return peer.reused
        return sum(client.connection.sock is old for client,old in zip(clients,sockets,strict=True))

    def paired():
        if peer:
            value=peer.command('measure','measured')
            peer.reused=value['reused']
            return value['cases'],value['rounds']
        values={'list':[],'detail':[]}
        rounds=[]
        with ThreadPoolExecutor(max_workers=20) as pool:
            for _ in range(10):
                for case in values:
                    start=Barrier(20)
                    def timed(client):
                        start.wait(timeout=12)
                        now=time.perf_counter()
                        request(client,case)
                        return (time.perf_counter()-now)*1000
                    measured=list(pool.map(timed,clients))
                    values[case].extend(measured)
                    rounds.append({'case':case,**summary(measured)})
                    time.sleep(1.20)
        return {key:summary(samples) for key,samples in values.items()},rounds

    if aligned:
        idle_sockets=warm_connections()
    else:
        for case in ('list','detail'):
            for _ in range(3):request(clients[0],case)
    time.sleep(1.2)
    with Sampler(probe) as idle_session:
        idle_stop=Event()
        idle_observations=[]
        def idle_sample():
            while not idle_stop.is_set():
                idle_observations.append(observe(probe,['00000000-0000-0000-0000-000000000000'],idle_session.sql))
                idle_stop.wait(.5)
        idle_monitor=Thread(target=idle_sample,daemon=True)
        idle_monitor.start()
        try:
            idle,idle_rounds=paired()
        finally:
            idle_stop.set()
            idle_monitor.join(timeout=6)
        assert not idle_monitor.is_alive() and idle_observations
    result.update(phase='idle_measured',idle=idle,idle_rounds=idle_rounds,resources=resources)
    if db_four:
        idle_after=cpu_stats()
        result['postgres_idle_cpu_delta']={key:idle_after[key]-value for key,value in cpu_idle.items()}
    if aligned:
        result['warm_http_connections_reused_idle']=same_connections(idle_sockets)
        assert result['warm_http_connections_reused_idle']==20
        if not peer:
            for client in clients:client.connection.close()
    write(path,result)
    label=('bg04-mixed-one-urgent' if one_urgent else 'bg04-mixed-db-four' if db_four else 'bg04-mixed-web-three' if web_three else 'bg04-mixed-linux-peer' if linux_peer else 'bg04-mixed-aligned-02' if aligned else 'bg04-mixed-scaled' if scaled else 'bg04-mixed-tuned' if tuned
           else 'bg04-mixed-seed-02' if resume_seed else 'bg04-mixed-seed')
    loaded=seed_jobs(probe,label,{},anchor_lead=75 if aligned else 12)
    jobs=loaded['jobs']
    assert list(jobs.values()).count('urgent')==150 and list(jobs.values()).count('bulk')==40
    anchor=datetime.fromisoformat(loaded['anchor']).timestamp()
    cpu_mixed=cpu_stats() if db_four else None
    preload_margin=anchor-datetime.fromisoformat(loaded['committed']).timestamp()
    if aligned:
        assert preload_margin>=10 and anchor-time.time()>=6,preload_margin
        result.update(phase='preloaded',preload_margin_seconds=round(preload_margin,3))
        write(path,result)
        time.sleep(max(0,anchor-time.time()-5))
        mixed_sockets=warm_connections()
        assert time.time()<anchor,'Warm-up ran into the scheduled load interval'
    time.sleep(max(0,anchor-time.time()))
    samples=[]
    sampling_done=Event()
    with Sampler(probe) as live_session:
        def sample():
            while not sampling_done.is_set():
                samples.append(observe(probe,jobs,live_session.sql))
                if sampling_done.wait(.5):break
        monitor=Thread(target=sample,daemon=True)
        monitor.start()
        try:
            mixed,mixed_rounds=paired()
            if aligned:
                result['warm_http_connections_reused']=same_connections(mixed_sockets)
                assert result['warm_http_connections_reused']==20
                if not peer:
                    for client in clients:client.connection.close()
            wait(lambda:samples and samples[-1]['completed']==190,timeout=120)
        finally:
            sampling_done.set()
            monitor.join(timeout=6)
    samples.append(observe(probe,jobs))
    assert not monitor.is_alive() and samples and any(row['running']>=2 for row in samples)
    assert any(row['bulk_completed']<40 and row['running']>=2 for row in samples if row['at']>=anchor+20)
    telemetry=[]
    for pool,count in (('urgent',urgent_count),('bulk',2)):
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
    result.update(phase='mixed_measured',mixed=mixed,mixed_rounds=mixed_rounds,worker_timings=timings,oldest_urgent_ms=oldest,
                  bulk_drain_seconds=bulk_seconds,bulk_throughput_per_second=40/bulk_seconds,
                  pg_connections_peak=max(row['pg_connections'] for row in samples),
                  pg_active_peak=max(row['pg_active'] for row in samples),
                  queue_peak=max(row['queued'] for row in samples),sample_count=len(samples))
    if peer:
        peer.close()
        result['http_client']='Linux client on the same edge network, through the real reverse proxy'
        result['windows_loopback_scoped_sanity_passed']=True
    if web_three:
        after=listen(probe)
        result['listen_counters_delta']={name:after[name]-value for name,value in listen_before.items()}
        result['http_client']='Windows loopback through the real reverse proxy'
    if db_four:
        mixed_after=cpu_stats()
        result['postgres_mixed_cpu_delta']={key:mixed_after[key]-value for key,value in cpu_mixed.items()}
    write(path,result)
    web_passed=all(mixed[key]['p95_ms']<500 and mixed[key]['p95_ms']<=1.25*idle[key]['p95_ms']
                   for key in mixed)
    queue_passed=timings['urgent']['start']['p95_ms']<=3000 and oldest<=10000 and bulk_seconds<=120
    if not one_urgent:
        assert web_passed and queue_passed,(mixed,timings['urgent'])
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
    assert observe(probe,restart['jobs'])['ready']>0
    mechanism=probe.kill(probe.lane(running))
    recovered=time.monotonic()
    wait(lambda:observe(probe,restart['jobs'])['completed']==40,timeout=120)
    after=time.monotonic()-recovered
    assert after<=120 and before==snapshot()
    probe.operator.run('drain')
    result.update(phase='passed' if web_passed and queue_passed else 'restart_passed_latency_missed',
                  mixed_web_targets_passed=web_passed,mixed_queue_targets_passed=queue_passed,
                  recovered_after_seconds=round(after,3),restart=mechanism,
                  native_notes_unchanged=True,notifications=150,scoped_reports=40,
                  restart_reports=40)
    write(path,result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    run_name=sys.argv[sys.argv.index('--run')+1] if '--run' in sys.argv else 'bg-03-01'
    run(resume_seed='--resume-seed' in sys.argv[1:],tuned='--tuned' in sys.argv[1:],
        scaled='--scaled' in sys.argv[1:],aligned='--aligned' in sys.argv[1:],
        linux_peer='--linux-peer' in sys.argv[1:],web_three='--web-three' in sys.argv[1:],
        db_four='--db-four' in sys.argv[1:],one_urgent='--one-urgent' in sys.argv[1:],run_name=run_name)
