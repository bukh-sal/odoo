"""Once-only G6 native job/event fixture; never copies an existing database.

Core bootstrap is explicit OS-operator initialization. Every reference plugin
then enters through the normal immutable plan/register/approve/apply path.
"""
import argparse,configparser,hashlib,io,json,secrets,shutil,socket,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local/g6';OUTPUT=ROOT/'docs/evidence/G6/20261029-durable-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk')]
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.native_executor import NativeExecutor
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
from modular_platform.plans import data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.workers import ensure,wait_ready
from modular import configuration

PROTECTED=['.local/operator/targets/g5.json','.local/g5-manager-upgrade/operator/target.json','.local/g5-lifecycle/operator/target.json','.local/g5-dispatch/operator/target.json','.local/g5-httpsecurity/operator/target.json','.local/g5-clean-recovery/operator/target.json']
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def save(name,value):
 path=OUTPUT/name;assert not path.exists();write(path,value)
def phase(state,value):state.update(phase=value,utc=datetime.now(timezone.utc).isoformat());write(LOCAL/'state.json',state);print(json.dumps(dict(phase=value,project=state['project'])),flush=True)
def guard(state):assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in state['protected_configurations'].items())
def command(label,args,*,input=None,timeout=180):
 # Raw native/config diagnostics never enter tracked evidence or Docker logs.
 prefix=LOCAL/'logs'/label;assert not prefix.with_suffix('.stdout').exists()
 with prefix.with_suffix('.stdout').open('xb') as stdout,prefix.with_suffix('.stderr').open('xb') as stderr:r=subprocess.run(args,input=input,stdout=stdout,stderr=stderr,timeout=timeout,cwd=ROOT)
 assert r.returncode==0,'Inspect exact private step logs/marker; do not repeat mutation'
 return prefix.with_suffix('.stdout').read_bytes()
def sql(state,label,query,*,database=None):
 return command(label,['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',database or state['active_db'],'-v','ON_ERROR_STOP=1'],input=query.encode())
