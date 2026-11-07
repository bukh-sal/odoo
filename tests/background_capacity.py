"""Native BX-04 telemetry/CLI qualification before the admitted load runs."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from background_site import load,write,ROOT
from background_workers import Probe,docker,wait
from background_web_capacity import resize_stock_web
from modular_platform.capacity_advisor import advise
from modular_platform.plans import data_digest


SEED="""
from datetime import datetime,timedelta,timezone
import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
jobs=[]
for index in range(6):
    workspace='A' if index%2==0 else 'B';who='alice' if workspace=='A' else 'bob'
    actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][who]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
    current=actor['mp.background.task']._job_env()
    now=datetime.now(timezone.utc)
    handler='org.example.background:load' if index<3 else 'org.example.background:report'
    inputs={'iterations':[250000,1000000,5000000][index]} if index<3 else {'first':1,'last':1}
    jobs.append(enqueue_scheduled(current,'jobs',handler,inputs,'bx04-native-'+str(index),
        schedule=JobSchedule(now,now+timedelta(seconds=180),20),version=1 if index<3 else 2))
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(jobs=jobs)))
"""


def main(phase):
    probe=Probe('bx-04-capacity-01')
    path=probe.site.local/'bx04-native.json'
    record=load(path) if path.exists() else {}
    if phase=='size':
        assert not record
        resize_stock_web(probe)
        database=probe.project+'-db-1'
        row,=json.loads(docker('inspect',database))
        assert row['Config']['Labels']['com.docker.compose.project']==probe.project
        docker('update','--cpus','4',database)
        # Exact same read workload as BG-04's paired test.
        for workspace,who,count in [('A','alice',10000),('B','bob',1)]:
            principal=probe.fixture['users'][who]['principal_id'];ws=probe.fixture['workspaces'][workspace]['id']
            probe.sql(f"""INSERT INTO mp_example_note
                (workspace_id,public_id,title,body,author_id,revision,create_uid,write_uid,create_date,write_date)
                SELECT {ws},gen_random_uuid()::text,'BG benchmark '||lpad(n::text,5,'0'),repeat(md5(n::text),300),
                    p.id,1,p.user_id,p.user_id,timezone('UTC',now()),timezone('UTC',now())
                FROM generate_series(1,{count}) n CROSS JOIN mp_principal p WHERE p.public_id='{principal}'""")
        probe.sql('ANALYZE mp_example_note')
        record=dict(phase='sized',web_workers=3,postgres_cpus=4)
    elif phase=='native':
        assert record['phase']=='sized'
        review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
        record.update(phase='starting',approval=review['approval']);write(path,record)
        start=datetime.now(timezone.utc)
        status=probe.operator.run('profile-apply',approval=review['approval'])
        assert status['state']=='ready'
        record.update(phase='ready',startup_seconds=(datetime.now(timezone.utc)-start).total_seconds());write(path,record)
        raw=probe.site.native(dict(probe.state),'bx04-native-seed',[],
            'FIXTURE='+repr(probe.fixture)+'\n'+SEED).decode()
        write(probe.site.local/'state.json',probe.state)
        seed,=[json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BX04_RESULT=')]
        record.update(phase='seeded',seed=seed);write(path,record)
        wait(lambda:all(probe.row(job)['state']=='completed' for job in seed['jobs']),60)
        snapshot=probe.operator.run('capacity')
        assert snapshot['complete'] and snapshot['fleet_state']=='ready' and snapshot['dispatch']=='enabled'
        keys={sample['handler_version'] for sample in snapshot['samples']}
        assert {'org.example.background:report:2','org.example.background:load:1'}<=keys
        assert len(snapshot['samples'])==6,snapshot['samples']
        policy=dict(protocol=1,maximum_age_seconds=30,startup_seconds=record['startup_seconds'],drain_seconds=120,
            pools=dict(urgent=dict(minimum=1,maximum=1,start_target_seconds=3),bulk=dict(minimum=1,maximum=6,start_target_seconds=60)),
            handlers={key:dict(pool='bulk',default_seconds=2,arrival_per_second=0) for key in keys},
            headroom=dict(web_p95_ms=500,db_cpu_fraction=.85,connection_fraction=.7,lock_wait_seconds=2))
        missing=advise(snapshot,policy,expected_pins=snapshot['pins'])
        assert missing['state']=='hold' and 'missing_headroom' in missing['reasons']
        write(probe.site.local/'bx04-capacity-snapshot.json',snapshot)
        write(probe.site.local/'bx04-capacity-policy.json',policy)
        cli=probe.operator.run('advise',observation=probe.site.local/'bx04-capacity-snapshot.json',policy=probe.site.local/'bx04-capacity-policy.json')
        assert cli['state']=='hold' and not cli['mutation_authorized']
        telemetry=[]
        for name in probe.operator._lanes():telemetry.extend(probe.logs(name))
        claims={row['job_id']:row for row in telemetry if row.get('event')=='claimed' and row.get('job_id') in seed['jobs']}
        ends={row['job_id']:row for row in telemetry if row.get('event')=='attempt_end' and row.get('job_id') in seed['jobs']}
        assert set(claims)==set(ends)==set(seed['jobs'])
        for job in seed['jobs']:
            assert ends[job]['worker_duration_ms']==ends[job]['duration_ms']+claims[job]['preparation_upper_bound_ms']
            assert claims[job]['generation']==ends[job]['generation']
        record.update(phase='passed',snapshot=snapshot,missing_headroom_hold=cli,
            telemetry=dict(claims=claims,ends=ends),profile_state=probe.operator.run('status'))
    else:raise ValueError(phase)
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],startup_seconds=record.get('startup_seconds'))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['size','native'])
    main(parser.parse_args().phase)
