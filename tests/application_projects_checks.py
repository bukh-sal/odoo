"""Actual native Projects contract on an independently installed synthetic site."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from application_adoption_site import AdoptionSite,load,write
from check_reference import Client


def denied(client,method,args,*,kind='AccessError'):
    status,value=client.request('/web/dataset/call_kw/mp.aurora.project.'+method,
        dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.aurora.project',method=method,args=args,kwargs={})))
    assert status==200 and value.get('error',{}).get('data',{}).get('name')=='odoo.exceptions.'+kind,value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',default='ap03-projects-only-01');p.add_argument('--port',type=int,default=18174);a=p.parse_args()
    site=AdoptionSite(a);state=site.state();assert state['phase']=='native_installed'
    path=site.local/'project-contract.json';assert not path.exists(),'Inspect the last committed step before continuation'
    record=dict(phase='authenticating',checks=[]);write(path,record)
    def step(name):record['phase']=name;write(path,record)
    def passed(name):record['checks'].append(name);write(path,record)
    clients={n:Client(site,n) for n in ('alice','bob','operator','worker')};users=load(site.local/'fixtures.json')['users']
    alice,bob,manager,outsider=[clients[n] for n in ('alice','bob','operator','worker')]
    uid=lambda n:users[n]['id']
    def call(c,method,args=None,kwargs=None):return c.native('mp.aurora.project',method,args,kwargs,workspace=None)
    assert call(alice,'search_count',[[]])==0
    assert call(alice,'default_get',[['owner_id','manager_id']])==dict(owner_id=uid('alice'),manager_id=uid('alice'))
    views=call(alice,'get_views',kwargs=dict(views=[(False,'list'),(False,'form'),(False,'search')],options={}))
    assert all('<'+kind in views['views'][kind]['arch'] for kind in ('list','form','search'))
    passed('actual new-form defaults/current owner+manager and native list/form/search descriptors')
    step('creating_shared_project')
    project,=call(alice,'create',[[dict(name='  Pump inspection  ',description='Fictional scheduled inspection project',owner_id=uid('bob'),
        manager_id=uid('operator'),member_ids=[(6,0,[uid('bob')])])]])
    record['project']=project;write(path,record)
    fields=['name','description','owner_id','manager_id','member_ids','status','active','can_edit','can_own']
    row=call(alice,'read',[[project],fields])[0]
    assert row['name']=='Pump inspection' and row['owner_id'][0]==uid('alice') and row['status']=='planned' and row['can_edit'] and row['can_own']
    assert call(manager,'read',[[project],['can_edit','can_own']])[0]==dict(id=project,can_edit=True,can_own=False)
    assert call(bob,'read',[[project],['can_edit','can_own']])[0]==dict(id=project,can_edit=False,can_own=False)
    assert call(outsider,'search_count',[[]])==0
    denied(outsider,'read',[[project],['name']]);denied(outsider,'write',[[project],dict(description='foreign')])
    for actor,values in [(bob,dict(description='member mutation')),(bob,dict(member_ids=[(5,)])),(bob,dict(active=False)),
                         (manager,dict(manager_id=uid('bob'))),(alice,dict(owner_id=uid('bob'))),(alice,dict(can_edit=True))]:
        denied(actor,'write',[[project],values])
    denied(bob,'action_activate',[[project]]);denied(manager,'unlink',[[project]])
    passed('owner/manager/member distinct permissions;forged owner clobbered;10 direct outsider/member/immutable-role denials')
    step('manager_lifecycle')
    for method,expected in [('action_activate','active'),('action_activate','active'),('action_hold','on_hold')]:
        assert call(manager,method,[[project]]) and call(alice,'read',[[project],['status']])[0]['status']==expected
    denied(manager,'action_complete',[[project]],kind='ValidationError')
    for method,expected in [('action_activate','active'),('action_complete','completed'),('action_reopen','planned'),('action_cancel','cancelled'),('action_reopen','planned')]:
        assert call(manager,method,[[project]]) and call(alice,'read',[[project],['status']])[0]['status']==expected
    denied(alice,'write',[[project],dict(status='completed')],kind='ValidationError')
    passed('real locked lifecycle/harmless repetition/direct invalid transition refusal;ends planned')
    step('manager_changes_membership')
    assert call(manager,'write',[[project],dict(description='Manager confirmed the inspection plan',member_ids=[(5,)])])
    denied(bob,'read',[[project],['name']])
    assert call(alice,'write',[[project],dict(member_ids=[(6,0,[uid('bob')])])])
    assert call(bob,'read',[[project],['can_edit']])[0]['can_edit'] is False
    step('owner_transfers_manager')
    assert call(alice,'write',[[project],dict(manager_id=uid('alice'))]);denied(manager,'read',[[project],['name']])
    assert call(alice,'write',[[project],dict(manager_id=uid('operator'))])
    assert call(manager,'read',[[project],['can_edit']])[0]['can_edit']
    passed('current membership/manager revocation affects existing authenticated sessions;owner restores useful roles')
    step('role_validation')
    public=int(site.sql(state,'public-user-id',"SELECT res_id FROM ir_model_data WHERE module='base' AND name='public_user' AND model='res.users';").strip())
    denied(alice,'write',[[project],dict(member_ids=[(6,0,[public])])],kind='ValidationError')
    denied(alice,'write',[[project],dict(manager_id=public)],kind='ValidationError')
    denied(alice,'write',[[project],dict(name=' '*3)],kind='ValidationError')
    denied(alice,'write',[[project],dict(name='x'*129)],kind='ValidationError')
    passed('portal membership/manager and empty/oversize names refused without changing useful record')
    step('archive_roundtrip')
    assert call(manager,'write',[[project],dict(active=False)])
    assert call(alice,'search_count',[[]])==0 and call(bob,'read',[[project],['active']])[0]['active'] is False
    assert call(alice,'write',[[project],dict(active=True)])
    passed('manager archives/default list hides;authorized member historical read;owner unarchives')
    step('creating_foreign_owner')
    foreign,=call(outsider,'create',[[dict(name='Independent private project',owner_id=uid('alice'))]])
    record['foreign']=foreign;write(path,record)
    assert call(outsider,'read',[[foreign],['owner_id']])[0]['owner_id'][0]==uid('worker')
    denied(alice,'read',[[foreign],['name']])
    before=call(alice,'read',[[project],fields])
    denied(alice,'write',[[project,foreign],dict(name='Mixed unauthorized bulk mutation')])
    assert call(alice,'read',[[project],fields])==before
    assert call(alice,'search_count',[[]])==call(bob,'search_count',[[]])==call(manager,'search_count',[[]])==call(outsider,'search_count',[[]])==1
    passed('independent own-project create;other owner remains private;unauthorized mixed bulk is atomic')
    step('owner_only_delete')
    disposable,=call(alice,'create',[[dict(name='Owned delete witness',manager_id=uid('bob'))]])
    record['deleted']=disposable;write(path,record)
    denied(bob,'unlink',[[disposable]]);assert call(alice,'unlink',[[disposable]])
    passed('manager cannot delete;owner deletes own disposable business record through native authority')
    assert site.sql(state,'projects-independent-app',"SELECT count(*) FROM mp_plugin_installation WHERE plugin_id IN ('dev.aurora.tasks','dev.aurora.projects_tasks');").strip()==b'0'
    assert site.sql(state,'tasks-table-absent',"SELECT to_regclass('mp_aurora_task') IS NULL;").strip()==b't'
    passed('useful Projects installation without Tasks/extension metadata,Task tables or workspace authority')
    record.update(phase='passed',rows=call(alice,'read',[[project],fields]));write(path,record)
    print(json.dumps(dict(result='passed',checks=len(record['checks']),project=project)),flush=True)

if __name__=='__main__':main()
