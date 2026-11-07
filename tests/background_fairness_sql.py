"""PostgreSQL selection-ticket races, ring order and fenced metadata writes."""
import ast
import hashlib
import json
import subprocess
import time

from background_capacity_sql import PG,CLIENT
from background_site import ROOT,write
from background_workers import docker

NAME='mp-bx04-fairness-sql-01'

PROBE="""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import json,sys,types,psycopg2
from modular_platform import durable
module=types.ModuleType('modular_platform.job_fairness');module.__package__='modular_platform'
sys.modules[module.__name__]=module;exec(FAIRNESS,module.__dict__)
exec(READY,durable.__dict__)
SITE='00000000-0000-4000-8000-000000000001';RELEASE='sha256:'+'1'*64
settings=dict(host='127.0.0.1',user='postgres',dbname='mp_bx_fairness',connect_timeout=5)
class Cursor:
    def __init__(self,connection,fail=False):self.connection=connection;self.cr=connection.cursor();self.fail=fail
    def __getattr__(self,name):return getattr(self.cr,name)
    def commit(self):
        if self.fail:raise RuntimeError('Injected reservation commit failure')
        self.connection.commit()
class Registry:
    def __init__(self,fail=False):self.fail=fail
    @contextmanager
    def cursor(self):
        connection=psycopg2.connect(**settings);connection.set_session(isolation_level='REPEATABLE READ')
        try:yield Cursor(connection,self.fail)
        finally:connection.rollback();connection.close()
def denied(error,fn):
    try:fn()
    except error:return
    raise AssertionError('Expected fenced or invalid reservation refusal')
with psycopg2.connect(**settings) as connection:
    with connection.cursor() as cr:
        cr.execute(DDL.replace('CREATE TEMP TABLE','CREATE TABLE'))
        cr.execute('CREATE TABLE ir_config_parameter(id serial PRIMARY KEY,key varchar UNIQUE,value varchar,create_uid int,write_uid int,create_date timestamp,write_date timestamp)')
        cr.execute('INSERT INTO ir_config_parameter(key,value) VALUES(%s,%s),(%s,%s)',
            ['mp.site_id',SITE,'mp.release_digest',RELEASE])
        durable.set_control(cr,SITE,RELEASE,'enabled');connection.commit()
        registry=Registry();checks={}
        first=module.read(cr,SITE,RELEASE,'bulk');second=module.read(cr,SITE,RELEASE,'bulk')
        assert first.after==0 and first.raw is None
        assert module.reserve(registry,first,1) and not module.reserve(registry,second,2)
        checks['first_insert_and_stale_selector']=True
        key=module._key(SITE,RELEASE,'bulk')
        current=module.read(cr,SITE,RELEASE,'bulk')
        denied(RuntimeError,lambda:module.reserve(Registry(fail=True),current,2))
        assert module.read(cr,SITE,RELEASE,'bulk').raw==current.raw
        checks['failed_commit_rolls_back_hint']=True
        urgent=module.read(cr,SITE,RELEASE,'urgent')
        assert urgent.raw is None and module.reserve(registry,urgent,40)
        assert module.read(cr,SITE,RELEASE,'bulk').after==1
        checks['pool_keys_independent']=True
        connection.commit()
        durable.set_control(cr,SITE,RELEASE,'paused');connection.commit()
        denied(durable.DispatchPaused,lambda:module.reserve(registry,current,2))
        durable.set_control(cr,SITE,RELEASE,'enabled');connection.commit()
        cr.execute("UPDATE ir_config_parameter SET value=%s WHERE key='mp.release_digest'",['sha256:'+'2'*64]);connection.commit()
        denied(durable.DispatchPaused,lambda:module.reserve(registry,current,2))
        cr.execute("UPDATE ir_config_parameter SET value=%s WHERE key='mp.release_digest'",[RELEASE]);connection.commit()
        checks['paused_and_changed_release_refused']=True
        cr.execute('UPDATE ir_config_parameter SET value=%s WHERE key=%s',['broken-json',key]);connection.commit()
        malformed=module.read(cr,SITE,RELEASE,'bulk');assert malformed.after==0
        assert module.reserve(registry,malformed,4)
        assert module.read(cr,SITE,RELEASE,'bulk').after==4
        checks['bounded_corruption_replaced_atomically']=True
        denied(durable.QueueError,lambda:module.read(cr,SITE,RELEASE,'../foreign'))
        denied(durable.QueueError,lambda:module.reserve(registry,current,True))
        checks['scope_and_integer_validation']=True
        cr.execute('DELETE FROM ir_config_parameter WHERE key=%s',[key]);connection.commit()
        tickets=[module.read(cr,SITE,RELEASE,'bulk') for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda pair:module.reserve(registry,*pair),[(tickets[0],1),(tickets[1],2)]))
        assert sum(results)==1
        checks['concurrent_missing_hint_has_one_winner']=True
        cr.execute('''INSERT INTO mp_job(public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
            idempotency_key,release_digest,payload,input_digest,effect_mode,state,attempts,max_attempts,
            claim_generation,dispatch_generation,available_at,deadline_at,cancel_requested,effect_started,progress,created_at)
            SELECT gen_random_uuid()::text,%s,n,1,1,'org.example.fair:load',1,n::text,%s,'{}'::jsonb,
            'digest','idempotent','pending',0,5,0,1,timezone('UTC',now()),timezone('UTC',now())+interval '180 seconds',
            false,false,0,timezone('UTC',now()) FROM generate_series(1,70) n''',[SITE,RELEASE]);connection.commit()
        routes=[('org.example.fair:load',1)]
        assert durable.ready_workspaces(cr,SITE,RELEASE,routes)==list(range(1,65))
        assert durable.ready_workspaces(cr,SITE,RELEASE,routes,after=64)==list(range(65,71))+list(range(1,59))
        connection.rollback()
        checks['legacy_order_and_bounded_ring_wrap']=True
        cr.execute('DELETE FROM ir_config_parameter WHERE key=%s',[key]);connection.commit()
        selected=[]
        for _ in range(70):
            ticket=module.read(cr,SITE,RELEASE,'bulk')
            candidates=durable.ready_workspaces(cr,SITE,RELEASE,routes,after=ticket.after)
            assert len(candidates)==64 and module.reserve(registry,ticket,candidates[0])
            selected.append(candidates[0])
        connection.rollback()
        assert selected==list(range(1,71))
        checks['all70_selected_before_second_turn']=True
        cr.execute("SELECT count(*) FROM mp_job WHERE state='pending'");assert cr.fetchone()==(70,)
        checks['selection_hint_does_not_claim_or_enqueue']=True
        print(json.dumps(dict(state='passed',checks=checks)),flush=True)
"""


