"""Paired native web load and PostgreSQL lock timing during reviewed retention."""

from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime, timedelta, timezone
import json
import re
import subprocess
import time

from background_lifecycle import shell
from background_load import BrowserConnection, summary
from background_site import load, write
from background_web_capacity import listen, resize_stock_web
from background_workers import Probe, docker
from modular_platform.job_operator import JobOperator


RUN = 'bx-01-cleanup-load-01'
BATCH = dict(job=100, delivery=25, consumption=25, event=25, subscription=25)
LIMITS = dict(readers=20, phase_seconds=55, web_p95_ms=500, relative_p95=1.25, lock_ms=500)
CASES = ('list', 'detail', 'history')


class TracedOperator(JobOperator):
    def _base(self, runtime, name):
        return ['--env', 'PGOPTIONS=-c log_min_duration_statement=0 -c application_name=bx_archive_trace',
                *super()._base(runtime, name)]


def seed(probe):
    assert probe.sql('SELECT count(*) FROM mp_example_note') == '0'
    actor = probe.fixture['users']['alice']['principal_id']
    workspace = probe.fixture['workspaces']['A']['id']
    probe.sql(f"""INSERT INTO mp_example_note
        (workspace_id,public_id,title,body,author_id,revision,create_uid,write_uid,create_date,write_date)
        SELECT {workspace},gen_random_uuid()::text,'BX read '||n,repeat(md5(n::text),300),
            p.id,1,p.user_id,p.user_id,timezone('UTC',now()),timezone('UTC',now())
        FROM generate_series(1,10000) n CROSS JOIN mp_principal p WHERE p.public_id='{actor}'""")
    probe.sql(f"""INSERT INTO mp_job(public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
            release_digest,payload,input_digest,idempotency_key,effect_mode,state,attempts,max_attempts,
            claim_generation,dispatch_generation,available_at,deadline_at,cancel_requested,effect_started,progress,created_at,finished_at)
        SELECT gen_random_uuid()::text,c.site_id,{workspace},p.id,i.id,'org.example.background:report',2,
            c.release_digest,'{{}}'::jsonb,'sha256:'||repeat('a',64),'bx-load:'||n,'idempotent','completed',1,1,1,c.generation,
            timezone('UTC',now())-interval '11 days',stamp,false,false,100,timezone('UTC',now())-interval '11 days',stamp
        FROM generate_series(1,80400) n CROSS JOIN mp_dispatch_control c CROSS JOIN mp_principal p
        CROSS JOIN mp_plugin_installation i CROSS JOIN LATERAL (SELECT timezone('UTC',now())-
            CASE WHEN n>80000 THEN interval '10 days' ELSE interval '1 day' END AS stamp) stamp_values
        WHERE p.public_id='{actor}' AND i.plugin_id='org.example.background' ORDER BY n;
        INSERT INTO mp_job_identity(site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key,
            job_public_id,input_digest,release_digest,effect_mode,terminal_state,finished_at,archived_at)
        SELECT c.site_id,{workspace},p.id,i.id,'org.example.background:report',2,'bx-old:'||n,gen_random_uuid()::text,
            'sha256:'||repeat('b',64),c.release_digest,'idempotent','completed',timezone('UTC',now())-interval '20 days',timezone('UTC',now())
        FROM generate_series(1,100002) n CROSS JOIN mp_dispatch_control c CROSS JOIN mp_principal p
        CROSS JOIN mp_plugin_installation i WHERE p.public_id='{actor}' AND i.plugin_id='org.example.background'""")
    probe.sql(f"""CREATE TEMP TABLE bx_events AS WITH inserted AS (
        INSERT INTO mp_outbox(public_id,site_id,workspace_id,actor_id,installation_id,plugin_id,topic,schema_version,
            aggregate_id,aggregate_sequence,occurred_at,correlation_id,payload,release_digest,dispatch_generation,state)
        SELECT gen_random_uuid()::text,c.site_id,{workspace},p.id,i.id,i.plugin_id,'org.example.notes.changed',1,
            gen_random_uuid()::text,n,timezone('UTC',now())-CASE WHEN n>80000 THEN interval '10 days' ELSE interval '1 day' END,
            gen_random_uuid()::text,'{{}}'::jsonb,c.release_digest,c.generation,'published'
        FROM generate_series(1,80200) n CROSS JOIN mp_dispatch_control c CROSS JOIN mp_principal p
        CROSS JOIN mp_plugin_installation i WHERE p.public_id='{actor}' AND i.plugin_id='org.example.notes' ORDER BY n
        RETURNING id,aggregate_sequence,site_id,workspace_id,actor_id,installation_id,release_digest)
        SELECT * FROM inserted WHERE aggregate_sequence>80000;
        CREATE TEMP TABLE bx_subs AS WITH inserted AS (
        INSERT INTO mp_event_subscription(public_id,site_id,workspace_id,actor_id,installation_id,topic,binding,
            release_digest,idempotency_key,input_digest,state,created_at,expires_at)
        SELECT gen_random_uuid()::text,c.site_id,{workspace},p.id,i.id,'org.example.notes.changed','{{}}'::jsonb,
            c.release_digest,gen_random_uuid()::text,repeat('c',64),'closed',timezone('UTC',now())-interval '10 days 1 hour',timezone('UTC',now())-interval '10 days'
        FROM generate_series(1,100) n CROSS JOIN mp_dispatch_control c CROSS JOIN mp_principal p
        CROSS JOIN mp_plugin_installation i WHERE p.public_id='{actor}' AND i.plugin_id='org.example.notes' ORDER BY n RETURNING id)
        SELECT id,row_number() OVER (ORDER BY id) AS n FROM inserted;
        INSERT INTO mp_event_delivery(public_id,subscription_id,event_id,state,generation,attempts,replays,available_at,acknowledged_at)
        SELECT gen_random_uuid()::text,s.id,e.id,'acknowledged',1,1,0,timezone('UTC',now())-interval '9 days',timezone('UTC',now())-interval '9 days'
        FROM bx_events e JOIN bx_subs s ON s.n=e.aggregate_sequence-80000 WHERE e.aggregate_sequence BETWEEN 80051 AND 80100 ORDER BY e.id;
        INSERT INTO mp_event_consumption(public_id,workspace_id,actor_id,installation_id,event_id,handler,created_at)
        SELECT gen_random_uuid()::text,workspace_id,actor_id,installation_id,id,'org.example.notes:fixture',timezone('UTC',now())-interval '9 days'
        FROM bx_events WHERE aggregate_sequence BETWEEN 80101 AND 80150 ORDER BY id""")
    probe.sql('ANALYZE mp_example_note; ANALYZE mp_job; ANALYZE mp_job_identity; ANALYZE mp_outbox; '
              'ANALYZE mp_event_delivery; ANALYZE mp_event_consumption; ANALYZE mp_event_subscription; '
              'GRANT SET ON PARAMETER log_min_duration_statement TO modular')


