"""Separate explicit operator runtime/image/approval change; no installer launch."""
import argparse,copy,hashlib,json,subprocess,sys,time,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import suspend as s
ROOT,OUT,PRIVATE,f,j,base=s.ROOT,s.OUT,s.PRIVATE,s.f,s.j,s.base
from modular_platform.worker_operator import WorkerOperator
from modular_platform.operator_os import OperatorError
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
RUNTIME=PRIVATE/'runtime.json'
PROJECT='mp-disposable-document-stats-06';VOLUME=PROJECT+'-public-config'
def context():return s.context()
def op(native):return WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json')
def cli(native):return base.prefix()+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]
def phase(record,value):record['state']=value;f.write(RUNTIME,record)
def scoped_entry(document,scope):
    rows=[e for e in document['endpoints'] if all(e['descriptor'][k]==scope[k] for k in ['site_id','workspace_id','installation_id'])]
    assert len(rows)==1
    return rows[0]

def revoke():
    state,native=context();cycle=f.load(s.MARKER);assert cycle['suspend']['state']=='preservation_verified' and not RUNTIME.exists()
    operator=op(native);publication=operator.publisher._document();assert publication['generation']==7
    entry=scoped_entry(publication,cycle['scope']);assert entry['descriptor']['generation']==5 and entry['descriptor']['state']=='enabled'
    before=base.snapshot(state,'image-runtime-before-revoke');assert len(before['mp_job'])==29
    installation=next(r for r in before['mp_plugin_installation'] if r['public_id']==cycle['scope']['installation_id'])
    features=[r for r in before['mp_workspace_plugin'] if r['installation_id']==installation['id']]
    assert len(features)==1 and all(r['availability']=='suspended' for r in features)
    f.write(PRIVATE/'runtime-data-before.json',before);f.write(PRIVATE/'runtime-worker-before.json',base.worker(native,'image-runtime-worker-before'))
    f.write(PRIVATE/'runtime-authority-before.json',publication);f.write(PRIVATE/'runtime-config-before.json',operator.config)
    record=dict(scope=cycle['scope'],key_id=entry['key_id'],old_container=f.load(PRIVATE/'runtime-worker-before.json')['container_id'])
    endpoint=copy.deepcopy(entry['descriptor']);endpoint.update(generation=6,state='revoked');f.write(PRIVATE/'runtime-revoked-endpoint.json',endpoint)
    phase(record,'preparing_revocation')
    review=json.loads(f.command('image-runtime-revoke-prepare',cli(native)+['prepare','--endpoint',str(PRIVATE/'runtime-revoked-endpoint.json'),'--key-id',record['key_id']]))
    assert json.loads(f.command('image-runtime-revoke-review',cli(native)+['review',review['plan']['operation_id']]))==review
    f.save('runtime-revocation-review.json',review);phase(record,'publishing_revocation')
    result=json.loads(f.command('image-runtime-revoke-publish',cli(native)+['publish',review['plan']['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive']))
    assert result['generation']==8 and result['state']=='revoked';f.save('runtime-revocation.json',result)
    assert base.snapshot(state,'image-runtime-after-revoke')==before
    phase(record,'revoked8');print('Separate operator publication8/endpoint6 revoked; all provider scopes suspended and data exact',flush=True)

def switch():
    state,native=context();record=f.load(RUNTIME);assert record['state']=='revoked8';operator=op(native)
    assert operator.publisher._document()['generation']==8
    build=f.load(OUT/'worker-build.json');image=build['image_id'];old=f.load(PRIVATE/'runtime-worker-before.json')
    assert image!=old['image'] and record['old_container']==old['container_id']
    absent=subprocess.run(['docker','volume','inspect',VOLUME],capture_output=True,timeout=15);assert absent.returncode!=0
    existing=f.command('image-runtime-project06-absent',['docker','ps','--all','--filter','label=com.docker.compose.project='+PROJECT,'--format','{{.ID}}']);assert not existing.strip()
    phase(record,'creating_public_only_volume')
    f.command('image-runtime-create-public-volume',['docker','volume','create','--label','com.modular.disposable='+PROJECT,VOLUME])
    entry=scoped_entry(f.load(PRIVATE/'runtime-authority-before.json'),record['scope']);public=(operator.publisher.keys/(entry['descriptor']['public_key_ref']+'.pem')).read_text()
    digest=hashlib.sha256(public.encode()).hexdigest();assert digest==old['public_digest']
    payload=dict(scope=record['scope'],public=public,key_id=record['key_id'])
    code="import json,pathlib,sys;r=pathlib.Path('/config');assert not list(r.iterdir());v=json.load(sys.stdin);(r/'public.pem').write_text(v['public']);(r/'public.pem').chmod(0o444);(r/'config.json').write_text(json.dumps(dict(v['scope'],key_id=v['key_id'],public_key_file='/run/worker/public.pem',endpoint_generation=7)));(r/'config.json').chmod(0o444);assert {p.name for p in r.iterdir()}=={'config.json','public.pem'};print('Public-only scope/key/config7 provisioned')"
    f.command('image-runtime-initialize-public-volume',['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--log-driver','none','--mount','type=volume,source='+VOLUME+',target=/config','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code],input=json.dumps(payload).encode())
    phase(record,'stopping_old_worker')
    info=json.loads(f.command('image-runtime-old-before-stop',['docker','inspect',record['old_container']]))[0]
    assert info['Image']==old['image'] and info['State']['Running']
    f.command('image-runtime-stop-old',['docker','stop','--time','20',record['old_container']],timeout=40)
    info=json.loads(f.command('image-runtime-old-stopped',['docker','inspect',record['old_container']]))[0]
    assert not info['State']['Running'] and info['State']['ExitCode']==0
    phase(record,'starting_new_worker')
    env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=build['expected_image'],MP_DOCUMENT_STATS_NETWORK=operator.config['runtime']['network'],MP_DOCUMENT_STATS_CONFIG_VOLUME=VOLUME)
    # f.command intentionally owns stdout/stderr; the environment contains only public runtime identities.
    args=['docker','compose','-p',PROJECT,'-f','services/document_stats/compose.yaml','--profile','worker','up','-d','--no-build','--pull','never']
    with (PRIVATE/'compose.stdout').open('xb') as out,(PRIVATE/'compose.stderr').open('xb') as err:
        result=subprocess.run(args,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=90)
    assert result.returncode==0
    ident=f.command('image-runtime-new-container',['docker','ps','--all','--no-trunc','--filter','label=com.docker.compose.project='+PROJECT,'--filter','label=com.docker.compose.service=document-stats','--format','{{.ID}}']).decode().strip();assert len(ident)==64
    record.update(container_id=ident,image_id=image,public_digest=digest);phase(record,'new_worker_started')
    config=copy.deepcopy(operator.config);config['runtime'].update(project=PROJECT,public_config_volume=VOLUME,image=build['expected_image'])
    f.write(j.LOCAL/'operator/worker-target.json',config)
    endpoint=copy.deepcopy(entry['descriptor']);endpoint.update(generation=7,state='enabled',expected_image_digest=image);f.write(PRIVATE/'runtime-new-endpoint.json',endpoint)
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        info=json.loads(subprocess.check_output(['docker','inspect',ident],timeout=10))[0]
        if info['State'].get('Health',{}).get('Status')=='healthy':break
        time.sleep(1)
    assert info['State']['Running'] and info['State']['Health']['Status']=='healthy' and info['Image']==image
    observed=op(native).observer(endpoint,digest,record['key_id']);assert observed['container_id']==ident
    assert base.snapshot(state,'image-runtime-after-switch')==f.load(PRIVATE/'runtime-data-before.json')
    f.save('runtime-switch.json',dict(result='passed_separate_operator_image_switch_before_metadata_upgrade',old_container=record['old_container'],new_container=ident,
        old_image=old['image'],new_image=image,old_worker_stopped_retained=True,public_only_config_volume=VOLUME,new_endpoint_generation=7,
        authority_still_revoked8=True,all29jobs_30Notes_other17tables_exact=True,no_installer_runtime_control=True))
    phase(record,'new_worker_attested');print('Explicit operator Compose06 new image/config7 healthy; old05 stopped retained, authority still revoked8',flush=True)

def repair_reference():
    """Finish the diagnosed raw-ID Config.Image refusal, without replaying switch."""
    state,native=context();record=f.load(RUNTIME);assert record['state']=='new_worker_started';operator=op(native)
    build=f.load(OUT/'worker-build.json');ident=record['container_id'];image=build['image_id']
    assert operator.publisher._document()['generation']==8
    info=json.loads(f.command('image-runtime-reference-refusal-inspect',['docker','inspect',ident]))[0]
    assert info['Image']==info['Config']['Image']==image and info['Config']['Labels']['com.docker.compose.project']==PROJECT
    assert info['State']['Running'] and info['State']['Health']['Status']=='healthy'
    images=json.loads(f.command('image-runtime-reference-image',['docker','image','inspect',image]))[0]
    assert images['Id']==image and build['expected_image'] in images['RepoDigests']
    f.write(PRIVATE/'discarded-raw-ID-worker.json',info);phase(record,'recreating_exact_worker_with_verified_digest_reference')
    f.command('image-runtime-stop-raw-ID-worker',['docker','stop','--time','20',ident],timeout=40)
    stopped=json.loads(f.command('image-runtime-raw-ID-stopped',['docker','inspect',ident]))[0]
    assert not stopped['State']['Running'] and stopped['State']['ExitCode']==0
    f.command('image-runtime-remove-raw-ID-worker',['docker','rm',ident])
    env=dict(os.environ,MP_DOCUMENT_STATS_IMAGE=build['expected_image'],MP_DOCUMENT_STATS_NETWORK=operator.config['runtime']['network'],MP_DOCUMENT_STATS_CONFIG_VOLUME=VOLUME)
    args=['docker','compose','-p',PROJECT,'-f','services/document_stats/compose.yaml','--profile','worker','up','-d','--no-build','--pull','never']
    with (PRIVATE/'compose-reference.stdout').open('xb') as out,(PRIVATE/'compose-reference.stderr').open('xb') as err:
        result=subprocess.run(args,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=90)
    assert result.returncode==0
    current=f.command('image-runtime-reference-container',['docker','ps','--all','--no-trunc','--filter','label=com.docker.compose.project='+PROJECT,'--filter','label=com.docker.compose.service=document-stats','--format','{{.ID}}']).decode().strip()
    assert len(current)==64 and current!=ident;record.update(container_id=current,discarded_raw_id_container=ident);phase(record,'reference_worker_started')
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        info=json.loads(subprocess.check_output(['docker','inspect',current],timeout=10))[0]
        if info['State'].get('Health',{}).get('Status')=='healthy':break
        time.sleep(1)
    endpoint=f.load(PRIVATE/'runtime-new-endpoint.json')
    observed=operator.observer(endpoint,record['public_digest'],record['key_id']);assert observed['container_id']==current
    assert base.snapshot(state,'image-runtime-after-reference-correction')==f.load(PRIVATE/'runtime-data-before.json')
    old=f.load(PRIVATE/'runtime-worker-before.json')
    f.save('runtime-switch.json',dict(result='passed_separate_operator_image_switch_before_metadata_upgrade',old_container=record['old_container'],new_container=current,
        old_image=old['image'],new_image=image,actual_Config_Image_and_RepoDigests_match_verified_reference=True,old_worker_stopped_retained=True,
        public_only_config_volume=VOLUME,new_endpoint_generation=7,authority_still_revoked8=True,all29jobs_30Notes_other17tables_exact=True,
        no_installer_runtime_control=True,guard_correctly_refused_raw_id_Config_Image=True,discarded_unused_misconfigured_container_removed=True))
    phase(record,'new_worker_attested');print('Exact cached digest reference/actual image/config/scope/network attested; unused raw-ID container archived/removed, pub8 remains revoked',flush=True)

def publish():
    state,native=context();record=f.load(RUNTIME);assert record['state']=='new_worker_attested';operator=op(native)
    endpoint=f.load(PRIVATE/'runtime-new-endpoint.json')
    negatives=[]
    for kind in ['old_image','third_image']:
        bad=copy.deepcopy(endpoint);bad['expected_image_digest']=f.load(PRIVATE/'runtime-worker-before.json')['image'] if kind=='old_image' else 'sha256:'+'0'*64
        try:operator.publisher.prepare(bad,record['key_id'],operator.observer)
        except OperatorError as exc:negatives.append(dict(case=kind,result='refused',reason=str(exc)))
        else:raise AssertionError('Wrong actual image accepted')
    assert operator.publisher._document()['generation']==8
    review=json.loads(f.command('image-runtime-new-prepare',cli(native)+['prepare','--endpoint',str(PRIVATE/'runtime-new-endpoint.json'),'--key-id',record['key_id']]))
    assert json.loads(f.command('image-runtime-new-review',cli(native)+['review',review['plan']['operation_id']]))==review
    f.save('runtime-new-review.json',review);record.update(publication_operation=review['plan']['operation_id']);phase(record,'publishing_new_image')
    result=json.loads(f.command('image-runtime-new-publish',cli(native)+['publish',review['plan']['operation_id'],'--plan-hash',review['plan_hash'],'--noninteractive']))
    assert result['generation']==9 and result['state']=='enabled';f.save('runtime-new-publication.json',result)
    try:ReferenceDispatchMaintenance(native).reference_policy(native.config)
    except OperatorError as exc:
        assert 'exact independently published endpoint/image' in str(exc);negatives.append(dict(case='ordinary_old_metadata_new_image',result='refused',reason=str(exc)))
    else:raise AssertionError('Default maintenance admitted unreviewed mismatch')
    f.save('runtime-refusals.json',dict(result='passed_actual_operator_image_and_default_maintenance_refusals',cases=negatives))
    f.save('runtime-planning-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
    assert base.snapshot(state,'image-runtime-after-publication')==f.load(PRIVATE/'runtime-data-before.json')
    f.write(PRIVATE/'runtime-worker-current.json',base.worker(native,'image-runtime-current'))
    phase(record,'new_image_published9');f.phase(state,'image_transition_new_worker_approved_metadata_old_suspended')
    print('Independent new-image publication9/endpoint7 enabled; wrong images/default mismatch refused, metadata remains old+suspended',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['revoke','switch','repair_reference','publish']);a=p.parse_args();globals()[a.action]()
