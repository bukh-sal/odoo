"""Explicit operator reference-runtime generation change, outside installation."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core15-upgrade-01'))
import activate as base
from modular import configuration
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
j=base.j;f=base.f;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'manager-reregister-01';MARKER=PRIVATE/'runtime.json'

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    assert native.config['generation'] in (15,16)
    return state,native

def operator(native):return WorkerOperator(native.store,native.target_path,native.target_path.with_name('worker-target.json'))
def command(label,args,*,input=None,timeout=120):
    out=PRIVATE/(label+'.stdout');err=PRIVATE/(label+'.stderr');assert not out.exists()
    with out.open('xb') as o,err.open('xb') as e:
        result=subprocess.run(args,input=input,stdout=o,stderr=e,cwd=ROOT,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert result.returncode==0,'Inspect private step without replay: '+label
    return out.read_bytes()
def inspect(ident):return json.loads(subprocess.check_output(['docker','inspect',ident],timeout=15))[0]
def physical(row):return {k:row[k] for k in ['Id','Image','Mounts','Config','HostConfig']}|dict(network_names=sorted(row['NetworkSettings']['Networks']))
def cli():return base.prefix()+['worker','--store',str(j.LOCAL/'operator/control'),'--deployment-config',str(j.LOCAL/'operator/target.json'),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]

def baseline():
    state,native=context();assert not PRIVATE.exists();protect_directory(PRIVATE)
    op=operator(native);document=op.publisher._document();assert document['generation']==4
    scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope'];entry=next(e for e in document['endpoints'] if e['descriptor']['installation_id']==scope['installation_id'])
    assert entry['descriptor']['generation']==2 and entry['descriptor']['state']=='revoked'
    old=copy.deepcopy(entry['descriptor']);old['generation']=1
    observed=op.observer(old,op.publisher._key_digest(old),entry['key_id']);info=inspect(observed['container_id'])
    f.write(PRIVATE/'worker-before.json',info);f.write(PRIVATE/'publication-before.json',document)
    f.write(PRIVATE/'data-before.json',base.snapshot(state,'manager-reregister01-runtime-data-before'))
    data=f.load(PRIVATE/'data-before.json');assert next(r for r in data['mp_plugin_installation'] if r['public_id']==scope['installation_id'])['state']=='removed'
    raw=f.sql(state,'manager-reregister01-control-before',"BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(c) ORDER BY id) FROM mp_dispatch_control c; ROLLBACK;")
    control=json.loads(raw);assert control[0]['generation']==76 and control[0]['state']=='enabled';f.write(PRIVATE/'control-before.json',control)
    endpoint=copy.deepcopy(entry['descriptor']);endpoint.update(generation=3,state='enabled');f.write(PRIVATE/'enabled-endpoint.json',endpoint)
    f.write(MARKER,dict(state='baseline_captured',scope=scope,container_id=info['Id'],key_id=entry['key_id'],public_digest=observed['public_digest']))
    print('Current removed metadata/control76/revoked publication4 and exact worker baseline confirmed')

def transition():
    state,native=context();m=f.load(MARKER);assert m['state']=='baseline_captured';old=f.load(PRIVATE/'worker-before.json')
    assert physical(inspect(m['container_id']))==physical(old)
    m['state']='operator_stopping_for_public_config';f.write(MARKER,m)
    command('operator-stop-config',['docker','stop','--time','20',m['container_id']],timeout=40)
    stopped=inspect(m['container_id']);assert not stopped['State']['Running'] and stopped['State']['ExitCode']==0
    op=operator(native);volume=op.config['runtime']['public_config_volume']
    volumeinfo=json.loads(command('public-volume-inspect',['docker','volume','inspect',volume]))[0]
    assert volumeinfo['Labels']['com.modular.disposable']==op.config['runtime']['project']
    m['state']='operator_updating_public_config';f.write(MARKER,m)
    code="import json,pathlib,hashlib,os,sys;r=pathlib.Path('/config');v=json.load(sys.stdin);assert {p.name for p in r.iterdir()}=={'config.json','public.pem'};assert hashlib.sha256((r/'public.pem').read_bytes()).hexdigest()==v['public_digest'];p=r/'config.json';c=json.loads(p.read_text());expected=dict(v['scope'],public_key_file='/run/worker/public.pem',key_id=v['key_id'],endpoint_generation=1);assert c==expected;c['endpoint_generation']=3;t=r/'config.next';t.write_text(json.dumps(c));t.chmod(0o444);os.replace(t,p);print('Exact public-only configuration advanced1to3; immutable key retained')"
    payload=dict(scope={k:m['scope'][k] for k in ['site_id','workspace_id','installation_id']},key_id=m['key_id'],public_digest=m['public_digest'])
    command('operator-update-public-config',['docker','run','--rm','-i','--name',state['project']+'-reference-public-config3','--log-driver','none','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/config','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code],input=json.dumps(payload).encode())
    m['state']='operator_starting_config3';f.write(MARKER,m)
    command('operator-start-config3',['docker','start',m['container_id']])
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        if inspect(m['container_id'])['State'].get('Health',{}).get('Status')=='healthy':break
        time.sleep(1)
    endpoint=f.load(PRIVATE/'enabled-endpoint.json');attested=op.observer(endpoint,m['public_digest'],m['key_id'])
    assert attested['container_id']==m['container_id'] and physical(inspect(m['container_id']))==physical(old)
    assert base.snapshot(state,'manager-reregister01-runtime-data-after-transition')==f.load(PRIVATE/'data-before.json')
    assert op.publisher._document()==f.load(PRIVATE/'publication-before.json')
    f.save('operator-runtime-transition.json',dict(result='passed_separate_operator_public_config_transition',same_worker_container_image_mounts_network_config=True,public_key_digest_unchanged=True,public_config_generation_before=1,public_config_generation_after=3,metadata_unchanged_removed=True,all17tables_exact=True,independent_publication_still4_revoked=True,no_metadata_executor_invoked=True,new_images=0,new_volumes=0,update_helper_auto_removed=True))
    m['state']='config3_attested';f.write(MARKER,m);f.guard(state)
    print('Separate operator stop/public-config3/start attested; same worker/key/image, metadata remains removed')

def publish():
    state,native=context();m=f.load(MARKER);assert m['state']=='config3_attested'
    review=json.loads(command('prepare-publication5',cli()+['prepare','--endpoint',str(PRIVATE/'enabled-endpoint.json'),'--key-id',m['key_id']]))
    assert json.loads(command('review-publication5',cli()+['review',review['plan']['operation_id']]))==review
    f.save('publication-independent-review.json',review);m.update(state='publishing5',publication_operation=review['plan']['operation_id'],publication_hash=review['plan_hash']);f.write(MARKER,m)
    result=json.loads(command('publish5',cli()+['publish',m['publication_operation'],'--plan-hash',m['publication_hash'],'--noninteractive']))
    assert result['generation']==5 and result['state']=='enabled';f.save('publication-result.json',result)
    m['state']='published5';f.write(MARKER,m);f.phase(state,'manager_reregister01_endpoint3_published5');print('Exact independently reviewed enabled endpoint3/document5 published; no metadata registration yet')

def stop_for_registration():
    state,native=context();m=f.load(MARKER);assert m['state']=='published5'
    op=operator(native);endpoint=f.load(PRIVATE/'enabled-endpoint.json');op.observer(endpoint,m['public_digest'],m['key_id'])
    m['state']='operator_stopping_for_registration';f.write(MARKER,m)
    command('operator-stop-registration',['docker','stop','--time','20',m['container_id']],timeout=40)
    row=inspect(m['container_id']);assert not row['State']['Running'] and row['State']['ExitCode']==0
    f.write(PRIVATE/'worker-stopped.json',row);f.write(PRIVATE/'publication5.json',op.publisher._document())
    observed=op.planning_state();assert observed['service_health'][m['scope']['installation_id']+':'+m['scope']['workspace_id']]['state']=='unavailable'
    f.save('stopped-profile-publication.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
    assert base.snapshot(state,'manager-reregister01-stopped-data-after')==f.load(PRIVATE/'data-before.json')
    f.save('stopped-runtime-prerequisite.json',dict(result='passed_actual_operator_stopped_runtime_registration_preimage',publication_generation=5,endpoint_generation=3,endpoint_approved_but_process_stopped=True,all17tables_exact=True,metadata_still_removed=True,no_installer_runtime_control=True))
    m['state']='stopped_registration_ready';f.write(MARKER,m);f.phase(state,'manager_reregister01_worker_stopped_registration_ready');f.guard(state)
    print('Exact worker separately stopped; current approved endpoint3 observed unavailable, metadata still removed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','transition','publish','stop_for_registration']);args=p.parse_args();globals()[args.action]()
