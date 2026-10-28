"""Actual after-commit connection cancellation and process exit on the clone.

Only a separate test worker bypasses the default production entrypoint to load
the existing immutable trusted fault fixture. Normal guarded workers stay up.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import socket
import sys
import time
from uuid import uuid4
import rfc8785

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL, command
import r1
from r1_probe import Client


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    output = args.output.resolve(); assert output.is_relative_to(ROOT/'docs/evidence/G5') and not output.exists()
    private = ROOT/'.local/g5/client-release-clones'/(output.name+'.json'); assert not private.exists()
    clone = json.loads((private.parent/'20261028-client-release-clone-01.json').read_text(encoding='utf-8'))
    ingress = json.loads((private.parent/'20261028-client-release-ingress-01.json').read_text(encoding='utf-8'))
    assert ingress['state'] == 'fixtures_restored' and clone['state'] == 'browser_qualified_subset' and clone['generation'] == 18
    target = json.loads((ROOT/'.local/operator/targets/g5.json').read_text(encoding='utf-8'))
    observer = DockerObserver(target); catalog = Catalog(ROOT/'.local/operator/catalog', configuration(ROOT/'.local/operator/trust.json'), readonly=True).snapshot()
    source = observer.state(observer.read(), catalog)['state']; assert data_digest(source) == clone['source_state_digest']
    db = observer._container('db'); database = clone['database']; assert database == 'mp_disposable_r0_r1_client_d44f98595a294031'

    def sql(query): return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',database], input=query.encode())
    business = json.loads(sql(BUSINESS_SQL)); assert data_digest(business) == clone['business_digest']
    fixture = json.loads((ROOT/'.local/g5/fixtures.json').read_text(encoding='utf-8')); fixture['bindings'] = {}
    for key, space in fixture['workspaces'].items():
        installation = next(row for row in source['installations'] if row['plugin_id']=='org.example.notes' and row['workspace_id']==space['public_id'])
        fixture['bindings'][key] = next(row for row in source['bindings'] if row['consumer_installation_id']==installation['installation_id'] and row['alias']=='documents' and row['workspace_id']==space['public_id'])
    r1.r0.LOCAL = ROOT/'.local/g5'; state = {'active_db':database, 'port':clone['port']}; normal = Client(state, fixture)
    prefix = 'Postcommit '+uuid4().hex+' '; worker = clone['volume']+'-postcommit-worker'; edge = clone['volume']+'-postcommit-edge'
    volume = clone['volume']+'-postcommit'
    arm = {'fault':'delay_after_commit', 'nonce':uuid4().hex, 'database':database,
           'principal_id':fixture['users']['alice']['principal_id'], 'workspace_id':fixture['workspaces']['A']['public_id'],
           'service':'org.example.notes.documents', 'method':'create', 'key':'cancel-'+uuid4().hex}
    delay_values = {'title':prefix+'cancelled', 'body':'Committed despite closed connection'}
    arm['input_sha256'] = hashlib.sha256(rfc8785.dumps(delay_values)).hexdigest()
    record = {'state':'prepared', 'database':database, 'worker':worker, 'edge':edge, 'volume':volume, 'port':18076,
              'prefix':prefix, 'delay_arm':dict(arm), 'image_id':clone['image_id']}
    report = {'result':'in_progress', 'utc':datetime.now(timezone.utc).isoformat(), 'database':database,
              'image_id':clone['image_id'], 'inventory_digest':clone['inventory_digest'], 'generation':18,
              'checks':[], 'limits':['Separately instrumented disposable HTTP worker; not independent executor crash/recovery or a production startup claim.',
               'Actual socket cancellation proves committed/unknown transport outcome; browser-facing unknown outcome is covered by unchanged source/client tests and retained browser recovery qualification.']}
    output.mkdir(parents=True)

    def save():
        private.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        (output/'postcommit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

    def configure(arm_value, first=False):
        payload = {'arm':arm_value}
        if first:
            payload['nginx'] = 'server {listen 8069; server_name _; location ^~ /web/database {return 403;} location / {proxy_set_header Host $http_host; proxy_pass http://'+worker+':8069;}}'
        code = "import json,pathlib,sys; d=json.load(sys.stdin); p=pathlib.Path('/probe'); f=p/('arm-'+d['arm']['nonce']+'.new'); f.write_text(json.dumps(d['arm'])); f.chmod(0o444); f.replace(p/'arm.json');\nif 'nginx' in d:\n (p/'edge').mkdir();(p/'edge/clone.conf').write_text(d['nginx']);(p/'edge/clone.conf').chmod(0o444)"
        command(['docker','run','--rm','-i','--read-only','--network','none','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',clone['image_id'],'-c',code],input=json.dumps(payload).encode())

    def logs():
        # docker logs writes native diagnostics to stderr; inspect only explicit
        # fixture events without collecting request bodies or credentials.
        import subprocess
        value = subprocess.run(['docker','logs',worker],capture_output=True,check=True)
        return (value.stdout+value.stderr).decode(errors='replace')

    def await_event(event, nonce):
        until = time.monotonic()+15
        while True:
            lines = [line for line in logs().splitlines() if event in line and nonce in line]
            if lines: assert len(lines)==1; return lines[0]
            if time.monotonic()>until: raise RuntimeError('Expected bounded postcommit event absent')
            time.sleep(.15)

    started = False; save()
    try:
        with socket.socket() as check: check.bind(('127.0.0.1',18076))
        fixture_hash = hashlib.sha256((ROOT/'tests/fixtures/addons/v1/mp_r1_fault/controllers.py').read_bytes()).hexdigest()
        actual_hash = command(['docker','exec',clone['app'],'/venv/bin/python','-c',"import pathlib,hashlib;print(hashlib.sha256(pathlib.Path('/opt/modular/fixtures/v1/mp_r1_fault/controllers.py').read_bytes()).hexdigest())"]).decode().strip()
        assert fixture_hash == actual_hash
        report['immutable_fault_fixture_sha256'] = actual_hash
        record['state']='creating_fixture_worker'; save()
        command(['docker','volume','create','--label','modular.disposable=client-postcommit',volume]); configure(arm,True)
        command(['docker','run','-d','--name',worker,'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',target['project']+'_runtime','--memory','1g','--pids-limit','256','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777',
                 '--mount','type=volume,source='+clone['volume']+',target=/run/secrets,volume-subpath=config,readonly',
                 '--mount','type=volume,source='+clone['volume']+',target=/var/lib/modular,volume-subpath=data',
                 '--mount','type=volume,source='+volume+',target=/run/mp-fault,readonly',
                 '-e','MP_R1_FAULT_FILE=/run/mp-fault/arm.json','--entrypoint','/venv/bin/python',clone['image_id'],
                 'odoo-bin','-c','/run/secrets/odoo_config','--addons-path=/opt/modular/addons,/opt/modular/fixtures/v1','--load=base,web,mp_r1_fault'])
        started=True
        edge_image=command(['docker','inspect',clone['edge'],'--format','{{.Image}}']).decode().strip()
        command(['docker','create','--name',edge,'--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',clone['edge_network'],'--publish','127.0.0.1:18076:8069','--tmpfs','/var/cache/nginx:rw,nosuid,nodev,noexec,mode=1777','--tmpfs','/var/run:rw,nosuid,nodev,noexec,mode=1777','--mount','type=volume,source='+volume+',target=/etc/nginx/conf.d,volume-subpath=edge,readonly',edge_image])
        command(['docker','network','connect',target['project']+'_runtime',edge]);command(['docker','start',edge])
        until=time.monotonic()+35
        while True:
            try: client=Client({**state,'port':18076},fixture);break
            except (OSError,AssertionError):
                if time.monotonic()>until:raise
                time.sleep(.3)
        payload={'api_version':'1.0','request_id':uuid4().hex,'idempotency_key':arm['key'],'input':delay_values}
        headers={'Content-Type':'application/json','Cookie':'; '.join(c.name+'='+c.value for c in client.jar),
                 'X-CSRFToken':client.csrf,'X-MP-Client-Release':client.release_token,
                 'X-MP-Workspace':fixture['workspaces']['A']['public_id'],'X-MP-Binding':fixture['bindings']['A']['binding_id']}
        record['state']='delay_request_sent';save()
        connection=http.client.HTTPConnection('127.0.0.1',18076,timeout=15)
        connection.request('POST','/api/v1/services/org.example.notes.documents/create',body=json.dumps(payload),headers=headers)
        start=await_event('MP_R1_POSTCOMMIT_DELAY_START',arm['nonce'])
        # No response was read. Terminate this client connection after independent
        # evidence that both record and saved idempotent outcome were committed.
        connection.close();record['state']='client_cancelled_after_commit';save()
        rows=normal.native('search_read',[[('title','=',delay_values['title'])]],{'fields':['public_id','revision','body']})
        assert len(rows)==1 and rows[0]['revision']==1 and rows[0]['body']==delay_values['body']
        recovered=normal.call('create',delay_values,key=arm['key']);assert recovered['id']==rows[0]['public_id']
        assert normal.call('create',delay_values,key=arm['key'])==recovered
        end=await_event('MP_R1_POSTCOMMIT_DELAY_END',arm['nonce'])
        report['checks'].append({'name':'cancelled connection after actual commit; outcome discoverable once without rollback claim', 'result':'passed','nonce':arm['nonce'],'events':[start,end], 'same_key_replayed_twice':True,'one_effect':True})
        record['state']='delay_qualified';save()
        crash_values={'title':prefix+'crash','body':'Committed before worker exit86'}
        arm.update(fault='exit_after_commit',nonce=uuid4().hex,key='crash-'+uuid4().hex,input_sha256=hashlib.sha256(rfc8785.dumps(crash_values)).hexdigest())
        record['crash_arm']=dict(arm);record['state']='arming_crash';save();configure(arm)
        payload.update(request_id=uuid4().hex,idempotency_key=arm['key'],input=crash_values)
        status,value=client.request('/api/v1/services/org.example.notes.documents/create',payload,'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':fixture['bindings']['A']['binding_id']})
        assert status==502 and value=={'non_json_status':502},(status,value)
        event=await_event('MP_R1_POSTCOMMIT_EXIT',arm['nonce'])
        exit_status=command(['docker','wait',worker]).decode().strip();assert exit_status=='86'
        rows=normal.native('search_read',[[('title','=',crash_values['title'])]],{'fields':['public_id','revision','body']})
        assert len(rows)==1 and rows[0]['revision']==1 and rows[0]['body']==crash_values['body']
        recovered=normal.call('create',crash_values,key=arm['key']);assert recovered['id']==rows[0]['public_id']
        assert normal.call('create',crash_values,key=arm['key'])==recovered
        assert normal.native('search_count',[[('title','=',crash_values['title'])]])==1
        report['checks'].append({'name':'actual exit86 after commit before response; separate guarded worker replays one saved result', 'result':'passed','nonce':arm['nonce'],'event':event,'initial_status':status,'exit_code':86,'same_key_replayed_twice':True,'one_effect':True})
        report['result']='passed';record['state']='postcommit_qualified';save()
    except Exception as error:
        report.update(result='failed',error_type=type(error).__name__);raise
    finally:
        if started:
            inspect=json.loads(command(['docker','inspect',worker]))[0]
            if inspect['State']['Running']:command(['docker','stop','--time','15',worker])
        for row in normal.native('search_read',[[('title','=like',prefix+'%')]],{'fields':['public_id','revision']}):
            normal.call('delete',{'note_id':row['public_id'],'expected_revision':row['revision']})
        assert json.loads(sql(BUSINESS_SQL))==business
        for name in [clone['app'],ingress['secondary']]:
            current=json.loads(command(['docker','inspect',name]))[0]
            assert current['State']['Running'] and current['Image']==clone['image_id']
            assert current['Config']['Entrypoint']==['/venv/bin/python','/opt/modular/tools/start_worker.py']
            assert not any(value.startswith('MP_R1_FAULT_FILE=') for value in current['Config']['Env'])
            assert not any(mount['Destination']=='/run/mp-fault' for mount in current['Mounts'])
        assert observer.state(observer.read(),catalog)['state']==source
        record['state']='reconciled_'+report['result']
        report.update(original_business_restored=True,normal_guarded_workers_unchanged=True,source_state_unchanged=True,
                      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        save()
    print(json.dumps({'result':report['result'],'checks':len(report['checks']),'evidence':output.relative_to(ROOT).as_posix()}))


if __name__=='__main__':main()
