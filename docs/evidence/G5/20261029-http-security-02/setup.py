"""Own PG/app/dev edge/local TLS edge; existing deployments are read only."""
import configparser
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity';SOURCE=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from modular_platform.profile_channel import publish_profile
from modular_platform.plans import data_digest
from modular_platform.workers import wait_ready
from http_profile import render,validate_production_config
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
import r0

COPY="""import json,os,pathlib,shutil,sys
d=json.load(sys.stdin);root=pathlib.Path('/target');assert not (root/'filestore').exists();(root/'filestore').mkdir();shutil.copytree(pathlib.Path('/source/filestore')/d['source'],root/'filestore'/d['database'])
for p in [root,*(root.rglob('*'))]:os.chown(p,10001,10001)
"""
TLS="""from cryptography import x509
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from datetime import datetime,timedelta,timezone
import ipaddress,os,pathlib
root=pathlib.Path('/tls');assert not (root/'server.key').exists();key=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'security.localhost qualification only')]);now=datetime.now(timezone.utc)
cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName('security.localhost'),x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(key,hashes.SHA256())
(root/'server.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));(root/'server.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
for p in root.iterdir():p.chmod(0o400 if p.suffix=='.key' else 0o444);os.chown(p,101,101)
print('Local two-day qualification certificate generated; private key not displayed')
"""
NGINX='nginx:stable-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951'


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));assert not LOCAL.exists();protect_directory(LOCAL);(OUTPUT/'setup').mkdir()
    source=load(SOURCE/'operator/target.json');source_state=load(SOURCE/'state.json');assert source['generation']==18;reader=DockerObserver(source);business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    for port in [18082,18083,18443]:
        with socket.socket() as sock:sock.bind(('127.0.0.1',port))
    token=uuid4().hex[:12];project='mp-r0-r1http'+token;database='mp_disposable_r0_r1_http_'+token;site=str(uuid4());deployment=str(uuid4());origin='https://security.localhost:18443'
    state=dict(disposable=True,project=project,active_db=database,databases=[database],image_id=source['image_id'],inventory_digest=source['published_release']['core_inventory_digest'],generation=18,site_id=site,phase='preparing',origin=origin,port=18082,https_port=18443,redirect_port=18083,evidence=(OUTPUT/'setup').relative_to(ROOT).as_posix(),variant='v1',operator_trust_config=source_state['operator_trust_config'],operator_catalog=source_state['operator_catalog'],containers=[])
    def phase(value):state.update(phase=value,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'setup.stderr').write_bytes(r.stderr);raise RuntimeError('Inspect exact owned state and diagnostics; never reset or recreate')
        return r.stdout
    phase('preparing')
    for name in ['postgres-password','app-db-password','bootstrap-password','database-master-password','retired-admin-password']:(LOCAL/name).write_text(secrets.token_urlsafe(32)+'\n',encoding='utf8')
    fixture=load(SOURCE/'fixtures.json');accounts={}
    for actor in ['alice','bob','operator']:
        password=secrets.token_urlsafe(32);(LOCAL/('password-'+actor)).write_text(password+'\n',encoding='utf8');accounts[actor]=dict(id=fixture['users'][actor]['id'],login='sec_'+actor+'_'+token,password=password);fixture['users'][actor]['login']=accounts[actor]['login']
    original=command(['docker','exec',source['worker_id'],'/venv/bin/python','-c',"from pathlib import Path;print(Path('/run/secrets/odoo_config').read_text(),end='')"]);cfg=configparser.ConfigParser();cfg.read_string(original.decode());cfg['options'].update(db_name=database,dbfilter='^'+database+'$',db_password=(LOCAL/'app-db-password').read_text(encoding='utf8').strip(),admin_passwd=(LOCAL/'database-master-password').read_text(encoding='utf8').strip(),workers='2',max_cron_threads='0',proxy_mode='True',log_handler=':INFO,werkzeug:ERROR')
    with (LOCAL/'odoo.conf').open('x',encoding='utf8') as stream:cfg.write(stream)
    validate_production_config(LOCAL/'odoo.conf');production=render('production',origin);(LOCAL/'production.conf').write_text(production,encoding='utf8')
    (LOCAL/'compose.env').write_text('MP_COMPOSE_PROJECT='+project+'\nMP_HTTP_PORT=18082\nMP_IMAGE='+source['image_id']+'\n',encoding='utf8');r0.LOCAL=LOCAL;r0.STATE=LOCAL/'state.json';r0.seed_volumes(state)
    compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml')];phase('starting_owned_database');command(compose+['up','-d','--wait','db']);db=command(compose+['ps','-q','db']).decode().strip();state['db_container']=db
    archive=command(['docker','exec',reader._container('db'),'pg_dump','-U','postgres','--no-owner','-Fc',source['sites'][0]['database']]);(LOCAL/'source.dump').write_bytes(archive);phase('restoring_owned_copy');command(['docker','exec',db,'createdb','-U','postgres','-T','template0','-O','modular',database]);command(['docker','exec','-i',db,'pg_restore','-U','postgres','--no-owner','--role=modular','--exit-on-error','-d',database],input=archive)
    changes="BEGIN; UPDATE ir_config_parameter SET value='"+site+"' WHERE key='mp.site_id'; UPDATE ir_config_parameter SET value='"+deployment+"' WHERE key='mp.deployment_id'; UPDATE ir_config_parameter SET value='"+secrets.token_hex(32)+"' WHERE key='database.secret'; UPDATE mp_service_binding SET descriptor=jsonb_set(descriptor,'{site_id}',to_jsonb('"+site+"'::text)); UPDATE mp_service_credential SET state='revoked'; COMMIT;"
    command(['docker','exec','-i',db,'psql','-X','-q','-U','postgres','-v','ON_ERROR_STOP=1','-d',database],input=changes.encode())
    for suffix in ['filestore','prodproxy','tls']:command(['docker','volume','create','--label','com.modular.qualification=G5-HTTP-security',project+'_'+suffix])
    command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+source['project']+'_filestore,target=/source,readonly','--mount','type=volume,source='+project+'_filestore,target=/target','--entrypoint','/venv/bin/python',source['image_id'],'-c',COPY],input=json.dumps(dict(source=source['sites'][0]['database'],database=database)).encode())
    finish_setup(state,source,production,project,database,accounts,origin,fixture,site,deployment,reader,business,schema,phase,command)


