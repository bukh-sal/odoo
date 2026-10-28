"""Actual workspace administrator/technical/metadata authority qualification."""
import json
import subprocess
import sys
from uuid import uuid4

from r1_probe import Client,r1


def policy(action):
    completed=subprocess.run([sys.executable,str(r1.r0.ROOT/'tools/r1_policy.py'),action],cwd=r1.r0.ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if completed.returncode:raise RuntimeError('Known fixture policy action failed: '+action)


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text())
    report=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-administrator-authority.json');checks=[]
    def record(name):
        checks.append({'name':name,'result':'passed'});report.write_text(json.dumps({'state':'in_progress','checks':checks},indent=2)+'\n')
    client=Client(state,fixture);outsider=Client(state,fixture,'outsider');worker=Client(state,fixture,'worker')
    def meta(path,payload=None,workspace='A',expect=200,code=None):
        status,result=client.request('/api/v1/workspace/'+path,payload,workspace,{'X-CSRFToken':client.csrf})
        assert status==expect,(path,status,result)
        if code:assert result.get('error',{}).get('code')==code,(path,result)
        else:assert 'data' in result,(path,result)
        return result.get('data',result)
    admin=False;original=None;created=None;target_added=False
    try:
        for path in ['members','settings']:meta(path,expect=403,code='FORBIDDEN')
        meta('members',{'operation':'add','principal_id':fixture['users']['outsider']['principal_id'],'role':'editor'},expect=403,code='FORBIDDEN')
        worker.call('list',{'limit':25},expect=403,code='FORBIDDEN')
        record('editor cannot administer workspace; service password session has no implicit model authority')
        policy('admin_alice_a');admin=True
        rows=meta('members');assert {r['principal_id'] for r in rows}=={fixture['users'][who]['principal_id'] for who in ['alice','worker']}
        original=meta('settings');assert original['workspace_id']==fixture['workspaces']['A']['public_id']
        meta('members',workspace='B',expect=403,code='FORBIDDEN');meta('settings',workspace='B',expect=403,code='FORBIDDEN')
        record('administrator sees only selected workspace directory/configuration; viewer B remains denied')
        for forbidden in ['workspace_id','site_id','user_id','installation_id','sudo','command']:
            meta('settings',{'name':'Rejected',forbidden:fixture['workspaces']['B']['public_id']},expect=400,code='VALIDATION_FAILED')
        meta('settings',{'timezone':'not/a/real/timezone'},expect=400,code='VALIDATION_FAILED')
        record('strict configuration DTO rejects scope installer sudo and invalid timezone inputs')
        changed={'name':'Personal administration proof','default_locale':'ar','timezone':'Asia/Riyadh'}
        meta('settings',changed);current=meta('settings');assert all(current[k]==v for k,v in changed.items())
        status,context=client.request('/api/v1/context?plugin_id=org.example.notes',workspace='A')
        assert status==200 and context['data']['context']['direction']=='rtl' and context['data']['context']['timezone']=='Asia/Riyadh'
        assert 'org.modularplatform.identity:workspace.members.manage' in context['data']['context']['capabilities']
        meta('settings',{k:original[k] for k in ['name','default_locale','timezone']})
        record('authorized metadata change updates validated context generation locale timezone; original values restored')
        target=fixture['users']['outsider']['principal_id']
        meta('members',{'operation':'add','principal_id':target,'role':'viewer'});target_added=True
        assert outsider.call('list',{'limit':25})['items']
        outsider.call('create',{'title':'Denied viewer','body':''},expect=403,code='FORBIDDEN')
        meta('members',{'operation':'update','principal_id':target,'role':'editor'})
        created=outsider.call('create',{'title':'Administrator scope proof '+uuid4().hex,'body':'Synthetic'},key='admin-'+uuid4().hex)
        outsider.call('get',{'note_id':fixture['objects']['B']['public_id']},expect=404,code='NOT_FOUND')
        outsider.call('delete',{'note_id':created['id'],'expected_revision':1});created=None
        meta('members',{'operation':'remove','principal_id':target});target_added=False
        outsider.call('list',{'limit':25},expect=403,code='FORBIDDEN')
        record('membership add role update and revoke change real actor permissions without cross-workspace access')
        alice=fixture['users']['alice']['principal_id']
        meta('members',{'operation':'remove','principal_id':alice},expect=409,code='CONFLICT')
        meta('members',{'operation':'update','principal_id':alice,'role':'viewer'},expect=409,code='CONFLICT')
        meta('members',{'operation':'add','principal_id':fixture['users']['worker']['principal_id'],'role':'administrator'},expect=400,code='VALIDATION_FAILED')
        record('last human administrator cannot be removed/demoted; technical principal cannot become workspace administrator')
        client.native('write',[[fixture['memberships']['aliceA']],{'role':'administrator'}],model='mp.membership',deny=True)
        installs=client.native('search',[[]],model='mp.plugin.installation',deny=True)
        client.native('search',[[('name','=','mp_example_notes')]],model='ir.module.module',deny=True)
        # Operator harness resolves the real target ID; the ordinary workspace
        # administrator remains unable to discover or mutate module metadata.
        module_log=r1.shell(state,'r1-known-module-target',"""import json
row=env['ir.module.module'].search([('name','=','mp_example_notes')],limit=1)
assert row.state=='installed'
print('MP_R1_RESULT='+json.dumps({'module_id':row.id}))
""")
        module_result=[json.loads(line.split('MP_R1_RESULT=',1)[1]) for line in module_log.read_text(errors='replace').splitlines() if line.startswith('MP_R1_RESULT=')]
        assert len(module_result)==1
        modules=[module_result[0]['module_id']]
        status,value=client.request('/web/dataset/call_kw/ir.module.module.button_immediate_install',{'jsonrpc':'2.0','method':'call','id':1,'params':{'model':'ir.module.module','method':'button_immediate_install','args':[modules],'kwargs':{}}},'A')
        assert status==200 and value.get('error',{}).get('data',{}).get('name')=='odoo.exceptions.AccessDenied',(status,value)
        assert set(value['error']['data'])=={'name','message','request_id'},'Native error must not expose traces/arguments/context'
        record('workspace administrator gains no legacy metadata ACL/native installation privilege')
        log=r1.shell(state,'r1-audit-authority-check',f"""import json
rows=env['mp.audit.event'].search([],order='id desc',limit=400)
assert rows.filtered(lambda r:r.decision=='allowed') and rows.filtered(lambda r:r.decision=='denied')
assert rows.filtered(lambda r:r.action=='/api/v1/workspace/members' and r.actor_id=={fixture['users']['alice']['principal_id']!r})
assert all(len(r.request_id)==36 for r in rows)
from pathlib import Path
serialized=json.dumps(rows.read(['actor_id','workspace_public_id','plugin_id','action','target_id','decision','request_id','metadata']))
assert Path('/run/mp-bootstrap/password').read_text().strip() not in serialized
assert 'A private place for ideas' not in serialized
print('MP_R1_RESULT='+json.dumps({{'allowed':len(rows.filtered(lambda r:r.decision=='allowed')),'denied':len(rows.filtered(lambda r:r.decision=='denied')),'audit_redaction':'passed'}}))
""")
        record('real audit records retain allowed/denied actor scope request identity without passwords/note content')
        report.write_text(json.dumps({'state':'passed','scope':'C04 administrator/technical/audit subset; other G3 qualification remains open','checks':checks,'audit_evidence':str(log.relative_to(r1.r0.ROOT))},indent=2)+'\n')
        print(json.dumps({'state':'passed','checks':len(checks),'evidence':str(report.relative_to(r1.r0.ROOT))}))
    except Exception:
        report.write_text(json.dumps({'state':'failed','checks':checks},indent=2)+'\n');raise
    finally:
        if admin:
            if created:
                current=client.call('get',{'note_id':created['id']});client.call('delete',{'note_id':created['id'],'expected_revision':current['revision']})
            if target_added:meta('members',{'operation':'remove','principal_id':fixture['users']['outsider']['principal_id']})
            if original:meta('settings',{k:original[k] for k in ['name','default_locale','timezone']})
            policy('restore_alice_a')


if __name__=='__main__':main()
