"""Real immutable default-entrypoint probes on new owned disposable copies only."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.operator_store import _write_new
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql

SEED="""import configparser,json,os,pathlib,shutil,sys
data=json.load(sys.stdin);base=pathlib.Path('/probe')
config=configparser.ConfigParser();config.read('/source-config/odoo_config')
config['options'].update(db_name=data['database'],dbfilter='^'+data['database']+'$',workers='0',max_cron_threads='0')
(base/'config').mkdir();(base/'data').mkdir()
with (base/'config/odoo_config').open('x') as stream:config.write(stream)
(base/'config/odoo_config').chmod(0o444)
source=pathlib.Path('/source-data/filestore')/data['source_database'];dest=base/'data/filestore'/data['database'];dest.parent.mkdir()
shutil.copytree(source,dest)
for p in [base/'data',*(base/'data').rglob('*')]:os.chown(p,10001,10001)
"""


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));marker=LOCAL/'worker-fence-matrix.json';dest=OUTPUT/'default-startup-matrix.json';resume=sys.argv[1:]==['--resume'];assert sys.argv[1:] in ([],['--resume']) and marker.exists()==resume and not dest.exists()
    config=load(LOCAL/'operator/target.json');assert config['generation']==17 and config['project']=='mp-r0-r1lifef99acae9d906'
    project=config['project'];reader=DockerObserver(config);db=reader._container('db');candidate=load(OUTPUT/'candidate-build.json');image=candidate['image_id'];pin=candidate['inventory_digest']
    old='sha256:967c4b54371291a54ab5490e438c37358d561fa66e11293943096122a2608bc1';oldpin=inspect_image(old)['inventory_digest']
    assert json.loads(subprocess.check_output(['docker','network','inspect',project+'_runtime']))[0]['Internal'] is True
    record=load(marker) if resume else dict(state='preparing',token=uuid4().hex[:12],source_generation=17,image_id=image,databases={},containers=[]);token=record['token']
    if resume:assert record['state']=='starting_old-code-current-schema' and len(record['containers'])==1 and load(OUTPUT/'matrix-log-reconciliation.json')['result']=='guard_correct_harness_log_capture_failed'
    else:_write_new(marker,record)
    def phase(value):record.update(state=value,utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'worker-fence-matrix.stderr').write_bytes(r.stderr);raise RuntimeError('Matrix command failed; inspect marker/owned target before any further action')
        return r.stdout+r.stderr if args[:2]==['docker','logs'] else r.stdout
    def query(statement,database):return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',database],input=statement.encode())
    before_business=json.loads(sql(reader,BUSINESS_SQL));before_schema=json.loads(sql(reader,SCHEMA));sources={};baselines={};reports=[]
    if not resume:
        for case,source in [('healthy',config['sites'][0]['database']),('partial','mp_disposable_r0_r1_g5_life_f99acae9d906'),('removed',config['sites'][0]['database'])]:
            database='mp_disposable_r0_r1_wf_'+token+'_'+case;volume='mp-g5-worker-fence-'+token+'-'+case
            assert re.fullmatch('mp_disposable_r0_r1_wf_[a-z0-9_]+',database) and len(database)<64
            assert query("SELECT count(*) FROM pg_database WHERE datname='"+database+"';",'postgres').strip()==b'0'
            record['databases'][case]=dict(database=database,volume=volume,source_database=source);phase('creating_'+case)
            owner=query('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database();',source).decode().strip();assert re.fullmatch('[a-z_][a-z0-9_]*',owner)
            if case=='removed':archive=(LOCAL/'operator/control/checkpoints/39e37944-6648-4f7e-8aa1-30d01b452747/database.dump').read_bytes()
            else:archive=command(['docker','exec',db,'pg_dump','-U','postgres','--no-owner','-Fc',source])
            command(['docker','exec',db,'createdb','-U','postgres','-T','template0','-O',owner,database])
            command(['docker','exec','-i',db,'pg_restore','-U','postgres','--exit-on-error','--no-owner','--role',owner,'-d',database],input=archive)
            query("UPDATE ir_config_parameter SET value='"+pin+"' WHERE key='mp.active_inventory_digest';",database)
            command(['docker','volume','create','--label','com.modular.qualification=G5-worker-fence',volume])
            command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+project+'_appconfig,target=/source-config,readonly','--mount','type=volume,source='+project+'_filestore,target=/source-data,readonly','--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',image,'-c',SEED],input=json.dumps(dict(database=database,source_database=source)).encode())
            baselines[case]=(json.loads(query(BUSINESS_SQL,database)),json.loads(query(SCHEMA,database)))
    else:
        previous=ROOT/'docs/evidence/G5/20261029-concurrency-01'
        failed=ROOT/'docs/evidence/G5/20261029-executor-crash-01'
        for case,business,schema in [('healthy',previous/'business-after.json',previous/'schema-after.json'),('partial',failed/'business-after-commit.json',failed/'schema-after-commit.json'),('removed',previous/'owner/business-after.json',previous/'owner/schema-after.json')]:
            database=record['databases'][case]['database'];assert database=='mp_disposable_r0_r1_wf_'+token+'_'+case
            actual=(json.loads(query(BUSINESS_SQL,database)),json.loads(query(SCHEMA,database)))
            assert actual==(load(business),load(schema)),case
            baselines[case]=actual
        if not (OUTPUT/'matrix-resume.json').exists():(OUTPUT/'matrix-resume.json').write_text(json.dumps(dict(result='existing_copies_and_stopped_first_container_verified',database_recreation=False,first_negative_startup_repeated=False),indent=2)+'\n',encoding='utf8')
    def run(case,label,selected,expected_pin,expected_error=None):
        database=record['databases'][case]['database'];volume=record['databases'][case]['volume'];name='mp-g5-worker-fence-'+token+'-'+label
        args=['docker','create','--name',name,'--label','com.modular.qualification=G5-worker-fence','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--memory','768m','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+volume+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+volume+',target=/var/lib/modular,volume-subpath=data','-e','MP_EXPECTED_DATABASE='+database,'-e','MP_EXPECTED_INVENTORY_DIGEST='+expected_pin,selected]
        existing=next((r for r in record['containers'] if r['label']==label),None)
        if existing:
            assert resume and label=='old-code-current-schema';cid=existing['container_id'];assert not inspect(cid)['State']['Running'] and inspect(cid)['State']['ExitCode']==1
        else:
            cid=command(args).decode().strip();record['containers'].append(dict(label=label,container_id=cid));phase('starting_'+label);command(['docker','start',cid])
        if expected_error:
            exit_code=int(command(['docker','wait',cid],timeout=90).decode().strip());assert exit_code!=0
            logs=command(['docker','logs',cid]);(LOCAL/('worker-fence-'+label+'.log')).write_bytes(logs)
            assert expected_error.encode() in logs and b'odoo.modules.loading' not in logs
        else:
            deadline=time.monotonic()+60
            while True:
                status=inspect(cid)
                if not status['State']['Running']:raise RuntimeError('Positive bootstrap exited; inspect private default-entrypoint logs')
                r=subprocess.run(['docker','exec',cid,'/venv/bin/python','-c',"import urllib.request;assert urllib.request.urlopen('http://127.0.0.1:8069/web/login',timeout=3).status==200"],capture_output=True,timeout=10)
                if r.returncode==0:break
                if time.monotonic()>deadline:raise RuntimeError('Positive default bootstrap readiness timed out; inspect existing container')
                time.sleep(.5)
            command(['docker','stop','--time','20',cid]);exit_code=inspect(cid)['State']['ExitCode'];assert exit_code==0
            logs=command(['docker','logs',cid]);(LOCAL/('worker-fence-'+label+'.log')).write_bytes(logs);assert b'odoo.modules.loading' in logs
        item=inspect(cid);assert item['Config']['Entrypoint']==['/venv/bin/python','/opt/modular/tools/start_worker.py'] and item['Config']['Cmd']==['-c','/run/secrets/odoo_config']
        assert not item['HostConfig']['PortBindings'] and 'app' not in (item['NetworkSettings']['Networks'][project+'_runtime'].get('Aliases') or [])
        assert not item['State']['Running'];command(['docker','network','disconnect',project+'_runtime',cid])
        assert json.loads(query(BUSINESS_SQL,database))==baselines[case][0] and json.loads(query(SCHEMA,database))==baselines[case][1]
        reports.append(dict(case=label,container_id=cid,image_id=selected,exit_code=exit_code,default_entrypoint=True,expected_error=expected_error,registry_http_ready=expected_error is None,business_schema_unchanged=True,retained_stopped_disconnected=True,no_public_port_or_app_alias=True))
    run('healthy','old-code-current-schema',old,oldpin,'Database release inventory differs')
    healthy=record['databases']['healthy']['database']
    query("UPDATE ir_config_parameter SET value='"+oldpin+"' WHERE key='mp.active_inventory_digest';",healthy)
    run('healthy','old-code-relabeled-pin',old,oldpin,'Native module state/version differs')
    query("UPDATE ir_config_parameter SET value='"+pin+"' WHERE key='mp.active_inventory_digest';",healthy)
    run('partial','partial-uninstall-candidate',image,pin,'Installed package differs from native registration')
    run('healthy','coherent-installed-candidate',image,pin)
    run('removed','coherent-uninstalled-candidate',image,pin)
    assert json.loads(sql(reader,BUSINESS_SQL))==before_business and json.loads(sql(reader,SCHEMA))==before_schema and load(LOCAL/'operator/target.json')==config
    phase('completed_verified');report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),cases=reports,source_target_unchanged=True,databases=record['databases'],native_jobs_disabled=True,limits=['Disposable bootstrap copies with isolated inventory-pin substitutions; not approved deployed/public release state.','No external job/outbox implementation; G6 requalification remains.','Positive HTTP readiness is internal only; no browser/public alias/port.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))


def inspect(cid):return json.loads(subprocess.check_output(['docker','inspect',cid]))[0]


if __name__=='__main__':main()
