"""Once-only populated clone: actual native factory/preflight/HTTP retention.

The operated source remains unchanged. Keep all named clone resources and its
write-ahead marker; reconcile any interruption rather than re-running setup.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import http.cookiejar
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.plans import data_digest
from modular_platform.release_staging import validate_core_upgrade
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL,SEED,command
from qualify_release_reader_rollout import files
import r1,r1_probe


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image-id',required=True);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--port',type=int,default=18077);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to(ROOT/'docs/evidence/G5') and not output.exists()
    private=ROOT/'.local/g5/asset-clones';private.mkdir(exist_ok=True)
    marker=private/(output.name+'.json');assert not marker.exists()
    config=json.loads((ROOT/'.local/operator/targets/g5.json').read_text(encoding='utf-8'));assert config['generation']==22 and config['project']=='mp-r0-r1g5fd0445d406d6'
    validator=configuration(ROOT/'.local/operator/trust.json');catalog=Catalog(ROOT/'.local/operator/catalog',validator,readonly=True).snapshot()
    observer=DockerObserver(config);observation=observer.read();before=observer.state(observation,catalog)['state'];runtime=inspect_image(args.image_id)
    diff,core=validate_core_upgrade(observation['runtime'],runtime,{'base_image_id':config['image_id'],'target_image_id':args.image_id})
    assert core==[{'addon':'mp_shell','previous_version':'19.0.0.1.2','target_version':'19.0.0.1.3','migrations':[]}]
    token=uuid4().hex[:16];database='mp_disposable_r0_r1_assets_'+token;volume='mp-r1-assets-'+token
    app=volume+'-app';maintenance=volume+'-maintenance';edge=volume+'-edge';network=volume+'-edge-network';port=args.port
    assert 18000<=port<19000
    with socket.socket() as check:check.bind(('127.0.0.1',port))
    db=observer._container('db');nonce=uuid4().hex;synthetic_url='/web/assets/'+nonce[:7]+'/mp_shell.assets_host.min.js'
    record={'state':'preparing','database':database,'volume':volume,'app':app,'maintenance':maintenance,'edge':edge,'network':network,'port':port,
        'image_id':args.image_id,'inventory_digest':runtime['inventory_digest'],'source_database':config['sites'][0]['database'],
        'source_state_digest':data_digest(before),'synthetic_url':synthetic_url,'nonce':nonce,'experimental_not_approved_release':True}
    output.mkdir(parents=True)
    def phase(name):
        record.update(state=name,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    def sql(query,name=database):return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',name],input=query.encode())
    def container(name):
        return ['docker','run','--name',name,'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--network',config['project']+'_runtime','--memory','1536m','--pids-limit','256','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777',
            '--mount','type=volume,source='+volume+',target=/run/secrets,volume-subpath=config,readonly',
            '--mount','type=volume,source='+volume+',target=/var/lib/modular,volume-subpath=data']
    def child(name,image,arguments,*,payload=None):
        result=subprocess.run(container(name)+(['-i'] if payload is not None else [])+['--entrypoint','/venv/bin/python',image]+arguments,
            input=payload,capture_output=True,timeout=240)
        (private/(output.name+'-'+name.removeprefix(volume+'-')+'.log')).write_bytes(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Bounded asset clone child failed: '+name)
        return result.stdout
    phase('copying_source')
    business=json.loads(sql(BUSINESS_SQL,record['source_database']));assert len(business['notes'])==4 and business['boards'][0]['revision']==2
    old_assets_query="SELECT jsonb_agg(jsonb_build_object('url',url,'checksum',checksum,'mimetype',mimetype,'store_fname',store_fname) ORDER BY url,id) FROM ir_attachment WHERE public AND res_model='ir.ui.view' AND res_id=0 AND create_uid=1 AND url LIKE '/web/assets/%/mp_shell.assets_host%';"
    old_assets=json.loads(sql(old_assets_query,record['source_database']));assert old_assets and any(row['url'].endswith('.min.js') for row in old_assets)
    old_files=files(observer)
    owner=sql('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database();',record['source_database']).decode().strip()
    assert owner.replace('_','a').isalnum()
    archive=command(['docker','exec',db,'pg_dump','-U','postgres','-Fc',record['source_database']])
    command(['docker','exec',db,'createdb','-U','postgres','-T','template0','-O',owner,database])
    command(['docker','exec','-i',db,'pg_restore','-U','postgres','--exit-on-error','--no-owner','--role',owner,'-d',database],input=archive)
    assert json.loads(sql(BUSINESS_SQL))==business
    command(['docker','volume','create','--label','modular.disposable=asset-retention',volume])
    command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN',
        '--mount','type=volume,source='+config['project']+'_appconfig,target=/source,readonly',
        '--mount','type=volume,source='+config['project']+'_filestore,target=/old,readonly',
        '--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',args.image_id,'-c',SEED],
        input=json.dumps({'database':database,'source_database':record['source_database']}).encode())
    phase('seeding_public_asset_fixture')
    fixture_bytes=('/* public asset retention fixture '+nonce+' */').encode()
    seed="assert env.cr.dbname=="+repr(database)+"\na=env['ir.attachment'].with_user(1).create({'name':'mp_shell.assets_host.min.js','url':"+repr(synthetic_url)+",'mimetype':'application/javascript','public':True,'res_model':'ir.ui.view','res_id':0,'type':'binary','raw':"+repr(fixture_bytes)+"});env.cr.commit()\n"
    child(volume+'-seed',config['image_id'],['odoo-bin','shell','-c','/run/secrets/odoo_config','-d',database,'--no-http','--workers=0','--max-cron-threads=0'],payload=seed.encode())
    phase('migrating_shell')
    child(maintenance,args.image_id,['odoo-bin','-c','/run/secrets/odoo_config','-d',database,'-u','mp_shell','--stop-after-init','--no-http','--workers=0','--max-cron-threads=0','--without-demo'])
    assert sql("SELECT latest_version FROM ir_module_module WHERE name='mp_shell';").strip()==b'19.0.0.1.3'
    assert json.loads(sql(BUSINESS_SQL))==business
    generation=23;digest=data_digest({'experimental_asset_clone':token,'generation':generation,'inventory':runtime['inventory_digest']})
    sql("UPDATE ir_config_parameter SET value=CASE key WHEN 'mp.release_generation' THEN '23' WHEN 'mp.release_digest' THEN '"+digest+"' ELSE '"+runtime['inventory_digest']+"' END WHERE key IN ('mp.release_generation','mp.release_digest','mp.active_inventory_digest');")
    phase('preparing_assets_offline')
    payload={'database':database,'site_id':config['sites'][0]['site_id'],'deployment_id':config['deployment_id'],'generation':23,'release_digest':digest,'inventory_digest':runtime['inventory_digest']}
    raw=child(volume+'-assets',args.image_id,['-c',(ROOT/'packages/platform_sdk/modular_platform/prepare_assets.py').read_text(encoding='utf-8')],payload=json.dumps(payload).encode())
    prepared=json.loads(raw);assert prepared['result']=='prepared' and len(prepared['assets'])>=2
    (output/'prepared-assets.json').write_text(json.dumps(prepared,indent=2)+'\n',encoding='utf-8')
    all_assets=json.loads(sql(old_assets_query));assert all(row in all_assets for row in old_assets)
    phase('starting_guarded_worker')
    start=container(app);start.insert(2,'-d')
    command(start+['-e','MP_EXPECTED_DATABASE='+database,'-e','MP_EXPECTED_INVENTORY_DIGEST='+runtime['inventory_digest'],args.image_id])
    nginx='server {listen 8069; server_name _; location ^~ /web/database {return 403;} location / {proxy_set_header Host $http_host; proxy_pass http://'+app+':8069;}}'
    command(['docker','run','--rm','--network','none','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',args.image_id,'-c',"import pathlib,sys;p=pathlib.Path('/probe/edge');p.mkdir();(p/'clone.conf').write_text(sys.argv[1]);(p/'clone.conf').chmod(0o444)",nginx])
    command(['docker','network','create','--label','modular.disposable=asset-retention',network])
    nginx_image=command(['docker','inspect',observer._container('edge'),'--format','{{.Image}}']).decode().strip()
    command(['docker','create','--name',edge,'--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',network,'--publish','127.0.0.1:'+str(port)+':8069','--tmpfs','/var/cache/nginx:rw,nosuid,nodev,noexec,mode=1777','--tmpfs','/var/run:rw,nosuid,nodev,noexec,mode=1777','--mount','type=volume,source='+volume+',target=/etc/nginx/conf.d,volume-subpath=edge,readonly',nginx_image])
    command(['docker','network','connect',config['project']+'_runtime',edge]);command(['docker','start',edge])
    fixture=json.loads((ROOT/'.local/g5/fixtures.json').read_text(encoding='utf-8'));fixture['bindings']={}
    for key,space in fixture['workspaces'].items():
        installation=next(row for row in before['installations'] if row['plugin_id']=='org.example.notes' and row['workspace_id']==space['public_id'])
        fixture['bindings'][key]=next(row for row in before['bindings'] if row['consumer_installation_id']==installation['installation_id'] and row['workspace_id']==space['public_id'] and row['alias']=='documents')
    r1.r0.LOCAL=ROOT/'.local/g5';until=time.monotonic()+40
    while True:
        try:client=r1_probe.Client({'active_db':database,'port':port},fixture);break
        except (OSError,AssertionError):
            if time.monotonic()>until:raise
            time.sleep(.3)
    no_redirect=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(client.jar),NoRedirect())
    results=[]
    for asset in old_assets+prepared['assets']+[{'url':synthetic_url,'checksum':hashlib.sha1(fixture_bytes).hexdigest(),'mimetype':'application/javascript'}]:
        with no_redirect.open(client.base+asset['url'],timeout=30) as response:
            body=response.read();assert response.status==200 and response.geturl()==client.base+asset['url']
            if 'checksum' in asset:assert hashlib.sha1(body).hexdigest()==asset['checksum']
            if 'sha256' in asset:assert hashlib.sha256(body).hexdigest()==asset['sha256']
            assert response.headers.get_content_type()==asset['mimetype'] and 'immutable' in response.headers.get('Cache-Control','')
            results.append({'url':asset['url'],'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'status':200,'redirected':False})
    row=next(row for row in business['notes'] if row['workspace_id']==1);client.call('get',{'note_id':row['public_id']});client.native('read',[[row['id']],['title']])
    assert json.loads(sql(BUSINESS_SQL))==business and observer.state(observer.read(),catalog)['state']==before
    assert json.loads(sql(BUSINESS_SQL,record['source_database']))==business
    report={'result':'passed_native_asset_clone','utc':datetime.now(timezone.utc).isoformat(),'database':database,'image_id':args.image_id,'inventory_digest':runtime['inventory_digest'],
        'native_shell_version':'19.0.0.1.3','generation':23,'experimental_not_approved_release':True,'old_actual_host_assets':len(old_assets),'prepared_before_worker':prepared['assets'],
        'synthetic_distinct_old_public_payload_retained':True,'http_assets':results,'current_pin_native_gateway_positive':True,'original_business_exact':True,'operated_source_unchanged':True,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':['Actual candidate clone, not independent executor/restore/normal rollout qualification.','Preflight covers regular minified host assets; full locale/RTL/accessibility qualification remains G7.','Assets deleted by historical legacy releases are not retroactively recreated.']}
    (output/'asset-retention.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');record.update(generation=23,release_digest=digest,business_digest=data_digest(business));phase('qualified_native_http')
    print(json.dumps({'result':report['result'],'database':database,'port':port,'assets':len(results),'source_unchanged':True}))


if __name__=='__main__':main()
