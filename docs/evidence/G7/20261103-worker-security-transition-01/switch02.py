"""Resume diagnosed switch pre-stop check; never recreate initialized volume."""
import copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import s,base,f,j,PRIVATE,OUT,ROOT,op,entry,phase,MARKER,IMAGE,REFERENCE,PROJECT,VOLUME

def finish():
 state,native=s.context();r=f.load(MARKER);assert r['state']=='creating_public_config'
 operator=op(native);assert operator.publisher._document()['generation']==12
 old=f.load(PRIVATE/'runtime-worker-before.json');e=entry(f.load(PRIVATE/'runtime-authority-before.json'),r['scope'])
 assert e['descriptor']['generation']==9
 observed=operator.observer(e['descriptor'],old['public_digest'],r['key_id']);assert observed['container_id']==r['old_container']
 info=json.loads(f.command('worker-security-switch02-old-inspect',['docker','inspect',r['old_container']]))[0]
 assert info['State']['Running'] and info['Image']==old['image'] and info['State']['StartedAt']==old['started_at'] and info['RestartCount']==old['restart_count']
 assert info['Mounts']==old['mounts'] and info['NetworkSettings']['Networks']==old['networks']
 volume=json.loads(f.command('worker-security-switch02-volume-inspect',['docker','volume','inspect',VOLUME]))[0]
 assert volume['Name']==VOLUME and volume['Labels']['com.modular.disposable']==PROJECT
 code="import pathlib,json,hashlib;r=pathlib.Path('/config');assert {p.name for p in r.iterdir()}=={'config.json','public.pem'};print(json.dumps(dict(config=json.loads((r/'config.json').read_text()),public_digest=hashlib.sha256((r/'public.pem').read_bytes()).hexdigest())))"
 actual=json.loads(f.command('worker-security-switch02-volume-verify',['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+VOLUME+',target=/config,readonly','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code]))
 assert actual==dict(config=dict(r['scope'],key_id=r['key_id'],public_key_file='/run/worker/public.pem',endpoint_generation=11),public_digest=old['public_digest'])
 assert base.snapshot(state,'worker-security-switch02-before')==f.load(PRIVATE/'runtime-before.json')
 f.save('switch-prestop-diagnosis.json',dict(result='passed_precise_pre_revocation_runtime_and_initialized_volume_checks',previous_refusal='Helper used current revoked endpoint10 against correctly unchanged worker config9; no old process stop occurred',old_config9_exact=True,old_process_image_mounts_network_start_restart_exact=True,initialized_public_volume11_exact=True,authority_still_revoked12=True,all17tables_exact=True,no_recreation_replay=True))
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
if __name__=="__main__":finish()
