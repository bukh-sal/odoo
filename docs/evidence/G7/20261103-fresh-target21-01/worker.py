"""Explicit independent operator worker provisioning on the fresh target21 site."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from uuid import UUID,uuid5
sys.path.insert(0,str(Path(__file__).parent))
from target import ROOT,OUT,LOCAL,f,NEW
from modular import configuration
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
PRIVATE=LOCAL/'worker-setup';PUBLIC=OUT/'worker';f.OUTPUT=PUBLIC
IMAGE='sha256:87ad9d2d1c950cde6f6e233232ae2ae719d8df64601f0c7293e0a4b0be96e38f';REFERENCE='modular-document-stats@'+IMAGE
PROJECT='mp-disposable-document-stats-g7qual';VOLUME=PROJECT+'-public-config'
def context():
 state=f.load(LOCAL/'state.json');f.guard(state)
 return state,NativeExecutor(OperatorStore(LOCAL/'operator/control'),LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'))
def prefix():return [sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'operator/trust.json')]
def cli(native):return prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(LOCAL/'operator/worker-target.json')]
def phase(r,state):r['state']=state;f.write(PRIVATE/'state.json',r)
def provision():
 state,native=context();assert state['phase']=='references_installed' and native.config['generation']==2 and native.config['image_id']==NEW
 assert not PRIVATE.exists() and not PUBLIC.exists();protect_directory(PRIVATE);PUBLIC.mkdir()
 fixture=f.load(LOCAL/'fixtures.json');scope=dict(site_id=state['site_id'],workspace_id=fixture['workspaces']['A']['public_id'],installation_id=str(uuid5(UUID(state['site_id']),'plugin:org.example.document_stats')))
 authority=state['project']+'_target21_worker_authority'
 config=dict(schema_version=1,deployment_id=state['deployment_id'],site_id=state['site_id'],runtime=dict(project=PROJECT,service='document-stats',network=state['project']+'_runtime',public_config_volume=VOLUME,image=REFERENCE,destination='http://document-stats:8080'),authority_volume=authority,helper_image=NEW)
 assert not f.command('fresh-worker-project-absent',['docker','ps','-aq','--filter','label=com.docker.compose.project='+PROJECT]).strip()
 for volume in (VOLUME,authority):assert subprocess.run(['docker','volume','inspect',volume],capture_output=True,timeout=10).returncode!=0
 image=json.loads(f.command('fresh-worker-image',['docker','image','inspect',IMAGE]))[0];assert image['Id']==IMAGE and REFERENCE in image['RepoDigests']
 network=json.loads(f.command('fresh-worker-network',['docker','network','inspect',config['runtime']['network']]))[0];assert network['Internal'] and network['Labels']['com.modular.disposable']==state['project']
 f.write(LOCAL/'operator/worker-target.json',config);operator=WorkerOperator(native.store,native.target_path,LOCAL/'operator/worker-target.json');assert operator.publisher._document()['generation']==0
 r=dict(scope=scope,project=PROJECT,public_volume=VOLUME,authority_volume=authority,worker_image=IMAGE,key_id='g7-target21-key');phase(r,'reviewed_before_creating_runtime')
 f.save('runtime-review.json',dict(result='reviewed_fresh_operator_runtime_configuration',scope=scope,config=config,existing_image_verified=True,existing_internal_network_verified=True,private_authority_only_for_guarded_runner=True,metadata_installer_controls_no_runtime=True))
 for index,volume in enumerate((VOLUME,authority)):
  f.command('fresh-worker-create-volume-'+str(index),['docker','volume','create','--label','com.modular.disposable='+PROJECT,'--label','com.modular.worker-authority='+state['deployment_id'],volume])
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048);private=PRIVATE/'issuer.pem';public=PRIVATE/'public.pem'
 private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
 phase(r,'provisioning_keys')
 provisioned=json.loads(f.command('fresh-worker-provision-keys',cli(native)+['provision-keys','--private-reference','g7target21_issuer','--public-reference','g7target21_public','--private-key',str(private),'--public-key',str(public)]));f.save('keys-provisioned.json',provisioned)
 endpoint=f.load(ROOT/'packages/contracts/examples/v1/endpoint.json');endpoint.update(**scope,expected_image_digest=IMAGE,public_key_ref='g7target21_public',issuer_key_ref='g7target21_issuer',generation=1);f.write(PRIVATE/'endpoint.json',endpoint)
 code="import json,pathlib,sys;r=pathlib.Path('/config');assert not list(r.iterdir());v=json.load(sys.stdin);assert set(v)=={'config.json','public.pem'}\nfor n,t in v.items():\n p=r/n;p.write_text(t);p.chmod(0o444)\nprint('Public-only verification/scope/config1 initialized')"
 publicconfig=dict(scope,public_key_file='/run/worker/public.pem',key_id=r['key_id'],endpoint_generation=1)
 f.command('fresh-worker-seed-public',['docker','run','--rm','-i','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+VOLUME+',target=/config','--entrypoint','/venv/bin/python',NEW,'-c',code],input=json.dumps({'config.json':json.dumps(publicconfig),'public.pem':public.read_text()}).encode())
 phase(r,'starting_separately_operated_runtime')
 env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=REFERENCE,MP_DOCUMENT_STATS_CONFIG_VOLUME=VOLUME,MP_DOCUMENT_STATS_NETWORK=config['runtime']['network'])
 with (PRIVATE/'compose.stdout').open('xb') as out,(PRIVATE/'compose.stderr').open('xb') as err:result=subprocess.run(['docker','compose','-p',PROJECT,'-f','services/document_stats/compose.yaml','--profile','worker','up','-d','--no-build','--pull','never','--wait','--wait-timeout','40'],cwd=ROOT,env=env,stdout=out,stderr=err,timeout=70)
 assert result.returncode==0
 phase(r,'reviewing_endpoint_publication')
 review=json.loads(f.command('fresh-worker-prepare-publication',cli(native)+['prepare','--endpoint',str(PRIVATE/'endpoint.json'),'--key-id',r['key_id']]))
 assert json.loads(f.command('fresh-worker-review-publication',cli(native)+['review',review['plan']['operation_id']]))==review;f.save('publication-review.json',review)
 r.update(publication_operation=review['plan']['operation_id'],publication_hash=review['plan_hash']);phase(r,'publishing_exact_review')
 result=json.loads(f.command('fresh-worker-publish',cli(native)+['publish',r['publication_operation'],'--plan-hash',r['publication_hash'],'--noninteractive']));assert result['generation']==1
 f.save('publication.json',result);operator=WorkerOperator(native.store,native.target_path,LOCAL/'operator/worker-target.json');observed=operator.planning_state();assert observed['service_health'][scope['installation_id']+':'+scope['workspace_id']]['state']=='healthy'
 attested=operator.observer(endpoint,hashlib.sha256(public.read_bytes()).hexdigest(),r['key_id']);r['container_id']=attested['container_id'];phase(r,'published_healthy')
 f.save('planning-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
 f.save('provisioned.json',dict(result='fresh_operator_scoped_worker_published',scope=scope,container_id=r['container_id'],worker_image=IMAGE,public_config_generation=1,endpoint_generation=1,publication_generation=1,public_volume=VOLUME,issuer_volume=authority,private_key_never_mounted_to_worker_or_HTTP=True,actual_runtime_image_key_scope_network_user_mounts_attested=True,metadata_not_installed_yet=True,new_images=0,new_runtime_containers=1,new_volumes=2))
 f.phase(state,'fresh_target21_worker_published');print('Fresh worker87 healthy with independent scoped config/key/publication1; metadata still uninstalled',flush=True)
if __name__=='__main__':provision()
