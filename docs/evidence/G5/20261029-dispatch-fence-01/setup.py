"""New isolated project for an actual recovery/dispatch guard experiment."""
import configparser
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent/'setup';LOCAL=ROOT/'.local/g5-dispatch';SOURCE=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.profile_channel import publish_profile
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
import r0

SEED="""import json,os,pathlib,shutil,sys
data=json.load(sys.stdin);target=pathlib.Path('/target');source=pathlib.Path('/source/filestore')/data['source']
assert not (target/'filestore').exists()
(target/'filestore').mkdir();shutil.copytree(source,target/'filestore'/data['database'])
for p in [target,*(target.rglob('*'))]:os.chown(p,10001,10001)
"""


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));assert not LOCAL.exists() and not OUTPUT.exists();protect_directory(LOCAL);OUTPUT.mkdir()
    source=load(SOURCE/'operator/target.json');source_state=load(SOURCE/'state.json');assert source['generation']==18 and source['project']=='mp-r0-r1lifef99acae9d906'
    reader=DockerObserver(source);before=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    nonce=uuid4().hex[:12];project='mp-r0-r1disp'+nonce;database='mp_disposable_r0_r1_disp_'+nonce;deployment=str(uuid4())
    for port in range(18081,18101):
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port));break
            except OSError:continue
    else:raise RuntimeError('No loopback fixture port available')
    state=dict(disposable=True,project=project,active_db=database,databases=[database],port=port,image_id=source['image_id'],generation=18,phase='setup_preparing',variant='v1',evidence=OUTPUT.relative_to(ROOT).as_posix(),site_id=source['sites'][0]['site_id'],operator_catalog=source_state['operator_catalog'],operator_trust_config=source_state['operator_trust_config'])
    def phase(value):
        state.update(phase=value,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    phase('setup_preparing')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'setup.stderr').write_bytes(r.stderr);raise RuntimeError('Fixture setup failed; reconcile exact owned targets without reset/recreation')
        return r.stdout
    original=command(['docker','exec',source['worker_id'],'/venv/bin/python','-c',"from pathlib import Path;print(Path('/run/secrets/odoo_config').read_text(),end='')"])
    parser=configparser.ConfigParser();parser.read_string(original.decode());options=parser['options']
    for name in ['postgres-password','app-db-password','database-master-password']:(LOCAL/name).write_text(secrets.token_urlsafe(32)+'\n',encoding='utf8')
    (LOCAL/'bootstrap-password').write_bytes((SOURCE/'bootstrap-password').read_bytes())
    options.update(db_name=database,dbfilter='^'+database+'$',db_password=(LOCAL/'app-db-password').read_text(encoding='utf8').strip(),admin_passwd=(LOCAL/'database-master-password').read_text(encoding='utf8').strip())
    assert options.get('addons_path')=='/opt/modular/addons' and options.getint('max_cron_threads')==0
    with (LOCAL/'odoo.conf').open('x',encoding='utf8') as stream:parser.write(stream)
    (LOCAL/'compose.env').write_text('MP_COMPOSE_PROJECT='+project+'\nMP_HTTP_PORT='+str(port)+'\nMP_IMAGE='+source['image_id']+'\n',encoding='utf8')
    override={'services':{'app':{'command':['-c','/run/secrets/odoo_config'],'environment':{'MP_EXPECTED_DATABASE':database,'MP_EXPECTED_INVENTORY_DIGEST':source['published_release']['core_inventory_digest']}}}}
    (LOCAL/'compose.override.json').write_text(json.dumps(override,indent=2)+'\n',encoding='utf8')
    r0.LOCAL=LOCAL;r0.STATE=LOCAL/'state.json';r0.seed_volumes(state)
    compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml'),'-f',str(LOCAL/'compose.override.json')]
    phase('starting_new_database');command(compose+['up','-d','--wait','db'])
    db=command(compose+['ps','-q','db']).decode().strip();assert db
    phase('importing_source_copy');archive=command(['docker','exec',reader._container('db'),'pg_dump','-U','postgres','--no-owner','-Fc',source['sites'][0]['database']])
    (LOCAL/'source.dump').write_bytes(archive)
    command(['docker','exec',db,'createdb','-U','postgres','-O','modular',database]);command(['docker','exec','-i',db,'pg_restore','-U','postgres','--no-owner','--role=modular','--exit-on-error','-d',database],input=archive)
    reset="UPDATE ir_config_parameter SET value='"+deployment+"' WHERE key='mp.deployment_id'; UPDATE ir_config_parameter SET value='"+secrets.token_hex(32)+"' WHERE key='database.secret'; UPDATE mp_service_credential SET state='revoked';"
    command(['docker','exec','-i',db,'psql','-X','-q','-U','postgres','-v','ON_ERROR_STOP=1','-d',database],input=reset.encode())
    phase('creating_stopped_worker_edge');command(compose+['create','--no-build','app','edge'])
    command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+source['project']+'_filestore,target=/source,readonly','--mount','type=volume,source='+project+'_filestore,target=/target','--entrypoint','/venv/bin/python',source['image_id'],'-c',SEED],input=json.dumps(dict(source=source['sites'][0]['database'],database=database)).encode())
    phase('starting_guarded_copy');command(compose+['start','app','edge'])
    app=command(compose+['ps','-q','app']).decode().strip();app=json.loads(command(['docker','inspect',app]))[0]['Id']
    target=dict(source,project=project,deployment_id=deployment,sites=[dict(source['sites'][0],database=database)],worker_id=app)
    protect_directory(LOCAL/'operator');(LOCAL/'operator/target.json').write_text(json.dumps(target,indent=2)+'\n',encoding='utf8')
    OperatorStore.initialize(LOCAL/'operator/control',{deployment:[state['site_id']]},allow_noninteractive=True)
    from modular_platform.workers import wait_ready
    wait_ready(app)
    fixture=load(SOURCE/'fixtures.json');fixture['database']=database;(LOCAL/'fixtures.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf8')
    observer=DockerObserver(target);catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True)
    observed=observer.state(observer.read(),catalog.snapshot())['state'];assert observed['installations'] and len(observed['installations'])==6
    assert json.loads(sql(observer,BUSINESS_SQL))==before and json.loads(sql(observer,SCHEMA))==schema
    publish_profile(observer,catalog)
    assert json.loads(sql(reader,BUSINESS_SQL))==before and json.loads(sql(reader,SCHEMA))==schema
    phase('setup_verified');report=dict(result='passed_new_disposable_recovery_fixture',project=project,deployment_id=deployment,site_id=state['site_id'],database=database,port=port,image_id=source['image_id'],generation=18,source_target_configuration_exact=load(SOURCE/'operator/target.json')==source,source_business_schema_exact=True,copied_reference_business_schema_exact=True,new_private_control_store=True,technical_credentials_revoked=True,session_secret_rotated=True)
    for name,value in [('setup.json',report),('state-before.json',observed),('business-before.json',before),('schema-before.json',schema),('configuration-before.json',target)]: (OUTPUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':main()
