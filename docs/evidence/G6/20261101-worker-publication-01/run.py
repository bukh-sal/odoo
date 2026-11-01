"""Actual operator review/Compose observation/atomic volume/readonly reader proof.

One unregistered synthetic scope; no installed native bridge or metadata lifecycle
claim. All one-shot helpers auto-remove after diagnostics capture. No image build.
"""
import gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_publication import WorkerAuthorityPublisher,DockerWorkerObservation
from modular_platform.worker_projection import DockerWorkerProjection
PRIVATE=protect_directory(ROOT/'.local/document-stats/publication-04');MARKER=PRIVATE/'state.json'
assert not MARKER.exists(),'Inspect retained exact operation/handles; never replay setup'
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def command(label,args,*,input=None,env=None):
    out=PRIVATE/(label+'.stdout');err=PRIVATE/(label+'.stderr');assert not out.exists()
    with out.open('xb') as stdout,err.open('xb') as stderr:
        process=subprocess.Popen(args,stdin=subprocess.PIPE if input else subprocess.DEVNULL,stdout=stdout,stderr=stderr,cwd=ROOT,env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:process.communicate(input,timeout=45)
        except subprocess.TimeoutExpired:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10)
            else:process.kill()
            process.wait(timeout=10);raise RuntimeError('Owned command timed out; reconcile exact state: '+label)
    assert process.returncode==0,'Inspect retained diagnostics without replay: '+label
    return out.read_bytes()

