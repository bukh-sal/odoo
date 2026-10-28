"""Crash a disposable HTTP worker after commit, before delivering a response.

The optional trusted fixture is server-wide only during this bounded procedure.
Its operator-owned match file is read-only to the app, and removed from the
runtime configuration in finally. Never enables this on a non-fixture site.
"""
import hashlib
import json
import subprocess
import time
from uuid import uuid4

import rfc8785
import r1
from r1_probe import Client


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text())
    assert fixture['database']==state['active_db'] and state['active_db'].startswith('mp_disposable_r0_r1_')
    nonce=uuid4().hex;key='postcommit-'+nonce;values={'title':'Crash retry '+nonce,'body':'Synthetic same-database effect'}
    arm={'nonce':nonce,'database':state['active_db'],'principal_id':fixture['users']['alice']['principal_id'],'workspace_id':fixture['workspaces']['A']['public_id'],'service':'org.example.notes.documents','method':'create','key':key,'input_sha256':hashlib.sha256(rfc8785.dumps(values)).hexdigest()}
    volume=state['project']+'_fault_'+nonce
    override=r1.r0.LOCAL/'fault-compose.json'
    override.write_text(json.dumps({'services':{'app':{'command':['-c','/run/secrets/odoo_config','--addons-path=/opt/modular/addons,/opt/modular/fixtures/v1','--load=base,web,mp_r1_fault'],'environment':{'MP_R1_FAULT_FILE':'/run/mp-fault/arm.json'},'volumes':[volume+':/run/mp-fault:ro']}},'volumes':{volume:{'external':True}}},indent=2))
    command=r1.r0.compose()+['-f',str(override)]
    out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-crash-before-response.json')
    report={'state':'in_progress','nonce':nonce,'effect':'not_observed','cleanup':'pending'};out.write_text(json.dumps(report,indent=2)+'\n')
    created=None
    try:
        r1.r0.execute(state,'r1-fault-volume',['docker','volume','create','--label','com.modular.disposable='+state['project'],volume])
        seed="import json,pathlib,sys; p=pathlib.Path('/arm/arm.json'); p.write_text(json.dumps(json.load(sys.stdin))); p.chmod(0o444); print('Read-only disposable fault match configured')"
        r1.r0.execute(state,'r1-fault-config',['docker','run','--rm','-i','--network','none','--mount','type=volume,source='+volume+',target=/arm','--user','0','--entrypoint','python','modular-platform:r1','-c',seed],input_bytes=json.dumps(arm).encode())
        r1.r0.execute(state,'r1-fault-up',command+['up','-d','--force-recreate','app'])
        deadline=time.monotonic()+30
        while True:
            try:client=Client(state,fixture);break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(.3)
        payload={'api_version':'1.0','request_id':nonce,'idempotency_key':key,'input':values}
        headers={'X-CSRFToken':client.csrf,'X-MP-Binding':fixture['bindings']['A']['binding_id']}
        status,lost=client.request('/api/v1/services/org.example.notes.documents/create',payload,'A',headers)
        assert status==502 and lost=={'non_json_status':502},(status,lost)
        # Independent authenticated request sees the committed effect, despite
        # the original client never receiving its ID/success response.
        rows=client.native('search_read',[[('title','=',values['title'])]],{'fields':['public_id','revision','body']})
        assert len(rows)==1 and rows[0]['revision']==1 and rows[0]['body']==values['body'];created=rows[0]['public_id']
        replay=client.call('create',values,key=key)
        assert replay['id']==created and replay['revision']==1
        assert client.call('create',values,key=key)==replay
        assert client.native('search_count',[[('title','=',values['title'])]])==1
        logs=subprocess.run(['docker','logs',state['project']+'-app-1'],capture_output=True,text=True,check=True)
        lines=[line for line in (logs.stdout+logs.stderr).splitlines() if ('MP_R1_POSTCOMMIT_EXIT' in line or ('Worker' in line and ('86' in line or 'HTTP' in line)))]
        assert sum('MP_R1_POSTCOMMIT_EXIT' in line and nonce in line for line in lines)==1
        report.update(state='passed',initial_client_status=status,effect='one_committed_record',saved_result_replayed_twice=True,worker_events=lines)
    except Exception:
        report['state']='failed';raise
    finally:
        # Recreate without the fixture and its mount/env, restoring normal app.
        r1.r0.execute(state,'r1-fault-disable',r1.r0.compose()+['up','-d','--force-recreate','app'])
        deadline=time.monotonic()+30
        while True:
            try:client=Client(state,fixture);break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(.3)
        # Reconcile by unique title even when the initial result was uncertain.
        rows=client.native('search_read',[[('title','=',values['title'])]],{'fields':['public_id','revision']})
        for row in rows:client.call('delete',{'note_id':row['public_id'],'expected_revision':row['revision']})
        inspect=json.loads(subprocess.run(['docker','inspect',state['project']+'-app-1'],capture_output=True,text=True,check=True).stdout)[0]
        assert not any('MP_R1_FAULT_FILE=' in value for value in inspect['Config']['Env'])
        assert not any(m['Destination']=='/run/mp-fault' for m in inspect['Mounts'])
        assert 'mp_r1_fault' not in ' '.join(inspect['Config']['Cmd'])
        report['cleanup']='normal_image_command_restored_no_fault_mount_or_environment_synthetic_note_removed'
        out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':report['state'],'evidence':str(out.relative_to(r1.r0.ROOT))}))


if __name__=='__main__':main()
