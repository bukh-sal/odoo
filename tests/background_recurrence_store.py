"""Actual PostgreSQL transactions for the private, not-yet-enabled recurrence store."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
import os
from uuid import uuid4

import psycopg2
from psycopg2.errors import SerializationFailure

from background_postgres import DDL,expect
from modular_platform import durable as q,recurrence_store as store
from modular_platform.dispatch_lifecycle import PHYSICAL_SCHEMA,UNIQUE,JOB_IDENTITY
from modular_platform.recurrence import RecurrenceRule,occurrence_key


SITE='00000000-0000-4000-8000-000000000001'
RELEASE='sha256:'+'1'*64


def table(cr,name,columns,unique):
    fields=['id serial PRIMARY KEY']+[key+' '+value for key,value in columns.items() if key!='id']
    fields += ['UNIQUE('+','.join(keys)+')' for keys in unique if keys!=('id',)]
    cr.execute('CREATE TABLE '+name+'('+','.join(fields)+')')


def run(first,second):
    scope=q.DispatchScope(SITE,1,2,3,RELEASE)
    anchor=datetime.now(timezone.utc).replace(microsecond=0)
    rule=RecurrenceRule(anchor,60,3600,5)
    payload=dict(input={'n':1},context={'credential_id':7})
    def authorize(row):
        assert (row['site_id'],row['workspace_id'],row['actor_id'],row['installation_id'])==(SITE,1,2,3)
    with first.cursor() as cr:
        cr.execute(DDL.replace('CREATE TEMP TABLE','CREATE TABLE'))
        table(cr,JOB_IDENTITY,PHYSICAL_SCHEMA[JOB_IDENTITY],UNIQUE[JOB_IDENTITY])
        table(cr,'mp_job_schedule',store.SCHEDULE_COLUMNS,{('public_id',),('site_id','workspace_id','actor_id','installation_id','idempotency_key')})
        table(cr,'mp_job_occurrence',store.OCCURRENCE_COLUMNS,{('site_id','schedule_id','nominal_at'),('job_public_id',)})
        q.set_control(cr,SITE,RELEASE,'enabled')
    first.commit()
    checks={}
    with first.cursor() as cr:
        def create(key):return store.create(cr,scope,'org.example.rec:test',1,payload,rule,key,authorize=authorize)
        def row(ident):
            cr.execute('SELECT to_jsonb(s) FROM mp_job_schedule s WHERE public_id=%s',[ident])
            return cr.fetchone()[0]
        def submit(record,timing,key):
            envelope=dict(schema_version=2,**record['payload'],schedule=timing.wire())
            return q.enqueue(cr,scope,record['handler'],record['handler_version'],envelope,key,
                schedule=timing,retain_identity=True)
        def advance(ident,now=anchor,**kw):return store.advance(cr,scope,ident,now,authorize=authorize,submit=kw.pop('submit',submit),**kw)
        def count(table_name):
            assert table_name in {'mp_job','mp_job_identity','mp_job_occurrence'}
            cr.execute('SELECT count(*) FROM '+table_name)
            return cr.fetchone()[0]
        a=create('a')
        assert create('a')==a
        first.commit()
        emitted=advance(a)
        assert emitted['outcome']=='emitted' and count('mp_job')==count('mp_job_occurrence')==1
        first.commit()
        assert advance(a,anchor+timedelta(seconds=181))['outcome']=='busy'
        assert count('mp_job')==1
        checks['one_outstanding_occurrence']=True
        cr.execute("UPDATE mp_job SET state='completed',finished_at=timezone('UTC',clock_timestamp()) WHERE public_id=%s",[emitted['job_id']])
        later=advance(a,anchor+timedelta(seconds=121))
        assert later['outcome']=='emitted' and later['skipped']==1 and count('mp_job')==2
        first.commit()
        checks['coalesced_cursor_job_and_receipt_committed_together']=True
        cr.execute("UPDATE mp_job SET state='outcome_unknown' WHERE public_id=%s",[later['job_id']])
        assert advance(a,anchor+timedelta(seconds=301))['outcome']=='busy' and count('mp_job')==2
        cr.execute("UPDATE mp_job SET state='held' WHERE public_id=%s",[later['job_id']])
        assert advance(a,anchor+timedelta(seconds=301))['outcome']=='busy' and count('mp_job')==2
        first.commit()
        checks['held_and_unknown_outcomes_block_overlap']=True
        b=create('b');first.commit()
        before=row(b)
        def fail(record,timing,key):
            submit(record,timing,key)
            raise RuntimeError('Injected failure after one-off insertion')
        expect(RuntimeError,advance,b,submit=fail)
        # The caller deliberately catches the failure and commits other work.
        cr.execute("INSERT INTO bg_effect VALUES('unrelated caller commit')")
        first.commit()
        assert row(b)==before and count('mp_job')==2 and count('mp_job_occurrence')==2
        checks['caught_enqueue_failure_cannot_commit_orphan_job_or_cursor']=True
        advance(b)
        first.rollback()
        assert row(b)==before and count('mp_job')==2
        checks['caller_rollback_reverts_job_receipt_and_cursor']=True
        c=create('c');first.commit()
        second.set_session(isolation_level='REPEATABLE READ')
        with second.cursor() as stale:
            stale.execute('SELECT next_at FROM mp_job_schedule WHERE public_id=%s',[c]);stale.fetchone()
            original=advance(c);first.commit()
            try:store.advance(stale,scope,c,anchor,authorize=authorize,submit=lambda *_:None)
            except SerializationFailure as error:assert error.pgcode=='40001'
            else:raise AssertionError('Stale producer advanced the changed cursor')
        second.rollback()
        with second.cursor() as fresh:
            repeated=store.advance(fresh,scope,c,anchor,authorize=authorize,submit=lambda *_:None)
            assert repeated['outcome']=='busy' and repeated['job_id']==original['job_id']
        second.commit()
        first.rollback()
        checks['stale_duplicate_tick_forced_to_retry_then_observed_original']='40001'
        cr.execute("UPDATE mp_job SET state='completed',finished_at=timezone('UTC',clock_timestamp()) WHERE public_id=%s",[original['job_id']])
        version=store.edit(cr,scope,c,1,handler='org.example.rec:test',version=2,
            payload=dict(payload,input={'n':2}),rule=replace(rule,interval_seconds=90),authorize=authorize)
        assert version==2 and row(c)['next_at']==(anchor+timedelta(seconds=90)).replace(tzinfo=None).isoformat()
        assert create('c')==c
        checks['edits_preserve_creation_identity_and_advance_past_considered_nominal']=True
        cr.execute('UPDATE mp_job_schedule SET next_at=%s,considered_at=NULL,outstanding_job_id=NULL WHERE public_id=%s',[anchor.replace(tzinfo=None),c])
        replay=advance(c)
        assert replay['outcome']=='replayed' and replay['job_id']==original['job_id'] and count('mp_job')==3
        checks['retained_receipt_suppresses_rewound_cursor_after_handler_edit']=True
        version=store.set_state(cr,scope,c,2,'paused',authorize=authorize)
        assert advance(c,anchor+timedelta(seconds=900))['outcome']=='paused'
        expect(q.QueueError,store.set_state,cr,scope,c,2,'active',authorize=authorize)
        version=store.set_state(cr,scope,c,version,'active',authorize=authorize)
        first.commit()
        checks['pause_and_optimistic_resume_keep_cursor_and_receipt']=True
        foreign=replace(scope,actor_id=999)
        expect(q.QueueError,store.advance,cr,foreign,c,anchor,authorize=lambda _:None,submit=lambda *_:None)
        first.commit()
        checks['foreign_scope_cannot_advance']=True
        before=row(c)
        def revoked(_):raise PermissionError('Synthetic revoked service scope')
        expect(PermissionError,store.advance,cr,scope,c,anchor+timedelta(seconds=900),authorize=revoked,submit=submit)
        first.commit()
        assert row(c)==before and count('mp_job')==3
        checks['current_authority_failure_keeps_cursor_unchanged']=True
    return checks


def history(connection):
    scope=q.DispatchScope(SITE,1,2,3,RELEASE)
    checks={}
    with connection.cursor() as cr:
        cr.execute("SELECT to_jsonb(s) FROM mp_job_schedule s WHERE idempotency_key='c'")
        record=cr.fetchone()[0]
        ident=record['public_id'];old=record['outstanding_job_id']
        assert old is not None
        def row():
            cr.execute('SELECT to_jsonb(s) FROM mp_job_schedule s WHERE public_id=%s',[ident])
            return cr.fetchone()[0]
        age=datetime.now(timezone.utc)-timedelta(days=9)
        cr.execute("UPDATE mp_job SET created_at=%s,available_at=%s,deadline_at=%s,finished_at=%s WHERE public_id=%s AND state='completed'",[age,age,age,age,old])
        assert cr.rowcount==1
        archived=q.archive_terminal_jobs(cr,SITE,RELEASE,cutoff=datetime.now(timezone.utc)-timedelta(days=8),limit=100)
        assert archived==[old],archived
        connection.commit()
        def submit(record,timing,key):
            return q.enqueue(cr,scope,record['handler'],record['handler_version'],
                dict(schema_version=2,**record['payload'],schedule=timing.wire()),key,
                schedule=timing,retain_identity=True)
        now=store._time(record['next_at'])
        result=store.advance(cr,scope,ident,now,authorize=lambda _:None,submit=submit)
        assert result['outcome']=='emitted' and result['job_id']!=old
        connection.commit()
        checks['compact_terminal_history_unblocks_future_occurrence']=True
        saved=row()
        bad=str(uuid4())
        cr.execute('UPDATE mp_job_schedule SET outstanding_job_id=%s WHERE public_id=%s',[bad,ident])
        connection.commit()
        before=row()
        expect(q.QueueError,store.advance,cr,scope,ident,now+timedelta(seconds=90),authorize=lambda _:None,submit=submit)
        connection.commit()
        assert row()==before
        checks['missing_outstanding_receipt_never_implies_completion']=True
        cr.execute('UPDATE mp_job_schedule SET outstanding_job_id=%s WHERE public_id=%s',[saved['outstanding_job_id'],ident])
        connection.commit()
        foreign=replace(scope,actor_id=888)
        timing=q.JobSchedule(now,now+timedelta(seconds=3600),5)
        job=q.enqueue(cr,foreign,'org.example.rec:test',1,dict(schema_version=2,schedule=timing.wire()),'foreign',schedule=timing,retain_identity=True)
        cr.execute('UPDATE mp_job_schedule SET outstanding_job_id=%s WHERE public_id=%s',[job,ident])
        connection.commit()
        before=row()
        expect(q.QueueError,store.advance,cr,scope,ident,now+timedelta(seconds=90),authorize=lambda _:None,submit=submit)
        connection.commit()
        assert row()==before
        checks['foreign_job_pointer_cannot_supply_a_terminal_or_active_status']=True
        cr.execute('UPDATE mp_job_schedule SET outstanding_job_id=%s WHERE public_id=%s',[saved['outstanding_job_id'],ident])
        store.hold(cr,scope,ident,saved['config_version'],'FORBIDDEN')
        connection.commit()
        assert row()['state']=='held'
        def denied(_):raise PermissionError('Synthetic lost current authority')
        expect(PermissionError,store.set_state,cr,scope,ident,saved['config_version'],'active',authorize=denied)
        connection.commit()
        assert row()['state']=='held'
        checks['held_schedule_requires_current_authority_to_resume']=True
    return checks


if __name__=='__main__':
    database=os.environ['MP_BX_FIXTURE_DATABASE']
    assert database=='mp_bx_recurrence_store'
    settings=dict(host='127.0.0.1',dbname=database,user='postgres',connect_timeout=5)
    with psycopg2.connect(**settings) as first,psycopg2.connect(**settings) as second:
        checks=history(first) if os.environ.get('MP_BX_STORE_HISTORY')=='1' else run(first,second)
        print(json.dumps(dict(state='passed',scope='Private SQL store and existing one-off enqueue only; no native producer or lifecycle integration',checks=checks),sort_keys=True))
