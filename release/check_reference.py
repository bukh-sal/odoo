"""Once-only minimal backend walkthrough of a new kit reference installation."""
from __future__ import annotations
import argparse,http.cookiejar,json,sys,urllib.error,urllib.request
from pathlib import Path
from uuid import uuid4
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from initialize_reference import Reference,load,write
from modular_platform.contracts import validate

class Client:
    def __init__(self,reference,actor):
        self.reference=reference;self.fixture=load(reference.local/'fixtures.json');self.state=reference.state()
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        passwords=load(reference.local/'account-passwords.json');self.token=None
        status,value=self.request('/web/session/authenticate',dict(jsonrpc='2.0',method='call',id=1,params=dict(db=self.state['database'],login=self.fixture['users'][actor]['login'],password=passwords[actor])))
        assert status==200 and value.get('result',{}).get('uid')==self.fixture['users'][actor]['id'],'Reference login failed'
        status,value=self.request('/api/v1/session');assert status==200;self.csrf=value['data']['csrf_token']
        status,value=self.request('/api/v1/client-release');assert status==200;validate('client-release',value['data']);self.token=value['data']['token']
    def request(self,path,payload=None,workspace=None,headers=None):
        headers=dict(headers or {})
        if self.token:headers['X-MP-Client-Release']=self.token
        if workspace:headers['X-MP-Workspace']=self.fixture['workspaces'][workspace]['public_id']
        if payload is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.state['url']+path,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
        try:response=self.http.open(request,timeout=30)
        except urllib.error.HTTPError as error:response=error
        with response:return response.status,json.loads(response.read())
    def service(self,plugin,alias,method,values,workspace='A',*,expect=200,key=None):
        document=load(self.reference.local/'installed-state.json');wid=self.fixture['workspaces'][workspace]['public_id']
        installation=next(i['installation_id'] for i in document['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
        binding=next(b for b in document['bindings'] if b['consumer_installation_id']==installation and b['workspace_id']==wid and b['alias']==alias)
        payload=dict(api_version=binding['api_version'],request_id=str(uuid4()),input=values)
        if key:payload['idempotency_key']=key
        status,value=self.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':self.csrf,'X-MP-Binding':binding['binding_id']})
        assert status==expect,'Unexpected reference service status: '+str(status)
        return value['data'] if status==200 else value['error']
    def native(self,model,method,args=None,kwargs=None,workspace='A'):
        status,value=self.request('/web/dataset/call_kw/'+model+'.'+method,dict(jsonrpc='2.0',method='call',id=1,params=dict(model=model,method=method,args=args or [],kwargs=kwargs or {})),workspace)
        assert status==200 and 'result' in value,'Native reference call failed: '+model+'.'+method
        return value['result']

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--kit',type=Path,required=True);parser.add_argument('--workdir',type=Path,required=True);args=parser.parse_args()
    reference=Reference(args);state=reference.state();assert state['phase']=='references_installed'
    marker=reference.local/'reference-checks.json'
    if marker.exists():raise ValueError('Walkthrough attempted; inspect saved step and actual effects before continuation')
    record=dict(phase='authenticating',run_id=str(uuid4()),checks=[],notes={});write(marker,record)
    def step(name):record['phase']=name;write(marker,record)
    def passed(name):record['checks'].append(name);write(marker,record)
    alice=Client(reference,'alice');bob=Client(reference,'bob');passed('fresh distinct-credential human sessions and current client release')
    for workspace,client in [('A',alice),('B',bob)]:
        assert client.native('mp.example.note','search_count',[[]],workspace=workspace)==0
        step('creating_one_reference_note_'+workspace)
        note=client.service('org.example.notes','documents','create',dict(title='Release reference '+workspace,body='Minimal backend qualification.'),workspace,key=record['run_id']+'-note-'+workspace)
        record['notes'][workspace]=note;write(marker,record)
        views=client.native('mp.example.note','get_views',kwargs=dict(views=[(False,'list'),(False,'form')],options={}),workspace=workspace)
        assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
        rows=client.native('mp.example.note','search_read',[[]],dict(fields=['public_id','workspace_id']),workspace)
        assert len(rows)==1 and rows[0]['public_id']==note['id'] and rows[0]['workspace_id'][0]==client.fixture['workspaces'][workspace]['id']
    passed('one scoped Note in each workspace; native Odoo list/form descriptors and scoped record reads')
    step('checking_asymmetric_permissions')
    denied=alice.service('org.example.notes','documents','create',dict(title='Denied',body=''),'B',expect=403)
    assert denied['code']=='FORBIDDEN'
    denied=bob.service('org.example.notes','documents','get',dict(note_id=record['notes']['A']['id']),'B',expect=404)
    assert denied['code']=='NOT_FOUND';passed('Alice viewer write denied in B; Bob cannot read A record')
    step('applying_reference_labels')
    labeled=alice.service('org.example.notes_labels','labels','set_labels',dict(note_id=record['notes']['A']['id'],expected_revision=record['notes']['A']['revision'],labels=['reference']),'A',key=record['run_id']+'-labels')
    assert labeled['labels']==['reference'];record['notes']['A']=labeled;passed('native Notes Labels extension through its registered binding')
    assert alice.native('mp.example.canvas.board','search_count',[[]])==0
    step('creating_one_reference_board_once')
    board=alice.native('mp.example.canvas.board','create',[dict(name='Release reference board',cards=[dict(id=str(uuid4()),text='Minimal reference card',lane='inbox',note_id=record['notes']['A']['id'])])])
    record['board_native_id']=board;write(marker,record)
    current=alice.native('mp.example.canvas.board','read',[[board],['public_id','revision','cards']])[0]
    dto=alice.service('org.example.canvas','boards','get',{})
    assert dto['id']==current['public_id'] and len(dto['cards'])==1;passed('minimal optional Canvas reference uses native creation and registered custom-page service')
    record.update(phase='passed',limits=['Backend HTTP/native descriptors only; no browser rendering, accessibility, worker, performance or full G7 claim.'])
    write(marker,record);reference.phase(state,'minimal_backend_reference_qualified');print(json.dumps(dict(result='passed',checks=len(record['checks']),notes=2,boards=1)))

if __name__=='__main__':main()
