"""Useful native/scoped peer work and managed jobs during AT-04 recovery."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_release_site import ReleaseSite,load,write
from foundation_workers import ENQUEUE
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore

WORKFLOW='''
import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
actor=api.Environment(env.cr,FIXTURE['users']['alice']['id'],{},su=False)
if SITE=='maintenance':
 request=actor['maintenance.request'].browse(APP['request'])
 assert request.equipment_id.id==APP['equipment'] and request.maintenance_team_id.id==APP['team']
 request.write(dict(description='Actual useful peer inspection completed during Tasks recovery'))
 request.message_post(body='Independent peer remains useful during failed Tasks release')
 assert 'Actual useful peer inspection completed during Tasks recovery' in request.description
else:
 task=actor['mp.aurora.task'].browse(APP['task'])
 assert task.assignee_id.id==FIXTURE['users']['operator']['id']
 task.write(dict(description=task.description+'; verified recovered native workflow'))
 assert task.name=='Original47 assigned task'
scoped=scoped_environment(actor,FIXTURE['workspaces']['A']['public_id'])
note=scoped['mp.example.note'].browse(WORK['workspaces']['A']['note'])
note.with_context(expected_revision=note.revision).write(dict(body='Actual scoped edit during independent application qualification'))
assert note.title=='Original47 scoped note A'
env.cr.commit()
print('MP_AT_WORK='+json.dumps(dict(native_record=request.id if SITE=='maintenance' else task.id,note=note.id,actor=actor.uid)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['start','workflow','enqueue_peer','verify_peer','verify_source','drain'])
    p.add_argument('--run',required=True);p.add_argument('--site',choices=['tasks','maintenance'],required=True)
    p.add_argument('--port',type=int,required=True);p.add_argument('--label',default='recovery')
    a=p.parse_args();assert a.label.replace('-','').isalnum()
    site=ReleaseSite(a);state=site.state();target=load(site.private/'target.json')
    state.update(image_id=target['image_id'],database=target['sites'][0]['database'])
    op=JobOperator(OperatorStore(site.private/'control'),site.private/'target.json')
    path=site.local/(a.action+'-'+a.label+'.json')
    assert not path.exists(),'Inspect previous result instead of repeating work'
    result=dict(phase='started',utc=datetime.now(timezone.utc).isoformat())
    if a.action=='start':
        review=op.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
        write(path,dict(phase='reviewed',approval=review['approval']))
        profile=op.run('profile-apply',approval=review['approval']);assert profile['state']=='ready'
        result.update(phase='verified',profile=profile)
    elif a.action=='workflow':
        if a.site=='maintenance':
            fault=load(site.local.parent/'tasks/tasks-fault.json')
            status=OperatorStore(site.local.parent/'tasks/operator/control').status(fault['operation'])
            assert fault['failed_app_stopped'] and status['state']=='recovery_required' and not status['traffic_resumed']
            result['failed_operation']=fault['operation']
        code='FIXTURE='+repr(load(site.local/'fixtures.json'))+'\nAPP='+repr(load(site.local/'app-fixtures.json'))+'\nWORK='+repr(load(site.local/'source-work.json'))+'\nSITE='+repr(a.site)+'\n'+WORKFLOW
        raw=site.native(state,'useful-work-'+a.label,[],code)
        data,=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_WORK=')]
        result.update(phase='verified',**data)
    elif a.action=='enqueue_peer':
        assert a.site=='maintenance'
        fault=load(site.local.parent/'tasks/tasks-fault.json')
        status=OperatorStore(site.local.parent/'tasks/operator/control').status(fault['operation'])
        assert fault['failed_app_stopped'] and status['state']=='recovery_required' and not status['traffic_resumed']
        code='FIXTURE='+repr(load(site.local/'fixtures.json'))+'\nCOUNT=16\nPREFIX='+repr('at04-peer-'+a.label+'-')+'\n'+ENQUEUE
        raw=site.native(state,'enqueue-peer-'+a.label,[],code)
        jobs,=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('CF_PEER_JOBS=')]
        assert len(jobs)==16
        result.update(phase='queued',jobs=jobs,failed_operation=fault['operation'])
    elif a.action in {'verify_source','verify_peer'}:
        saved=load(site.local/('source-pending.json' if a.action=='verify_source' else 'enqueue_peer-'+a.label+'.json'))
        jobs=list(saved['jobs'].values()) if a.action=='verify_source' else saved['jobs']
        ids=','.join("'"+j+"'" for j in jobs)
        deadline=time.monotonic()+50
        while True:
            raw=site.sql(state,'observe-'+a.action+'-'+str(time.monotonic_ns()),"SELECT jsonb_agg(jsonb_build_object('id',public_id,'state',state,'attempts',attempts,'result',result,'error',error_code)) FROM mp_job WHERE public_id IN ("+ids+");")
            rows=json.loads(raw)
            if len(rows)==len(jobs) and all(r['state'] in {'completed','failed','cancelled','dead_letter'} for r in rows):break
            assert time.monotonic()<deadline,rows
            time.sleep(.5)
        assert all(r['state']=='completed' and r['result']['count']==2 for r in rows),rows
        for row in rows:
            if a.action=='verify_source':
                label=next(k for k,v in saved['jobs'].items() if v==row['id'])
                assert row['attempts']==(2 if label=='claimed' else 1),row
                assert row['result']['points']==(34 if label=='other_actor' else 13),row
            else:assert row['attempts']==1 and row['result']['points']==13,row
        result.update(phase='verified',rows=rows,effects=len(rows),profile=op.run('status'))
    else:
        profile=op.run('drain');assert profile['state']=='paused'
        result.update(phase='verified',profile=profile)
    write(path,result);write(site.local/'state.json',state)
    print(json.dumps(dict(result=result['phase'],action=a.action,site=a.site)))


if __name__=='__main__':main()
