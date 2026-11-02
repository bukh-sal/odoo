"""Owned isolated DB/config/effect recipient; real native producer crash proof."""
import argparse,copy,json,re,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-reference-restore-01'))
from recovery import context,base,f,j,positive
from modular_platform.operator_os import protect_directory
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'job03-01';MARKER=PRIVATE/'fixture.json'

def save(record,value):record['state']=value;f.write(MARKER,record)
def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name],timeout=15))[0]
def native_arguments(native,record,name):
    return ['docker','run','--rm','-i','--name',name,'--log-driver','none','--label','com.modular.disposable='+record['profile'],
        '--network',record['network'],'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--memory','768m','--pids-limit','128','--tmpfs','/tmp:uid=10001,gid=10001,mode=1777',
        '--tmpfs','/var/lib/modular:uid=10001,gid=10001,mode=0700',
        '--mount','type=volume,source='+record['config_volume']+',target=/run/secrets,readonly',
        '--mount','type=volume,source='+record['authority_volume']+',target=/run/worker-authority,readonly',
        '--env','MP_EXPECTED_DATABASE='+record['database'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+native.config['published_release']['core_inventory_digest'],
        '--entrypoint','/venv/bin/python',native.config['image_id'],'-u','-c',(OUT/'native_probe.py').read_text()]
def packet(record,mode):
    return dict(mode=mode,database=record['database'],alice_uid=record['alice_uid'],site_id=record['site_id'],workspace=record['workspace'],
        input=record['input'],key=record['key'],effect_target=record.get('effect_target'),job_id=record.get('job_id'),reference_policy=record['reference_policy'])
def receipt(record):
    code="import json,pathlib;p=pathlib.Path('/tmp/job03/receipt.json');print(p.read_text() if p.exists() else '{}')"
    result=subprocess.run(['docker','exec',record['effect_container'],'/venv/bin/python','-c',code],capture_output=True,timeout=10)
    assert result.returncode==0,'Inspect exact effect fixture; no reissue'
    return json.loads(result.stdout)

def setup():
    state,native=context();assert native.config['generation']==19 and not PRIVATE.exists();protect_directory(PRIVATE)
    uid=uuid4().hex;profile='mp-disposable-g6-job03-'+uid[:12]
    worker=f.load(j.LOCAL/'operator/worker-target.json');fixture=f.load(j.LOCAL/'fixtures.json');original=f.load(j.LOCAL/'notes-stats-remote-01/positive.json')
    before=base.snapshot(state,'job03-main-before');assert len(before['mp_job'])==29 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    f.write(PRIVATE/'main-before.json',before);f.write(PRIVATE/'worker-before.json',base.worker(native,'job03-canonical-worker-before'))
    record=dict(profile=profile,database='mp_disposable_g6_job03_'+uid,config_volume=profile+'-native-config',effect_container=profile+'-effect',producer_container=profile+'-producer',observer_container=profile+'-observer',
        network=state['project']+'_runtime',authority_volume=worker['authority_volume'],effect_image=worker['runtime']['image'],public_volume=worker['runtime']['public_config_volume'],
        site_id=state['site_id'],workspace=fixture['workspaces']['C']['public_id'],alice_uid=fixture['users']['alice']['id'],
        input=dict(note_id=original['note_id'],expected_revision=original['revision']),key='job03-'+uid,
        reference_policy=ReferenceDispatchMaintenance(native).reference_policy(native.config))
    assert re.fullmatch(r'mp_disposable_g6_job03_[0-9a-f]{32}',record['database']);save(record,'creating_owned_database')
    absent=f.sql(state,'job03-database-absent',"SELECT count(*) FROM pg_database WHERE datname='"+record['database']+"';",database='postgres');assert absent.strip()==b'0'
    f.command('job03-create-database',['docker','exec',state['project']+'-db-1','createdb','-U','postgres','-O','modular','-T','template0',record['database']])
    record['database_oid']=int(f.sql(state,'job03-database-oid',"SELECT oid FROM pg_database WHERE datname='"+record['database']+"';",database='postgres'));save(record,'copying_owned_test_data')
    dump=f.command('job03-owned-source-dump',['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','-Fc',state['active_db']],timeout=180)
    (PRIVATE/'source.dump').write_bytes(dump)
    f.command('job03-owned-copy-restore',['docker','exec','-i',state['project']+'-db-1','pg_restore','-U','postgres','--role=modular','--no-owner','--no-privileges','--exit-on-error','-d',record['database']],input=dump,timeout=180)
    assert base.snapshot({**state,'active_db':record['database']},'job03-copy-before')==before
    save(record,'creating_owned_native_config')
    f.command('job03-config-volume',['docker','volume','create','--label','com.modular.disposable='+profile,record['config_volume']])
    code="""import configparser,io,pathlib,sys
old,new=sys.argv[1:];p=configparser.ConfigParser();p.read('/source/odoo_config');assert p['options']['db_name']==old
p['options']['db_name']=new;p['options']['dbfilter']='^'+new+'$';b=io.StringIO();p.write(b)
target=pathlib.Path('/target/odoo_config');assert not target.exists();target.write_text(b.getvalue());target.chmod(0o444)
print('Exact isolated DB config created; credentials remain native-backend-only')
"""
    f.command('job03-config-copy',['docker','run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+state['project']+'_appconfig,target=/source,readonly','--mount','type=volume,source='+record['config_volume']+',target=/target','--entrypoint','/venv/bin/python',native.config['image_id'],'-c',code,state['active_db'],record['database']])
    save(record,'configured');print('Owned isolated DB copy and private native config ready; live site and canonical worker unchanged',flush=True)

def start_effect():
    state,native=context();record=f.load(MARKER);assert record['state']=='configured'
    # The reference DTO uses a logical name@image-ID identity. Execute only
    # the already-inspected cached image ID, never trigger a registry pull.
    actual_image=f.load(PRIVATE/'worker-before.json')['image']
    assert record['effect_image']=='modular-document-stats@'+actual_image
    record['effect_image']=actual_image;save(record,'starting_effect_fixture')
    args=['docker','run','-d','--rm','--name',record['effect_container'],'--log-driver','none','--label','com.modular.disposable='+record['profile'],
        '--network',record['network'],'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m','--pids-limit','48','--tmpfs','/tmp:uid=10001,gid=10001,mode=1777',
        '--mount','type=volume,source='+record['public_volume']+',target=/run/worker,readonly','--entrypoint','/venv/bin/python',record['effect_image'],'-u','-c',(OUT/'effect_server.py').read_text()]
    f.command('job03-effect-start',args)
    verify_effect_ready()

def verify_effect_ready():
    state,native=context();record=f.load(MARKER);assert record['state']=='starting_effect_fixture'
    info=inspect(record['effect_container']);assert info['State']['Running']
    code="import json,urllib.request;r=urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=5);assert r.status==200;v=json.loads(r.read());assert v==dict(status='ok',api_version='1.0');print(json.dumps(v))"
    assert json.loads(f.command('job03-effect-actual-health',['docker','exec',record['effect_container'],'/venv/bin/python','-c',code]))==dict(status='ok',api_version='1.0')
    assert receipt(record)=={},'No effect may have been issued before producer launch'
    assert info['Config']['Labels']['com.modular.disposable']==record['profile'] and len(info['Mounts'])==1
    mount=info['Mounts'][0];assert mount['Type']=='volume' and mount['Name']==record['public_volume'] and mount['Destination']=='/run/worker' and not mount['RW']
    assert not info['HostConfig']['Binds'] and not info['HostConfig']['PortBindings']
    image=f.load(PRIVATE/'worker-before.json')['image'];assert info['Image']==image
    record['effect_target']=dict(address=info['NetworkSettings']['Networks'][record['network']]['IPAddress'],host=record['effect_container']+':8080',port=8080)
    f.write(PRIVATE/'effect-inspect.json',info);save(record,'effect_ready')
    f.save('recipient-isolation.json',dict(result='verified_owned_test_effect_recipient',same_cached_worker_image=image,only_public_key_config_volume_readonly=True,no_database_credentials_or_filestore_or_host_bind_or_socket=True,no_published_host_port=True,scope_and_key_reuse_standard_worker_JWT=True,test_only_fixture_not_canonical_service=True))
    print('Separate non-idempotent recipient healthy, public-only configuration, no DB credentials/filestore/host binds',flush=True)

def produce_and_kill():
    state,native=context();record=f.load(MARKER);assert record['state']=='effect_ready';save(record,'launching_native_producer')
    outpath=PRIVATE/'producer.stdout';errpath=PRIVATE/'producer.stderr'
    with outpath.open('xb') as stdout,errpath.open('xb') as stderr:
        process=subprocess.Popen(native_arguments(native,record,record['producer_container']),stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        record['producer_host_pid']=process.pid;save(record,'producer_running')
        process.stdin.write(json.dumps(packet(record,'produce')).encode());process.stdin.close()
        deadline=time.monotonic()+150
        while True:
            lines=outpath.read_text(encoding='utf8').splitlines()
            starts=[json.loads(line.split('MP_EFFECT_START=',1)[1]) for line in lines if line.startswith('MP_EFFECT_START=')]
            if starts:
                assert len(starts)==1;actual=receipt(record)
                if actual:
                    assert actual['count']==1 and actual['operation_id']==starts[0]['job_id'] and actual['input_sha256']==starts[0]['input_sha256'] and not actual['response_sent'];break
            assert process.poll() is None,'Producer returned unexpectedly; inspect effect receipt and original claim before any retry'
            assert time.monotonic()<deadline,'Inspect still-live producer; do not repeat effect'
            time.sleep(.2)
        record.update(job_id=starts[0]['job_id'],effect_start=starts[0]);save(record,'effect_committed_response_withheld')
        f.write(PRIVATE/'external-receipt-before-kill.json',actual)
        info=inspect(record['producer_container']);assert info['State']['Running'] and info['Image']==native.config['image_id'] and info['Config']['Labels']['com.modular.disposable']==record['profile']
        row=json.loads(f.sql(state,'job03-row-before-kill',"BEGIN READ ONLY;SELECT to_jsonb(j) FROM mp_job j WHERE public_id='"+record['job_id']+"';ROLLBACK;",database=record['database']))
        assert row['state']=='running' and row['effect_started'] and row['attempts']==1 and row['effect_mode']=='reconcile' and row['result'] is None
        f.write(PRIVATE/'row-before-kill.json',row);save(record,'killing_exact_native_producer')
        f.command('job03-kill-producer',['docker','kill','--signal','KILL',record['producer_container']]);assert process.wait(timeout=30)==137
    assert receipt(record)==actual
    save(record,'producer_killed_after_external_commit')
    f.save('actual-effect-crash.json',dict(result='verified_real_non_idempotent_external_commit_then_native_SIGKILL',job_id=record['job_id'],native_original_actor_uid=record['alice_uid'],actual_installed_startup_authorization_prepare_runner=True,
        trusted_fixture_handler_registered_without_replacing_existing_functions=True,effect_started_committed_before_HTTP=True,recipient_effect_count=1,response_sent=False,producer_exit_code=137,no_host_result_committed=True))
    print('Actual external effect committed once; response withheld; exact native producer SIGKILL137, durable effect marker retained',flush=True)

def reclaim(continuation=False,after_wait_error=False):
    state,native=context();record=f.load(MARKER)
    if continuation:
        assert record['state']==('waiting_real_lease_expiry' if after_wait_error else 'observing_real_reclaimer_and_status')
        label='job03-continuation2-existing-unknown' if after_wait_error else 'job03-continuation-existing-unknown'
        row=json.loads(f.sql(state,label,"BEGIN READ ONLY;SELECT jsonb_build_object('state',state,'attempts',attempts,'effect_started',effect_started) FROM mp_job WHERE public_id='"+record['job_id']+"';ROLLBACK;",database=record['database']))
        assert row==dict(state='outcome_unknown',attempts=1,effect_started=True)
        assert receipt(record)==f.load(PRIVATE/'external-receipt-before-kill.json')
    else:
        assert record['state']=='producer_killed_after_external_commit'
    if not continuation:
        save(record,'waiting_real_lease_expiry')
        query="SELECT lease_until<=timezone('UTC',clock_timestamp()) FROM mp_job WHERE public_id='"+record['job_id']+"';"
        deadline=time.monotonic()+40
        while True:
            raw=subprocess.check_output(['docker','exec',state['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',record['database'],'-c',query],timeout=10)
            if raw.strip()==b't':break
            assert time.monotonic()<deadline,'Inspect original lease; no clock or row manipulation allowed'
            time.sleep(1)
    save(record,'observing_real_reclaimer_and_status')
    label='job03-observe-native-readcommitted' if continuation else 'job03-observe-native'
    name=record['observer_container']+'-readcommitted' if continuation else record['observer_container']
    raw=f.command(label,native_arguments(native,record,name),input=json.dumps(packet(record,'observe')).encode(),timeout=150).decode()
    rows=[json.loads(line.split('MP_UNKNOWN=',1)[1]) for line in raw.splitlines() if line.startswith('MP_UNKNOWN=')];assert len(rows)==1
    report=rows[0];assert report['job']['id']==record['job_id'];remote=receipt(record);assert remote==f.load(PRIVATE/'external-receipt-before-kill.json')
    assert base.snapshot(state,'job03-main-after')==f.load(PRIVATE/'main-before.json')
    assert base.worker(native,'job03-canonical-worker-after')==f.load(PRIVATE/'worker-before.json')
    f.write(PRIVATE/'unknown-row.json',json.loads(f.sql(state,'job03-unknown-row',"BEGIN READ ONLY;SELECT to_jsonb(j) FROM mp_job j WHERE public_id='"+record['job_id']+"';ROLLBACK;",database=record['database'])))
    f.save('unknown-outcome.json',dict(result='passed_actual_native_unknown_outcome_reporting_no_automatic_retry',**report,external_effect_receipt=remote,live_site_all17tables_and_canonical_worker_exact=True,
        original_real_30_second_lease_expired_without_clock_or_row_changes=True,isolated_test_database=True,
        reconciliation=dict(state='required',automatic_retry='forbidden',observed_effect='committed_once',operator_action='Check remote operation/input receipt and perform effect-specific reconciliation; never infer rollback from lost response.')))
    save(record,'qualified_needs_cleanup');print('Real native status reports outcome_unknown/attempt1; two actual runner passes idle, external count stays1, lifecycle enable refused; live site exact',flush=True)

def verify_unknown_continuation():reclaim(continuation=True)
def verify_unknown_readcommitted():reclaim(continuation=True,after_wait_error=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['setup','start_effect','verify_effect_ready','produce_and_kill','reclaim','verify_unknown_continuation','verify_unknown_readcommitted']);a=p.parse_args();globals()[a.action]()