PLAN = """
import json
from datetime import datetime
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable, event_retention
assert env.cr.dbname == EXPECTED_DB and EXPECTED_DB.startswith('mp_disposable_r0_r1_release_')
release=current_release(env)
site,digest=release['site_id'],release['release_digest']

class ObserveSelection:
    def __getattr__(self, name):
        return getattr(env.cr,name)

    def execute(self, query, params):
        if 'ORDER BY id LIMIT' in query or 'ORDER BY r.id LIMIT' in query:
            query='EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query
        return env.cr.execute(query,params)

cr=ObserveSelection()
cutoff=datetime.fromisoformat(CUTOFF)
plans={'job':durable.terminal_archive_candidates(cr,site,cutoff=cutoff,limit=100)[0][0][0]}
for kind in event_retention.TABLES:
    _,rows=event_retention.candidates(cr,site,digest,kind,cutoff,25)
    plans[kind]=rows[0][0][0]
env.cr.rollback()
print('BX_PLANS='+json.dumps(plans))
"""


def selection_plans(probe, cutoff, *, label='bx01-cleanup-plan'):
    raw = shell(probe, label, f'EXPECTED_DB={probe.state["database"]!r}\nCUTOFF={cutoff!r}\n'+PLAN)
    plans, = [json.loads(line.split('=', 1)[1]) for line in raw.splitlines() if line.startswith('BX_PLANS=')]

    def nodes(node):
        return [dict(node=node['Node Type'], relation=node.get('Relation Name'), index=node.get('Index Name'),
                     rows=node['Actual Rows'], filtered=node.get('Rows Removed by Filter',0))] + [
            row for child in node.get('Plans',[]) for row in nodes(child)]

    return {kind:dict(execution_ms=plan['Execution Time'], plan=nodes(plan['Plan'])) for kind,plan in plans.items()}


