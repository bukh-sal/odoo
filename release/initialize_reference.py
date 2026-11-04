"""Once-only local reference deployment from a verified kit; never resets old data."""
from __future__ import annotations
import argparse,configparser,json,secrets,shutil,socket,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(Path(__file__).parent)]
from verify import verify
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import protect_directory,verify_private_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.profile_channel import publish_profile
from modular_platform.workers import ensure,wait_ready

def load(path):return json.loads(Path(path).read_bytes())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')

class Reference:
    def __init__(self,args):
        self.kit=args.kit.resolve();self.manifest=verify(self.kit);self.work=args.workdir.resolve()
        self.operator=load(self.work/'operator-setup.json')
        if Path(sys.executable).resolve()!=Path(self.operator['python']).resolve():raise ValueError('Use the kit-created operator interpreter')
        self.private=Path(self.operator['private']);verify_private_directory(self.private)
        self.local=self.private/'reference';self.args=args
    def state(self):return load(self.local/'state.json')
    def phase(self,state,name):
        state['phase']=name;state['updated_utc']=datetime.now(timezone.utc).isoformat();write(self.local/'state.json',state)
        print(json.dumps(dict(phase=name,project=state['project'])),flush=True)
    def command(self,label,args,*,data=None,timeout=180):
        prefix=self.local/'logs'/label
        if prefix.with_suffix('.stdout').exists():raise RuntimeError('Step already attempted; inspect process/state/diagnostics')
        with prefix.with_suffix('.stdout').open('xb') as out,prefix.with_suffix('.stderr').open('xb') as err:
            result=subprocess.run(args,input=data,stdout=out,stderr=err,cwd=ROOT,timeout=timeout)
        if result.returncode:raise RuntimeError('Inspect private '+label+' diagnostic and actual state; do not retry mutation')
        return prefix.with_suffix('.stdout').read_bytes()
    def compose(self,state,*args):
        return self.command('compose-'+args[0],['docker','compose','-f',str(self.local/'compose.json'),*args])
    def sql(self,state,label,query,*,database=None):
        return self.command(label,['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',database or state['database']],data=query.encode())
    def native(self,state,label,args,code=None):
        self.phase(state,label)
        command=['docker','run','--name',state['project']+'-'+label,'--label','com.modular.disposable='+state['project'],'--log-driver','none',
                 '--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
                 '--tmpfs','/tmp','--memory','1536m','--pids-limit','128','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly',
                 '--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--mount','type=volume,source='+state['project']+'_bootstrap,target=/run/mp-bootstrap,readonly',
                 '--entrypoint','/venv/bin/python',state['image_id'],'odoo-bin']
        if code is not None:command.insert(2,'-i');command+=['shell']
        return self.command(label,command+['-c','/run/secrets/odoo_config','-d',state['database'],'--no-http','--workers=0','--max-cron-threads=0']+args,data=code.encode() if code else None,timeout=300)
    def prepare(self):
        if not self.args.reference_fixture:raise ValueError('Explicit --reference-fixture acknowledgement required')
        if self.local.exists():raise ValueError('Reference already attempted; inspect its state, never reset it')
        protect_directory(self.local);protect_directory(self.local/'logs');protect_directory(self.local/'operator')
        nonce=secrets.token_hex(6);project='mp-r0-r1release'+nonce;database='mp_disposable_r0_r1_release_'+nonce
        port=self.args.port
        with socket.socket() as connection:connection.bind(('127.0.0.1',port))
        images=load(self.kit/'images.json');app=images['images']['application']['image_id']
        state=dict(phase='preparing',project=project,database=database,image_id=app,inventory_digest=images['application_inventory_digest'],
                   port=port,hostname='release-'+nonce+'.localhost',site_id=str(uuid4()),deployment_id=str(uuid4()),bootstrap_id=str(uuid4()),
                   created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),source_commit=self.manifest['source_commit'],
                   owned_resources=dict(networks=[project+'_runtime',project+'_edge'],volumes=[project+'_'+n for n in ['appconfig','dbconfig','bootstrap','proxyconfig','filestore','pgdata']]))
        state['url']='http://'+state['hostname']+':'+str(port);write(self.local/'state.json',state)
        self.command('load-kit-images',['docker','load','--input',str(self.kit/'images.tar')],timeout=240)
        for role,row in images['images'].items():
            actual=json.loads(self.command('inspect-'+role,['docker','image','inspect',row['image_id']]))[0]
            if actual['Id']!=row['image_id']:raise ValueError('Loaded image differs')
        if inspect_image(app)['inventory_digest']!=state['inventory_digest']:raise ValueError('Unexpected app inventory')
        self.phase(state,'creating_owned_networks')
        for name in ['runtime','edge']:
            full=project+'_'+name
            if subprocess.run(['docker','network','inspect',full],capture_output=True).returncode==0:raise ValueError('Network already exists')
            self.command('network-'+name,['docker','network','create',*(['--internal'] if name=='runtime' else []),
                '--label','com.docker.compose.project='+project,'--label','com.docker.compose.network='+name,'--label','com.modular.disposable='+project,full])
        for name in ['appconfig','dbconfig','bootstrap','proxyconfig','filestore','pgdata']:
            full=project+'_'+name
            if subprocess.run(['docker','volume','inspect',full],capture_output=True).returncode==0:raise ValueError('Volume already exists')
            self.command('volume-'+name,['docker','volume','create','--label','com.modular.disposable='+project,'--label','com.docker.compose.project='+project,'--label','com.docker.compose.volume='+name,full])
        passwords={name:secrets.token_urlsafe(32) for name in ['admin','operator','alice','bob','worker','postgres','application_db','database_master']}
        write(self.local/'account-passwords.json',passwords)
        config=configparser.ConfigParser();config['options']=dict(db_host='db',db_port='5432',db_user='modular',db_password=passwords['application_db'],
            admin_passwd=passwords['database_master'],db_name=database,dbfilter='^'+database+'$',list_db='False',data_dir='/var/lib/modular',
            addons_path='/opt/modular/addons',server_wide_modules='base,web',without_demo='True',max_cron_threads='0',workers='2',db_maxconn='12',
            http_interface='0.0.0.0',proxy_mode='True',limit_memory_soft='536870912',limit_memory_hard='671088640',log_handler=':INFO,werkzeug:ERROR')
        with (self.local/'odoo.conf').open('x',encoding='utf8') as stream:config.write(stream)
        groups={'appconfig':{'odoo_config':(self.local/'odoo.conf').read_text()},
            'dbconfig':{'postgres_password':passwords['postgres'],'app_db_password':passwords['application_db'],'init-db.sh':(ROOT/'deploy/init-db.sh').read_text(),'postgres-entrypoint.sh':(ROOT/'deploy/postgres-entrypoint.sh').read_text()},
            'bootstrap':{'reference.json':json.dumps(dict(database=database,site_id=state['site_id'],deployment_id=state['deployment_id'],passwords=passwords))},
            'proxyconfig':{'default.conf':(ROOT/'deploy/nginx-r0.conf').read_text()},'filestore':{},'pgdata':{}}
        seed="""import json,os,pathlib,sys
groups=json.load(sys.stdin)
for name,files in groups.items():
 root=pathlib.Path('/volumes')/name;assert not list(root.iterdir());root.chmod(0o755)
 if name=='filestore':root.chmod(0o700);os.chown(root,10001,10001)
 for name,data in files.items():
  path=root/name;path.write_text(data,encoding='utf8');path.chmod(0o444)
print('New owned configuration volumes seeded')
"""
        self.command('seed-owned-volumes',['docker','run','--rm','-i','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN',
            *[arg for name in groups for arg in ['--mount','type=volume,source='+project+'_'+name+',target=/volumes/'+name]],'--entrypoint','/venv/bin/python',app,'-c',seed],data=json.dumps(groups).encode())
        compose=dict(name=project,services={
            'db':dict(image=images['images']['postgres']['image_id'],pull_policy='never',environment={'POSTGRES_PASSWORD_FILE':'/run/secrets/postgres_password'},
                volumes=['pgdata:/var/lib/postgresql/data','dbconfig:/run/secrets:ro'],entrypoint=['bash','/run/secrets/postgres-entrypoint.sh'],command=['postgres','-c','max_connections=64','-c','shared_buffers=128MB'],
                healthcheck=dict(test=['CMD-SHELL','pg_isready -U postgres -d postgres'],interval='3s',timeout='3s',retries=30),mem_limit='512m',cpus=1,networks=['runtime']),
            'edge':dict(image=images['images']['proxy']['image_id'],pull_policy='never',user='101:101',entrypoint=['nginx','-g','daemon off;'],volumes=['proxyconfig:/etc/nginx/conf.d:ro'],
                ports=['127.0.0.1:'+str(port)+':8069'],read_only=True,tmpfs=['/tmp','/var/cache/nginx:uid=101,gid=101,mode=0755','/var/run:uid=101,gid=101,mode=0755'],mem_limit='128m',cpus=.5,networks=['runtime','edge'])},
            volumes={name:dict(external=True,name=project+'_'+name) for name in groups},networks={name:dict(external=True,name=project+'_'+name) for name in ['runtime','edge']})
        write(self.local/'compose.json',compose)
        shutil.copyfile(self.kit/'plugins/curated-trust.json',self.local/'operator/trust.json')
        store=OperatorStore.initialize(self.local/'operator/control',{state['deployment_id']:[state['site_id']]},allow_noninteractive=True)
        state.update(policy_version=store.policy['policy_version'],operator_authorization_generation=store.policy['authorization_generation'])
        self.phase(state,'configured')
    def initialize(self):
        state=self.state()
        if state['phase']!='configured':raise ValueError('Initialization already attempted; inspect the exact phase')
        self.phase(state,'starting_empty_database')
        self.compose(state,'up','-d','--wait','--no-deps','db')
        if self.sql(state,'assert-new-database',"SELECT count(*) FROM pg_database WHERE datname='"+state['database']+"';",database='postgres').strip()!=b'0':raise ValueError('Database exists; never overwrite')
        self.command('create-empty-database',['docker','exec',state['project']+'-db-1','createdb','-U','postgres','-O','modular','-T','template0',state['database']])
        self.native(state,'core-init',['-i','mp_shell,auth_password_policy','--stop-after-init','--without-demo'])
        raw=self.native(state,'core-provision',[],(ROOT/'release/reference_seed.py').read_text())
        rows=[line.split('MP_REFERENCE_RESULT=',1)[1] for line in raw.decode().splitlines() if line.startswith('MP_REFERENCE_RESULT=')]
        if len(rows)!=1:raise ValueError('Provisioning result uncertain; inspect native state before any retry')
        write(self.local/'fixtures.json',json.loads(rows[0]));self.publish(state)
    def publish(self,state):
        self.phase(state,'publishing_core_bootstrap')
        target=self.local/'operator/target.json';trust=configuration(self.local/'operator/trust.json')
        catalog=Catalog(self.private/'catalog',trust,readonly=True)
        config=dict(schema_version=1,deployment_id=state['deployment_id'],project=state['project'],sites=[dict(site_id=state['site_id'],database=state['database'])],
                    image_id=state['image_id'],generation=1,policy_version=state['policy_version'],operator_authorization_generation=state['operator_authorization_generation'],release_created_at=state['created_at'])
        reader=DockerObserver(config);observed=reader.read(quiesced=True,missing_worker=True);document=reader.state(observed,catalog.snapshot())
        lock=document['state']['release_lock'];config['published_release']=lock
        values={'mp.release_digest':data_digest(lock),'mp.active_inventory_digest':state['inventory_digest'],'web.base.url':state['url'],'web.base.url.freeze':'True'}
        payload=json.dumps(values).replace("'","''")
        self.sql(state,'bootstrap-release-pins',"INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date) SELECT key,value,1,1,timezone('UTC',now()),timezone('UTC',now()) FROM jsonb_each_text('"+payload+"'::jsonb) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value;")
        self.phase(state,'starting_guarded_core')
        worker=ensure(config,state['image_id'],state['bootstrap_id'],inventory_digest=state['inventory_digest']);config['worker_id']=worker;write(target,config)
        self.command('start-guarded-core',['docker','start',worker]);wait_ready(worker)
        reader=DockerObserver(config);observed=reader.read();document=reader.state(observed,catalog.snapshot())
        if document['state']['installations']:raise ValueError('Unexpected existing installations')
        NativeExecutor(OperatorStore(self.local/'operator/control'),target,self.private/'catalog',trust)._prepare_assets(state['bootstrap_id'],config,document['state'],observed,protect_directory(self.local/'operator/bootstrap-assets'))
        publish_profile(reader,catalog)
        self.command('start-core-edge',['docker','compose','-f',str(self.local/'compose.json'),'up','-d','--no-deps','edge'])
        self.phase(state,'core_only_ready')
    def install(self):
        state=self.state()
        if state['phase']!='core_only_ready':raise ValueError('Install already attempted or core not ready')
        target=self.local/'operator/target.json';config=load(target);reader=DockerObserver(config)
        catalog=Catalog(self.private/'catalog',configuration(self.local/'operator/trust.json'),readonly=True);rows=catalog.snapshot()
        observed=reader.read();document=reader.state(observed,rows);fixture=load(self.local/'fixtures.json')
        targets=[dict(installation_id=installation_id(observed['sites'][0],plugin),site_id=state['site_id'],workspace_id=w['public_id'],plugin_id=plugin,action='install')
            for w in fixture['workspaces'].values() for plugin in ['org.example.notes','org.example.notes_labels','org.example.canvas']]
        bundle=prepare_current_install_targets(document,observed['sites'],rows,activation_targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        write(self.local/'install-bundle.json',bundle);write(self.local/'install.json',dict(operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']))
        prefix=[sys.executable,'-I',str(ROOT/'tools/modular.py'),'--config',str(self.local/'operator/trust.json')]
        options=['--deployment-config',str(target),'--catalog',str(self.private/'catalog')];store=['--store',str(self.local/'operator/control')];operation=bundle['plan']['operation_id']
        self.phase(state,'registering_reference_install')
        self.command('register-reference-install',prefix+['operations',*store,'register','--bundle',str(self.local/'install-bundle.json'),*options])
        self.command('approve-reference-install',prefix+['operations',*store,'approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions',*options])
        self.phase(state,'applying_reference_install')
        completed=load_bytes(self.command('apply-reference-install',prefix+['plugin','apply',operation,*store,*options],timeout=600))
        if completed['state']!='completed':raise ValueError('Install did not complete; inspect independent journal')
        config=load(target);reader=DockerObserver(config);after=reader.state(reader.read(),catalog.snapshot())['state']
        if len(after['installations'])!=6 or not all(i['feature_state']=='enabled' and i['metadata_state']=='installed' for i in after['installations']):raise ValueError('Reference install verification failed')
        write(self.local/'installed-state.json',after);self.phase(state,'references_installed')
    def status(self):
        state=self.state();print(json.dumps({k:state[k] for k in ['phase','project','database','url','image_id','inventory_digest']}))

def load_bytes(raw):return json.loads(raw)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','initialize','install','status']);parser.add_argument('--kit',type=Path,required=True);parser.add_argument('--workdir',type=Path,required=True)
    parser.add_argument('--reference-fixture',action='store_true');parser.add_argument('--port',type=int,default=18100)
    args=parser.parse_args();getattr(Reference(args),args.action)()
