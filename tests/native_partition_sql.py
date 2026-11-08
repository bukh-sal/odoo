"""Real PostgreSQL partition/fairness/claim/metric primitives, no app authority claim."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import json
from uuid import uuid4

import psycopg2
from modular_platform import durable as q,job_fairness,job_capacity
from modular_platform.job_runner import _claim_guard
from modular_platform.job_supervisor import partition_slot
from background_postgres import DDL

settings=dict(host='db',user='postgres',dbname='at_partition_probe',connect_timeout=5)
SITE=str(uuid4());RELEASE='sha256:'+'a'*64;HANDLER='dev.aurora.tasks:partition-probe';ROUTES=[(HANDLER,1)]
checks={}


class Cursor:
    def __init__(self,connection):self.connection=connection;self.cr=connection.cursor()
    def __getattr__(self,name):return getattr(self.cr,name)
    def commit(self):self.connection.commit()
    def rollback(self):self.connection.rollback()


class Registry:
    @contextmanager
    def cursor(self):
        connection=psycopg2.connect(**settings);cursor=Cursor(connection)
        try:yield cursor
        finally:connection.rollback();cursor.cr.close();connection.close()


registry=Registry()
with registry.cursor() as cr:
    ddl=DDL.replace('CREATE TEMP TABLE','CREATE TABLE').replace('workspace_id int NOT NULL','workspace_id int')
    ddl=ddl.replace('UNIQUE (site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)',
                    'UNIQUE NULLS NOT DISTINCT (site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)')
    cr.execute(ddl)
    cr.execute('CREATE TABLE ir_config_parameter(id serial PRIMARY KEY,key varchar UNIQUE,value varchar,create_uid int,write_uid int,create_date timestamp,write_date timestamp)')
    cr.execute('INSERT INTO ir_config_parameter(key,value) VALUES(%s,%s),(%s,%s)',
               ['mp.site_id',SITE,'mp.release_digest',RELEASE])
    q.set_control(cr,SITE,RELEASE,'enabled');cr.commit()
    now=datetime.now(timezone.utc)-timedelta(seconds=1)
    timing=q.JobSchedule(now,now+timedelta(minutes=10),30)
    payload=dict(schema_version=2,schedule=timing.wire(),input={})
    native=[]
    for ident in range(1,71):
        scope=q.NativeDispatchScope(SITE,2,ident,RELEASE)
        native.append(q.enqueue(cr,scope,HANDLER,1,payload,'first',schedule=timing))
    assert q.enqueue(cr,q.NativeDispatchScope(SITE,2,1,RELEASE),HANDLER,1,payload,'first',schedule=timing)==native[0]
    q.enqueue(cr,q.NativeDispatchScope(SITE,2,1,RELEASE),HANDLER,1,payload,'second',schedule=timing)
    workspace=[]
    for ident in (1,2):workspace.append(q.enqueue(cr,q.DispatchScope(SITE,ident,2,3,RELEASE),HANDLER,1,payload,'first',schedule=timing))
    cr.commit()
    ready=q.ready_partitions(cr,SITE,RELEASE,ROUTES)
    assert len(ready)==64 and ready[0]==q.ExecutionPartition('native',1) and ready[-1]==q.ExecutionPartition('native',64)
    rotated=q.ready_partitions(cr,SITE,RELEASE,ROUTES,after=ready[-1].key)
    assert rotated[0]==q.ExecutionPartition('native',65) and q.ExecutionPartition('workspace',1) in rotated
    assert q.ready_partitions(cr,SITE,RELEASE,ROUTES,after=q.ExecutionPartition('workspace',2).key)[0]==ready[0]
    checks['bounded_mixed_partition_ring_reaches_workspaces_and_wraps']=True
    assert q.ready_workspaces(cr,SITE,RELEASE,ROUTES)==[1,2]
    checks['legacy_workspace_candidate_api_excludes_native_rows']=True
    cr.commit()
    first=job_fairness.read_partitions(cr,SITE,RELEASE,'urgent')
    assert first.after=='' and job_fairness.reserve_partition(registry,first,ready[0])
    assert not job_fairness.reserve_partition(registry,first,ready[1])
    current=job_fairness.read_partitions(cr,SITE,RELEASE,'urgent')
    assert current.after==ready[0].key
    old=job_fairness.read(cr,SITE,RELEASE,'urgent')
    assert old.after==0 and job_fairness.reserve(registry,old,2)
    assert job_fairness.read_partitions(cr,SITE,RELEASE,'urgent').after==ready[0].key
    checks['rotation_cas_rejects_stale_ticket_and_keeps_legacy_hint_separate']=True
    cr.commit()

with partition_slot(registry,SITE,'urgent',q.ExecutionPartition('native',1)) as native_locked:
    assert native_locked
    with partition_slot(registry,SITE,'urgent',q.ExecutionPartition('native',1)) as duplicate:assert not duplicate
    with partition_slot(registry,SITE,'urgent',q.ExecutionPartition('workspace',1)) as workspace_locked:assert workspace_locked
    with partition_slot(registry,SITE,'bulk',q.ExecutionPartition('native',1)) as bulk_locked:assert bulk_locked
    checks['native_workspace_and_pool_slots_are_distinct']=True
    with registry.cursor() as cr:
        with _claim_guard(cr,'urgent',None,1) as locked:
            assert locked
            claim=q.claim(cr,SITE,RELEASE,str(uuid4()),[HANDLER],routes=ROUTES,pool='urgent',native_installation_id=1)
            assert claim.job_id==native[0];cr.commit()

with registry.cursor() as cr:
    with _claim_guard(cr,'urgent',None,1) as locked:
        assert locked
        assert q.claim(cr,SITE,RELEASE,str(uuid4()),[HANDLER],routes=ROUTES,pool='urgent',native_installation_id=1) is None
        cr.commit()
    checks['running_native_claim_still_blocks_after_compute_slot_release']=True
    with _claim_guard(cr,'urgent',1) as locked:
        assert locked
        other=q.claim(cr,SITE,RELEASE,str(uuid4()),[HANDLER],routes=ROUTES,pool='urgent',workspace_id=1)
        assert other.job_id==workspace[0];cr.commit()
    checks['workspace_claim_runs_while_same_numeric_native_partition_is_busy']=True
    def effect(row):
        cr.execute('INSERT INTO bg_effect(key) VALUES(%s)',[row['public_id']]);return dict(applied=True)
    assert q.run_fenced(cr,claim,effect)==dict(applied=True);cr.commit()
    try:q.run_fenced(cr,claim,effect)
    except q.ClaimLost:cr.rollback()
    else:raise AssertionError('Repeated claim applied')
    cr.execute('SELECT count(*) FROM bg_effect');assert cr.fetchone()[0]==1
    checks['native_fenced_completion_applies_once']=True
    snapshot=job_capacity.observe(cr,SITE,RELEASE,{'urgent':ROUTES,'bulk':[]})
    assert snapshot['complete']
    assert len(snapshot['groups'])==72
    assert {r['partition'] for r in snapshot['groups'] if r['workspace'] is None}=={q.ExecutionPartition('native',i).key for i in range(1,71)}
    checks['capacity_preserves_each_native_partition_instead_of_merging_null_workspaces']=True
    cr.commit()
    q.set_control(cr,SITE,RELEASE,'paused');cr.commit()
    try:job_fairness.reserve_partition(registry,current,ready[1])
    except q.DispatchPaused:pass
    else:raise AssertionError('Paused rotation changed')
    checks['dispatch_pause_fences_partition_hint_mutation']=True

print('MP_AT_SQL='+json.dumps(dict(result='passed_native_workspace_partition_sql',checks=checks,
    scope='Current SDK source against minimal PostgreSQL table fixture; no managed application startup or business authorization claim.')))