def check_history_scope(probe, client):
    a=probe.fixture['workspaces']['A']['id']
    b=probe.fixture['workspaces']['B']['id']
    live=int(probe.sql(f'SELECT 2::bigint*id FROM mp_job WHERE workspace_id={a} ORDER BY id DESC LIMIT 1'))
    archived=int(probe.sql(f'SELECT 2::bigint*id+1 FROM mp_job_identity WHERE workspace_id={a} AND job_public_id IS NOT NULL ORDER BY id LIMIT 1'))
    foreign=int(probe.sql(f'SELECT 2::bigint*id FROM mp_job WHERE workspace_id={b} ORDER BY id LIMIT 1'))
    rows=client.native('mp.job.history','read',[[live,archived],['public_id','archived']])
    assert [row['archived'] for row in rows]==[False,True]

    def denied(ids,workspace):
        status,response=client.request('/web/dataset/call_kw/mp.job.history.web_read',dict(jsonrpc='2.0',method='call',id=1,
            params=dict(model='mp.job.history',method='web_read',args=[ids,{}],kwargs={})),workspace)
        assert status==200 and response.get('error',{}).get('data',{}).get('name','').endswith('AccessError')

    denied([live,foreign],'A')
    denied([archived],'B')
    denied([live],None)
    return dict(mixed_live_archived_read=True,mixed_foreign_batch_denied=True,foreign_archived_denied=True,absent_scope_denied=True)


LOG = re.compile(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+) UTC \[(\d+)\] LOG:\s+duration: ([\d.]+) ms\s+statement: (.*)', re.S)


def lock_trace(probe, since):
    raw = subprocess.check_output(['docker','logs','--since',since.isoformat(),probe.project+'-db-1'],stderr=subprocess.STDOUT).decode()
    statements = {}
    for line in re.split(r'\n(?=\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',raw):
        match=LOG.match(line.strip())
        if match:
            when,pid,duration,query=match.groups()
            statements.setdefault(pid,[]).append((datetime.fromisoformat(when).replace(tzinfo=timezone.utc).timestamp(),float(duration),query))
    batches=[]
    for pid,items in statements.items():
        for when,duration,query in items:
            normalized=' '.join(query.split())
            if not normalized.startswith('INSERT INTO mp_event_history') and not normalized.startswith('DELETE FROM mp_job WHERE id='):
                continue
            before=[item for item in items if item[0]<=when and 'mp_dispatch_control' in item[2]
                    and ('generation=generation' in item[2] or 'FOR SHARE' in item[2])]
            after=[item for item in items if item[0]>=when and item[2].strip().upper()=='COMMIT']
            if not before or not after:
                continue
            lock=before[0]
            committed=after[0][0]
            if any(row['committed']==committed and row['pid']==pid for row in batches):
                continue
            kind='job' if normalized.startswith('DELETE FROM mp_job') else re.search(r"'(delivery|consumption|event|subscription)'",normalized).group(1)
            row_locks=[item for item in items if lock[0]<=item[0]<=committed and 'FOR UPDATE' in item[2] and 'FROM mp_job' in item[2]]
            batches.append(dict(kind=kind, started=lock[0]-lock[1]/1000, committed=committed, pid=pid,
                control_acquisition_ms=lock[1], control_hold_upper_ms=round((committed-lock[0])*1000+lock[1]+1,3),
                first_job_row_hold_upper_ms=round((committed-row_locks[0][0])*1000+row_locks[0][1]+1,3) if row_locks else None))
    for batch in batches:
        batch.pop('pid')
    return sorted(batches,key=lambda batch:batch['started'])


