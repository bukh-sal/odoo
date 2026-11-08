"""Actual urgent/bulk work under the exact final47 image, then reviewed drain."""
import argparse
from datetime import datetime,timezone
import json
import time
from addon_cleanup_baseline_workloads import Baseline
from foundation_jobs import shell
from foundation_workers import ENQUEUE
from foundation_lifecycle import sql
from foundation_release import load,write
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore

IMAGE='sha256:a572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['start','bulk','verify','urgent','drain']);a=p.parse_args()
    site=Baseline('final-jobs');target=load(site.private/'target.json');assert target['image_id']==IMAGE
    op=JobOperator(OperatorStore(site.private/'control'),site.private/'target.json')
    path=site.local/('ar05-jobs-'+a.phase+'.json');assert not path.exists(),'Inspect the recorded attempt; no uncertain replay'
    if a.phase in ('start','drain'):
        if a.phase=='start':
            review=op.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
            write(path,dict(phase='reviewed',approval=review['approval']))
            result=op.run('profile-apply',approval=review['approval']);assert result['state']=='ready'
        else:
            result=op.run('drain');assert result['state']=='paused'
        write(path,dict(phase='verified',image=IMAGE,result=result))
    elif a.phase=='bulk':
        code=f"FIXTURE={load(site.local/'fixtures.json')!r}\nCOUNT=8\nPREFIX='ar-final47-bulk-'\n"+ENQUEUE
        raw=shell(site,'ar-final47-bulk',code)
        jobs,=[json.loads(r.split('=',1)[1]) for r in raw.splitlines() if r.startswith('CF_PEER_JOBS=')]
        write(path,dict(phase='queued',image=IMAGE,jobs=jobs))
    elif a.phase=='verify':
        jobs=load(site.local/'ar05-jobs-bulk.json')['jobs'];ids=','.join("'"+j+"'" for j in jobs)
        until=time.monotonic()+120
        while True:
            rows=json.loads(sql(target,"SELECT json_agg(json_build_object('state',state,'attempts',attempts,'result',result)) FROM mp_job WHERE public_id IN ("+ids+");"))
            if len(rows)==8 and all(r['state']=='completed' for r in rows):break
            assert time.monotonic()<until,rows
            time.sleep(.5)
        assert all(r['attempts']==1 and r['result']['count']==2 and r['result']['points']==10 for r in rows)
        write(path,dict(phase='verified',image=IMAGE,completed_once=8,exact_count=2,exact_points=10,rows=rows))
    else:
        code=f"FIXTURE={load(site.local/'fixtures.json')!r}\n"+'''
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
import json
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']]);principal=env.cr.fetchone()[0]
task=actor['mp.background.task'].create(dict(name='AR final47 urgent witness',points=0,assignee_id=principal,due_at=(datetime.now(timezone.utc)+timedelta(seconds=1)).replace(tzinfo=None)))
job=task._queue_current();env.cr.commit()
print('AR_URGENT='+json.dumps(dict(task=task.id,job=job)))
'''
        raw=shell(site,'ar-final47-urgent',code)
        result,=[json.loads(r.split('=',1)[1]) for r in raw.splitlines() if r.startswith('AR_URGENT=')]
        write(path,dict(phase='queued',image=IMAGE,**result))
        until=time.monotonic()+60
        while sql(target,"SELECT state FROM mp_job WHERE public_id='"+result['job']+"';")!='completed':
            assert time.monotonic()<until
            time.sleep(.5)
        assert sql(target,'SELECT count(*) FROM mp_background_notification WHERE task_id='+str(result['task'])+';')=='1'
        write(path,dict(phase='verified',image=IMAGE,notification_once=True,**result))
    print(json.dumps(dict(result='passed',phase=a.phase,image=IMAGE,utc=datetime.now(timezone.utc).isoformat())))


if __name__=='__main__':main()