def native(state,label,args,code=None):
 phase(state,label);argv=['docker','run','--name',state['project']+'-'+label,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','1536m','--pids-limit','128','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--mount','type=volume,source='+state['project']+'_bootstrap,target=/run/mp-bootstrap,readonly','--entrypoint','/venv/bin/python',state['image_id'],'odoo-bin']
 if code is not None:argv.insert(2,'-i');argv+=['shell']
 return command(label,argv+['-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0']+args,input=code.encode() if code else None,timeout=300)
def configure():
 assert not LOCAL.exists();OUTPUT.mkdir(parents=True,exist_ok=False);protect_directory(LOCAL);protect_directory(LOCAL/'logs');protect_directory(LOCAL/'operator');source=ROOT/'.local/operator';shutil.copyfile(source/'trust.json',LOCAL/'operator/trust.json');shutil.copytree(source/'catalog',LOCAL/'operator/catalog',copy_function=shutil.copyfile)
 build=load(ROOT/'docs/evidence/G6/20261029-durable-candidate-01/candidate-build.json');image=build['image_id'];runtime=inspect_image(image);assert runtime['inventory_digest']==build['inventory_digest'] and runtime['native_manifests']['mp_core']['version']=='19.0.0.1.7';nonce=secrets.token_hex(6);project='mp-r0-r1g6'+nonce;database='mp_disposable_r0_r1_g6_'+nonce
 for port in range(18085,18100):
  try:
   with socket.socket() as sock:sock.bind(('127.0.0.1',port))
   break
  except OSError:continue
 else:raise RuntimeError('No free disposable port')
 for name in ['postgres-password','app-db-password','bootstrap-password','database-master-password']:(LOCAL/name).write_text(secrets.token_urlsafe(32)+'\n',encoding='utf8')
 cfg=configparser.ConfigParser();cfg['options']=dict(db_host='db',db_port='5432',db_user='modular',db_password=(LOCAL/'app-db-password').read_text().strip(),admin_passwd=(LOCAL/'database-master-password').read_text().strip(),db_name=database,dbfilter='^'+database+'$',list_db='False',data_dir='/var/lib/modular',addons_path='/opt/modular/addons',server_wide_modules='base,web',without_demo='True',max_cron_threads='0',workers='2',db_maxconn='12',http_interface='0.0.0.0',proxy_mode='True',limit_memory_soft='536870912',limit_memory_hard='671088640',log_handler=':INFO,werkzeug:WARNING')
 with (LOCAL/'odoo.conf').open('x',encoding='utf8') as stream:cfg.write(stream)
 state=dict(phase='configured',disposable=True,project=project,active_db=database,databases=[database],image_id=image,inventory_digest=runtime['inventory_digest'],port=port,url='http://g6.localhost:'+str(port),site_id=str(uuid4()),deployment_id=str(uuid4()),bootstrap_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),protected_configurations={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in PROTECTED});write(LOCAL/'state.json',state)
 store=OperatorStore.initialize(LOCAL/'operator/control',{state['deployment_id']:[state['site_id']]},allow_noninteractive=True);state.update(policy_version=store.policy['policy_version'],operator_authorization_generation=store.policy['authorization_generation']);write(LOCAL/'state.json',state)
 (LOCAL/'compose.env').write_text('MP_COMPOSE_PROJECT='+project+'\nMP_HTTP_PORT='+str(port)+'\nMP_IMAGE='+image+'\n',encoding='utf8')
 groups={'appconfig':{'odoo_config':(LOCAL/'odoo.conf').read_text()},'dbconfig':{'postgres_password':(LOCAL/'postgres-password').read_text(),'app_db_password':(LOCAL/'app-db-password').read_text(),'init-db.sh':(ROOT/'deploy/init-db.sh').read_text(),'postgres-entrypoint.sh':(ROOT/'deploy/postgres-entrypoint.sh').read_text()},'bootstrap':{'password':(LOCAL/'bootstrap-password').read_text()},'proxyconfig':{'default.conf':(ROOT/'deploy/nginx-r0.conf').read_text()},'filestore':{}}
 phase(state,'creating_empty_volumes');argv=['docker','run','--name',project+'-seed-private-volumes','--log-driver','none','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN']
 for group in groups:
  volume=project+'_'+group;assert subprocess.run(['docker','volume','inspect',volume],capture_output=True).returncode!=0;command('create-volume-'+group,['docker','volume','create','--label','com.modular.disposable='+project,volume]);argv+=['--mount','type=volume,source='+volume+',target=/'+group]
 code="import json,os,pathlib,sys; data=json.load(sys.stdin)\nfor group,files in data.items():\n root=pathlib.Path('/')/group\n assert not list(root.iterdir())\n for name,text in files.items():\n  p=root/name;p.write_text(text);p.chmod(0o444)\n if group=='filestore':root.chmod(0o700);os.chown(root,10001,10001)\nprint('Empty project volumes initialized; no secret values emitted')"
 command('seed-private-volumes',argv+['--entrypoint','/venv/bin/python',image,'-c',code],input=json.dumps(groups).encode());phase(state,'configured');guard(state);save('fresh-configuration.json',dict(project=project,database=database,image=image,port=port,site_id=state['site_id'],deployment_id=state['deployment_id'],empty_owned_volumes=True,no_existing_DB_or_filestore_copied=True,independent_new_control_store=True,inventory_digest=runtime['inventory_digest']))
def initialize():
 state=load(LOCAL/'state.json');guard(state);assert state['phase']=='configured';compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml')];phase(state,'starting_empty_database');command('database-up',compose+['up','-d','--wait','--no-deps','db']);assert sql(state,'check-database-absent',"SELECT count(*) FROM pg_database WHERE datname='"+state['active_db']+"';",database='postgres').strip()==b'0';command('create-empty-database',['docker','exec',state['project']+'-db-1','createdb','-U','postgres','-O','modular','-T','template0',state['active_db']]);native(state,'core-init',['-i','mp_shell,auth_password_policy','--stop-after-init','--without-demo'])
 provision_core(state,'core-provision')
 publish_bootstrap(state)

