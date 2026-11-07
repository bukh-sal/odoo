"""Actual PostgreSQL visibility and heartbeat races for pooled claims."""
import ast
import hashlib
import json
import subprocess
import time

from background_capacity_sql import PG,CLIENT
from background_site import ROOT,write
from background_workers import docker

NAME='mp-bx04-claim-guard-sql-01'

PROBE="""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import hashlib,importlib,json,sys,types,psycopg2
from uuid import uuid4
q=types.ModuleType('modular_platform.durable');q.__package__='modular_platform'
sys.modules[q.__name__]=q;importlib.import_module('modular_platform').durable=q
exec(DURABLE,q.__dict__)
namespace=dict(contextmanager=contextmanager,durable=q)
exec(GUARD,namespace);guard=namespace['_claim_guard']
SITE='00000000-0000-4000-8000-000000000001';RELEASE='sha256:'+'1'*64
settings=dict(host='127.0.0.1',user='postgres',dbname='mp_bx_claims',connect_timeout=5)
class Cursor:
    def __init__(self,connection):self.connection=connection;self.cr=connection.cursor()
    def __getattr__(self,name):return getattr(self.cr,name)
    def rollback(self):self.connection.rollback()
    def commit(self):self.connection.commit()
def connection():
    value=psycopg2.connect(**settings);value.set_session(isolation_level='REPEATABLE READ');return value
def denied(error,fn):
    try:fn()
    except error:return
    raise AssertionError('Expected pooled claim refusal')
first,second,third,slot=[connection() for _ in range(4)]
try:
    a,b,c,s=map(Cursor,(first,second,third,slot))
    a.execute(DDL.replace('CREATE TEMP TABLE','CREATE TABLE'))
    a.execute('CREATE TABLE ir_config_parameter(key varchar PRIMARY KEY,value varchar)')
    a.execute('INSERT INTO ir_config_parameter VALUES(%s,%s)',['mp.site_id',SITE])
    q.set_control(a,SITE,RELEASE,'enabled')
    jobs={}
    for workspace in range(1,6):
        scope=q.DispatchScope(SITE,workspace,1,1,RELEASE)
        for index in range(2):
            now=datetime.now(timezone.utc)-timedelta(seconds=1)
            timing=q.JobSchedule(now,now+timedelta(seconds=180),20)
            payload=dict(schema_version=2,input={},context={},schedule=timing.wire())
            jobs[workspace,index]=q.enqueue(a,scope,'org.example.claim:bulk',1,payload,
                'bulk-'+str(workspace)+'-'+str(index),schedule=timing)
    timing=q.JobSchedule(datetime.now(timezone.utc)-timedelta(seconds=1),datetime.now(timezone.utc)+timedelta(seconds=180),20)
    urgent=q.enqueue(a,q.DispatchScope(SITE,1,1,1,RELEASE),'org.example.claim:urgent',1,
        dict(schema_version=2,input={},context={},schedule=timing.wire()),'urgent',schedule=timing)
    a.commit();checks={}
    def claim(cr,workspace=1,pool='bulk'):
        handler='org.example.claim:'+pool
        return q.claim(cr,SITE,RELEASE,str(uuid4()),[handler],workspace_id=workspace,
            routes=[(handler,1)],pool=pool,lease_seconds=6)
    denied(q.QueueError,lambda:claim(a));a.rollback()
    checks['unguarded_pool_refused']=True
    # Hold the compute slot on a third connection, then lose only that one.
    compute=int.from_bytes(hashlib.sha256(f'mp-job:{SITE}:bulk:1'.encode()).digest()[:8],'big',signed=True)
    s.execute('SELECT pg_try_advisory_lock(%s)',[compute]);assert s.fetchone()==(True,);s.rollback()
    s.execute('SELECT pg_backend_pid()');pid,=s.fetchone();s.rollback()
    with guard(a,'bulk',1) as locked:
        assert locked;old=claim(a);assert old.job_id==jobs[1,0]
        c.execute('SELECT pg_terminate_backend(%s)',[pid]);assert c.fetchone()==(True,);c.commit()
        with guard(b,'bulk',1) as other:assert not other
        a.commit()
    checks['invisible_preparation_still_excluded_after_slot_loss']=True
    with guard(b,'bulk',1) as locked:
        assert locked and claim(b) is None;b.commit()
    checks['committed_running_row_blocks_different_claim']=True
    with guard(b,'urgent',1) as locked:
        assert locked and claim(b,pool='urgent').job_id==urgent;b.commit()
    with guard(b,'bulk',2) as locked:
        assert locked and claim(b,2).job_id==jobs[2,0];b.commit()
    checks['other_pool_and_workspace_continue']=True
    with guard(a,'bulk',3) as locked:
        assert locked;rolled=claim(a,3);a.rollback()
        with guard(b,'bulk',3) as other:assert not other
    with guard(b,'bulk',3) as locked:
        assert locked;retried=claim(b,3);assert retried.job_id==rolled.job_id and retried.generation==1;b.commit()
    checks['caller_rollback_and_guard_release']=True
    # A stale snapshot existed before the other connection committed a claim.
    b.execute('SELECT state FROM mp_job WHERE public_id=%s',[jobs[4,0]]);assert b.fetchone()==('pending',)
    with guard(a,'bulk',4) as locked:assert locked;claim(a,4);a.commit()
    b.execute('SELECT state FROM mp_job WHERE public_id=%s',[jobs[4,0]]);assert b.fetchone()==('pending',)
    with guard(b,'bulk',4) as locked:assert locked and claim(b,4) is None;b.commit()
    checks['acquisition_discards_stale_repeatable_read_snapshot']=True
    a.execute("UPDATE mp_job SET lease_until=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[old.job_id]);a.commit()
    c.execute('SELECT id FROM mp_job WHERE public_id=%s FOR UPDATE',[old.job_id]);c.fetchone()
    c.execute("UPDATE mp_job SET lease_until=timezone('UTC',clock_timestamp())+interval '60 seconds' WHERE public_id=%s",[old.job_id])
    with guard(b,'bulk',1) as locked:
        assert locked and claim(b) is None;b.commit()
    c.commit()
    checks['locked_expired_attempt_and_pending_renewal_block_other_claim']=True
    with guard(b,'bulk',1) as locked:assert locked and claim(b) is None;b.commit()
    checks['renewed_live_attempt_still_excludes']=True
    a.execute("UPDATE mp_job SET lease_until=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[old.job_id]);a.commit()
    with guard(b,'bulk',1) as locked:
        assert locked;new=claim(b);assert new.job_id!=old.job_id
        denied(q.ClaimLost,lambda:q.run_fenced(b,old,lambda row:{'unexpected':True}))
        b.commit()
    checks['unlocked_expiry_reaps_and_old_apply_refused']=True
    # Reconcile-mode uncertainty remains unknown, never silently retried.
    with guard(a,'bulk',5) as locked:assert locked;uncertain=claim(a,5);a.commit()
    a.execute("UPDATE mp_job SET effect_mode='reconcile',effect_started=true,lease_until=timezone('UTC',clock_timestamp())-interval '1 second' WHERE public_id=%s",[uncertain.job_id]);a.commit()
    with guard(b,'bulk',5) as locked:
        assert locked;next_job=claim(b,5);assert next_job.job_id!=uncertain.job_id;b.commit()
    a.execute('SELECT state FROM mp_job WHERE public_id=%s',[uncertain.job_id]);assert a.fetchone()==('outcome_unknown',);a.rollback()
    checks['unknown_remote_effect_not_retried']=True
    print(json.dumps(dict(state='passed',checks=checks)),flush=True)
finally:
    for value in (first,second,third,slot):value.close()
"""


