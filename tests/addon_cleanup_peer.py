"""Fresh useful Aurora peer for AR-04; reuses qualified fixture workflows."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from addon_cleanup_profiles import CleanupProfile
from foundation_release import FoundationSite,load,write
from foundation_jobs import shell
from foundation_workers import ENQUEUE
from foundation_lifecycle import sql
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','initialize','verify','install_notes','install_background','workflow',
        'seed_jobs','start_jobs','enqueue_peer','verify_jobs','drain'])
    p.add_argument('--candidate',type=Path)
    p.add_argument('--label',default='baseline')
    a=p.parse_args();a.run='ar04-peer-01';a.profile='aurora';a.site='aurora';a.port=18161
    site=CleanupProfile(a)
    if a.phase=='seed_jobs':
        path=site.local/'job-fixtures.json';assert not path.exists()
        code='FIXTURE='+repr(load(site.local/'fixtures.json'))+'\n'+'''
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
import json
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
tasks=actor['mp.background.task'].create([dict(name='AR peer four',points=4),dict(name='AR peer six',points=6)])
env.cr.commit()
print('AR_PEER_TASKS='+json.dumps(tasks.ids))
'''
        raw=shell(site,'ar-peer-task-seed',code)
        tasks,=[json.loads(r.split('=',1)[1]) for r in raw.splitlines() if r.startswith('AR_PEER_TASKS=')]
        write(path,dict(tasks=tasks,points=10));print(json.dumps(dict(result='seeded',tasks=len(tasks))))
    elif a.phase in ('start_jobs','drain'):
        op=JobOperator(OperatorStore(site.private/'control'),site.private/'target.json')
        path=site.local/('job-'+a.phase+'.json');assert not path.exists()
        if a.phase=='start_jobs':
            review=op.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
            write(path,dict(phase='reviewed',approval=review['approval']))
            result=op.run('profile-apply',approval=review['approval']);assert result['state']=='ready'
        else:
            result=op.run('drain');assert result['state']=='paused'
        write(path,dict(phase='verified',result=result));print(json.dumps(dict(result='passed',phase=a.phase)))
    elif a.phase=='enqueue_peer':
        fault=load(Path(__file__).resolve().parents[1]/'.local/addon-cleanup/baseline46/private/reference/operator/ar04-first.json')
        assert fault['phase']=='recovery_required' and fault['failed_app_stopped']
        path=site.local/'peer-jobs.json';assert not path.exists()
        code=f"FIXTURE={load(site.local/'fixtures.json')!r}\nCOUNT=16\nPREFIX='ar-peer-recovery-'\n"+ENQUEUE
        raw=shell(site,'ar-peer-recovery-jobs',code)
        jobs,=[json.loads(r.split('=',1)[1]) for r in raw.splitlines() if r.startswith('CF_PEER_JOBS=')]
        write(path,dict(phase='queued',jobs=jobs,failed_operation=fault['operation'],utc=datetime.now(timezone.utc).isoformat()))
        print(json.dumps(dict(result='queued',jobs=len(jobs),peer_app_down=True)))
    elif a.phase=='verify_jobs':
        path=site.local/'peer-jobs.json';record=load(path);assert record['phase']=='queued'
        target=load(site.private/'target.json');ids=','.join("'"+j+"'" for j in record['jobs'])
        until=time.monotonic()+120
        while True:
            rows=json.loads(sql(target,'SELECT json_agg(json_build_object(\'state\',state,\'attempts\',attempts,\'result\',result)) FROM mp_job WHERE public_id IN ('+ids+');'))
            if len(rows)==16 and all(r['state']=='completed' for r in rows):break
            assert time.monotonic()<until,rows
            time.sleep(.5)
        assert all(r['attempts']==1 and r['result']['count']==2 and r['result']['points']==10 for r in rows)
        record.update(phase='verified',exactly_once=True,rows=rows);write(path,record)
        print(json.dumps(dict(result='passed',completed_once=len(rows),exact_points=10)))
    elif a.phase=='initialize':FoundationSite.initialize(site)
    else:getattr(site,a.phase)()


if __name__=='__main__':main()
