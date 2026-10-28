"""Once-only populated clone experiment; never replace an operated target.

Keep the database, volume, maintenance container and HTTP worker for inspection.
The clone's publication is explicitly experimental, not an approved release.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest
from modular_platform.release_staging import validate_core_upgrade
from modular import configuration
import r1,r1_probe


SEED="""import configparser,json,os,pathlib,shutil,sys
data=json.load(sys.stdin);base=pathlib.Path('/probe')
config=configparser.ConfigParser();config.read('/source/odoo_config')
config['options'].update(db_name=data['database'],dbfilter='^'+data['database']+'$',workers='0',max_cron_threads='0')
(base/'config').mkdir();(base/'data').mkdir()
with (base/'config/odoo_config').open('x') as stream:config.write(stream)
(base/'config/odoo_config').chmod(0o444)
source=pathlib.Path('/old/filestore')/data['source_database']
destination=base/'data/filestore'/data['database']
shutil.copytree(source,destination)
for path in [base/'data',*(base/'data').rglob('*')]:os.chown(path,10001,10001)
"""
BUSINESS_SQL="""SELECT jsonb_build_object(
 'notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),
 'boards',(SELECT jsonb_agg(to_jsonb(b) ORDER BY id) FROM mp_example_canvas_board b),
 'features',(SELECT jsonb_agg(to_jsonb(f) ORDER BY id) FROM mp_workspace_plugin f),
 'bindings',(SELECT jsonb_agg(to_jsonb(b) ORDER BY id) FROM mp_service_binding b),
 'grants',(SELECT jsonb_agg(to_jsonb(g) ORDER BY id) FROM mp_plugin_grant g));"""


def command(args,*,input=None,timeout=120):
    result=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('Controlled clone command failed: '+args[0])
    return result.stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--image-id',required=True);parser.add_argument('--port',type=int,default=18073)
    parser.add_argument('--resume-network',action='store_true',help='Reconcile the exact internal-only publication failure; no DB/migration replay')
    args=parser.parse_args();resume=args.resume_network
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists()!=resume:raise ValueError('Fresh evidence or exact network reconciliation required')
    private=protect_directory(ROOT/'.local/g5/client-release-clones');marker=private/(output.name+'.json')
    if marker.exists()!=resume:raise ValueError('Clone attempt already recorded; reconcile it without replay')
    saved=json.loads(marker.read_text(encoding='utf-8')) if resume else None
    if resume and (saved['state']!='requires_reconciliation' or saved['interrupted_phase']!='worker_started' or saved['image_id']!=args.image_id):
        raise ValueError('Only exact recorded internal-network failure may resume')
    with socket.socket() as probe:probe.bind(('127.0.0.1',args.port))
    target=json.loads((ROOT/'.local/operator/targets/g5.json').read_text(encoding='utf-8'))
    reader=DockerObserver(target);catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True)
    observed=reader.read();before=reader.state(observed,catalog.snapshot())['state'];runtime=inspect_image(args.image_id)
    diff,core=validate_core_upgrade(observed['runtime'],runtime,{'base_image_id':target['image_id'],'target_image_id':args.image_id})
    assert {row['addon'] for row in core}=={'mp_identity','mp_core','mp_shell'}
    token=saved['database'].removeprefix('mp_disposable_r0_r1_client_') if resume else uuid4().hex[:16]
    assert re.fullmatch('[0-9a-f]{16}',token)
    database='mp_disposable_r0_r1_client_'+token;volume='mp-r1-client-'+token
    app=volume+'-app';maintenance=volume+'-maintenance';db=reader._container('db')
    assert len(database)<=63 and re.fullmatch(r'mp_disposable_r0_r1_[a-z0-9_]+',database)
    record=saved if resume else {'state':'preparing','database':database,'volume':volume,'app':app,'maintenance':maintenance,'port':args.port,
        'image_id':args.image_id,'inventory_digest':runtime['inventory_digest'],'source_database':target['sites'][0]['database'],
        'source_project':target['project'],'source_state_digest':data_digest(before),'native_core_changes':core,
        'experimental_not_approved_release':True,'evidence':output.relative_to(ROOT).as_posix()}
    if not resume:output.mkdir(parents=True);_write_new(marker,record)
    else:
        assert record['source_state_digest']==data_digest(before)
        assert json.loads(command(['docker','inspect',app,'--format','{{json .State.Running}}'])) is True
        assert command(['docker','inspect',app,'--format','{{.Image}}']).decode().strip()==args.image_id
        assert json.loads(command(['docker','inspect',maintenance,'--format','{{json .State}}']))['ExitCode']==0

    def phase(name):
        record['state']=name;record['utc']=datetime.now(timezone.utc).isoformat()
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    def sql(statement,name=database):
        return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',name],input=statement.encode())
    def snapshot(name=database):return json.loads(sql(BUSINESS_SQL,name))
    def container(name):
        return ['docker','run','--name',name,'--read-only','--user','10001:10001','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--network',target['project']+'_runtime','--memory','1g','--pids-limit','256',
            '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777',
            '--mount','type=volume,source='+volume+',target=/run/secrets,volume-subpath=config,readonly',
            '--mount','type=volume,source='+volume+',target=/var/lib/modular,volume-subpath=data']
    try:
        assert sql("SELECT count(*) FROM pg_database WHERE datname='"+database+"';",'postgres').strip()==(b'1' if resume else b'0')
        source_business=snapshot(target['sites'][0]['database'])
        owner=sql('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database();',target['sites'][0]['database']).decode().strip()
        assert re.fullmatch(r'[a-z_][a-z0-9_]*',owner)
        if not resume:
            archive=command(['docker','exec',db,'pg_dump','-U','postgres','-Fc',target['sites'][0]['database']])
            phase('creating_database')
            command(['docker','exec',db,'createdb','-U','postgres','-T','template0','-O',owner,database])
            command(['docker','exec','-i',db,'pg_restore','-U','postgres','--exit-on-error','--no-owner','--role',owner,'-d',database],input=archive)
            assert snapshot()==source_business
            phase('seeding_private_volume')
            command(['docker','volume','create','--label','modular.disposable=client-release-qualification',volume])
            command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN',
                '--mount','type=volume,source='+target['project']+'_appconfig,target=/source,readonly',
                '--mount','type=volume,source='+target['project']+'_filestore,target=/old,readonly',
                '--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',args.image_id,'-c',SEED],
                input=json.dumps({'database':database,'source_database':target['sites'][0]['database']}).encode())
        baseline=snapshot()
        if not resume:
            phase('migrating_native_core')
            with (private/(output.name+'-native.log')).open('xb') as log:
                result=subprocess.run(container(maintenance)+['--entrypoint','/venv/bin/python',args.image_id,'odoo-bin','-c','/run/secrets/odoo_config','-d',database,
                    '-u',','.join(row['addon'] for row in core),'--stop-after-init','--no-http','--workers=0','--max-cron-threads=0','--without-demo'],stdout=log,stderr=subprocess.STDOUT,timeout=180)
            assert result.returncode==0,'Native core migration failed; retained private log/container'
        assert snapshot()==baseline,'Core migration altered retained business/scopes'
        versions=json.loads(sql("SELECT jsonb_object_agg(name,latest_version) FROM ir_module_module WHERE name IN ('mp_identity','mp_core','mp_shell') AND state='installed';"))
        assert versions=={row['addon']:row['target_version'] for row in core}
        if not resume:
            record['generation']=target['generation']+1;record['release_digest']=data_digest({'experimental_clone':token,'generation':record['generation'],'inventory':runtime['inventory_digest']})
            phase('publishing_experimental_identity')
            sql("UPDATE ir_config_parameter SET value=CASE key WHEN 'mp.release_generation' THEN '"+str(record['generation'])+"' WHEN 'mp.release_digest' THEN '"+record['release_digest']+"' ELSE '"+runtime['inventory_digest']+"' END WHERE key IN ('mp.release_generation','mp.release_digest','mp.active_inventory_digest');")
            phase('starting_guarded_worker')
            cmd=container(app);cmd.insert(2,'-d')
            command(cmd+['--publish','127.0.0.1:'+str(args.port)+':8069','-e','MP_EXPECTED_DATABASE='+database,'-e','MP_EXPECTED_INVENTORY_DIGEST='+runtime['inventory_digest'],args.image_id])
        else:
            ports=json.loads(command(['docker','inspect',app,'--format','{{json .NetworkSettings.Ports}}']))
            assert ports.get('8069/tcp')==[],'Reconcile exact inactive internal-only binding, not a different failure'
            assert snapshot()==source_business
            record.update(edge=volume+'-edge',edge_network=volume+'-edge-network',previous_unpublished_port=record['port'],port=args.port)
            phase('adding_test_edge')
            nginx='server {listen 8069; server_name _; location ^~ /web/database {return 403;} location / {proxy_set_header Host $http_host; proxy_pass http://'+app+':8069;}}'
            command(['docker','run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',args.image_id,'-c',"import pathlib,sys;p=pathlib.Path('/probe/edge');p.mkdir();(p/'clone.conf').write_text(sys.argv[1]);(p/'clone.conf').chmod(0o444)",nginx])
            command(['docker','network','create','--label','modular.disposable=client-release-qualification',record['edge_network']])
            nginx_image=command(['docker','inspect',reader._container('edge'),'--format','{{.Image}}']).decode().strip()
            command(['docker','create','--name',record['edge'],'--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',record['edge_network'],
                '--publish','127.0.0.1:'+str(args.port)+':8069','--tmpfs','/var/cache/nginx:rw,nosuid,nodev,noexec,mode=1777','--tmpfs','/var/run:rw,nosuid,nodev,noexec,mode=1777',
                '--mount','type=volume,source='+volume+',target=/etc/nginx/conf.d,volume-subpath=edge,readonly',nginx_image])
            command(['docker','network','connect',target['project']+'_runtime',record['edge']]);command(['docker','start',record['edge']])
            (output/'network-reconciliation.json').write_text(json.dumps({'result':'same_clone_same_worker','native_migration_repeated':False,'database_recreated':False,'source_deployment_changed':False,'internal_only_binding':ports,'edge_port':args.port,'edge':record['edge']},indent=2)+'\n',encoding='utf-8')
        phase('worker_started')
        http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for attempt in range(40):
            try:
                with http.open('http://127.0.0.1:'+str(args.port)+'/web/login',timeout=3) as response:
                    if response.status==200:break
            except Exception:time.sleep(1)
        else:raise RuntimeError('Recorded worker did not become HTTP ready')
        phase('http_qualifying')
        fixture=json.loads((ROOT/'.local/g5/fixtures.json').read_text(encoding='utf-8'));fixture['bindings']={}
        for key,space in fixture['workspaces'].items():
            consumer=next(item for item in before['installations'] if item['plugin_id']=='org.example.notes' and item['workspace_id']==space['public_id'])
            fixture['bindings'][key]=next(item for item in before['bindings'] if item['consumer_installation_id']==consumer['installation_id'] and item['workspace_id']==space['public_id'] and item['alias']=='documents')
        state={'active_db':database,'port':args.port};r1.r0.LOCAL=ROOT/'.local/g5'
        alice=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob')
        status,context=alice.request('/api/v1/context?plugin_id=org.example.notes',workspace='A');assert status==200 and context['data']['release']['token']==alice.release_token
        row=baseline['notes'][0];original=alice.call('get',{'note_id':row['public_id']});assert original['title']==row['title']
        alice.native('read',[[row['id']],['public_id','title']],workspace='A')
        alice.native('read',[[row['id']],['public_id']],workspace='B',deny=True)
        bob.call('get',{'note_id':row['public_id']},workspace='B',expect=403,code='FORBIDDEN')
        for pin in ['', 'sha256:'+'0'*64]:
            denied=alice.call('update',{'note_id':row['public_id'],'expected_revision':row['revision'],'title':'MUST_NOT_CHANGE'},headers={'X-MP-Client-Release':pin},expect=409,code='CONFLICT')
            assert denied['error']['details']=={'field':'client_release','outcome':'not_started'}
            status,denied=alice.request('/web/dataset/call_kw',{'jsonrpc':'2.0','method':'call','id':1,'params':{'model':'mp.example.note','method':'write','args':[[row['id']],{'title':'MUST_NOT_CHANGE'}],'kwargs':{}}},'A',{'X-MP-Client-Release':pin})
            assert status==200 and denied['error']['data']['name'].endswith('.ClientReleaseMismatch')
        assert snapshot()==baseline
        with alice.http.open(alice.base+'/app/org.example.notes/notes?workspace='+fixture['workspaces']['A']['public_id']) as response:
            html=response.read().decode();assert response.headers.get('Cache-Control')=='no-store' and 'odoo.__mp_client_release__' in html and alice.release_token in html
        board=baseline['boards'][0]
        alice.native('read',[[board['id']],['public_id','revision']],workspace='A',model='mp.example.canvas.board')
        after=reader.state(reader.read(),catalog.snapshot())['state'];assert after==before
        assert snapshot(target['sites'][0]['database'])==source_business
        record['state_digest']=data_digest(after);record['business_digest']=data_digest(baseline);phase('http_qualified')
        report=record|{'result':'passed_clone_http_subset','native_versions':versions,'source_diff_count':len(diff),
            'checks':['Actual core native-u completed and business/scopes preserved','Default guarded candidate started with experimental identity',
                'Authenticated current-pin gateway/native/Canvas reads and context positive','Foreign/suspended/revoked scopes denied',
                'Missing/stale gateway+native mutations denied before handler; original business/scopes unchanged','No-store native bootstrap contains exact release pin',
                'Operated source deployment/business unchanged'],
            'source_sha256':{Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            'limits':['No browser, client mismatch epoch change, actor/draft/reload qualification or acceptance passes from this subset.',
                'Direct disposable clone experiment is not independent executor approval/operation or a published release; actual core fault/recovery/rollout remain.']}
        (output/'clone-http.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'result':report['result'],'database':database,'app':app,'port':args.port,'marker':str(marker)}))
    except BaseException as error:
        record['interrupted_phase']=record['state'];record['state']='requires_reconciliation';record['error_type']=type(error).__name__
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        failure=output/('failure-'+datetime.now(timezone.utc).strftime('%H%M%S')+'.json' if resume else 'failure.json')
        failure.write_text(json.dumps({'phase':record['interrupted_phase'],'error_type':type(error).__name__,
            'resources_retained':True,'automatic_retry_forbidden':True},indent=2)+'\n',encoding='utf-8')
        raise


if __name__=='__main__':main()
