"""New immutable SIGTERM fix, same public config, retained actual HTTP checks."""
import ast,hashlib,http.client,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import jwt
from cryptography.hazmat.primitives import serialization
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PARENT=ROOT/'.local/document-stats';PRIVATE=protect_directory(PARENT/'shutdown-03');MARKER=PRIVATE/'state.json';resume=False
# Reuse bounded process-tree supervision; no provisioning/action code imported.
previous=ROOT/'docs/evidence/G6/20261101-worker-compose-volume-02/run.py'
tree=ast.parse(previous.read_bytes());tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'write','command'}];exec(compile(tree,'retained_bounded_worker_commands','exec'))
assert not MARKER.exists();old=json.loads((PARENT/'volume-02/state.json').read_text());assert old['state']=='HTTP_verified_shutdown137_fix_required'
oldcontainer=json.loads(command('old-worker-terminal-01',['docker','inspect',old['container_id']]))[0];assert not oldcontainer['State']['Running'] and oldcontainer['State']['ExitCode']==137
project='mp-disposable-document-stats-03';assert not command('project-empty-01',['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).strip()
native=json.loads((ROOT/'.local/g6-events/state.json').read_text());protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*native['protected_configurations'],'.local/g6-events/operator/target.json']}
network=old['network'];volume=old['volume'];scope=old['scope'];configdir=PARENT/'public-config-01'
vol=json.loads(command('config-volume-owner-01',['docker','volume','inspect',volume]))[0];assert vol['Labels']['com.modular.disposable']==old['project']
key=serialization.load_pem_private_key((PARENT/'issuer-01.pem').read_bytes(),password=None)
assert (configdir/'public.pem').read_bytes()==key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
lock=json.loads((ROOT/'services/document_stats/image.lock.json').read_text());assert lock['image_id']!=old['image_id']
env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=lock['reference'],MP_DOCUMENT_STATS_CONFIG_VOLUME=volume,MP_DOCUMENT_STATS_NETWORK=network)
compose=['docker','compose','--project-name',project,'--file','services/document_stats/compose.yaml','--profile','worker']
record=dict(state='starting',project=project,scope=scope,volume=volume,image_id=lock['image_id'],network=network);write(MARKER,record)
command('compose-up-01',compose+['up','--detach','--no-build','--pull','never'],env=env)
original=(ROOT/'docs/evidence/G6/20261101-worker-compose-01/run.py').read_text();suffix=original[original.index("ident=command('compose-id-01'"):]
suffix=suffix.replace("['docker','stop','--time','5',ident]","['docker','stop','--timeout','10',ident]")
suffix=suffix.replace("internal_network=network,actual_configuration=","internal_network=network,public_config_backend='owned_linux_volume',actual_configuration=")
exec(compile(suffix,'retained_actual_worker_checks_on_SIGTERM_fix','exec'))
