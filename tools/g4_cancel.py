"""Operator-only disposable postcommit delay for real browser cancellation proof."""
import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from uuid import uuid4

import rfc8785
import r1
from r1_probe import Client


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['arm','verify','off']);args=parser.parse_args();state=r1.setup()
    assert state.get('g4_upgrade_status')=='registered' and state['active_db'].startswith('mp_disposable_r0_r1_')
    path=r1.r0.LOCAL/'g4-cancel-state.json';fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text());g4=json.loads((r1.r0.LOCAL/'g4-fixtures.json').read_text())
    client=Client(state,fixture);binding=g4['bindings']['Personal']['org.example.canvas']['boards']
    def call(method,values,key=None):
        body={'api_version':'1.0','request_id':uuid4().hex,'input':values}
        if key:body['idempotency_key']=key
        status,value=client.request('/api/v1/services/org.example.canvas.boards/'+method,body,'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']});assert status==200,(status,value)
        return value['data']
    if args.action=='arm':
        if path.exists():raise RuntimeError('Cancellation fixture already attempted; reconcile existing state')
        # New image may contain test fixture changes; all registered plugin bytes
        # must still match the immutable artifact identities before enabling it.
        raw=subprocess.check_output(['docker','run','--rm','--network','none','--entrypoint','python',state['image'],'-c',"import json;print(json.dumps(json.load(open('/opt/modular/distribution-inventory.json'))['artifacts']))"],text=True)
        assert json.loads(raw)==g4['packages'],'Image/plugin digest drift requires reconciliation'
        before=call('get',{});nonce=uuid4().hex;name='Cancellation proof '+nonce[:8]
        values={'board_id':before['id'],'expected_revision':before['revision'],'name':name,'cards':before['cards']}
        arm={'fault':'delay_after_commit','nonce':nonce,'database':state['active_db'],'principal_id':fixture['users']['alice']['principal_id'],'workspace_id':fixture['workspaces']['A']['public_id'],'service':'org.example.canvas.boards','method':'save','key_prefix':'board-','input_sha256':hashlib.sha256(rfc8785.dumps(values)).hexdigest()}
        record={'stage':'configuring','arm':arm,'before':before,'input':values,'volume':state['project']+'_cancel_'+nonce};path.write_text(json.dumps(record,indent=2)+'\n')
        volume=record['volume'];r1.r0.execute(state,'g4-cancel-volume',['docker','volume','create','--label','com.modular.disposable='+state['project'],volume])
        seed="import json,pathlib,sys; p=pathlib.Path('/arm/arm.json'); p.write_text(json.dumps(json.load(sys.stdin))); p.chmod(0o444);print('Bounded8-second one-shot postcommit match configured')"
        r1.r0.execute(state,'g4-cancel-config',['docker','run','--rm','-i','--network','none','--mount','type=volume,source='+volume+',target=/arm','--user','0','--entrypoint','python',state['image'],'-c',seed],input_bytes=json.dumps(arm).encode())
        override=r1.r0.LOCAL/'g4-cancel-compose.json';override.write_text(json.dumps({'services':{'app':{'command':['-c','/run/secrets/odoo_config','--addons-path=/opt/modular/addons,/opt/modular/fixtures/v1','--load=base,web,mp_r1_fault'],'environment':{'MP_R1_FAULT_FILE':'/run/mp-fault/arm.json'},'volumes':[volume+':/run/mp-fault:ro']}},'volumes':{volume:{'external':True}}},indent=2))
        r1.r0.execute(state,'g4-cancel-enable',r1.r0.compose()+['-f',str(override),'up','-d','--force-recreate','app'])
        deadline=time.monotonic()+30;http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while True:
            try:
                with http.open(f"http://127.0.0.1:{state['port']}/web/login",timeout=2) as response:
                    if response.code==200 and b'name="password"' in response.read():break
            except OSError:pass
            if time.monotonic()>deadline:raise RuntimeError('Fault fixture login readiness failed; inspect before retry')
            time.sleep(.25)
        record['stage']='armed';path.write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps({'fixture':'armed','set_board_name':name,'expected_revision':before['revision'],'nonce':nonce,'instruction':'Save in browser; confirm postcommit start in logs; Cancel request; same payload retry must return one effect'}))
    else:
        record=json.loads(path.read_text());nonce=record['arm']['nonce']
        if args.action=='verify':
            assert record['stage']=='armed'
            browser=json.loads((r1.r0.ROOT/state['evidence']/'browser-cancellation.json').read_text())
            assert browser['result']=='passed' and browser['nonce']==nonce
            current=call('get',{})
            assert current['id']==record['before']['id'] and current['revision']==record['before']['revision']+1 and current['name']==record['input']['name']
            logs=subprocess.run(['docker','logs',state['project']+'-app-1'],capture_output=True,text=True,check=True)
            lines=[line for line in (logs.stdout+logs.stderr).splitlines() if nonce in line and 'MP_R1_POSTCOMMIT_DELAY_' in line]
            assert sum('START' in line for line in lines)==1 and sum('END' in line for line in lines)==1,lines
            code=f"""assert env.cr.dbname=={state['active_db']!r}
env.cr.execute("SELECT key,state,result FROM mp_service_outcome WHERE service_id='org.example.canvas.boards' AND method='save' AND actor_id=%s AND input_digest=%s",[{fixture['users']['alice']['principal_id']!r},{record['arm']['input_sha256']!r}])
rows=env.cr.fetchall();assert len(rows)==1 and rows[0][1]=='completed' and rows[0][2]['revision']=={current['revision']!r}
import hashlib
print('MP_CANCEL_OUTCOME='+hashlib.sha256(rows[0][0].encode()).hexdigest())
"""
            log=r1.shell(state,'g4-cancel-saved-outcome',code)
            result={'result':'passed','nonce':nonce,'committed_revision':current['revision'],'one_committed_effect':True,'postcommit_events':lines,'outcome_log':log.name,'browser':'browser-cancellation.json','cleanup':'pending'}
            (r1.r0.ROOT/state['evidence']/'cancel-after-commit.json').write_text(json.dumps(result,indent=2)+'\n');record['stage']='verified';path.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(result))
        else:
            current=call('get',{})
            if current['name']==record['input']['name']:call('save',{'board_id':current['id'],'expected_revision':current['revision'],'name':record['before']['name'],'cards':current['cards']},'cancel-cleanup-'+nonce)
            r1.r0.execute(state,'g4-cancel-disable',r1.r0.compose()+['up','-d','--force-recreate','app'])
            inspect=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-app-1'],text=True))[0]
            assert not any('MP_R1_FAULT_FILE=' in v for v in inspect['Config']['Env'])
            assert not any(m['Destination']=='/run/mp-fault' for m in inspect['Mounts'])
            assert 'mp_r1_fault' not in ' '.join(inspect['Config']['Cmd'])
            record['stage']='off';path.write_text(json.dumps(record,indent=2)+'\n')
            evidence=r1.r0.ROOT/state['evidence']/'cancel-after-commit.json'
            if evidence.exists():result=json.loads(evidence.read_text());result['cleanup']='normal app command/env/mount restored; original board name restored';evidence.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps({'fixture':'off','board_name':'restored','production_fault_surface':'absent'}))


if __name__=='__main__':main()
