"""Explicit isolated G5 core bootstrap for real manager install/upgrade tests.

Never operates on the main G5 project. Reference plugins start uninstalled and
must enter through the normal manager request/independent executor path.
"""
import argparse
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

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-manager-upgrade-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import protect_directory,OperationLocks
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.release_staging import StageStore,validate_plugin_core_stability
from modular_platform.workers import ensure,wait_ready
from modular import configuration
import r0


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def command(arguments,*,input=None):
    p=subprocess.run(arguments,input=input,capture_output=True,timeout=180,cwd=ROOT)
    if p.returncode:raise RuntimeError('Fixture command failed; inspect fixed target and retained diagnostics')
    return p.stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','init','publish-stage','inspect']);parser.add_argument('--image-id');args=parser.parse_args()
    main_path=ROOT/'.local/operator/targets/g5.json';main_hash=hashlib.sha256(main_path.read_bytes()).hexdigest()
    def guard():
        assert hashlib.sha256(main_path.read_bytes()).hexdigest()==main_hash,'Main target changed during isolated qualification'
    if args.action=='setup':
        assert not LOCAL.exists() and args.image_id
        runtime=inspect_image(args.image_id);target_runtime=inspect_image('sha256:2c7eeda91f213aea51091f1c7a2523a04c3fb51b2c30f4dd12d292da55544383')
        validate_plugin_core_stability(runtime,target_runtime)
        identity=json.loads((OUTPUT/'baseline-artifact-identity.json').read_text(encoding='utf-8'))
        assert runtime['inventory']['artifacts']['org.example.notes']['digest']==identity['artifact_digest']
        protect_directory(LOCAL);protect_directory(LOCAL/'logs');protect_directory(LOCAL/'operator')
        nonce=secrets.token_hex(6);project='mp-r0-r1mgr'+nonce;database='mp_disposable_r0_r1_g5_mgr_'+nonce
        for port in range(18079,18100):
            try:
                with socket.socket() as sock:sock.bind(('127.0.0.1',port))
                break
            except OSError:continue
        else:raise RuntimeError('No free named fixture port')
        for name in ['postgres-password','app-db-password','bootstrap-password','database-master-password']:
            (LOCAL/name).write_text(secrets.token_urlsafe(32)+'\n',encoding='utf-8')
        config=configparser.ConfigParser();config['options']={'db_host':'db','db_port':'5432','db_user':'modular',
            'db_password':(LOCAL/'app-db-password').read_text().strip(),'admin_passwd':(LOCAL/'database-master-password').read_text().strip(),
            'db_name':database,'dbfilter':'^'+database+'$','list_db':'False','data_dir':'/var/lib/modular','addons_path':'/opt/modular/addons',
            'server_wide_modules':'base,web','without_demo':'True','max_cron_threads':'0','workers':'2','db_maxconn':'12',
            'http_interface':'0.0.0.0','proxy_mode':'False','limit_memory_soft':'536870912','limit_memory_hard':'671088640'}
        with (LOCAL/'odoo.conf').open('x',encoding='utf-8') as stream:config.write(stream)
        state={'phase':'configured','disposable':True,'project':project,'active_db':database,'databases':[database],'image_id':args.image_id,
            'port':port,'url':'http://g5upgrade.localhost:'+str(port),'variant':'v1','evidence':OUTPUT.relative_to(ROOT).as_posix(),
            'site_id':str(uuid4()),'deployment_id':str(uuid4()),'bootstrap_id':str(uuid4()),'runtime_inventory_digest':runtime['inventory_digest'],
            'main_target_sha256':main_hash,'created_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        write(LOCAL/'state.json',state)
        store=OperatorStore.initialize(LOCAL/'operator/control',{state['deployment_id']:[state['site_id']]},allow_noninteractive=True)
        state.update(policy_version=store.policy['policy_version'],operator_authorization_generation=store.policy['authorization_generation'])
        (LOCAL/'compose.env').write_text('MP_COMPOSE_PROJECT='+project+'\nMP_HTTP_PORT='+str(port)+'\nMP_IMAGE='+args.image_id+'\nMP_FIXTURE_VARIANT=v1\n',encoding='utf-8')
        r0.LOCAL=LOCAL;r0.seed_volumes(state)
        command(['docker','volume','create','--label','com.modular.disposable='+project,project+'_filestore'])
        write(LOCAL/'state.json',state);write(OUTPUT/'fixture-setup.json',{key:value for key,value in state.items() if key!='bootstrap_id'})
        guard();print(json.dumps({'result':'isolated_fixture_configured','project':project,'database':database,'port':port,'image_id':args.image_id}));return
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));assert state['disposable'] and state['project'].startswith('mp-r0-r1mgr') and state['main_target_sha256']==main_hash
    project=state['project'];database=state['active_db'];target_path=LOCAL/'operator/target.json';catalog_root=ROOT/'.local/operator/catalog';validator=configuration(ROOT/'.local/operator/trust.json');catalog=Catalog(catalog_root,validator,readonly=True);store=OperatorStore(LOCAL/'operator/control')
    compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml')]
    config={'schema_version':1,'deployment_id':state['deployment_id'],'project':project,'sites':[{'site_id':state['site_id'],'database':database}],
        'image_id':state['image_id'],'generation':1,'policy_version':state['policy_version'],
        'operator_authorization_generation':state['operator_authorization_generation'],'release_created_at':state['created_at']}
    def phase(value):
        state.update(phase=value,utc=datetime.now(timezone.utc).isoformat());write(LOCAL/'state.json',state)
    def sql(query,db=database):
        return command(['docker','exec','-i',project+'-db-1','psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',db],input=query.encode())
    def native(label,arguments,code=None):
        phase(label)
        argv=['docker','run','--name',project+'-'+label,'--label','com.modular.disposable='+project,'--network',project+'_runtime',
            '--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','1536m','--cpus','2',
            '--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly',
            '--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular',
            '--mount','type=volume,source='+project+'_bootstrap,target=/run/mp-bootstrap,readonly','--entrypoint','/venv/bin/python',state['image_id'],'odoo-bin']
        if code is not None:argv.insert(2,'-i');argv+=['shell']
        argv+=['-c','/run/secrets/odoo_config','-d',database,'--no-http','--workers=0','--max-cron-threads=0']+arguments
        with (LOCAL/'logs'/(label+'.log')).open('xb') as log:
            result=subprocess.run(argv,cwd=ROOT,input=code.encode() if code else None,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        assert result.returncode==0,'Native bootstrap failed; retained named child/private log, do not repeat'
    if args.action=='init':
        assert state['phase']=='configured','Bootstrap already attempted; inspect phase/children without repeating'
        phase('starting_database');command(compose+['up','-d','--wait','--no-deps','db'])
        assert sql("SELECT count(*) FROM pg_database WHERE datname='"+database+"';",'postgres').strip()==b'0'
        command(['docker','exec',project+'-db-1','createdb','-U','postgres','-O','modular','-T','template0',database]);phase('database_created')
        sql('COMMENT ON DATABASE '+database+" IS 'Modular Platform disposable manager upgrade qualification';")
        native('core_init',['-i','mp_shell,auth_password_policy','--stop-after-init','--without-demo'])
        code=(ROOT/'tools/g5_seed.py').read_text(encoding='utf-8').replace('G5_SITE_UUID',state['site_id']).replace('G5_DEPLOYMENT_UUID',state['deployment_id'])
        native('core_seed',[],code)
        rows=[line.split('MP_G5_RESULT=',1)[1] for line in (LOCAL/'logs/core_seed.log').read_text(encoding='utf-8',errors='replace').splitlines() if line.startswith('MP_G5_RESULT=')];assert len(rows)==1
        write(LOCAL/'fixtures.json',json.loads(rows[0]));phase('publishing_bootstrap_release')
        observer=DockerObserver(config);observation=observer.read(quiesced=True,missing_worker=True);document=observer.state(observation,catalog.snapshot());lock=document['state']['release_lock'];config['published_release']=lock
        for key,value in {'mp.release_digest':data_digest(lock),'mp.active_inventory_digest':state['runtime_inventory_digest']}.items():
            sql("INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date) VALUES ('"+key+"','"+value+"',1,1,timezone('UTC',now()),timezone('UTC',now())) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value;")
        phase('starting_guarded_worker');worker=ensure(config,config['image_id'],state['bootstrap_id'],inventory_digest=state['runtime_inventory_digest']);config['worker_id']=worker;write(target_path,config);command(['docker','start',worker]);wait_ready(worker)
        observer=DockerObserver(config);observation=observer.read();document=observer.state(observation,catalog.snapshot());assert not document['state']['installations']
        assert json.loads(sql("SELECT jsonb_build_object('notes',to_regclass('mp_example_note') IS NOT NULL,'canvas',to_regclass('mp_example_canvas_board') IS NOT NULL);"))=={'notes':False,'canvas':False}
        phase('preparing_bootstrap_assets');directory=protect_directory(LOCAL/'operator/bootstrap-assets');NativeExecutor(store,target_path,catalog_root,validator)._prepare_assets(state['bootstrap_id'],config,document['state'],observation,directory)
        publish_profile(observer,catalog);phase('starting_edge');command(compose+['up','-d','--no-deps','edge']);phase('core_only_ready')
        write(OUTPUT/'core-only-bootstrap.json',{'result':'isolated_core_ready_reference_native_models_absent','configuration':config,'port':state['port'],'url':state['url'],'no_reference_installations':True,'notes_table_absent':True,'canvas_table_absent':True,'assets_prepared_before_edge':True,'separate_operator_allowlist':True,'main_target_unchanged':True,'limits':['This is explicit trusted core bootstrap; reference plugins still require real manager/independent local approval.']})
    elif args.action=='publish-stage':
        config=json.loads(target_path.read_text(encoding='utf-8'));stages=StageStore(store,config,catalog)
        if args.image_id:stages.stage(args.image_id)
        with OperationLocks(store.root/'locks',config['deployment_id'],[item['site_id'] for item in config['sites']]):
            assert json.loads(target_path.read_text(encoding='utf-8'))==config
            staged=stages.load();result=publish_profile(DockerObserver(config),catalog,staged=staged)
        print(json.dumps(result));guard();return
    elif args.action=='inspect':
        print(json.dumps({'fixture':{key:state[key] for key in ['phase','project','active_db','port','image_id']},'containers':command(compose+['ps','--all','--format','json']).decode()}));guard();return
    guard();print(json.dumps({'result':state['phase'],'project':project,'port':state['port'],'database':database}))


if __name__=='__main__':main()
