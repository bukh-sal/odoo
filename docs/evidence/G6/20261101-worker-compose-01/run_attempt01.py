"""Once-only operator-launched worker fixture. No metadata installation or host changes."""
import hashlib,http.client,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PRIVATE=protect_directory(ROOT/'.local/document-stats');MARKER=PRIVATE/'compose-01.json'
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def command(label,args,*,input=None,env=None):
    assert not (PRIVATE/(label+'.stdout')).exists()
    result=subprocess.run(args,input=input,capture_output=True,timeout=120,env=env,cwd=ROOT)
    (PRIVATE/(label+'.stdout')).write_bytes(result.stdout);(PRIVATE/(label+'.stderr')).write_bytes(result.stderr)
    assert result.returncode==0,'Inspect exact private label; do not replay mutation: '+label
    return result.stdout
assert not MARKER.exists()
native=json.loads((ROOT/'.local/g6-events/state.json').read_text());protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*native['protected_configurations'],'.local/g6-events/operator/target.json']}
network=native['project']+'_runtime';net=json.loads(subprocess.check_output(['docker','network','inspect',network]))[0];assert net['Internal']
project='mp-disposable-document-stats-01';assert not subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).strip()
lock=json.loads((ROOT/'services/document_stats/image.lock.json').read_text());configdir=protect_directory(PRIVATE/'public-config-01');assert not list(configdir.iterdir())
scope=dict(site_id=str(uuid4()),workspace_id=str(uuid4()),installation_id=str(uuid4()),endpoint_generation=1)
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
(PRIVATE/'issuer-01.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
(configdir/'public.pem').write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
write(configdir/'config.json',dict(public_key_file='/run/worker/public.pem',key_id='owned-compose-01',**scope))
env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=lock['reference'],MP_DOCUMENT_STATS_CONFIG=str(configdir),MP_DOCUMENT_STATS_NETWORK=network)
compose=['docker','compose','--project-name',project,'--file','services/document_stats/compose.yaml','--profile','worker']
record=dict(state='starting',project=project,image_id=lock['image_id'],scope=scope,network=network);write(MARKER,record)
command('compose-up-01',compose+['up','--detach','--no-build','--pull','never'],env=env)
ident=command('compose-id-01',compose+['ps','-q','document-stats'],env=env).decode().strip();assert len(ident)==64;record.update(state='running',container_id=ident);write(MARKER,record)
info=json.loads(command('compose-inspect-01',['docker','inspect',ident]))[0]
assert info['Image']==lock['image_id'] and info['Config']['User']=='10002:10002'
assert info['HostConfig']['ReadonlyRootfs'] and info['HostConfig']['CapDrop']==['ALL'] and info['HostConfig']['PidsLimit']==64
assert info['HostConfig']['Memory']==268435456 and info['HostConfig']['NanoCpus']==1000000000
assert len(info['Mounts'])==1 and info['Mounts'][0]['Destination']=='/run/worker' and not info['Mounts'][0]['RW']
assert set(p.name for p in configdir.iterdir())=={'config.json','public.pem'}
assert not info['HostConfig']['PortBindings'] and list(info['NetworkSettings']['Networks'])==[network]
assert all(not any(w in item.split('=')[0].lower() for w in ['database','password','secret','token','private']) for item in info['Config']['Env'])
CLIENT="import http.client,json,sys,time;v=json.load(sys.stdin);c=http.client.HTTPConnection('127.0.0.1',8080,timeout=3);c.request('POST','/analyze',json.dumps(v['request']).encode(),{'Content-Type':'application/json',**({'Authorization':'Bearer '+v['token']} if v.get('token') else {})});r=c.getresponse();print(json.dumps(dict(status=r.status,body=json.loads(r.read()))));c.close()"
def token(**changes):
    now=int(time.time());claims=dict(iss='modular-platform-host-v1',aud='mp-document-stats-v1',sub=scope['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+120,methods=['analyze'],**scope);claims.update(changes)
    return jwt.encode(claims,key,algorithm='RS256',headers={'kid':'owned-compose-01'})
request=dict(api_version='1.0',request_id=str(uuid4()),operation_id=str(uuid4()),method='analyze',input=dict(text='COMPOSE_PRIVATE_TEXT_CANARY one two',note_id=str(uuid4()),expected_revision=1),**scope)
def call(label,request=request,credential=True):
    value=dict(request=request,token=token() if credential is True else credential)
    return json.loads(command(label,['docker','exec','-i',ident,'/venv/bin/python','-c',CLIENT],input=json.dumps(value).encode()))
def ready(label):
    code="import urllib.request,time\nfor n in range(50):\n try:\n  assert urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=1).status==200;break\n except OSError:\n  time.sleep(.1)\nelse:raise SystemExit(1)\nprint('healthy')"
    command(label,['docker','exec',ident,'/venv/bin/python','-c',code])
ready('compose-health-01');first=call('compose-positive-01');assert first['status']==200 and first['body']['data']['words']==3
assert call('compose-duplicate-01')==first
changed={**request,'input':{**request['input'],'text':'Different'}};assert call('compose-conflict-01',changed)['status']==409
assert call('compose-missing-auth-01',credential=None)['status']==401
assert call('compose-audience-01',credential=token(aud='wrong'))['status']==401
now=int(time.time());assert call('compose-expired-01',credential=token(iat=now-400,nbf=now-400,exp=now-1))['status']==401
for field in ['site_id','workspace_id','installation_id','endpoint_generation']:
    other=2 if field=='endpoint_generation' else str(uuid4());forged={**request,field:other}
    assert call('compose-forged-'+field,forged)['status']==401
    changes={field:other}
    if field=='installation_id':changes['sub']=other
    assert call('compose-other-approved-'+field,forged,token(**changes))['status']==403
record['state']='stopping_for_outage';write(MARKER,record);command('compose-stop-outage-01',['docker','stop','--time','5',ident])
stopped=json.loads(subprocess.check_output(['docker','inspect',ident]))[0];assert not stopped['State']['Running']
host=http.client.HTTPConnection('127.0.0.1',native['port'],timeout=5);host.request('GET','/web/login',headers={'Host':'g6events.localhost:'+str(native['port'])});response=host.getresponse();assert response.status==200;response.read();host.close()
record['state']='starting_after_outage';write(MARKER,record);command('compose-start-recovery-01',['docker','start',ident]);ready('compose-health-after-restart-01');assert call('compose-restart-result-01')==first
command('compose-stop-final-01',['docker','stop','--time','5',ident]);final=json.loads(subprocess.check_output(['docker','inspect',ident]))[0];assert not final['State']['Running'] and final['State']['ExitCode']==0
logs=command('compose-safe-logs-01',['docker','logs',ident]);assert b'COMPOSE_PRIVATE_TEXT_CANARY' not in logs and b'Bearer' not in logs and b'eyJ' not in logs
assert all(json.loads(line)['event'] in {'ready','request','connection_error'} for line in logs.splitlines())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
result=dict(result='passed_actual_independent_Compose_worker_prerequisite',utc=datetime.now(timezone.utc).isoformat(),image_id=lock['image_id'],reference=lock['reference'],container_id=ident,project=project,internal_network=network,actual_configuration=dict(user='10002:10002',read_only=True,public_key_config_only=True,no_database_or_signing_key_or_socket_or_filestore=True,ports_published=False,memory=268435456,pids=64,cpus=1),checks=['health and actual signed Linux HTTP','duplicate saved outcome and changed input conflict','missing/expired/wrong audience refused','forged site/workspace/installation/endpoint generation refused','otherwise valid separately scoped credentials refused by fixed worker configuration','actual worker outage leaves native login healthy','actual same-image restart returns deterministic outcome','structured logs omit text and bearer credentials'],all_helpers_terminal=True,final_worker_exit=0,protected_configurations=10,acceptance_credit=False,limits=['Standalone unregistered synthetic scope; no host service dispatch/Notes integration or metadata lifecycle/recovery qualification yet.','Slow worker/host timeout/degraded UI and managed external reconciliation remain required; SVC/JOB03 not marked passed.'])
write(OUT/'qualification.json',result);record['state']='qualified_stopped';write(MARKER,record)
print('Actual pinned Compose worker/auth/configuration/outage/restart proof passed; owned worker stopped exit0, native fixture unchanged.')