def main():
    evidence=ROOT/'docs/evidence/post-r1/background-execution/bx-04-fairness-sql.json';assert not evidence.exists()
    assert not docker('ps','-aq','--filter','name=^/'+NAME+'$').strip()
    docker('run','-d','--name',NAME,'--label','com.modular.disposable='+NAME,'--network','none',
        '--tmpfs','/var/lib/postgresql/data:rw','--env','POSTGRES_HOST_AUTH_METHOD=trust','--env','POSTGRES_DB=mp_bx_fairness',PG)
    try:
        for _ in range(30):
            if subprocess.run(['docker','exec',NAME,'pg_isready','-U','postgres'],capture_output=True,timeout=5).returncode==0:break
            time.sleep(.2)
        else:raise AssertionError('Isolated PostgreSQL not ready')
        tree=ast.parse((ROOT/'tests/background_postgres.py').read_text())
        ddl=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='DDL' for target in node.targets))
        path=ROOT/'packages/platform_sdk/modular_platform/job_fairness.py';source=path.read_text()
        durable=ast.parse((ROOT/'packages/platform_sdk/modular_platform/durable.py').read_text())
        ready=ast.unparse(next(node for node in durable.body if isinstance(node,ast.FunctionDef) and node.name=='ready_workspaces'))
        request='FAIRNESS='+repr(source)+'\nREADY='+repr(ready)+'\nDDL='+repr(ddl)+'\n'+PROBE
        report=json.loads(docker('run','--rm','-i','--network','container:'+NAME,'--read-only','--cap-drop','ALL',
            '--entrypoint','/venv/bin/python',CLIENT,'-c','import sys;exec(sys.stdin.read())',data=request.encode()))
    finally:
        row,=json.loads(docker('inspect',NAME));assert row['Config']['Labels']['com.modular.disposable']==NAME
        docker('rm','-fv',NAME)
    write(evidence,dict(report,source_sha256=hashlib.sha256(source.encode()).hexdigest(),postgres=PG,client=CLIENT,
        retired=dict(containers=1,volumes=0,networks=0),scope='Private SQL hint and candidate order only; native fairness/restart and load remain pending.'))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
