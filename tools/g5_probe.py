"""Real HTTP/native role fences for the separate core-only G5 site."""
import json
from pathlib import Path
import sys
from uuid import uuid4

import r1_probe
import r1
r1.r0.LOCAL=r1.r0.ROOT/'.local/g5'
sys.path.insert(0,str(r1.r0.ROOT/'packages/platform_sdk'))
from modular_platform.contracts import validate_operations_view


def main():
    local=r1.r0.LOCAL;state=json.loads((local/'state.json').read_text());fixture=json.loads((local/'fixtures.json').read_text())
    assert state['profile']=='G5' and state['install_status']=='seeded_core'
    clients={actor:r1_probe.Client(state,fixture,actor) for actor in ['operator','alice','bob','worker']}
    checks=[]
    status,context=clients['operator'].request('/api/v1/operations/context');assert status==200
    context=validate_operations_view(context['data']);assert context['can_request'] and len(context['workspaces'])==2
    checks.append('explicit human application operator can read two workspace metadata rows')
    status,catalog=clients['operator'].request('/api/v1/operations/catalog');assert status==200
    catalog=validate_operations_view(catalog['data']);assert len(catalog['items'])==6
    assert all(item['signature_verified'] is False for item in catalog['items'])
    checks.append('real sanitized six-artifact catalog validates with no signature claim')
    body={'schema_version':1,'operation':'prepare','operation_type':'suspend','plugin_id':'org.example.notes',
          'site_id':fixture['site_id'],'workspace_ids':[fixture['workspaces']['A']['public_id']],'cascade':False}
    for actor in ['alice','bob','worker']:
        client=clients[actor];status,value=client.request('/api/v1/operations/context');assert status==200 and value['data']['can_request'] is False and 'workspaces' not in value['data']
        assert client.request('/api/v1/operations/catalog')[0]==403
        assert client.request('/api/v1/operations/prepare',body,headers={'X-CSRFToken':client.csrf})[0]==403
        assert client.request('/api/v1/operations/status/'+str(uuid4()))[0]==403
    checks.append('workspace administrator/editor/technical browser principals cannot request/view operations')
    operator=clients['operator']
    assert operator.request('/api/v1/operations/prepare',body)[0]==403
    for extra in [{'approved':True},{'command':'do not execute'},{'operator_id':str(uuid4())}]:
        assert operator.request('/api/v1/operations/prepare',{**body,**extra},headers={'X-CSRFToken':operator.csrf})[0]==400
    assert operator.request('/api/v1/operations/prepare',{**body,'site_id':str(uuid4())},headers={'X-CSRFToken':operator.csrf})[0]==403
    assert operator.request('/api/v1/operations/prepare',{**body,'site_id':fixture['site_id']+'\n'},headers={'X-CSRFToken':operator.csrf})[0]==400
    checks.append('real CSRF/authority-key/site-override/terminal-newline fences before preparation')
    for model in ['mp.application.operator','mp.operation.profile','mp.operation.request']:
        status,response=operator.request('/web/dataset/call_kw/'+model+'/search_read',{'jsonrpc':'2.0','method':'call','id':1,
            'params':{'model':model,'method':'search_read','args':[],'kwargs':{'fields':['id'],'limit':1,'context':{}}}})
        assert response.get('error') and response['error']['data']['name']=='odoo.exceptions.AccessError',(model,status,response.get('error',{}).get('code'))
        assert 'debug' not in response['error']['data']
    checks.append('application operator has no generic native RPC read/write grant on control metadata models')
    # Current native installation footprint is intentionally empty; execution is
    # still pending, so a feature nomination cannot fabricate an installation.
    assert operator.request('/api/v1/operations/prepare',body,headers={'X-CSRFToken':operator.csrf})[0]==404
    checks.append('core-only site does not fabricate an installed Notes feature')
    output=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-operator-http.json')
    output.write_text(json.dumps({'result':'passed','checks':checks,'count':len(checks),
        'limitations':['No installed reference plugins or native apply yet; successful prepare/request/status comes with E-01d.']},indent=2)+'\n')
    print(json.dumps({'result':'passed','groups':len(checks),'evidence':str(output)}))


if __name__=='__main__':main()
