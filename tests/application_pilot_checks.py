"""Once-only AP-C live pilot checks; preserve intent before every mutation."""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from application_pilot import Pilot,load,write
from check_reference import Client


def denied(client,model,method,args,kwargs=None):
    status,value=client.request('/web/dataset/call_kw/'+model+'.'+method,
        dict(jsonrpc='2.0',method='call',id=1,params=dict(model=model,method=method,args=args,kwargs=kwargs or {})))
    assert status==200 and value.get('error',{}).get('data',{}).get('name')=='odoo.exceptions.AccessError',value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['roles','concurrency','outage']);p.add_argument('--run',default='ap01-pilot-01')
    p.add_argument('--port',type=int,default=18172);a=p.parse_args();site=Pilot(a)
    path=site.local/('check-'+a.phase+'.json');assert not path.exists(),'Inspect prior result before any continuation'
    record=dict(phase='authenticating',utc=datetime.now(timezone.utc).isoformat(),checks=[]);write(path,record)
    def step(name):record['phase']=name;write(path,record)
    def passed(name):record['checks'].append(name);write(path,record)
    alice,bob,operator,outsider=[Client(site,n) for n in ('alice','bob','operator','worker')]
    ids=load(site.local/'fixtures.json')['users'];uid=lambda n:ids[n]['id']
    call=lambda c,m,f,args=None,kwargs=None:c.native(m,f,args,kwargs,workspace=None)
    L='mp.aurora.task.list';T='mp.aurora.task';N='mp.aurora.notification'
    if a.phase=='roles':
        assert call(alice,L,'read',[[2],['owner_id','member_ids']])[0]['member_ids']==[uid('bob')]
        assert call(bob,L,'read',[[2],['owner_id']])[0]['owner_id'][0]==uid('alice')
        assert call(operator,T,'read',[[3],['creator_id','assignee_id']])[0]['assignee_id'][0]==uid('operator')
        for c,m,f,args in [(operator,L,'read',[[2],['name']]),(outsider,T,'read',[[3],['name']]),
            (outsider,T,'write',[[3],dict(name='forged')]),(outsider,T,'create',[[dict(name='forged',list_id=2)]]),
            (bob,L,'write',[[2],dict(member_ids=[(5,)])]),(bob,L,'write',[[2],dict(active=False)]),
            (bob,L,'unlink',[[2]]),(alice,L,'write',[[2],dict(owner_id=uid('bob'))]),
            (alice,T,'write',[[3],dict(creator_id=uid('bob'))])]:denied(c,m,f,args)
        passed('owner/member/assignee positive reads;9 direct ownership/list/outsider denials')
        step('creating_forged_owner_test')
        listing,=call(alice,L,'create',[[dict(name='Authority verification',owner_id=uid('bob'))]])
        record['list']=listing;write(path,record)
        assert call(alice,L,'read',[[listing],['owner_id']])[0]['owner_id'][0]==uid('alice')
        step('creating_forged_creator_test')
        task,=call(alice,T,'create',[[dict(name='Server-owned task identity',list_id=listing,creator_id=uid('bob'))]])
        record['task']=task;write(path,record)
        assert call(alice,T,'read',[[task],['creator_id']])[0]['creator_id'][0]==uid('alice')
        passed('forged create owner/creator overwritten by current user;defaults are not authority')
        notices=call(operator,N,'search_read',[[]],dict(fields=['id','title','is_read']))
        notice=next(n for n in notices if n['title']=='Confirm workshop access');assert notice['is_read']
        for c in (alice,bob,outsider):denied(c,N,'read',[[notice['id']],['title']])
        denied(operator,N,'read',[[notice['id']],['task_id']])
        denied(operator,N,'write',[[notice['id']],dict(title='forged')])
        passed('private delivered/read inbox;nonrecipients denied;hidden linkage and title immutable')
        step('reassigning_task')
        call(bob,T,'write',[[3],dict(assignee_id=uid('bob'))])
        denied(operator,T,'read',[[3],['name']]);denied(operator,N,'action_open_task',[[notice['id']]])
        assert call(operator,N,'read',[[notice['id']],['is_read']])[0]['is_read']
        passed('member assignment edit;former assignee loses task/open authority;history retained')
        step('restoring_assignment')
        call(alice,T,'write',[[3],dict(assignee_id=uid('operator'))])
        assert call(operator,T,'read',[[3],['assignee_id']])[0]['assignee_id'][0]==uid('operator')
        passed('owner restores useful assignment;new reminder occurrence is independently authorized')
    elif a.phase=='concurrency':
        step('creating_concurrency_task')
        task,=call(alice,T,'create',[[dict(name='Concurrent editor check',list_id=2,description='Original description')]])
        record['task']=task;write(path,record)
        first=call(alice,T,'read',[[task],['name','description']])[0]
        second=call(bob,T,'read',[[task],['name','description']])[0];assert first==second
        step('first_editor_write');call(alice,T,'write',[[task],dict(description='Alice saved first')])
        step('stale_second_editor_write');assert call(bob,T,'write',[[task],dict(description='Bob saved later')])
        final=call(alice,T,'read',[[task],['name','description']])[0]
        assert final['description']=='Bob saved later'
        record['same_field_policy']='last_committed_write_wins_no_optimistic_conflict_token'
        passed('two independent sessions observe same version;stale later same-field write accepted')
        step('disjoint_edits');call(alice,T,'write',[[task],dict(name='Concurrent editor check retained')]);call(bob,T,'write',[[task],dict(description='Independent field edit retained')])
        final=call(alice,T,'read',[[task],['name','description']])[0]
        assert final['name']=='Concurrent editor check retained' and final['description']=='Independent field edit retained'
        passed('native dirty-field writes retain disjoint changes;no general conflict protection claimed')
    else:
        target=load(site.private/'target.json');profile=load(site.local/'repair-worker-profile.json')['profile']
        lane,= [l for l in profile['lanes'] if l['pool']=='urgent']
        inspection=json.loads(site.command('outage-inspect',['docker','inspect',lane['container']]))[0]
        assert inspection['Name']=='/'+target['project']+'-job-urgent-1' and inspection['State']['Running']
        assert inspection['Image']==target['image_id']
        record.update(container=lane['container'],image=target['image_id']);step('stopping_exact_urgent_lane')
        site.command('outage-stop',['docker','stop','-t','5',lane['container']]);step('urgent_lane_stopped')
        try:
            due=(datetime.now(timezone.utc)-timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
            step('creating_work_during_outage')
            task,=call(alice,T,'create',[[dict(name='Reminder queued during worker outage',list_id=2,assignee_id=uid('bob'),due_date=due,reminder='0')]])
            record['task']=task;step('queued_while_stopped')
            for _ in range(3):
                assert call(alice,T,'read',[[task],['reminder_status']])[0]['reminder_status']=='queued'
                assert not call(bob,N,'search_count',[[('title','=','Reminder queued during worker outage')]])
                time.sleep(1)
            passed('unexpected lane stop retains dispatch and accepts valid work;no false delivery')
        finally:
            step('restarting_exact_urgent_lane');site.command('outage-start',['docker','start',lane['container']]);step('urgent_lane_restarted')
        for _ in range(45):
            notices=call(bob,N,'search_read',[[('title','=','Reminder queued during worker outage')]],dict(fields=['id','is_read']))
            if notices:break
            time.sleep(1)
        assert len(notices)==1 and not notices[0]['is_read']
        assert call(alice,T,'read',[[task],['reminder_status']])[0]['reminder_status']=='sent'
        time.sleep(2)
        assert call(bob,N,'search_count',[[('title','=','Reminder queued during worker outage')]])==1
        passed('same pinned lane restart produces one persisted recipient effect;business data retained')
    record['phase']='passed';write(path,record);print(json.dumps(dict(result='passed',phase=a.phase,checks=record['checks'])))

if __name__=='__main__':main()
