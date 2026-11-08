"""Actual independently reviewed urgent/bulk profile and native reminder workload."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'packages/platform_sdk')]
from aurora_tasks_site import TasksSite, load, write
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore

SEED = '''
import json
from datetime import timedelta
from odoo import api,fields
actor=api.Environment(env.cr,FIXTURE['users']['alice']['id'],{},su=False)
listing=actor['mp.aurora.task.list'].create(dict(name='Managed reminder workload'))
rows=actor['mp.aurora.task'].create([dict(name='Managed reminder '+str(i),list_id=listing.id,
    assignee_id=FIXTURE['users']['operator']['id'],due_date=fields.Datetime.now()-timedelta(seconds=1),reminder='0') for i in range(20)])
env.cr.execute('SELECT job_id FROM mp_aurora_reminder WHERE task_id=ANY(%s) ORDER BY task_id',[rows.ids])
jobs=[r[0] for r in env.cr.fetchall()]
assert len(jobs)==20
env.cr.commit()
print('MP_AT_WORKLOAD='+json.dumps(dict(tasks=rows.ids,jobs=jobs,list=listing.id)))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','workload','verify','drain'])
    parser.add_argument('--run',required=True)
    args=parser.parse_args()
    site=TasksSite(args);state=site.state()
    target=load(site.private/'target.json')
    state.update(database=target['sites'][0]['database'],image_id=target['image_id'])
    operator=JobOperator(OperatorStore(site.private/'control'),site.private/'target.json')
    receipt=site.local/'managed-profile.json'
    if args.action=='start':
        assert not receipt.exists()
        review=operator.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
        write(receipt,dict(phase='reviewed',approval=review['approval']))
        result=operator.run('profile-apply',approval=review['approval'])
        assert result['state']=='ready'
        write(receipt,dict(phase='ready',profile=result))
        print(json.dumps(dict(result='ready',urgent=1,bulk=1)))
    elif args.action=='workload':
        assert load(receipt)['phase']=='ready'
        assert not (site.local/'managed-workload.json').exists()
        raw=site.native(dict(state),'managed-seed',[],'FIXTURE='+repr(load(site.local/'fixtures.json'))+'\n'+SEED)
        rows=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_WORKLOAD=')]
        assert len(rows)==1
        write(site.local/'managed-workload.json',dict(phase='queued',**rows[0]))
        # Preserve the site's stable publication phase; command itself is durably logged.
        write(site.local/'state.json',state)
        print(json.dumps(dict(result='queued',jobs=len(rows[0]['jobs']))))
    elif args.action=='verify':
        path=site.local/'managed-workload.json';record=load(path)
        assert record['phase']=='queued'
        ids=','.join("'"+ident+"'" for ident in record['jobs'])
        # Bounded observation only; timeout never resubmits jobs.
        deadline=time.monotonic()+50
        while True:
            output=site.sql(state,'workload-status-'+str(time.monotonic_ns()),
                "SELECT jsonb_agg(jsonb_build_object('id',public_id,'state',state,'attempts',attempts,'error',error_code,'result',result)) FROM mp_job WHERE public_id IN ("+ids+");")
            rows=json.loads(output)
            if len(rows)==20 and all(r['state']=='completed' for r in rows):break
            if time.monotonic()>deadline:raise AssertionError('Inspect saved workload rows and process status; do not resubmit')
            time.sleep(.5)
        assert all(r['attempts']==1 and r['result']==dict(outcome='notified') for r in rows)
        taskids=','.join(map(str,record['tasks']))
        count=site.sql(state,'workload-effect-count', 'SELECT count(*),count(DISTINCT task_id) FROM mp_aurora_notification WHERE task_id IN ('+taskids+');').strip()
        assert count==b'20|20'
        record.update(phase='verified',rows=rows,effects=20,profile=operator.run('status'))
        write(path,record)
        print(json.dumps(dict(result='passed',completed_once=20,notifications=20)))
    else:
        result=operator.run('drain')
        write(site.local/'managed-drain.json',result)
        print(json.dumps(dict(result='drained')))


if __name__=='__main__':main()
