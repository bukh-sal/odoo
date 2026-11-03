"""Separate local operator runtime replacement; installer never starts workers."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import lifecycle as s
ROOT,OUT,PRIVATE,f,j,base=s.ROOT,s.OUT,s.PRIVATE,s.f,s.j,s.base
from modular_platform.worker_operator import WorkerOperator
from modular_platform.operator_os import OperatorError
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
IMAGE='sha256:87ad9d2d1c950cde6f6e233232ae2ae719d8df64601f0c7293e0a4b0be96e38f'
REFERENCE='modular-document-stats@'+IMAGE
PROJECT='mp-disposable-document-stats-07';VOLUME=PROJECT+'-public-config';MARKER=PRIVATE/'runtime.json'
def op(native):return WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')
def cli(native):return base.base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]
def phase(r,value):r['state']=value;f.write(MARKER,r)
def entry(document,scope):
 rows=[e for e in document['endpoints'] if all(e['descriptor'][k]==scope[k] for k in ('site_id','workspace_id','installation_id'))];assert len(rows)==1;return rows[0]
def publication(native,endpoint,key,label):
 p=PRIVATE/(label+'-endpoint.json');f.write(p,endpoint)
 review=json.loads(f.command('worker-security-'+label+'-prepare',cli(native)+['prepare','--endpoint',str(p),'--key-id',key]))
 assert json.loads(f.command('worker-security-'+label+'-review',cli(native)+['review',review['plan']['operation_id']]))==review
 f.save(label+'-review.json',review)
 result=json.loads(f.command('worker-security-'+label+'-publish',cli(native)+['publish',review['plan']['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive']))
 f.save(label+'-publication.json',result);return result
def revoke():
 state,native=s.context();assert f.load(s.path('suspend'))['state']=='verified' and not MARKER.exists()
 operator=op(native);document=operator.publisher._document();assert document['generation']==11
 scope=f.load(s.path('suspend'))['scope'];old=entry(document,scope);assert old['descriptor']['generation']==9 and old['descriptor']['state']=='enabled'
 before=base.snapshot(state,'worker-security-runtime-before');inst=next(x for x in before['mp_plugin_installation'] if x['public_id']==scope['installation_id'])
 features=[x for x in before['mp_workspace_plugin'] if x['installation_id']==inst['id']];assert len(features)==1 and all(x['availability']=='suspended' for x in features)
 f.write(PRIVATE/'runtime-before.json',before);f.write(PRIVATE/'runtime-worker-before.json',base.worker(native,'worker-security-runtime-worker-before'))
 f.write(PRIVATE/'runtime-config-before.json',operator.config);f.write(PRIVATE/'runtime-authority-before.json',document)
 build=f.load(OUT.parent/'20261103-worker-dependencies-image-01/candidate-build.json');assert build['image_id']==IMAGE
 info=json.loads(f.command('worker-security-candidate-inspect',['docker','image','inspect',IMAGE]))[0];assert REFERENCE in info['RepoDigests']
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in build['source_sha256'].items())
 review=dict(result='reviewed_explicit_local_operator_runtime_change',scope=scope,old_runtime=operator.config['runtime'],new_project=PROJECT,new_public_volume=VOLUME,new_image=IMAGE,new_reference=REFERENCE,new_endpoint_generation=11,retained_key=old['key_id'],public_config_only=True,protocol_engine_schemas_unchanged=True,reason='Actual cryptography50.0.2/pip26.3 dependency remediation; seven isolated immutable-image tests passed',limits=['This runtime review is not endpoint publication or metadata approval; those remain separate exact-hash operations.'])
 f.save('runtime-change-review.json',review)
 r=dict(scope=scope,key_id=old['key_id'],old_container=f.load(PRIVATE/'runtime-worker-before.json')['container_id']);phase(r,'revoking')
 endpoint=copy.deepcopy(old['descriptor']);endpoint.update(generation=10,state='revoked')
 result=publication(native,endpoint,r['key_id'],'revoke');assert result['generation']==12 and result['state']=='revoked'
 assert base.snapshot(state,'worker-security-runtime-after-revoke')==before
 phase(r,'revoked');print('Provider suspended; separate exact-reviewed publication12/endpoint10 revoked; runtime unchanged',flush=True)
def switch():
 state,native=s.context();r=f.load(MARKER);assert r['state']=='revoked';operator=op(native);assert operator.publisher._document()['generation']==12
 old=f.load(PRIVATE/'runtime-worker-before.json');assert old['container_id']==r['old_container']
 assert subprocess.run(['docker','volume','inspect',VOLUME],capture_output=True,timeout=15).returncode!=0
 assert not f.command('worker-security-project07-absent',['docker','ps','-aq','--filter','label=com.docker.compose.project='+PROJECT]).strip()
 phase(r,'creating_public_config')
 f.command('worker-security-create-public-volume',['docker','volume','create','--label','com.modular.disposable='+PROJECT,VOLUME])
 e=entry(f.load(PRIVATE/'runtime-authority-before.json'),r['scope']);public=(operator.publisher.keys/(e['descriptor']['public_key_ref']+'.pem')).read_text()
 assert hashlib.sha256(public.encode()).hexdigest()==old['public_digest']
 code="import json,pathlib,sys;r=pathlib.Path('/config');assert not list(r.iterdir());v=json.load(sys.stdin);(r/'public.pem').write_text(v['public']);(r/'public.pem').chmod(0o444);(r/'config.json').write_text(json.dumps(dict(v['scope'],key_id=v['key_id'],public_key_file='/run/worker/public.pem',endpoint_generation=11)));(r/'config.json').chmod(0o444);assert {p.name for p in r.iterdir()}=={'config.json','public.pem'};print('Public-only scope/key/config11 provisioned')"
 f.command('worker-security-public-volume-init',['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--log-driver','none','--mount','type=volume,source='+VOLUME+',target=/config','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code],input=json.dumps(dict(scope=r['scope'],public=public,key_id=r['key_id'])).encode())
 assert base.worker(native,'worker-security-old-last-check')==old
 phase(r,'stopping_old_worker');f.command('worker-security-old-stop',['docker','stop','--time','20',r['old_container']],timeout=40)
 stopped=json.loads(f.command('worker-security-old-stopped',['docker','inspect',r['old_container']]))[0];assert not stopped['State']['Running'] and stopped['State']['ExitCode']==0
 phase(r,'starting_new_worker')
 env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=REFERENCE,MP_DOCUMENT_STATS_NETWORK=operator.config['runtime']['network'],MP_DOCUMENT_STATS_CONFIG_VOLUME=VOLUME)
 args=['docker','compose','-p',PROJECT,'-f','services/document_stats/compose.yaml','--profile','worker','up','-d','--no-build','--pull','never']
 with (PRIVATE/'compose.stdout').open('xb') as out,(PRIVATE/'compose.stderr').open('xb') as err:result=subprocess.run(args,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=90)
 assert result.returncode==0
 ident=f.command('worker-security-new-ident',['docker','ps','--no-trunc','-q','--filter','label=com.docker.compose.project='+PROJECT,'--filter','label=com.docker.compose.service=document-stats']).decode().strip();assert len(ident)==64
 r.update(container_id=ident,image_id=IMAGE,public_digest=old['public_digest']);phase(r,'new_worker_started')
 config=copy.deepcopy(operator.config);config['runtime'].update(project=PROJECT,public_config_volume=VOLUME,image=REFERENCE);f.write(j.LOCAL/'operator/worker-target.json',config)
 endpoint=copy.deepcopy(e['descriptor']);endpoint.update(generation=11,state='enabled',expected_image_digest=IMAGE);f.write(PRIVATE/'new-endpoint.json',endpoint)
 deadline=time.monotonic()+45
 while time.monotonic()<deadline:
  info=json.loads(subprocess.check_output(['docker','inspect',ident],timeout=10))[0]
  if info['State'].get('Health',{}).get('Status')=='healthy':break
  time.sleep(1)
 observed=op(native).observer(endpoint,r['public_digest'],r['key_id']);assert observed['container_id']==ident
 image=json.loads(f.command('worker-security-runtime-image-config',['docker','image','inspect',IMAGE]))[0]
 assert info['Config']['Env']==image['Config']['Env']
 host=info['HostConfig'];assert host['Memory']==268435456 and host['NanoCpus']==1000000000 and host['PidsLimit']==64
 assert 'no-new-privileges:true' in host['SecurityOpt'] and set(host['Tmpfs'])=={'/tmp'}
 assert base.snapshot(state,'worker-security-runtime-after-switch')==f.load(PRIVATE/'runtime-before.json')
 f.save('runtime-switch.json',dict(result='passed_explicit_hardened_dependency_worker_switch',new_container=ident,new_image=IMAGE,old_container=r['old_container'],old_stopped_retained=True,issuer_key_unchanged=True,public_config_generation=11,authority_still_revoked12=True,all17tables_exact=True,observer_validated_actual_image_scope_key_network_user_mounts_resources=True,no_installer_runtime_control=True))
 phase(r,'attested');print('Actual87 image healthy and hardened runtime attested; old548 stopped retained; publication remains revoked12',flush=True)
def publish():
 state,native=s.context();r=f.load(MARKER);assert r['state']=='attested';operator=op(native);endpoint=f.load(PRIVATE/'new-endpoint.json');negatives=[]
 for label,image in [('old_image',f.load(PRIVATE/'runtime-worker-before.json')['image']),('third_image','sha256:'+'0'*64)]:
  bad=copy.deepcopy(endpoint);bad['expected_image_digest']=image
  try:operator.publisher.prepare(bad,r['key_id'],operator.observer)
  except OperatorError as exc:negatives.append(dict(case=label,result='refused',reason=str(exc)))
  else:raise AssertionError('Wrong image accepted')
 phase(r,'publishing_new_image');result=publication(native,endpoint,r['key_id'],'new-image');assert result['generation']==13 and result['state']=='enabled'
 try:ReferenceDispatchMaintenance(native).reference_policy(native.config)
 except OperatorError as exc:
  assert 'exact independently published endpoint/image' in str(exc);negatives.append(dict(case='default_old_metadata_new_image',result='refused',reason=str(exc)))
 else:raise AssertionError('Unreviewed default metadata/image mismatch accepted')
 f.save('runtime-refusals.json',dict(result='passed_actual_wrong_image_and_default_profile_refusals',cases=negatives))
 f.save('runtime-planning-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
 assert base.snapshot(state,'worker-security-runtime-after-publish')==f.load(PRIVATE/'runtime-before.json')
 phase(r,'published_new_image');f.phase(state,'worker_security_new_image_published_metadata_old_suspended');print('Separate reviewed publication13/endpoint11 enabled; metadata still old/suspended; strict default mismatch refused',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['revoke','switch','publish']);a=p.parse_args();globals()[a.action]()
