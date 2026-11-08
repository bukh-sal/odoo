"""A post-checkpoint workspace revocation must survive fresh old-image recovery."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_release_site import ReleaseSite,load,write
from modular_platform.operator_store import OperatorStore


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['revoke','verify'])
    p.add_argument('--run',required=True);p.add_argument('--port',type=int,default=18149)
    a=p.parse_args();a.site='tasks';site=ReleaseSite(a)
    fault=load(site.local/'tasks-fault.json');target=load(site.private/'target.json')
    status=OperatorStore(site.private/'control').status(fault['operation'])
    state=site.state();state.update(database=target['sites'][0]['database'],image_id=target['image_id'])
    fixture=load(site.local/'fixtures.json');bob=fixture['users']['bob']['principal_id'];space=fixture['workspaces']['B']['public_id']
    assert status['state']=='recovery_required' and not status['traffic_resumed']
    path=site.local/('authority-'+a.action+'.json');assert not path.exists()
    if a.action=='revoke':
        assert fault['phase']=='recovery_required' and fault['failed_app_stopped']
        query="BEGIN; UPDATE mp_membership m SET state='revoked' FROM mp_principal p,mp_workspace w WHERE m.principal_id=p.id AND m.workspace_id=w.id AND p.public_id='"+bob+"' AND w.public_id='"+space+"' AND m.state='active' RETURNING m.state; UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE public_id='"+space+"'; COMMIT;"
        assert site.sql(state,'post-checkpoint-authority-revoke',query).strip()==b'revoked'
        result=dict(result='revoked_after_checkpoint',operation=fault['operation'],old_checkpoint_had_active_membership=True)
    else:
        assert fault['phase']=='restored_closed' and fault['fresh_database']==state['database']
        raw=site.sql(state,'restored-membership-check',"SELECT m.state FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id JOIN mp_workspace w ON w.id=m.workspace_id WHERE p.public_id='"+bob+"' AND w.public_id='"+space+"';")
        assert raw.strip()==b'revoked'
        code='FIXTURE='+repr(fixture)+'\nAPP='+repr(load(site.local/'app-fixtures.json'))+'\n'+'''
import json
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
actor=api.Environment(env.cr,FIXTURE['users']['bob']['id'],{},su=False)
try:scoped_environment(actor,FIXTURE['workspaces']['B']['public_id'])
except AccessError:pass
else:raise AssertionError('Restore reinstated revoked workspace membership')
assert actor['mp.aurora.task'].browse(APP['completed_task']).read(['name'])[0]['name']=='Original47 completed task'
assert actor['mp.aurora.task.list'].browse(APP['completed_list']).read(['name'])
env.cr.rollback()
print('MP_AT_AUTHORITY='+json.dumps(dict(workspace_denied=True,native_owner_authority_preserved=True)))
'''
        raw=site.native(state,'restored-authority-native-check',[],code)
        result,=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_AUTHORITY=')]
        result.update(result='verified',fresh_database=True,traffic_closed=True)
    write(path,result);write(site.local/'state.json',state)
    print(json.dumps(dict(action=a.action,result=result['result'])))


if __name__=='__main__':main()