native=json.loads((ROOT/'.local/g6-events/state.json').read_text());project='mp-disposable-document-stats-04'
protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*native['protected_configurations'],'.local/g6-events/operator/target.json']}
assert not command('project-absent',['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).strip()
network=native['project']+'_runtime';assert json.loads(command('internal-network',['docker','network','inspect',network]))[0]['Internal']
lock=json.loads((ROOT/'services/document_stats/image.lock.json').read_text())
public_volume=project+'-public-config';authority_volume=project+'-authority'
record=dict(state='creating_owned_volumes',project=project,volumes=[public_volume,authority_volume],native_image=native['image_id'],worker_image=lock['image_id'])
write(MARKER,record)
for volume,label in [(public_volume,'public'),(authority_volume,'authority')]:
    assert not command(label+'-absent',['docker','volume','ls','--filter','name=^'+volume+'$','-q']).strip()
    command('create-'+label,['docker','volume','create','--label','com.modular.disposable='+project,
        '--label','com.modular.worker-authority='+native['deployment_id'],volume])

store=OperatorStore(ROOT/'.local/g6-events/operator/control')
publisher=WorkerAuthorityPublisher(store,native['deployment_id'],native['site_id'])
assert not (publisher.projection/'authority.json').exists(),'Existing publisher needs explicit resumption, never reset'
sink=DockerWorkerProjection(volume=authority_volume,deployment_id=native['deployment_id'],helper_image=native['image_id'],records=publisher.records)
publisher.sink=sink
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
endpoint=json.loads((ROOT/'packages/contracts/examples/v1/endpoint.json').read_text())
endpoint.update(site_id=native['site_id'],workspace_id=json.loads((ROOT/'.local/g6-events/fixtures.json').read_text())['workspaces']['C']['public_id'],installation_id=str(uuid4()),expected_image_digest=lock['image_id'],issuer_key_ref='stats04_private',public_key_ref='stats04_public')
publisher.provision_keypair(endpoint['issuer_key_ref'],endpoint['public_key_ref'],private,public)
key_id='stats04';config={k:endpoint[k] for k in ['site_id','workspace_id','installation_id']};config.update(public_key_file='/run/worker/public.pem',key_id=key_id,endpoint_generation=1)
payload={'public.pem':public.decode(),'config.json':json.dumps(config)}
script="import json,pathlib,sys;r=pathlib.Path('/config');assert not list(r.iterdir());v=json.load(sys.stdin);assert set(v)=={'public.pem','config.json'}\nfor n,t in v.items():\n p=r/n;p.write_text(t);p.chmod(0o444)\nprint('public verification configuration provisioned')"
command('seed-public',['docker','run','--rm','-i','--name',project+'-seed-public','--network','none','--log-driver','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+public_volume+',target=/config','--entrypoint','/venv/bin/python',lock['image_id'],'-c',script],input=json.dumps(payload).encode())
env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=lock['reference'],MP_DOCUMENT_STATS_CONFIG_VOLUME=public_volume,MP_DOCUMENT_STATS_NETWORK=network)
compose=['docker','compose','--project-name',project,'--file','services/document_stats/compose.yaml','--profile','worker']
record['state']='starting_worker';write(MARKER,record);command('compose-up',compose+['up','--detach','--no-build','--pull','never'],env=env)
ident=command('worker-id',compose+['ps','-q','document-stats'],env=env).decode().strip();record['container_id']=ident;write(MARKER,record)
for attempt in range(30):
    row=json.loads(command('health-'+str(attempt),['docker','inspect',ident]))[0]
    assert row['State']['Running']
    if row['State'].get('Health',{}).get('Status')=='healthy':break
    time.sleep(1)
else:raise AssertionError('Live worker did not become healthy; inspect exact instance')
observer=DockerWorkerObservation(dict(project=project,service='document-stats',network=network,public_config_volume=public_volume,image=lock['reference'],destination=endpoint['destination']))
record['state']='reviewing_publication';write(MARKER,record)
review=publisher.prepare(endpoint,key_id,observer);write(PRIVATE/'enable-review.json',review)
published=publisher.publish(review,exact_hash=review['plan_hash'],observer=observer,noninteractive=True);write(PRIVATE/'enable-result.json',published)

# Compile new SDK source into an isolated process. It has no database/config or
# Docker mount; signing material is available only through the read-only volume.
code="import sys,types,json\nsys.path.insert(0,'/opt/modular/packages/platform_sdk')\n"
for module,path in [('modular_platform.worker_dispatch','packages/platform_sdk/modular_platform/worker_dispatch.py'),('modular_platform.worker_authority','packages/platform_sdk/modular_platform/worker_authority.py')]:
    code+='m=types.ModuleType('+repr(module)+');m.__package__="modular_platform";sys.modules[m.__name__]=m\nexec(compile('+repr((ROOT/path).read_text())+",'source_worker_module','exec'),m.__dict__)\n"
code+="from modular_platform.worker_authority import PublishedWorkerAuthority,AuthorityUnavailable\nfrom modular_platform.worker_dispatch import WorkerClient\nfrom uuid import uuid4\nfrom pathlib import Path\n"
code+='reader=PublishedWorkerAuthority("/run/worker-authority",deployment_id='+repr(native['deployment_id'])+',site_id='+repr(native['site_id'])+')\nscope='+repr({k:endpoint[k] for k in ['installation_id','workspace_id','endpoint_config']})+'\n'
prefix=code
code+="snapshot=reader.select(**scope)\nclient=WorkerClient(lambda:reader.select(**scope).endpoint,lambda ref:reader.issuer(snapshot,ref),snapshot.egress,**{k:snapshot.endpoint[k] for k in ['site_id','workspace_id','installation_id']})\nvalue=client.analyze(dict(text='one two\\nthree',note_id=str(uuid4()),expected_revision=1),request_id=str(uuid4()),operation_id=str(uuid4()))\nassert value['data']==dict(characters=13,words=3,lines=2)\ntry:Path('/run/worker-authority/authority.json').write_text('{}')\nexcept OSError as error:assert error.errno in (13,30)\nelse:raise AssertionError('Projection was writable')\nprint('Actual scoped HTTP and read-only publication passed')"
def reader_args(label,source):return ['docker','run','--rm','--name',project+'-'+label,'--log-driver','none','--network',network,'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+authority_volume+',target=/run/worker-authority,readonly','--entrypoint','/venv/bin/python',native['image_id'],'-c',source]
command('actual-readonly-dispatch',reader_args('reader',code))
record['state']='testing_outage_revocation';write(MARKER,record)
command('compose-stop',compose+['stop','--timeout','5'],env=env)
endpoint.update(generation=2,state='revoked')
def down(*args):raise AssertionError('Revocation must not depend on worker health')
review=publisher.prepare(endpoint,key_id,down);write(PRIVATE/'revoke-review.json',review)
revoked=publisher.publish(review,exact_hash=review['plan_hash'],observer=down,noninteractive=True);write(PRIVATE/'revoke-result.json',revoked)
code=prefix+"try:reader.select(**scope)\nexcept AuthorityUnavailable:pass\nelse:raise AssertionError('Revoked runtime projection authorized')\nprint('Actual read-only revoked projection refused')"
command('actual-revoked-reader',reader_args('revoked-reader',code))
worker=json.loads(command('terminal-worker',['docker','inspect',ident]))[0];assert not worker['State']['Running'] and worker['State']['ExitCode']==0
(PRIVATE/'terminal-worker.inspect.json.gz').write_bytes(gzip.compress(json.dumps(worker).encode()))
command('retire-worker',['docker','rm',ident])
for volume in [public_volume,authority_volume]:command('retire-'+volume,['docker','volume','rm',volume])
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
record['state']='qualified_retired';write(MARKER,record)
result=dict(result='passed_actual_operator_publication_prerequisite',worker_image=lock['image_id'],native_image=native['image_id'],enabled_generation=published['generation'],revoked_generation=revoked['generation'],checks=['existing independent OS store target/owner/exact-hash review','actual running Compose image/RepoDigest/internal network/address/public-key configuration','atomic dedicated Linux volume projection and nonroot read-only application mount','actual WorkerClient signed HTTP with public-only worker config','worker stopped exit0; revocation publishes without health or process restart','fresh mounted reader refuses revoked endpoint'],all_helpers_auto_removed=True,worker_removed=True,owned_volumes_removed=2,new_images=0,protected_configurations=len(protected),limits=['Synthetic unregistered provider scope; not installed Notes bridge, metadata lifecycle, guarded runner, native rollout or recovery qualification.','Private publisher is operator-only API; CLI and normal native/job-runner mount/config integration remain required.'],source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['packages/platform_sdk/modular_platform/worker_publication.py','packages/platform_sdk/modular_platform/worker_projection.py','packages/platform_sdk/modular_platform/worker_authority.py','packages/platform_sdk/modular_platform/worker_dispatch.py']})
write(OUT/'qualification.json',result);print('Actual independent publication, readonly signed dispatch, outage revocation and retirement passed')
