"""Retained native transports and public error/size boundaries on disposable R1."""
import http.client
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import r1
from r1_probe import Client


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text())
    assert fixture['database']==state['active_db'] and state['active_db'].startswith('mp_disposable_r0_r1_')
    client=Client(state,fixture);checks=[];created=[];policy_changed=False;export_group_added=False
    broad_rule_name='R1 disposable broad rule '+uuid4().hex
    broad_domain="[(1, '=', 1)]"
    out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-retained-boundaries.json')
    def save(status):out.write_text(json.dumps({'state':status,'checks':checks},indent=2)+'\n')
    def passed(name,**evidence):checks.append({'name':name,'result':'passed',**evidence});save('in_progress')
    def policy(code,label):
        return r1.shell(state,label,f"assert env.cr.dbname == {state['active_db']!r}\n"+code+'\nenv.cr.commit()\nenv.registry.signal_changes()\n')
    try:
        policy(f"actor=env['res.users'].browse({fixture['users']['alice']['id']!r})\nassert actor.login=='r1_alice'\ngroup=env.ref('base.group_allow_export')\nassert group not in actor.group_ids\nactor.write({{'group_ids':[(4,group.id)]}})",'r1-boundary-export-authority');export_group_added=True
        policy(f"model=env['ir.model']._get('mp.example.note')\nassert env['ir.rule'].search_count([('model_id','=',model.id),('global','=',True)])\nenv['ir.rule'].create({{'name':{broad_rule_name!r},'model_id':model.id,'groups':[(6,0,env.ref('base.group_user').ids)],'domain_force':{broad_domain!r}}})",'r1-boundary-broad-group-rule')
        a=fixture['objects']['A']['id'];b=fixture['objects']['B']['id']
        own=client.native('read',[[a],['title','body','revision']])[0]
        for method,args,kwargs in [
            ('read',[[a,b],['title']],{}),('export_data',[[a,b],['title','body']],{}),
            ('write',[[a,b],{'title':'Must not change'}],{'context':{'expected_revision':own['revision']}}),
            ('unlink',[[a,b]],{}),('read',[[b],['title']],{'context':{'uid':1,'su':True,'allowed_company_ids':[1],'force_company':1}}),
        ]:client.native(method,args,kwargs,deny=True)
        assert client.native('read',[[a],['title','body','revision']])[0]==own
        assert client.native('name_search',['', [['id','=',b]]])==[]
        groups=client.native('read_group',[[],['id:count'],['workspace_id']])
        assert groups and all(row['workspace_id'][0]==fixture['workspaces']['A']['id'] for row in groups)
        exported=client.native('export_data',[[a],['title','body']])
        assert exported['datas']==[[own['title'],own['body']]]
        passed('mixed read/write/delete/export reject atomically; autocomplete and aggregates constrain ownership')
        for context in [{'uid':1,'su':True,'allowed_company_ids':[1],'force_company':1},{'mp_workspace_id':fixture['workspaces']['A']['id']},{'_mp_scope':{'role':'administrator'}}]:
            client.native('write',[[b],{'title':'Denied'}],{'context':context},workspace='B',deny=True)
        for selection in [None,str(uuid4()),fixture['workspaces']['A']['public_id'].upper()]:
            client.native('search_read',[[]],{'fields':['title']},workspace=selection,deny=True)
        passed('missing/unknown/noncanonical workspace and forged uid/sudo/company/private scope do not grant access')
        result=client.native('load',[['title','body','workspace_id/.id'],[['Unsafe import','Denied',str(fixture['workspaces']['B']['id'])]]])
        assert not result['ids'] and result['messages']
        assert client.native('search_count',[[('title','=','Unsafe import')]])==0
        result=client.native('load',[['title','body'],[['Viewer import','Denied']]],workspace='B')
        assert not result['ids'] and result['messages']
        created_note=client.native('create',[[{'title':'Native import/export probe','body':'Synthetic'}]])[0];created.append(created_note)
        good=client.native('load',[['.id','title'],[[str(created_note),'Imported safely']]],{'context':{'expected_revision':1}})
        assert good['ids']==[created_note],good
        row=client.native('read',[[created_note],['workspace_id','title','revision']])[0]
        assert row['workspace_id'][0]==fixture['workspaces']['A']['id'] and row['title']=='Imported safely' and row['revision']==2
        passed('native import uses current actor, ownership and revision checks; safe import/export works')
        denied=client.native('read',[[b],['title']],deny=True)
        data=denied['error']['data']
        assert set(data)=={'name','message','request_id'} and not any(k in data for k in ['debug','arguments','context'])
        path='/api/v1/services/org.example.notes.documents/create'
        headers={'X-CSRFToken':client.csrf,'X-MP-Binding':fixture['bindings']['A']['binding_id']}
        status,value=client.request(path,{'api_version':'1.0','request_id':'csrf-probe','input':{'title':'Denied','body':''}},'A',{'X-MP-Binding':headers['X-MP-Binding']})
        assert status==403 and value['error']['code']=='FORBIDDEN'
        cookie='; '.join(c.name+'='+c.value for c in client.jar)
        def raw(body,chunked=False,content_type='application/json'):
            connection=http.client.HTTPConnection('127.0.0.1',state['port'],timeout=15)
            try:
                h={**headers,'X-MP-Workspace':fixture['workspaces']['A']['public_id'],'Content-Type':content_type,'Cookie':cookie}
                connection.request('POST',path,body=iter([body[:30000],body[30000:]]) if chunked else body,headers=h,encode_chunked=chunked)
                response=connection.getresponse();return response.status,json.loads(response.read())
            finally:connection.close()
        for body,chunked,kind in [(b'{bad',False,'application/json'),(b'{}',False,'text/plain'),(b'{"api_version":"1.0","api_version":"2.0"}',False,'application/json'),(b' '+b'x'*65536,False,'application/json'),(b' '+b'x'*65536,True,'application/json')]:
            status,value=raw(body,chunked,kind)
            assert status==400 and value['error']['code']=='VALIDATION_FAILED',(status,value,chunked)
            assert set(value['error'])=={'code','message','request_id','retryable','details'}
        passed('malformed/duplicate/non-JSON/oversized and chunked bodies produce bounded typed errors; CSRF and native traceback redaction hold')
        # Warm all clients before demotion, then prove both actual HTTP worker PIDs.
        clients=[Client(state,fixture) for _ in range(8)]
        for c in clients:c.native('search_read',[[]],{'fields':['title']})
        policy_changed=True
        log=policy(f"row=env['mp.membership'].browse({fixture['memberships']['aliceA']!r})\nassert row.principal_id.user_id.login=='r1_alice'\nrow.write({{'role':'viewer'}})",'r1-boundary-demote')
        token='scopeproof-'+uuid4().hex
        def denied_write(index):
            c=clients[index%len(clients)]
            body={'jsonrpc':'2.0','method':'call','id':index,'params':{'model':'mp.example.note','method':'write','args':[[a],{'title':'Denied after demotion'}],'kwargs':{'context':{'expected_revision':own['revision']}}}}
            status,value=c.request('/web/dataset/call_kw/mp.example.note/write?proof='+token,body,'A')
            assert status==200 and value['error']['data']['name']=='odoo.exceptions.AccessError'
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(denied_write,range(48)))
        logs=subprocess.run(['docker','logs','--since','2m',state['project']+'-app-1'],capture_output=True,text=True,check=True)
        lines=[line for line in (logs.stdout+logs.stderr).splitlines() if token in line]
        pids=sorted({int(re.search(r'\d{2}:\d{2}:\d{2},\d+\s+(\d+)\s+INFO',line).group(1)) for line in lines})
        assert len(lines)==48 and len(pids)>=2,(len(lines),pids)
        log_path=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-cross-worker-demotion.log');log_path.write_text('\n'.join(lines)+'\n')
        passed('48 cached-client writes denied after committed demotion across both workers',workers=pids,log=log_path.name,policy_log=log.name)
        policy(f"env['mp.membership'].browse({fixture['memberships']['aliceA']!r}).write({{'role':'editor','state':'active'}})",'r1-boundary-restore');policy_changed=False
        # Installation suspension and feature suspension are different retained states.
        for table,column,value,restore in [('mp.workspace.plugin','availability','suspended','enabled'),('mp.plugin.installation','state','suspended','installed')]:
            domain=[('plugin_id','=','org.example.notes')]
            if table=='mp.workspace.plugin':domain.append(('workspace_id','=',fixture['workspaces']['A']['id']))
            code=f"row=env[{table!r}].search({domain!r});assert len(row)==1\nrow.write({{{column!r}:{value!r}}})"
            try:
                policy(code,'r1-boundary-suspend')
                client.native('read',[[a],['title']],deny=True)
                client.call('get',{'note_id':fixture['objects']['A']['public_id']},expect=409 if table=='mp.plugin.installation' else 403,code='PLUGIN_SUSPENDED' if table=='mp.plugin.installation' else 'FORBIDDEN')
            finally:policy(code.replace(repr(value),repr(restore)),'r1-boundary-resume')
            assert client.native('read',[[a],['title','body','revision']])[0]==own
        passed('feature and installation suspension block gateway and retained native reads while retaining data')
        save('passed');print(json.dumps({'result':'passed','checks':len(checks),'evidence':str(out.relative_to(r1.r0.ROOT))}))
    except Exception:
        save('failed');raise
    finally:
        if policy_changed:policy(f"env['mp.membership'].browse({fixture['memberships']['aliceA']!r}).write({{'role':'editor','state':'active'}})",'r1-boundary-final-restore')
        for ident in created:client.native('unlink',[[ident]])
        if export_group_added:policy(f"actor=env['res.users'].browse({fixture['users']['alice']['id']!r})\nassert actor.login=='r1_alice'\nactor.write({{'group_ids':[(3,env.ref('base.group_allow_export').id)]}})",'r1-boundary-export-restore')
        policy(f"env['ir.rule'].search([('name','=',{broad_rule_name!r}),('model_id','=',env['ir.model']._get('mp.example.note').id)]).unlink()",'r1-boundary-rule-restore')


if __name__=='__main__':main()