def finish_setup(state,source,production,project,database,accounts,origin,fixture,site,deployment,reader,business,schema,phase,command,*,seeded=False,tls_ready=False):
    if not seeded:
        seed="import sys;from pathlib import Path;p=Path('/proxy/default.conf');assert not p.exists();p.write_text(sys.stdin.read());p.chmod(0o444)";command(['docker','run','--rm','-i','--network','none','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+project+'_prodproxy,target=/proxy','--entrypoint','/venv/bin/python',source['image_id'],'-c',seed],input=production.encode())
    if not tls_ready:command(['docker','run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+project+'_tls,target=/tls','--entrypoint','/venv/bin/python',source['image_id'],'-c',TLS])
    cert=command(['docker','run','--rm','--network','none','--read-only','--mount','type=volume,source='+project+'_tls,target=/tls,readonly','--entrypoint','/venv/bin/python',source['image_id'],'-c',"from pathlib import Path;print(Path('/tls/server.crt').read_text(),end='')"]);(LOCAL/'server.crt').write_bytes(cert)
    phase('explicit_account_provisioning');payload=dict(database=database,inventory_digest=state['inventory_digest'],accounts=accounts,retired_admin_password=(LOCAL/'retired-admin-password').read_text(encoding='utf8').strip(),origin=origin,code=(OUTPUT/'provision_inside.py').read_text(encoding='utf8'))
    provision=command(['docker','run','--rm','-i','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--memory','1024m','--tmpfs','/tmp','--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular','--entrypoint','/venv/bin/python',source['image_id'],'-c',"import json,sys;data=json.load(sys.stdin);exec(compile(data['code'],'explicit_account_provisioning.py','exec'))"],input=json.dumps(payload).encode());result=json.loads(provision);assert result['old_admin_and_fixture_logins_inactive']
    (OUTPUT/'setup/account-provisioning.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    fixture.update(database=database,site_id=site)
    for binding in fixture['bindings'].values():binding['site_id']=site
    (LOCAL/'fixtures.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf8')
    app=command(['docker','create','--name',project+'-app','--label','com.docker.compose.project='+project,'--label','com.docker.compose.service=app','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--network-alias','app','--memory','1536m','--pids-limit','256','--tmpfs','/tmp','--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular','-e','MP_EXPECTED_DATABASE='+database,'-e','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],source['image_id']]).decode().strip();state['containers'].append(dict(purpose='application',container_id=app));phase('starting_guarded_application');command(['docker','start',app]);wait_ready(app)
    command(['docker','network','create','--label','com.modular.qualification=G5-HTTP-security',project+'_edge'])
    for mode,volume,ports in [('development','proxyconfig',[(18082,8069)]),('production','prodproxy',[(18083,8069),(18443,8443)])]:
        args=['docker','create','--name',project+'-edge-'+mode,'--label','com.modular.qualification=G5-HTTP-security','--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--memory','128m','--tmpfs','/tmp','--tmpfs','/var/cache/nginx:uid=101,gid=101,mode=0755','--tmpfs','/var/run:uid=101,gid=101,mode=0755','--mount','type=volume,source='+project+'_'+volume+',target=/etc/nginx/conf.d,readonly']
        if mode=='production':args+=['--mount','type=volume,source='+project+'_tls,target=/etc/mp-tls,readonly']
        for host_port,inner in ports:args+=['-p','127.0.0.1:'+str(host_port)+':'+str(inner)]
        args+=['--entrypoint','nginx',NGINX,'-g','daemon off;'];cid=command(args).decode().strip();state['containers'].append(dict(purpose=mode+'-edge',container_id=cid));command(['docker','network','connect',project+'_edge',cid]);phase('starting_'+mode+'_edge');command(['docker','start',cid]);command(['docker','exec',cid,'nginx','-t'])
    finalize_setup(state,source,production,project,database,origin,site,deployment,reader,business,schema,app,phase,command)


def finalize_setup(state,source,production,project,database,origin,site,deployment,reader,business,schema,app,phase,command):
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    target=dict(source,project=project,deployment_id=deployment,sites=[dict(database=database,site_id=site)],worker_id=app);protect_directory(LOCAL/'operator');(LOCAL/'operator/target.json').write_text(json.dumps(target,indent=2)+'\n',encoding='utf8')
    own=DockerObserver(target);catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True)
    # The new copied site's binding scopes are part of its release lock. This
    # is explicit disposable bootstrap, not lifecycle/install qualification.
    initial=dict(target);initial.pop('published_release');bootstrap=DockerObserver(initial)
    derived=bootstrap.state(bootstrap.read(),catalog.snapshot())['state']['release_lock']
    expected=json.loads(json.dumps(source['published_release']).replace(source['sites'][0]['site_id'],site));assert derived==expected
    previous=data_digest(source['published_release']);current=data_digest(derived)
    actual=json.loads(sql(own,"SELECT to_jsonb(value) FROM ir_config_parameter WHERE key='mp.release_digest';"));assert actual in (previous,current)
    if actual==previous:
        changed=json.loads(sql(own,"UPDATE ir_config_parameter SET value='"+current+"' WHERE key='mp.release_digest' AND value='"+previous+"' RETURNING to_jsonb(value);"));assert changed==current
    target['published_release']=derived;(LOCAL/'operator/target.json').write_text(json.dumps(target,indent=2)+'\n',encoding='utf8');own=DockerObserver(target);publish_profile(own,catalog)
    observed=own.state(own.read(),catalog.snapshot())['state'];assert json.loads(sql(own,SCHEMA))==schema
    assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema and load(SOURCE/'operator/target.json')==source
    for name,value in [('source-business',business),('source-schema',schema),('business-before',json.loads(sql(own,BUSINESS_SQL))),('schema-before',schema),('state-before',observed),('configuration',target)]: (OUTPUT/'setup'/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    phase('profiles_started_ready');report=dict(result='passed_setup_only',project=project,database=database,site_id=site,image_id=source['image_id'],origin=origin,ports=dict(development=18082,redirect=18083,TLS=18443),config_sha256=hashlib.sha256((LOCAL/'odoo.conf').read_bytes()).hexdigest(),development_proxy_sha256=hashlib.sha256((ROOT/'deploy/nginx-r0.conf').read_bytes()).hexdigest(),production_proxy_sha256=hashlib.sha256(production.encode()).hexdigest(),private_TLS_generated=True,accounts_explicitly_rotated=True,old_sample_and_admin_logins_inactive=True,guarded_startup=True,source_target_unchanged=True,acceptance_not_yet_qualified=True)
    (OUTPUT/'setup/qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))


if __name__=='__main__':main()
