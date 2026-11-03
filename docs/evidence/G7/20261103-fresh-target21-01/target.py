"""Fresh target21 logical site/control on the existing owned qualification realm."""
import argparse,configparser,hashlib,importlib.util,io,json,secrets,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent;PARENT=ROOT/'.local/g7-fresh-release-01';LOCAL=PARENT/'target21'
spec=importlib.util.spec_from_file_location('fresh_target_qualified_factory',OUT.parent/'20261103-fresh-release-01/fixture.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
f=old.f;f.LOCAL=LOCAL;f.OUTPUT=OUT/'site'
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.catalog import Catalog
from modular import configuration
OLD=old.OLD;NEW=old.NEW
def prepare():
 assert not LOCAL.exists() and not f.OUTPUT.exists()
 prior=f.load(PARENT/'state.json');prior_target=f.load(PARENT/'operator/target.json');qualified=f.load(PARENT/'dependency-recovery/state.json')
 assert qualified['state']=='dependency_fault_restore_qualified' and qualified['recovery']['state']=='qualified'
 assert prior['project']=='mp-r0-r1g7qualb513bc4f50d4' and prior_target['generation']==4 and prior_target['image_id']==OLD
 assert prior_target['sites'][0]['database']==prior['active_db']
 f.guard(prior)
 database='mp_disposable_r0_r1_g6_g7target_'+prior['project'][-12:]
 state=dict(prior,phase='preparing_target21',active_db=database,databases=[database],site_id=str(uuid4()),deployment_id=str(uuid4()),bootstrap_id=str(uuid4()),image_id=NEW,created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
 preview=dict(schema_version=1,deployment_id=state['deployment_id'],project=state['project'],sites=[dict(site_id=state['site_id'],database=database)],image_id=NEW,generation=1,policy_version=1,operator_authorization_generation=1,release_created_at=state['created_at']);DockerObserver(preview)
 runtime=inspect_image(NEW);assert runtime['platform_version']=='0.1.21' and runtime['native_manifests']['mp_core']['version']=='19.0.0.1.21';state['inventory_digest']=runtime['inventory_digest']
 protect_directory(LOCAL);protect_directory(LOCAL/'logs');protect_directory(LOCAL/'operator');f.OUTPUT.mkdir(parents=True)
 f.write(LOCAL/'prior-qualification-state.json',prior);f.write(LOCAL/'prior-qualification-target.json',prior_target)
 f.write(LOCAL/'state.json',state)
 for name in ('postgres-password','app-db-password','bootstrap-password','database-master-password'):shutil.copyfile(PARENT/name,LOCAL/name)
 shutil.copyfile(PARENT/'operator/trust.json',LOCAL/'operator/trust.json');shutil.copytree(PARENT/'operator/catalog',LOCAL/'operator/catalog')
 catalog=Catalog(LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'),readonly=True);assert len(catalog.snapshot())==19
 store=OperatorStore.initialize(LOCAL/'operator/control',{state['deployment_id']:[state['site_id']]},allow_noninteractive=True)
 state.update(policy_version=store.policy['policy_version'],operator_authorization_generation=store.policy['authorization_generation']);f.write(LOCAL/'state.json',state)
 assert f.sql(state,'target21-new-database-absent',"SELECT count(*) FROM pg_database WHERE datname='"+database+"';",database='postgres').strip()==b'0'
 for index,name in enumerate(prior['owned_resources']['volumes']):
  info=json.loads(f.command('target21-volume-ownership-'+str(index),['docker','volume','inspect',name]))[0];assert info['Labels']['com.modular.disposable']==state['project']
 reader=DockerObserver(prior_target);app=reader._container('app');edge=reader._container('edge')
 appinfo=json.loads(f.command('target21-prior-app-inspect',['docker','inspect',app]))[0];edgeinfo=json.loads(f.command('target21-prior-edge-inspect',['docker','inspect',edge]))[0]
 assert appinfo['Id']==prior_target['worker_id'] and appinfo['Image']==OLD and appinfo['State']['Running']
 assert edgeinfo['Config']['Labels']['com.docker.compose.project']==state['project'] and edgeinfo['State']['Running']
 counts=json.loads(f.command('target21-prior-unfinished-check',['docker','exec','-i',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',prior['active_db'],'-v','ON_ERROR_STOP=1'],input=b"BEGIN READ ONLY;SELECT jsonb_build_array((SELECT count(*) FROM mp_job WHERE state IN ('pending','running')),(SELECT count(*) FROM mp_event_delivery WHERE state='leased'));ROLLBACK;"));assert counts==[0,0]
 read="import pathlib;print(pathlib.Path('/config/odoo_config').read_text(),end='')"
 actual=f.command('target21-prior-mounted-config',['docker','run','--rm','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+state['project']+'_appconfig,target=/config,readonly','--entrypoint','/venv/bin/python',NEW,'-c',read])
 (LOCAL/'prior-mounted-odoo.conf').write_bytes(actual)
 cfg=configparser.ConfigParser();cfg.read_string(actual.decode());assert cfg['options']['db_name']==prior['active_db'] and cfg['options']['dbfilter']=='^'+prior['active_db']+'$'
 cfg['options']['db_name']=database;cfg['options']['dbfilter']='^'+database+'$';stream=io.StringIO();cfg.write(stream);text=stream.getvalue();(LOCAL/'odoo.conf').write_text(text,encoding='utf8')
 (LOCAL/'compose.env').write_text('MP_COMPOSE_PROJECT='+state['project']+'\nMP_HTTP_PORT='+str(state['port'])+'\nMP_IMAGE='+NEW+'\n',encoding='utf8')
 ownership=f.load(PARENT/'original-preservation-query.json');shutil.copyfile(PARENT/'original-preservation-query.json',LOCAL/'original-preservation-query.json')
 current=json.loads(f.command('target21-original-before',['docker','exec','-i',ownership['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',ownership['database'],'-v','ON_ERROR_STOP=1'],input=ownership['query'].encode()));assert current==ownership['expected']
 f.save('preparation-review.json',dict(result='reviewed_owned_fresh_target_bootstrap',project=state['project'],old_app=appinfo['Id'],old_image=OLD,new_image=NEW,new_inventory=runtime['inventory_digest'],new_database=database,new_site_id=state['site_id'],new_deployment_id=state['deployment_id'],old_database_retained=prior['active_db'],old_control_and_checkpoint_retained=True,new_empty_database_checked=True,existing_six_owned_volumes_two_networks_reused=True,no_user_DB_filestore_or_control_copied=True,original_working17tables_configs_exact=True,catalog_archives=19))
 state['phase']='target21_reviewed_before_stop';f.write(LOCAL/'state.json',state)
 f.command('target21-stop-owned-edge',['docker','stop','--time','20',edgeinfo['Id']],timeout=40)
 f.command('target21-stop-owned-app',['docker','stop','--time','20',appinfo['Id']],timeout=40)
 info=json.loads(f.command('target21-owned-stopped',['docker','inspect',edgeinfo['Id'],appinfo['Id']]))
 assert all(not row['State']['Running'] and row['State']['ExitCode']==0 for row in info)
 state['phase']='target21_switching_owned_config';f.write(LOCAL/'state.json',state)
 code="import hashlib,json,os,pathlib,sys;v=json.load(sys.stdin);r=pathlib.Path('/config');p=r/'odoo_config';assert hashlib.sha256(p.read_bytes()).hexdigest()==v['before'];t=r/'odoo_config.target21.tmp';assert not t.exists();t.write_text(v['text']);t.chmod(0o444);os.replace(t,p);assert hashlib.sha256(p.read_bytes()).hexdigest()==v['after'];print('Exact owned app configuration switched while app/edge stopped')"
 f.command('target21-switch-owned-config',['docker','run','--rm','-i','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+state['project']+'_appconfig,target=/config','--entrypoint','/venv/bin/python',NEW,'-c',code],input=json.dumps(dict(before=hashlib.sha256(actual).hexdigest(),after=hashlib.sha256(text.encode()).hexdigest(),text=text)).encode())
 f.phase(state,'configured');f.guard(state);print(json.dumps(dict(result='fresh_target21_prepared',project=state['project'],database=database,site_id=state['site_id'],deployment_id=state['deployment_id'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','initialize','install']);a=p.parse_args()
 if a.action=='prepare':prepare()
 else:getattr(f,a.action)()
