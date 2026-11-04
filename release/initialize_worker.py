"""Separately provision and approve the minimal reference worker; no plugin install."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
from uuid import UUID,uuid5
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from initialize_reference import ROOT,Reference,load,write
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerOperator
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--kit',type=Path,required=True);parser.add_argument('--workdir',type=Path,required=True);args=parser.parse_args()
    reference=Reference(args);state=reference.state();assert state['phase']=='minimal_backend_reference_qualified'
    local=reference.local/'worker'
    if local.exists():raise ValueError('Worker setup attempted; inspect exact phase, process, publication intent and runtime before any continuation')
    protect_directory(local);fixture=load(reference.local/'fixtures.json');lock=load(ROOT/'services/document_stats/image.lock.json')
    kit_images=load(reference.kit/'images.json');assert lock['image_id']==kit_images['images']['worker']['image_id']
    selected=json.loads(reference.command('worker-selected-image',['docker','image','inspect',lock['reference']]))[0]
    assert selected['Id']==lock['image_id'] and lock['reference'] in selected['RepoDigests']
    runtime_project='mp-disposable-document-stats-release-'+state['project'].removeprefix('mp-r0-r1release')
    public_volume=runtime_project+'-public-config';authority_volume=state['project']+'_worker_authority'
    scope=dict(site_id=state['site_id'],workspace_id=fixture['workspaces']['A']['public_id'],installation_id=str(uuid5(UUID(state['site_id']),'plugin:org.example.document_stats')))
    marker=dict(phase='preparing',project=runtime_project,scope=scope,volumes=[public_volume,authority_volume]);write(local/'state.json',marker)
    def phase(name):marker['phase']=name;write(local/'state.json',marker);print(json.dumps(dict(worker_phase=name)),flush=True)
    for name in [public_volume,authority_volume]:
        assert subprocess.run(['docker','volume','inspect',name],capture_output=True).returncode!=0,'Existing volume; never reuse unknown storage'
        reference.command('worker-volume-'+('public' if name==public_volume else 'authority'),['docker','volume','create','--label','com.modular.disposable='+state['project'],
            *(['--label','com.modular.worker-authority='+state['deployment_id']] if name==authority_volume else []),name])
    runtime=dict(project=runtime_project,service='document-stats',network=state['project']+'_runtime',public_config_volume=public_volume,image=lock['reference'],destination='http://document-stats:8080')
    worker_path=reference.local/'operator/worker-target.json'
    write(worker_path,dict(schema_version=1,deployment_id=state['deployment_id'],site_id=state['site_id'],runtime=runtime,authority_volume=authority_volume,helper_image=state['image_id']))
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    private=local/'issuer.pem';public=local/'public.pem'
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    target=reference.local/'operator/target.json';store=reference.local/'operator/control'
    prefix=[sys.executable,'-I',str(ROOT/'tools/modular.py'),'--config',str(reference.local/'operator/trust.json'),'worker','--store',str(store),'--deployment-config',str(target),'--worker-config',str(worker_path)]
    phase('provisioning_new_keys')
    reference.command('worker-provision-keys',prefix+['provision-keys','--private-reference','release_issuer','--public-reference','release_public','--private-key',str(private),'--public-key',str(public)])
    endpoint=load(ROOT/'packages/contracts/examples/v1/endpoint.json');endpoint.update(**scope,expected_image_digest=lock['image_id'],public_key_ref='release_public',issuer_key_ref='release_issuer',generation=1)
    write(local/'endpoint.json',endpoint);key_id='release-reference-key'
    public_config=dict(scope,public_key_file='/run/worker/public.pem',key_id=key_id,endpoint_generation=1)
    payload={'config.json':json.dumps(public_config),'public.pem':public.read_text()}
    script="import json,pathlib,sys;root=pathlib.Path('/config');assert not list(root.iterdir());data=json.load(sys.stdin);assert set(data)=={'config.json','public.pem'}\nfor name,text in data.items():\n path=root/name;path.write_text(text);path.chmod(0o444)\nprint('New public-only reference configuration seeded')"
    phase('seeding_public_configuration')
    reference.command('worker-seed-public',['docker','run','--rm','-i','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL',
        '--mount','type=volume,source='+public_volume+',target=/config','--entrypoint','/venv/bin/python',lock['image_id'],'-c',script],data=json.dumps(payload).encode())
    (local/'compose.env').write_text('MP_DOCUMENT_STATS_IMAGE='+lock['reference']+'\nMP_DOCUMENT_STATS_CONFIG_VOLUME='+public_volume+'\nMP_DOCUMENT_STATS_NETWORK='+runtime['network']+'\n',encoding='utf8')
    phase('starting_separately_operated_worker')
    reference.command('worker-compose-up',['docker','compose','--env-file',str(local/'compose.env'),'--project-name',runtime_project,'--file',str(ROOT/'services/document_stats/compose.yaml'),'--profile','worker',
        'up','--detach','--no-build','--pull','never','--wait','--wait-timeout','40'])
    phase('preparing_exact_publication')
    review=json.loads(reference.command('worker-prepare-publication',prefix+['prepare','--endpoint',str(local/'endpoint.json'),'--key-id',key_id]))
    shown=json.loads(reference.command('worker-review-publication',prefix+['review',review['plan']['operation_id']]));assert shown==review
    write(local/'publication-review.json',review);marker.update(operation_id=review['plan']['operation_id'],plan_hash=review['plan_hash'])
    phase('publishing_exact_reviewed_authority')
    result=json.loads(reference.command('worker-publish',prefix+['publish',marker['operation_id'],'--plan-hash',marker['plan_hash'],'--noninteractive']))
    operator=WorkerOperator(OperatorStore(store),target,worker_path);document=operator.publisher._document();assert document['generation']==1 and len(document['endpoints'])==1
    entry=document['endpoints'][0];attestation=operator.observer(entry['descriptor'],operator.publisher._key_digest(entry['descriptor']),entry['key_id'])
    assert operator.planning_state()['service_health'][scope['installation_id']+':'+scope['workspace_id']]['state']=='healthy'
    write(local/'qualified-runtime.json',dict(result=result,attestation=attestation,publication_generation=document['generation'],metadata_installed=False,job_executed=False))
    phase('scoped_worker_published_metadata_not_installed')

if __name__=='__main__':main()
