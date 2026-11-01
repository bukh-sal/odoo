"""Config-volume discriminator; reuse signed HTTP/outage cases, preserve original fixture."""
import hashlib,http.client,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import jwt
from cryptography.hazmat.primitives import serialization
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PARENT=ROOT/'.local/document-stats';PRIVATE=protect_directory(PARENT/'volume-02');MARKER=PRIVATE/'state.json'
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def command(label,args,*,input=None,env=None):
    stdout=PRIVATE/(label+'.stdout');stderr=PRIVATE/(label+'.stderr');assert not stdout.exists()
    with stdout.open('xb') as out,stderr.open('xb') as err:
        process=subprocess.Popen(args,stdin=subprocess.PIPE if input else subprocess.DEVNULL,stdout=out,stderr=err,cwd=ROOT,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:process.communicate(input,timeout=45)
        except subprocess.TimeoutExpired:
            # Exact child tree launched above, never a Docker daemon/runtime.
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10)
            else:process.kill()
            process.wait(timeout=10);raise RuntimeError('Owned CLI deadline; reconcile daemon operation before continuing: '+label)
    assert process.returncode==0,'Inspect private exact label, never replay operation: '+label
    return stdout.read_bytes()
assert not MARKER.exists()
old=json.loads((PARENT/'compose-01.json').read_text());assert old['state']=='starting'
rows=[json.loads(l) for l in command('retained-original-state-01',['docker','ps','-a','--no-trunc','--filter','label=com.docker.compose.project='+old['project'],'--format','{{json .}}']).splitlines()]
assert len(rows)==1 and rows[0]['State']=='created'
project='mp-disposable-document-stats-02';assert not command('owned-project-empty-01',['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).strip()
native=json.loads((ROOT/'.local/g6-events/state.json').read_text());protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*native['protected_configurations'],'.local/g6-events/operator/target.json']}
network=native['project']+'_runtime';assert json.loads(command('internal-network-01',['docker','network','inspect',network]))[0]['Internal']
lock=json.loads((ROOT/'services/document_stats/image.lock.json').read_text());scope=old['scope'];configdir=PARENT/'public-config-01'
key=serialization.load_pem_private_key((PARENT/'issuer-01.pem').read_bytes(),password=None)
assert (configdir/'public.pem').read_bytes()==key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
volume=project+'-public-config';assert not command('volume-absent-01',['docker','volume','ls','--filter','name=^'+volume+'$','-q']).strip()
record=dict(state='creating_owned_public_volume',project=project,scope=scope,image_id=lock['image_id'],network=network,volume=volume,retained_original=rows[0]['ID']);write(MARKER,record)
command('create-volume-01',['docker','volume','create','--label','com.modular.disposable='+project,volume])
payload={p.name:p.read_text() for p in configdir.iterdir()};assert set(payload)=={'config.json','public.pem'}
code="import json,pathlib,sys;r=pathlib.Path('/config');assert not list(r.iterdir());v=json.load(sys.stdin);assert set(v)=={'config.json','public.pem'}\nfor n,t in v.items():\n p=r/n;p.write_text(t);p.chmod(0o444)\nprint('Public verification config initialized once')"
command('seed-public-volume-01',['docker','run','--name',project+'-seed-public-config','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--log-driver','none','--mount','type=volume,source='+volume+',target=/config','--entrypoint','/venv/bin/python',lock['image_id'],'-c',code],input=json.dumps(payload).encode())
env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=lock['reference'],MP_DOCUMENT_STATS_CONFIG_VOLUME=volume,MP_DOCUMENT_STATS_NETWORK=network)
compose=['docker','compose','--project-name',project,'--file','services/document_stats/compose.yaml','--profile','worker']
record['state']='starting';write(MARKER,record);command('compose-volume-up-01',compose+['up','--detach','--no-build','--pull','never'],env=env)
# Retain identical test semantics/limits from the first attempt. This executes
# only the post-start portion, never original key/provisioning/startup steps.
original=(ROOT/'docs/evidence/G6/20261101-worker-compose-01/run.py').read_text()
suffix=original[original.index("ident=command('compose-id-01'"):]
suffix=suffix.replace('internal_network=network,actual_configuration=',"internal_network=network,public_config_backend='owned_linux_volume',actual_configuration=")
exec(compile(suffix,'retained_worker_HTTP_outage_checks','exec'))