def provision_core(state,label):
 code=(ROOT/'tools/g5_seed.py').read_text().replace("startswith('mp_disposable_r0_r1_g5_')","startswith('mp_disposable_r0_r1_g6_')").replace('G5_SITE_UUID',state['site_id']).replace('G5_DEPLOYMENT_UUID',state['deployment_id'])
 raw=native(state,label,[],code);rows=[line.split('MP_G5_RESULT=',1)[1] for line in raw.decode().splitlines() if line.startswith('MP_G5_RESULT=')];assert len(rows)==1;write(LOCAL/'fixtures.json',json.loads(rows[0]));phase(state,'publishing_core_bootstrap')

def resume_provision():
 state=load(LOCAL/'state.json');guard(state);assert state['phase']=='core-provision' and not (LOCAL/'fixtures.json').exists()
 counts=json.loads(sql(state,'reconcile-core-provision',"SELECT jsonb_build_object('principals',(SELECT count(*) FROM mp_principal),'installations',(SELECT count(*) FROM mp_plugin_installation),'site_parameters',(SELECT count(*) FROM ir_config_parameter WHERE key IN ('mp.site_id','mp.deployment_id')),'jobs',(SELECT count(*) FROM mp_job),'outbox',(SELECT count(*) FROM mp_outbox),'control',(SELECT count(*) FROM mp_dispatch_control),'core_version',(SELECT latest_version FROM ir_module_module WHERE name='mp_core' AND state='installed'));"))
 assert counts==dict(principals=0,installations=0,site_parameters=0,jobs=0,outbox=0,control=0,core_version='19.0.0.1.7')
 child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-core-provision']))[0];assert not child['State']['Running'] and child['State']['ExitCode']!=0
 assert 'AssertionError' in (LOCAL/'logs/core-provision.stderr').read_text()
 save('core-provision-attempt.json',dict(result='fixture_database_guard_refusal',before_any_seed_mutation=True,observed_counts=counts,diagnosis='Trusted shared G5 seed asserted its G5 DB prefix before any write. G6 driver now uses its own explicit G6 DB prefix; preserve failed child/logs and resume only provisioning/publishing, not initialization.'))
 provision_core(state,'core-provision-g6-prefix')
 publish_bootstrap(state)