def job_overlap(site_run):
    probe=Probe(site_run)
    path=probe.site.local/'cleanup-job-overlap.json'
    assert not path.exists()
    pairs=[load(probe.site.local/name) for name in ('cleanup-load.json','cleanup-load-repeat.json')]
    assert all(pair['image']==probe.state['image_id'] and pair['notes_preserved'] and pair['producer_revision_preserved'] for pair in pairs)
    assert all(pair['mixed']['reads'][case]['p95_ms']<LIMITS['web_p95_ms'] and
               pair['mixed']['reads'][case]['p95_ms']<=LIMITS['relative_p95']*pair['baseline']['reads'][case]['p95_ms']
               for pair in pairs for case in CASES)
    reference=probe.site
    reference.state=lambda:dict(probe.state)
    clients=[BrowserConnection(reference,'alice') for _ in range(20)]
    ident=int(probe.sql("SELECT id FROM mp_example_note WHERE title='BX read 100'"))
    operator=TracedOperator(probe.operator.store,probe.site.private/'target.json')
    cutoff=(datetime.now(timezone.utc)-timedelta(days=9)).isoformat()
    reviewed=operator.run('archive-review',cutoff=cutoff,limit=100)
    assert len(reviewed['review']['jobs'])==100

    def request(client):
        row,=client.native('mp.example.note','web_read',[[ident]],dict(specification=dict(title={},body={},revision={})))
        assert row['id']==ident and len(row['body'])==9600

    def phase(apply=False):
        start=time.monotonic()+1
        end=start+15
        def readers(index,client):
            samples=[]
            count=0
            while start+index*.025+count*.5<end:
                time.sleep(max(0,start+index*.025+count*.5-time.monotonic()))
                began=time.time()
                request(client)
                samples.append(dict(start=began,end=time.time()))
                count+=1
            return samples

        def cleanup():
            time.sleep(max(0,start+3-time.monotonic()))
            assert operator.run('archive-apply',approval=reviewed['approval'])['jobs']==reviewed['review']['jobs']

        for client in clients:
            client.connection.close()
            request(client)
        with ThreadPoolExecutor(max_workers=21) as pool:
            work=[pool.submit(readers,index,client) for index,client in enumerate(clients)]
            clean=pool.submit(cleanup) if apply else None
            samples=[row for future in work for row in future.result()]
            if clean:clean.result()
        return summary([(row['end']-row['start'])*1000 for row in samples]),samples

    try:
        baseline,_=phase()
        since=datetime.now(timezone.utc)
        mixed,samples=phase(apply=True)
        traces=lock_trace(probe,since)
        assert len(traces)==1 and traces[0]['kind']=='job'
        trace=traces[0]
        trace['overlapping_requests']=sum(row['start']<=trace['committed'] and row['end']>=trace['started'] for row in samples)
        passed=(trace['overlapping_requests']>0 and trace['control_hold_upper_ms']<=LIMITS['lock_ms']
                and mixed['p95_ms']<LIMITS['web_p95_ms'] and mixed['p95_ms']<=LIMITS['relative_p95']*baseline['p95_ms'])
        result=dict(phase='passed' if passed else 'measured_outside_target',image=probe.state['image_id'],
                    readers=20,sample_seconds=15,target_requests_per_second=40,
                    baseline=baseline,mixed=mixed,lock_trace=trace)
        write(path,result)
        print(json.dumps(result),flush=True)
        assert passed
    finally:
        for client in clients:client.connection.close()


