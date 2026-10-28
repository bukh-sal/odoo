"""Real packaged composition, named-major bindings, board/extension authority."""
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import r1
from r1_probe import Client


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text());g4=json.loads((r1.r0.LOCAL/'g4-fixtures.json').read_text())
    assert state.get('g4_install_status')=='provisioned' and fixture['database']==g4['database']==state['active_db']
    alice=Client(state,fixture);checks=[];note=None;out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-composition-api.json')
    def save(status):out.write_text(json.dumps({'state':status,'checks':checks},indent=2)+'\n')
    def passed(name,**extra):checks.append({'name':name,'result':'passed',**extra});save('in_progress')
    def call(client,plugin,alias,method,values,workspace='A',key=None,expect=200,code=None,headers=None,version=None):
        binding=g4['bindings']['Personal' if workspace=='A' else 'Research']['org.example.'+plugin][alias]
        payload={'api_version':version or binding['api_version'],'request_id':uuid4().hex,'input':values}
        if key:payload['idempotency_key']=key
        status,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id'],**(headers or {})})
        assert status==expect,(plugin,method,status,value)
        if code:assert value.get('error',{}).get('code')==code,(plugin,method,value)
        else:assert 'data' in value,(plugin,method,value)
        return value.get('data',value)
    def policy(code,label):return r1.shell(state,label,f"assert env.cr.dbname=={state['active_db']!r}\n"+code+'\nenv.cr.commit()\nenv.registry.signal_changes()\n')
    try:
        ident=fixture['objects']['A']['public_id']
        v1=call(alice,'notes','documents','get',{'note_id':ident})
        v2=call(alice,'canvas','documents','get',{'document_id':ident})
        assert v2['document_id']==v1['id'] and v2['content']=={'headline':v1['title'],'text':v1['body']} and 'id' not in v2
        call(alice,'canvas','documents','get',{'note_id':ident},expect=400,code='VALIDATION_FAILED')
        call(alice,'canvas','documents','get',{'document_id':ident},version='1.0',expect=400,code='VALIDATION_FAILED')
        call(alice,'canvas','documents','update',{},expect=404,code='NOT_FOUND')
        call(alice,'canvas','documents','get',{'document_id':ident},headers={'X-MP-Binding':str(uuid4())},expect=503,code='DEPENDENCY_UNAVAILABLE')
        passed('documents1.0 and2.0 coexist through distinct consumer aliases; invalid DTO/major/binding never choose latest')
        note=alice.call('create',{'title':'G4 extension authority proof','body':'Base content retained'})
        key='labels-'+uuid4().hex;values={'note_id':note['id'],'expected_revision':1,'labels':['Scoped','Native extension']}
        labeled=call(alice,'notes_labels','labels','set_labels',values,key=key)
        assert labeled['revision']==2 and labeled['body']==note['body'] and labeled['labels']==values['labels']
        assert call(alice,'notes_labels','labels','set_labels',values,key=key)==labeled
        call(alice,'notes_labels','labels','set_labels',{'note_id':fixture['objects']['B']['public_id'],'expected_revision':1,'labels':['Denied']},workspace='B',expect=403,code='FORBIDDEN',headers={'X-MP-Consumer':'administrator','X-MP-Actor':'root'})
        alice.native('write',[[fixture['objects']['B']['id']],{'x_notes_labels':['Denied']}],{'context':{'expected_revision':1}},workspace='B',deny=True)
        alice.native('search_read',[[]],{'context':{'_mp_call_frame':{'principal_id':'administrator'}}},deny=True)
        passed('Labels command uses actor-preserving base1.0 call; revision/idempotency and forged-frame/viewer denial hold')
        installation=g4['installations']['org.example.notes_labels'];wid=fixture['workspaces']['A']['id']
        grant=f"row=env['mp.plugin.grant'].search([('installation_id.public_id','=',{installation!r}),('workspace_id','=',{wid!r}),('capability','=','org.example.notes:notes.read')]);assert len(row)==1\n"
        try:
            policy(grant+"row.write({'state':'revoked'})",'g4-revoke-nested-grant')
            call(alice,'notes_labels','labels','set_labels',{'note_id':note['id'],'expected_revision':2,'labels':['Denied']},expect=403,code='FORBIDDEN')
            assert alice.call('get',{'note_id':note['id']})==labeled
        finally:policy(grant+"row.write({'state':'approved'})",'g4-restore-nested-grant')
        passed('revoked integration grant prevents supported nested dispatch without changing actor or effect')
        a=call(alice,'canvas','boards','get',{});b=call(alice,'canvas','boards','get',{},workspace='B')
        assert a['id']==g4['boards']['Personal']['id'] and b['id']==g4['boards']['Research']['id'] and a['id']!=b['id']
        call(alice,'canvas','boards','get',{'board_id':b['id']},expect=404,code='NOT_FOUND')
        call(alice,'canvas','boards','save',{'board_id':b['id'],'expected_revision':b['revision'],'name':b['name'],'cards':b['cards']},workspace='B',expect=403,code='FORBIDDEN')
        saved=call(alice,'canvas','boards','save',{'board_id':a['id'],'expected_revision':a['revision'],'name':a['name'],'cards':a['cards']},key='board-'+uuid4().hex)
        call(alice,'canvas','boards','save',{'board_id':a['id'],'expected_revision':a['revision'],'name':a['name'],'cards':a['cards']},expect=409,code='CONFLICT')
        foreign=[{**a['cards'][0],'note_id':fixture['objects']['B']['public_id']}]
        call(alice,'canvas','boards','save',{'board_id':a['id'],'expected_revision':saved['revision'],'name':a['name'],'cards':foreign},expect=404,code='NOT_FOUND')
        duplicate=[saved['cards'][0],{**saved['cards'][0],'text':'Different text same ID'}]
        call(alice,'canvas','boards','save',{'board_id':a['id'],'expected_revision':saved['revision'],'name':a['name'],'cards':duplicate},expect=400,code='VALIDATION_FAILED')
        assert call(alice,'canvas','boards','get',{})==saved
        passed('board persistence/CAS rejects cross-workspace references, duplicate card IDs, viewers and stale revisions atomically')
        clients=[Client(state,fixture) for _ in range(8)];key='parallel-board-'+uuid4().hex
        values={'board_id':saved['id'],'expected_revision':saved['revision'],'name':saved['name'],'cards':saved['cards']}
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda c:call(c,'canvas','boards','save',values,key=key),clients))
        assert all(value==results[0] for value in results) and results[0]['revision']==saved['revision']+1
        passed('eight concurrent same-key board saves produce one revision/effect')
        feature=f"row=env['mp.workspace.plugin'].search([('workspace_id','=',{wid!r}),('plugin_id','=','org.example.notes_labels')]);assert len(row)==1\n"
        try:
            policy(feature+"row.write({'availability':'suspended'})",'g4-suspend-labels')
            call(alice,'notes_labels','labels','set_labels',{'note_id':note['id'],'expected_revision':2,'labels':['Denied']},expect=409,code='PLUGIN_SUSPENDED')
            native=alice.native('search_read',[[('public_id','=',note['id'])]],{'fields':['id','title']})[0]
            alice.native('read',[[native['id']],['x_notes_labels']],deny=True)
            base=alice.call('get',{'note_id':note['id']});assert base['body']==note['body'] and base['labels']==[]
            status,slot=alice.request('/api/v1/ui/slot?slot_id=org.example.notes:slot:detail_actions&major=1',workspace='A');assert status==200 and slot['data']==[]
        finally:policy(feature+"row.write({'availability':'enabled'})",'g4-resume-labels')
        assert alice.call('get',{'note_id':note['id']})['labels']==labeled['labels']
        passed('suspended Labels retains native field/data but denies extension entry points and omits its action/content')
        save('passed');print(json.dumps({'result':'passed','checks':len(checks),'evidence':str(out.relative_to(r1.r0.ROOT))}))
    except Exception:save('failed');raise
    finally:
        if note:
            current=alice.call('get',{'note_id':note['id']});alice.call('delete',{'note_id':note['id'],'expected_revision':current['revision']})


if __name__=='__main__':main()
