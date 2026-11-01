"""Separate local operator artifact/worker provisioning, never installer control."""
import argparse,copy,hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID,uuid5
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerOperator
from reference_package import assemble
f=j.f;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'provider-registration';MARKER=PRIVATE/'setup.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    target=j.LOCAL/'operator/target.json';config=f.load(target)
    assert config['generation']==11 and config['image_id']==state['image_id']
    return state,target,config

def command(label,args,*,input=None,env=None,timeout=120):
    stdout=PRIVATE/(label+'.stdout');stderr=PRIVATE/(label+'.stderr');assert not stdout.exists()
    with stdout.open('xb') as out,stderr.open('xb') as err:
        result=subprocess.run(args,input=input,stdout=out,stderr=err,cwd=ROOT,env=env,timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert result.returncode==0,'Inspect exact private step without replay: '+label
    return stdout.read_bytes()

def cli():
    return [sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'worker',
        '--store',str(j.LOCAL/'operator/control'),'--deployment-config',str(j.LOCAL/'operator/target.json'),
        '--worker-config',str(j.LOCAL/'operator/worker-target.json')]

def curate():
    state,target,config=context();assert not PRIVATE.exists();protect_directory(PRIVATE)
    trust=j.LOCAL/'operator/trust.json';policy=f.load(trust)
    catalog=Catalog(j.LOCAL/'operator/catalog',configuration(trust),readonly=True)
    before= DockerObserver(config);observed=before.read();document=before.state(observed,catalog.snapshot())
    assert not any(p['runtime']=='external_service' for p in document['state']['release_lock']['plugins'])
    manifest,raw,files=assemble(ROOT,'plugins/document_stats/plugin.toml')
    assert raw==assemble(ROOT,'plugins/document_stats/plugin.toml')[1]
    assert manifest['runtime']==dict(kind='external_service') and set(files)=={'plugin.toml','schemas/stats-v1.json','notices/LICENSE','notices/COPYRIGHT','provenance.json','inventory.json'}
    archive=PRIVATE/'org.example.document_stats-0.1.0.mplug'
    with archive.open('xb') as stream:stream.write(raw)
    verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(archive)
    digest=verified.digest;assert digest not in policy['approved_digests']
    f.write(PRIVATE/'trust-before.json',policy)
    marker=dict(state='curating',artifact_digest=digest,archive=str(archive.relative_to(ROOT)))
    f.write(MARKER,marker)
    changed=copy.deepcopy(policy);changed['generation']+=1;changed['approved_digests'].append(digest);f.write(trust,changed)
    curated=Catalog(j.LOCAL/'operator/catalog',configuration(trust));descriptor=curated.add(archive,expected_digest=digest)
    after=before.state(before.read(),curated.snapshot())
    assert after['state']['release_lock']==document['state']['release_lock'] and after['state']['installations']==document['state']['installations']
    assert after['state']['bindings']==document['state']['bindings'] and after['state']['endpoints']==document['state']['endpoints']
    assert hashlib.sha256(target.read_bytes()).hexdigest()==hashlib.sha256(json.dumps(config,indent=2).encode()+b'\n').hexdigest()
    scope=dict(site_id=config['sites'][0]['site_id'],workspace_id=f.load(j.LOCAL/'fixtures.json')['workspaces']['C']['public_id'],
        installation_id=str(uuid5(UUID(config['sites'][0]['site_id']),'plugin:org.example.document_stats')))
    marker.update(state='curated',scope=scope);f.write(MARKER,marker)
    f.save('artifact-curation.json',dict(result='passed_exact_metadata_artifact_curation',digest=digest,files=sorted(files),
        previous_trust_generation=policy['generation'],current_trust_generation=changed['generation'],
        fixture_local_catalog_only=True,native_release_installations_bindings_endpoints_exact=True,
        artifact_not_installed=True,no_docker_assets_created=True,canonical_scope=scope))
    f.phase(state,'provider_artifact_curated');f.guard(state);print('Metadata-only artifact curated locally; native deployment unchanged')

def provision():
    state,target,config=context();marker=f.load(MARKER);assert marker['state']=='curated'
    worker=f.load(j.LOCAL/'operator/worker-target.json');runtime=worker['runtime'];lock=f.load(ROOT/'services/document_stats/image.lock.json')
    assert runtime['project']=='mp-disposable-document-stats-05' and runtime['public_config_volume']=='mp-disposable-document-stats-05-public-config'
    assert runtime['image']==lock['reference'] and runtime['network']==state['project']+'_runtime'
    assert not command('worker-absent',['docker','ps','-aq','--filter','label=com.docker.compose.project='+runtime['project']]).strip()
    assert not command('public-volume-absent',['docker','volume','ls','-q','--filter','name=^'+runtime['public_config_volume']+'$']).strip()
    network=json.loads(command('network',['docker','network','inspect',runtime['network']]))[0];assert network['Internal']
    image=json.loads(command('image',['docker','image','inspect',lock['image_id']]))[0]
    assert image['Id']==lock['image_id'] and lock['reference'] in image['RepoDigests']
    operator=WorkerOperator(OperatorStore(j.LOCAL/'operator/control'),target,j.LOCAL/'operator/worker-target.json')
    publication=operator.publisher._document();assert publication['generation']==2 and all(e['descriptor']['state']=='revoked' for e in publication['endpoints'])
    f.write(PRIVATE/'publication-before.json',publication)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    private=PRIVATE/'issuer13.pem';public=PRIVATE/'public13.pem'
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    marker['state']='provisioning_keys';f.write(MARKER,marker)
    provisioned=json.loads(command('provision-keys',cli()+['provision-keys','--private-reference','provider13_issuer','--public-reference','provider13_public',
        '--private-key',str(private),'--public-key',str(public)]))
    endpoint=f.load(ROOT/'packages/contracts/examples/v1/endpoint.json')
    endpoint.update(**marker['scope'],expected_image_digest=lock['image_id'],public_key_ref='provider13_public',issuer_key_ref='provider13_issuer',generation=1)
    f.write(PRIVATE/'endpoint.json',endpoint)
    public_config={k:endpoint[k] for k in ['site_id','workspace_id','installation_id']}
    public_config.update(public_key_file='/run/worker/public.pem',key_id='provider13-key',endpoint_generation=1)
    marker['state']='creating_public_volume';f.write(MARKER,marker)
    command('create-public-volume',['docker','volume','create','--label','com.modular.disposable='+runtime['project'],runtime['public_config_volume']])
    code="import json,pathlib,sys;r=pathlib.Path('/config');assert not list(r.iterdir());v=json.load(sys.stdin);assert set(v)=={'config.json','public.pem'}\nfor n,t in v.items():\n p=r/n;p.write_text(t);p.chmod(0o444)\nprint('Public verification configuration initialized once')"
    payload={'config.json':json.dumps(public_config),'public.pem':public.read_text()}
    command('seed-public-volume',['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--log-driver','none',
        '--mount','type=volume,source='+runtime['public_config_volume']+',target=/config','--entrypoint','/venv/bin/python',lock['image_id'],'-c',code],input=json.dumps(payload).encode())
    env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=lock['reference'],MP_DOCUMENT_STATS_CONFIG_VOLUME=runtime['public_config_volume'],MP_DOCUMENT_STATS_NETWORK=runtime['network'])
    marker['state']='starting_worker_separate_operator_action';f.write(MARKER,marker)
    compose=['docker','compose','--project-name',runtime['project'],'--file','services/document_stats/compose.yaml','--profile','worker']
    command('start-worker',compose+['up','--detach','--no-build','--pull','never','--wait','--wait-timeout','40'],env=env)
    review=json.loads(command('prepare-publication',cli()+['prepare','--endpoint',str(PRIVATE/'endpoint.json'),'--key-id','provider13-key']))
    shown=json.loads(command('review-publication',cli()+['review',review['plan']['operation_id']]));assert shown==review
    f.write(PRIVATE/'publication-review.json',review)
    marker.update(state='publication_prepared',publication_operation=review['plan']['operation_id'],publication_hash=review['plan_hash']);f.write(MARKER,marker)
    result=json.loads(command('publish',cli()+['publish',review['plan']['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive']))
    current=operator.publisher._document();assert current['generation']==3
    assert all(e in current['endpoints'] for e in publication['endpoints'])
    fresh=WorkerOperator(operator.store,target,j.LOCAL/'operator/worker-target.json').planning_state()
    assert fresh['service_health'][endpoint['installation_id']+':'+endpoint['workspace_id']]['state']=='healthy'
    f.save('worker-publication.json',dict(result='passed_actual_canonical_worker_publication',publication_generation=3,
        endpoint_generation=1,canonical_scope=marker['scope'],image=lock['image_id'],worker_project=runtime['project'],
        public_config_volume=runtime['public_config_volume'],independent_exact_review_and_image_address_key_scope_attestation=True,
        previous_revoked_entries_preserved=True,operator_started_runtime_separately=True,metadata_installer_not_invoked=True,
        new_images=0,new_runtime_containers=1,new_public_only_volumes=1,seed_helper_auto_removed=True))
    marker['state']='worker_published';f.write(MARKER,marker);f.phase(state,'provider_worker_published');f.guard(state)
    print('Canonical scoped worker separately provisioned, attested and independently published; no metadata installed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['curate','provision']);args=parser.parse_args();globals()[args.action]()