def main():
    output=ROOT/'docs/evidence/post-r1/background-execution/bx-04-claim-guard-sql.json';assert not output.exists()
    assert not docker('ps','-aq','--filter','name=^/'+NAME+'$').strip()
    docker('run','-d','--name',NAME,'--label','com.modular.disposable='+NAME,'--network','none',
        '--tmpfs','/var/lib/postgresql/data:rw','--env','POSTGRES_HOST_AUTH_METHOD=trust','--env','POSTGRES_DB=mp_bx_claims',PG)
    try:
        for _ in range(30):
            if subprocess.run(['docker','exec',NAME,'pg_isready','-U','postgres'],capture_output=True,timeout=5).returncode==0:break
            time.sleep(.2)
        else:raise AssertionError('Isolated PostgreSQL not ready')
        tree=ast.parse((ROOT/'tests/background_postgres.py').read_text())
        ddl=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='DDL' for target in node.targets))
        source=(ROOT/'packages/platform_sdk/modular_platform/durable.py').read_text()
        runner=ast.parse((ROOT/'packages/platform_sdk/modular_platform/job_runner.py').read_text())
        guard=ast.unparse(next(node for node in runner.body if isinstance(node,ast.FunctionDef) and node.name=='_claim_guard'))
        request='DURABLE='+repr(source)+'\nGUARD='+repr(guard)+'\nDDL='+repr(ddl)+'\n'+PROBE
        result=json.loads(docker('run','--rm','-i','--network','container:'+NAME,'--read-only','--cap-drop','ALL',
            '--entrypoint','/venv/bin/python',CLIENT,'-c','import sys;exec(sys.stdin.read())',data=request.encode()))
    finally:
        row,=json.loads(docker('inspect',NAME));assert row['Config']['Labels']['com.modular.disposable']==NAME
        docker('rm','-fv',NAME)
    write(output,dict(result,queue_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        guard_source_sha256=hashlib.sha256(guard.encode()).hexdigest(),postgres=PG,client=CLIENT,
        retired=dict(containers=1,volumes=0,networks=0),scope='Private pooled claim/guard transactions; native integration and load remain pending.'))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
