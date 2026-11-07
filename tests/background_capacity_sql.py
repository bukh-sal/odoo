"""Actual PostgreSQL bounds and state classification for BX-04 observations."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import time

from background_site import ROOT,write
from background_workers import docker

NAME='mp-bx04-capacity-sql-01'
PG='sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'
CLIENT='sha256:07cacdf471a5b7f1b6b502de15f9644998f0ceeae11a531ae62a8256dc6bf5e1'

PROBE="""
import json,psycopg2
namespace={};exec(METRICS,namespace);observe=namespace['observe']
with psycopg2.connect(host='127.0.0.1',user='postgres',dbname='mp_bx_capacity',connect_timeout=5) as connection:
    with connection.cursor() as cr:
        cr.execute(DDL)
        cr.execute('ALTER TABLE mp_job ALTER COLUMN idempotency_key SET DEFAULT gen_random_uuid()::text')
        def seed(state='pending',workspace=1,release='release',delay=-1,expiry=180,handler='report',site='site',n=1):
            cr.execute('''INSERT INTO mp_job(public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
                release_digest,payload,input_digest,effect_mode,state,attempts,max_attempts,claim_generation,dispatch_generation,
                available_at,deadline_at,cancel_requested,effect_started,progress,created_at)
                SELECT gen_random_uuid()::text,%s,%s,1,1,%s,2,%s,
                jsonb_build_object('schema_version',2,'schedule',jsonb_build_object('run_at',now()-interval '30 seconds')),
                'digest','idempotent',%s,0,5,0,1,timezone('UTC',now())+(%s*interval '1 second'),
                timezone('UTC',now())+(%s*interval '1 second'),false,false,0,timezone('UTC',now())
                FROM generate_series(1,%s)''',[site,workspace,handler,release,state,delay,expiry,n])
        seed(state='retry');seed(delay=60);seed(expiry=-1);seed(state='held');seed(state='outcome_unknown')
        seed(release='old');seed(handler='obsolete');seed(site='foreign')
        result=observe(cr,'site','release',{'bulk':[('report',2)],'urgent':[]})
        assert result['complete'] and result['live_rows_observed']==7,result
        current=next(row for row in result['groups'] if row['pool']=='bulk')
        assert [current[key] for key in ('ready','future','expired','held','unknown','retry')]==[1,1,1,1,1,1],current
        assert current['original_wait_ms']>=30000 and current['retry_wait_ms']<2000,current
        assert all(row['pool'] is None for row in result['groups'] if not row['current'] or row['handler']=='obsolete')
        checks=dict(state_classification=True,foreign_site_excluded=True,original_and_retry_eligibility_separate=True,
                    obsolete_and_old_release_unroutable=True,database_headroom_observed=True)
        cr.execute('TRUNCATE mp_job')
        seed(n=100001)
        over=observe(cr,'site','release',{'bulk':[('report',2)]})
        assert not over['complete'] and over['reason']=='live_table_limit' and over['groups']==[],over
        checks['live_limit_refuses_sizing']=True
        cr.execute('TRUNCATE mp_job')
        seed(n=1025)
        cr.execute('UPDATE mp_job SET workspace_id=id')
        groups=observe(cr,'site','release',{'bulk':[('report',2)]})
        assert not groups['complete'] and groups['reason']=='group_limit' and len(groups['groups'])==1024
        checks['group_output_bounded_and_incomplete']=True
        connection.rollback()
        print(json.dumps(dict(state='passed',checks=checks)),flush=True)
"""


def main():
    evidence=ROOT/'docs/evidence/post-r1/background-execution/bx-04-capacity-primitives.json'
    assert not evidence.exists()
    assert not docker('ps','-aq','--filter','name=^/'+NAME+'$').strip()
    docker('run','-d','--name',NAME,'--label','com.modular.disposable='+NAME,'--network','none',
        '--tmpfs','/var/lib/postgresql/data:rw','--env','POSTGRES_HOST_AUTH_METHOD=trust',
        '--env','POSTGRES_DB=mp_bx_capacity',PG)
    try:
        for _ in range(30):
            result=subprocess.run(['docker','exec',NAME,'pg_isready','-U','postgres'],capture_output=True,timeout=5)
            if result.returncode==0:break
            time.sleep(.2)
        else:raise AssertionError('Isolated PostgreSQL not ready')
        tree=ast.parse((ROOT/'tests/background_postgres.py').read_text())
        ddl=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='DDL' for target in node.targets))
        path=ROOT/'packages/platform_sdk/modular_platform/job_capacity.py';source=path.read_text()
        request='METRICS='+repr(source)+'\nDDL='+repr(ddl)+'\n'+PROBE
        raw=docker('run','--rm','-i','--network','container:'+NAME,'--read-only','--cap-drop','ALL',
            '--entrypoint','/venv/bin/python',CLIENT,'-c','import sys;exec(sys.stdin.read())',data=request.encode())
        report=json.loads(raw)
    finally:
        row,=json.loads(docker('inspect',NAME))
        assert row['Config']['Labels']['com.modular.disposable']==NAME
        docker('rm','-fv',NAME)
    write(evidence,dict(report,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        postgres=PG,client=CLIENT,retired=dict(containers=1,volumes=0,networks=0),
        scope='SQL observation and limits only; no native runner or load/scaling claim'))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
