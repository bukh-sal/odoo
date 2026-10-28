"""Real R1 HTTP/native boundary checks against a known disposable site."""
import http.cookiejar
import json
import urllib.request
import urllib.error
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import r1


class Client:
    def __init__(self,state,fixture,actor='alice'):
        self.state=state;self.fixture=fixture;self.base=f"http://127.0.0.1:{state['port']}"
        self.jar=http.cookiejar.CookieJar();self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(self.jar))
        status,result=self.request('/web/session/authenticate',{'jsonrpc':'2.0','method':'call','id':1,'params':{'db':state['active_db'],'login':fixture['users'][actor]['login'],'password':(r1.r0.LOCAL/'bootstrap-password').read_text().strip()}})
        assert status==200 and result.get('result',{}).get('uid')==fixture['users'][actor]['id'],('Fixture authentication failed',status,result.get('error',{}).get('code'))
        self.csrf=self.request('/api/v1/session')[1]['data']['csrf_token']

    def request(self,path,payload=None,workspace=None,headers=None):
        headers=dict(headers or {})
        if workspace:headers['X-MP-Workspace']=self.fixture['workspaces'].get(workspace,{}).get('public_id',workspace)
        if payload is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.base+path,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
        try:response=self.http.open(request,timeout=30)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read()
            try:value=json.loads(raw)
            except ValueError:value={'non_json_status':response.code}
            return response.code,value

    def call(self,method,values,workspace='A',key=None,expect=200,code=None,headers=None):
        extra={'X-CSRFToken':self.csrf,'X-MP-Binding':self.fixture['bindings'][workspace]['binding_id'],**(headers or {})}
        body={'api_version':'1.0','request_id':'probe-'+uuid4().hex,'input':values}
        if key:body['idempotency_key']=key
        status,result=self.request('/api/v1/services/org.example.notes.documents/'+method,body,workspace,extra)
        assert status==expect,(method,status,result)
        if code:assert result.get('error',{}).get('code')==code,(method,result)
        else:assert 'data' in result,(method,result)
        return result.get('data',result)

    def native(self,method,args=None,kwargs=None,workspace='A',deny=False,model='mp.example.note'):
        status,result=self.request('/web/dataset/call_kw/'+model+'.'+method,{'jsonrpc':'2.0','method':'call','id':1,'params':{'model':model,'method':method,'args':args or [],'kwargs':kwargs or {}}},workspace)
        if deny:
            assert status==200 and result.get('error',{}).get('data',{}).get('name')=='odoo.exceptions.AccessError',(method,status,result)
            return result
        assert status==200 and 'result' in result,(method,status,result)
        return result['result']


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text());assert fixture['database']==state['active_db']
    client=Client(state,fixture);checks=[];out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-notes-api.json')
    def passed(name):
        checks.append({'name':name,'result':'passed'});out.write_text(json.dumps({'state':'in_progress','checks':checks},indent=2)+'\n')
    try:
        for workspace,role in [('A','editor'),('B','viewer')]:
            status,data=client.request('/api/v1/context?plugin_id=org.example.notes',workspace=workspace)
            assert status==200 and data['data']['context']['workspace_id']==fixture['workspaces'][workspace]['public_id']
            assert ('org.example.notes:notes.write' in data['data']['context']['capabilities'])==(role=='editor')
            visible={r['id'] for r in client.call('list',{'limit':25},workspace)['items']}
            assert fixture['objects'][workspace]['public_id'] in visible
            assert fixture['objects']['B' if workspace=='A' else 'A']['public_id'] not in visible
        passed('generic contexts and Notes search stay in explicit asymmetric workspaces')
        for method,values in [('create',{'title':'Denied','body':''}),('update',{'note_id':fixture['objects']['B']['public_id'],'expected_revision':1,'title':'Denied'}),('delete',{'note_id':fixture['objects']['B']['public_id'],'expected_revision':1})]:
            client.call(method,values,'B',expect=403,code='FORBIDDEN',headers={'X-MP-Consumer':'org.modularplatform.operator','X-MP-Actor':'administrator'})
        passed('viewer create/update/delete denied despite forged browser attribution')
        for ident in [fixture['objects']['B']['public_id'],str(uuid4())]:client.call('get',{'note_id':ident},expect=404,code='NOT_FOUND')
        passed('foreign and nonexistent public IDs have identical not-found policy')
        bob=Client(state,fixture,'bob')
        bob.call('get',{'note_id':fixture['objects']['A']['public_id']},workspace='B',expect=404,code='NOT_FOUND')
        for method in ['update','delete']:
            values={'note_id':fixture['objects']['A']['public_id'],'expected_revision':1}
            if method=='update':values['title']='Must not cross workspace'
            bob.call(method,values,workspace='B',expect=404,code='NOT_FOUND')
        for method,args in [('read',[[fixture['objects']['A']['id']],['title']]),('write',[[fixture['objects']['A']['id']],{'title':'Denied'}]),('unlink',[[fixture['objects']['A']['id']]]),('create',[{'workspace_id':fixture['workspaces']['A']['id'],'title':'Denied','body':''}])]:
            bob.native(method,args,workspace='B',deny=True)
        legitimate=bob.call('create',{'title':'Bob scoped CRUD proof','body':'Synthetic'},workspace='B')
        bob.call('delete',{'note_id':legitimate['id'],'expected_revision':1},workspace='B')
        passed('independent editor in B cannot read mutate delete or create into A; legitimate B CRUD works')
        client.call('sudo',{},expect=404,code='NOT_FOUND')
        client.call('create',{'title':'Bad','body':'','actor_id':'administrator'},expect=400,code='VALIDATION_FAILED')
        passed('only registered methods and strict method schemas dispatch')
        key='crud-'+uuid4().hex;created=client.call('create',{'title':'Probe note','body':'Private'},key=key)
        assert client.call('create',{'title':'Probe note','body':'Private'},key=key)==created
        client.call('create',{'title':'Different','body':'Private'},key=key,expect=409,code='CONFLICT')
        updated=client.call('update',{'note_id':created['id'],'expected_revision':1,'title':'Updated'},key='update-'+uuid4().hex)
        assert updated['revision']==2 and updated['body']=='Private'
        client.call('update',{'note_id':created['id'],'expected_revision':1,'title':'Stale'},expect=409,code='CONFLICT')
        client.call('delete',{'note_id':created['id'],'expected_revision':2},key='delete-'+uuid4().hex)
        passed('create/update/delete revision CAS and saved idempotency outcome work')
        key='concurrent-'+uuid4().hex
        clients=[Client(state,fixture) for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes=list(pool.map(lambda c:c.call('create',{'title':'Concurrent proof '+key,'body':'One effect'},key=key),clients))
        assert len({value['id'] for value in outcomes})==1
        assert client.native('search_count',[[('title','=','Concurrent proof '+key)]])==1
        client.call('delete',{'note_id':outcomes[0]['id'],'expected_revision':1})
        passed('eight concurrent same-key requests produce one committed effect/result')
        for workspace in ['A','B']:
            rows=client.native('search_read',[[]],{'fields':['public_id','title','revision','workspace_id']},workspace)
            assert fixture['objects'][workspace]['public_id'] in [r['public_id'] for r in rows]
            assert all(r['workspace_id'][0]==fixture['workspaces'][workspace]['id'] for r in rows)
        client.native('read',[[fixture['objects']['B']['id']],['title']],workspace='A',deny=True)
        client.native('write',[[fixture['objects']['B']['id']],{'title':'Denied'}],workspace='B',deny=True)
        client.native('create',[{'workspace_id':fixture['workspaces']['B']['id'],'title':'Wrong','body':''}],deny=True)
        client.native('search_read',[[]],{'context':{'mp_workspace_id':fixture['workspaces']['B']['id']}},deny=True)
        passed('retained native RPC cannot bypass owner viewer or forged-context guards')
        client.native('create',[{'name':'Forbidden public attachment','res_model':'mp.example.note','res_id':fixture['objects']['A']['id'],'public':True,'datas':'cHJpdmF0ZQ=='}],model='ir.attachment',deny=True)
        passed('excluded workspace attachment feature cannot be enabled through legacy public attachments')
        client.call('create',{'title':'Never created','body':''},expect=504,code='DEADLINE_EXCEEDED',headers={'X-MP-Deadline-Ms':'0'})
        passed('pre-dispatch deadline reports not-started without false rollback claim')
        result={'state':'passed','scope':'initial G3 backend subset; remaining G3/browser/fault acceptance open','checks':checks};out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'state':'passed','checks':len(checks),'evidence':str(out.relative_to(r1.r0.ROOT))}))
    except Exception:
        out.write_text(json.dumps({'state':'failed','checks':checks,'next':'inspect concrete failure; do not mark G3 passed'},indent=2)+'\n');raise


if __name__=='__main__':main()
