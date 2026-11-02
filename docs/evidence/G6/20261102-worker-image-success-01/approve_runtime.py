"""Separate operator reapproval after verified changed-image recovery."""
import argparse,copy,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-worker-image-upgrade-01'))
import upgrade as previous
from modular_platform.worker_operator import WorkerOperator
from modular_platform.operator_os import protect_directory
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
base,f,j=previous.base,previous.f,previous.j
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'worker-image-success-01';MARKER=PRIVATE/'runtime.json'
def context():return previous.context()
def op(native):return WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')
def cli(native):return base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]
def phase(record,value):record['state']=value;f.write(MARKER,record)

def configure():
    state,native=context();assert native.config['generation']==22 and not PRIVATE.exists();protect_directory(PRIVATE)
    old=f.load(j.LOCAL/'worker-image-upgrade-01/metadata.json');assert old['state']=='resumed'
    assert native.store.status(old['operation_id'])['state']=='revoked'
    operator=op(native);publication=operator.publisher._document();assert publication['generation']==10
    entry=next(e for e in publication['endpoints'] if all(e['descriptor'][k]==old['scope'][k] for k in ['site_id','workspace_id','installation_id']))
    endpoint=copy.deepcopy(entry['descriptor']);assert endpoint['state']=='revoked' and endpoint['generation']==8
    physical=copy.deepcopy(endpoint);physical.update(generation=7,state='enabled')
    digest=operator.publisher._key_digest(endpoint);observed=operator.observer(physical,digest,entry['key_id'])
    assert observed['container_id']=='6e786efe43b7bf5716fd82e276ba7fd95133492dc872b91d6a4ce2807ab8a93d'
    before=base.snapshot(state,'image-success-before-config');assert before==f.load(j.LOCAL/'worker-image-upgrade-01/data-closed.json')
    f.write(PRIVATE/'operator-data-before.json',before);f.write(PRIVATE/'publication-before.json',publication)
    info=json.loads(f.command('image-success-worker-before-config',['docker','inspect',observed['container_id']]))[0]
    f.write(PRIVATE/'worker-before-config.json',info)
    volume=operator.config['runtime']['public_config_volume'];assert volume=='mp-disposable-document-stats-06-public-config'
    endpoint.update(generation=9,state='enabled');f.write(PRIVATE/'enabled-endpoint.json',endpoint)
    record=dict(scope=old['scope'],container_id=observed['container_id'],public_digest=digest,key_id=entry['key_id'],image=info['Image'],retired_operation=old['operation_id'])
    phase(record,'operator_stopping_for_public_config9')
    f.command('image-success-stop-config7',['docker','stop','--time','20',record['container_id']],timeout=40)
    stopped=json.loads(f.command('image-success-stopped-config7',['docker','inspect',record['container_id']]))[0]
    assert not stopped['State']['Running'] and stopped['State']['ExitCode']==0
    code="""import hashlib,json,os,pathlib,sys
r=pathlib.Path('/config');v=json.load(sys.stdin);assert {p.name for p in r.iterdir()}=={'config.json','public.pem'}
assert hashlib.sha256((r/'public.pem').read_bytes()).hexdigest()==v['public_digest']
p=r/'config.json';c=json.loads(p.read_bytes());assert c==dict(v['scope'],public_key_file='/run/worker/public.pem',key_id=v['key_id'],endpoint_generation=7)
c['endpoint_generation']=9;t=r/'config.next';t.write_text(json.dumps(c));t.chmod(0o444);os.replace(t,p)
print('Public scope/key unchanged; configuration7->9')
"""
    phase(record,'operator_writing_public_config9')
    f.command('image-success-update-public-config9',['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--log-driver','none',
        '--mount','type=volume,source='+volume+',target=/config','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code],input=json.dumps(dict(scope=record['scope'],public_digest=digest,key_id=record['key_id'])).encode())
    phase(record,'operator_starting_public_config9');f.command('image-success-start-config9',['docker','start',record['container_id']])
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        after=json.loads(subprocess.check_output(['docker','inspect',record['container_id']],timeout=10))[0]
        if after['State'].get('Health',{}).get('Status')=='healthy':break
        time.sleep(1)
    assert operator.observer(endpoint,digest,record['key_id'])['container_id']==record['container_id']
    assert after['Image']==info['Image'] and after['Config']==info['Config'] and after['HostConfig']==info['HostConfig'] and after['Mounts']==info['Mounts']
    assert base.snapshot(state,'image-success-after-config')==before and operator.publisher._document()==publication
    f.save('public-config9.json',dict(result='passed_separate_operator_public_configuration_update',container_id=record['container_id'],image=record['image'],
        same_container_image_runtime_mounts_public_key=True,endpoint_generation_before=7,endpoint_generation_after=9,
        approval_still_revoked10=True,all29jobs_and_host_data_exact=True,metadata_installer_not_involved=True))
    phase(record,'public_config9_attested');print('Separate operator updated publicconfig7->9/restarted same worker/image; approval remains revoked10 and all host data exact',flush=True)

def publish():
    state,native=context();record=f.load(MARKER);assert record['state']=='public_config9_attested';operator=op(native)
    assert operator.publisher._document()['generation']==10
    phase(record,'preparing_current_approval')
    review=json.loads(f.command('image-success-prepare-publication11',cli(native)+['prepare','--endpoint',str(PRIVATE/'enabled-endpoint.json'),'--key-id',record['key_id']]))
    assert json.loads(f.command('image-success-review-publication11',cli(native)+['review',review['plan']['operation_id']]))==review
    f.save('runtime-review.json',review);phase(record,'publishing_current_approval')
    result=json.loads(f.command('image-success-publish11',cli(native)+['publish',review['plan']['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive']))
    assert result['generation']==11 and result['state']=='enabled';f.save('runtime-publication.json',result)
    current=base.worker(native,'image-success-worker-current');assert current['container_id']==record['container_id'] and current['image']==record['image']
    f.write(PRIVATE/'worker-current.json',current)
    assert base.snapshot(state,'image-success-after-publication')==f.load(PRIVATE/'operator-data-before.json')
    f.save('current-planning-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
    phase(record,'current_image_published11');f.phase(state,'image_success_worker_current11_metadata_old_suspended')
    print('Fresh independent publication11/endpoint9/current worker approved; host metadata remains old+suspended until a NEW upgrade',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['configure','publish']);a=p.parse_args();globals()[a.action]()