def publish_bootstrap(state):
 compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml')]
 config=dict(schema_version=1,deployment_id=state['deployment_id'],project=state['project'],sites=[dict(site_id=state['site_id'],database=state['active_db'])],image_id=state['image_id'],generation=1,policy_version=state['policy_version'],operator_authorization_generation=state['operator_authorization_generation'],release_created_at=state['created_at']);catalog=Catalog(LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'),readonly=True);reader=DockerObserver(config);observation=reader.read(quiesced=True,missing_worker=True);document=reader.state(observation,catalog.snapshot());lock=document['state']['release_lock'];config['published_release']=lock
 values={'mp.release_digest':data_digest(lock),'mp.active_inventory_digest':state['inventory_digest'],'web.base.url':state['url'],'web.base.url.freeze':'True'};payload=json.dumps(values).replace("'","''");sql(state,'bootstrap-release-pins',"INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date) SELECT key,value,1,1,timezone('UTC',now()),timezone('UTC',now()) FROM jsonb_each_text('"+payload+"'::jsonb) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value;")
 phase(state,'starting_guarded_core');worker=ensure(config,state['image_id'],state['bootstrap_id'],inventory_digest=state['inventory_digest']);config['worker_id']=worker;write(LOCAL/'operator/target.json',config);command('start-core-worker',['docker','start',worker]);wait_ready(worker);reader=DockerObserver(config);observed=reader.read();document=reader.state(observed,catalog.snapshot());assert not document['state']['installations'];assert json.loads(sql(state,'core-native-absent',"SELECT jsonb_build_array(to_regclass('mp_example_note') IS NULL,to_regclass('mp_example_canvas_board') IS NULL);"))==[True,True]
 NativeExecutor(OperatorStore(LOCAL/'operator/control'),LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'))._prepare_assets(state['bootstrap_id'],config,document['state'],observed,protect_directory(LOCAL/'operator/bootstrap-assets'));publish_profile(reader,catalog);phase(state,'starting_core_edge');command('start-core-edge',compose+['up','-d','--no-deps','edge']);phase(state,'core_only_ready');save('core-only-bootstrap.json',dict(result='passed',project=state['project'],configuration=config,reference_tables_absent=True,installations_empty=True,guarded_core_and_assets_ready=True));guard(state)
def install():
 state=load(LOCAL/'state.json');guard(state);assert state['phase']=='core_only_ready';assert json.loads(sql(state,'assert-fresh-dispatch-absent',"SELECT jsonb_build_array((SELECT count(*) FROM mp_job),(SELECT count(*) FROM mp_outbox),(SELECT count(*) FROM mp_dispatch_control));"))==[0,0,0];target=LOCAL/'operator/target.json';config=load(target);reader=DockerObserver(config);catalog=Catalog(LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'),readonly=True);snapshot=catalog.snapshot();obs=reader.read();document=reader.state(obs,snapshot);fixture=load(LOCAL/'fixtures.json');targets=[dict(installation_id=installation_id(obs['sites'][0],plugin),site_id=state['site_id'],workspace_id=w['public_id'],plugin_id=plugin,action='install') for w in fixture['workspaces'].values() for plugin in ['org.example.notes','org.example.canvas','org.example.notes_labels']];bundle=prepare_current_install_targets(document,obs['sites'],snapshot,activation_targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'));save('install-bundle.json',bundle);write(LOCAL/'install.json',dict(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']));phase(state,'registering_reference_install')
 prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'operator/trust.json')];ops=prefix+['operations','--store',str(LOCAL/'operator/control')];options=['--deployment-config',str(target),'--catalog',str(LOCAL/'operator/catalog')];operation=bundle['plan']['operation_id'];command('register-reference-install',ops+['register','--bundle',str(OUTPUT/'install-bundle.json')]+options);command('approve-reference-install',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+options);phase(state,'applying_reference_install');completed=json.loads(command('apply-reference-install',prefix+['plugin','apply',operation,'--store',str(LOCAL/'operator/control')]+options,timeout=600));assert completed['state']=='completed';current=load(target);reader=DockerObserver(current);after=reader.state(reader.read(),catalog.snapshot())['state'];assert len(after['installations'])==6 and all(i['feature_state']=='enabled' and i['metadata_state']=='installed' for i in after['installations']);fixture['database']=state['active_db'];fixture['bindings']={key:next(b for b in after['bindings'] if b['workspace_id']==space['public_id'] and b['alias']=='documents' and b['consumer_installation_id']==next(i['installation_id'] for i in after['installations'] if i['workspace_id']==space['public_id'] and i['plugin_id']=='org.example.notes')) for key,space in fixture['workspaces'].items()};write(LOCAL/'fixtures.json',fixture);write(LOCAL/'install.json',dict(state='completed_verified',operation_id=operation,plan_hash=bundle['plan_hash']));phase(state,'references_installed');save('reference-install.json',dict(result='passed',operation_id=operation,plan_hash=bundle['plan_hash'],configuration=current,completed=completed,installations=6,independent_exact_approval=True));save('installed-state.json',after);guard(state)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['configure','initialize','install','resume-provision']);args=parser.parse_args();globals()[args.action.replace('-','_')]()