def run(resume=False, site_run=RUN, repeat=False):
    probe = Probe(site_run)
    path = probe.site.local/('cleanup-load-repeat.json' if repeat else 'cleanup-load.json')
    prior=load(probe.site.local/'cleanup-load.json') if repeat else None
    cutoff=(datetime.now(timezone.utc)-timedelta(days=9)).isoformat()
    if repeat:
        assert not path.exists() and prior['phase']=='measured_outside_target' and prior['image']==probe.state['image_id']
        assert all(prior['mixed']['reads'][case]['p95_ms']<LIMITS['web_p95_ms'] and
                   prior['mixed']['reads'][case]['p95_ms']<=LIMITS['relative_p95']*prior['baseline']['reads'][case]['p95_ms'] for case in CASES)
        assert any(not trace['overlapping_requests'] for trace in prior['lock_traces'])
        result=dict(phase='prepared',image=probe.state['image_id'],limits=LIMITS,batches=BATCH,
                    plans=selection_plans(probe,cutoff,label='bx01-cleanup-plan-repeat'),first_pair='cleanup-load.json')
        write(path,result)
    elif resume:
        result=load(path)
        assert result['phase']=='prepared' and result['image']==probe.state['image_id']
    else:
        assert not path.exists()
        resize_stock_web(probe)
        db=probe.project+'-db-1'
        row,=json.loads(docker('inspect',db))
        assert row['Config']['Labels']['com.docker.compose.project']==probe.project
        docker('update','--cpus','4',db)
        seed(probe)
        result=dict(phase='prepared',image=probe.state['image_id'],limits=LIMITS,batches=BATCH,
                    plans=selection_plans(probe,cutoff))
        write(path,result)
    operator=TracedOperator(probe.operator.store,probe.site.private/'target.json')
    reference=probe.site
    reference.state=lambda:dict(probe.state)
    writer=BrowserConnection(reference,'alice')
    if resume or repeat:
        note,current_revision=map(int,probe.sql("SELECT id,revision FROM mp_example_note WHERE title='BX producer'").split('|'))
    else:
        note=writer.native('mp.example.note','create',[dict(title='BX producer',body='0')])
        current_revision=1
    ident=int(probe.sql("SELECT id FROM mp_example_note WHERE title='BX read 100'"))
    clients=[BrowserConnection(reference,'alice') for _ in range(LIMITS['readers'])]
    result['history_guard']=check_history_scope(probe,clients[0])
    frozen="SELECT md5(string_agg(md5(to_jsonb(n)::text),'' ORDER BY id)) FROM mp_example_note n WHERE title LIKE 'BX read %'"
    before=probe.sql(frozen)

    def request(client,case):
        if case=='detail':
            row,=client.native('mp.example.note','web_read',[[ident]],dict(specification=dict(title={},body={},revision={})))
            assert row['id']==ident and len(row['body'])==9600
            return
        model,size,fields=('mp.example.note',80,('title','revision','write_date')) if case=='list' else (
            'mp.job.history',50,('public_id','state','status_at','archived'))
        rows=client.native(model,'web_search_read',kwargs=dict(domain=[],offset=0,limit=size,count_limit=10000,
                           specification={name:{} for name in fields}))['records']
        assert len(rows)==size and (case!='list' or all(row['title'].startswith('BX ') for row in rows))

    def warm():
        for client in [*clients,writer]:
            client.connection.close()
            request(client,'detail')

    def phase(reviews=()):
        started=time.monotonic()+1
        end=started+LIMITS['phase_seconds']
        def pace(when):
            time.sleep(max(0,when-time.monotonic()))

        def read(index,client):
            rows=[]
            count=0
            while True:
                scheduled=started+index*.04+count*1.2
                if scheduled>=end:
                    return rows
                pace(scheduled)
                case=CASES[(index+count)%len(CASES)]
                now=time.time()
                request(client,case)
                rows.append(dict(case=case,start=now,end=time.time()))
                count+=1

        def produce():
            nonlocal current_revision
            count=0
            while started+count*1.2<end:
                pace(started+count*1.2)
                assert writer.native('mp.example.note','write',[[note],dict(body=str(current_revision))],
                                     dict(context=dict(expected_revision=current_revision)))
                current_revision+=1
                count+=1
            return count

        def clean():
            pace(started+(1.4 if repeat else 1))
            records=[]
            for kind,approval in reviews:
                receipt=operator.run('archive-apply',approval=approval)
                count=len(receipt['jobs' if kind=='job' else 'records'])
                assert count==BATCH[kind]
                records.append(dict(kind=kind,count=count))
            assert time.monotonic()<end
            return records

        with ThreadPoolExecutor(max_workers=22) as pool:
            readers=[pool.submit(read,i,client) for i,client in enumerate(clients)]
            writes=pool.submit(produce)
            cleanup=pool.submit(clean) if reviews else None
            samples=[sample for future in readers for sample in future.result()]
            return dict(reads={case:summary([(sample['end']-sample['start'])*1000 for sample in samples if sample['case']==case])
                               for case in CASES},writes=writes.result(),cleanup=cleanup.result() if cleanup else []),samples

    try:
        warm()
        baseline_listen=listen(probe)
        baseline,_=phase()
        result.update(phase='baseline_measured',baseline=baseline)
        write(path,result)
        reviews=[]
        for kind,limit in BATCH.items():
            reviewed=probe.operator.run('archive-review',kind=kind,cutoff=cutoff,limit=limit)
            assert len(reviewed['review']['jobs' if kind=='job' else 'records'])==limit
            reviews.append((kind,reviewed['approval']))
        warm()
        since=datetime.now(timezone.utc)
        mixed,samples=phase(reviews)
        write(path.with_name(path.stem+'-timestamps.json'),dict(since=since.isoformat(),samples=samples))
        traces=lock_trace(probe,since)
        for trace in traces:
            trace['overlapping_requests']=sum(row['start']<=trace['committed'] and row['end']>=trace['started'] for row in samples)
        drops={key:value-baseline_listen[key] for key,value in listen(probe).items()}
        preserved=probe.sql(frozen)==before
        producer=probe.sql(f'SELECT revision FROM mp_example_note WHERE id={note}')==str(current_revision)
        coverage={kind:sum(item['overlapping_requests'] for item in traces+(prior['lock_traces'] if prior else [])
                           if item['kind']==kind) for kind in BATCH}
        passed=(all(mixed['reads'][case]['p95_ms']<LIMITS['web_p95_ms'] and
                    mixed['reads'][case]['p95_ms']<=LIMITS['relative_p95']*baseline['reads'][case]['p95_ms'] for case in CASES)
                and sorted(item['kind'] for item in traces)==sorted(BATCH)
                and all(item['control_hold_upper_ms']<=LIMITS['lock_ms'] for item in traces) and all(coverage.values())
                and not any(drops.values()) and preserved and producer)
        result.update(phase='passed' if passed else 'measured_outside_target',mixed=mixed,lock_traces=traces,
                      listen_deltas=drops,notes_preserved=preserved,producer_revision_preserved=producer,overlap_coverage=coverage)
        write(path,result)
        print(json.dumps({key:result[key] for key in ('phase','baseline','mixed','lock_traces','listen_deltas')}),flush=True)
        assert passed
    finally:
        for client in [*clients,writer]:
            client.connection.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',choices=(RUN,'bx-01-cleanup-load-02'),default=RUN)
    parser.add_argument('--resume-prepared',action='store_true')
    parser.add_argument('--repeat-pair',action='store_true')
    parser.add_argument('--job-overlap',action='store_true')
    args=parser.parse_args()
    if args.job_overlap:
        job_overlap(args.run)
    else:
        run(resume=args.resume_prepared,site_run=args.run,repeat=args.repeat_pair)
