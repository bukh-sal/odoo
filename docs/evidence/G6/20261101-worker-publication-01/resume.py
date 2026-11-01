"""Resume verified generation1 after read-only errno assertion correction only."""
import ast,gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_publication import WorkerAuthorityPublisher
from modular_platform.worker_projection import DockerWorkerProjection
PRIVATE=ROOT/'.local/document-stats/publication-04';MARKER=PRIVATE/'state.json'
record=json.loads(MARKER.read_text());assert record['state']=='reviewing_publication'
original=(OUT/'run.py').read_text();tree=ast.parse(original);tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'write','command'}];exec(compile(tree,'retained_fixture_commands','exec'))
native=json.loads((ROOT/'.local/g6-events/state.json').read_text());project=record['project'];public_volume,authority_volume=record['volumes'];network=native['project']+'_runtime';ident=record['container_id']
protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*native['protected_configurations'],'.local/g6-events/operator/target.json']}
lock=json.loads((ROOT/'services/document_stats/image.lock.json').read_text());store=OperatorStore(ROOT/'.local/g6-events/operator/control')
publisher=WorkerAuthorityPublisher(store,native['deployment_id'],native['site_id'])
publisher.sink=DockerWorkerProjection(volume=authority_volume,deployment_id=native['deployment_id'],helper_image=native['image_id'],records=publisher.records)
document=publisher._document();assert document['generation']==1 and len(document['endpoints'])==1
endpoint=document['endpoints'][0]['descriptor'];assert endpoint['state']=='enabled' and endpoint['generation']==1
published=json.loads((PRIVATE/'enable-result.json').read_text());assert published['generation']==1
row=json.loads(command('resume-inspect-live',['docker','inspect',ident]))[0]
assert row['State']['Running'] and row['State']['Health']['Status']=='healthy' and row['Image']==lock['image_id']
env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=lock['reference'],MP_DOCUMENT_STATS_CONFIG_VOLUME=public_volume,MP_DOCUMENT_STATS_NETWORK=network)
compose=['docker','compose','--project-name',project,'--file','services/document_stats/compose.yaml','--profile','worker']
key_id='stats04'
exec(compile(original[original.index('# Compile new SDK'):original.index("command('actual-readonly-dispatch'")],'corrected_readonly_fixture','exec'))
command('actual-readonly-dispatch-02',reader_args('reader-02',code))
exec(compile(original[original.index("record['state']='testing_outage_revocation'"):],'continue_never_replay_publication','exec'))
