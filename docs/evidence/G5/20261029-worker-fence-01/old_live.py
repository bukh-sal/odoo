"""Retained generation17 code must refuse the actual generation18 database."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import _write_new
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'old-worker-live-database.json';marker=LOCAL/'worker-fence-old-live.json';assert not dest.exists() and not marker.exists()
    config=load(LOCAL/'operator/target.json');before=load(OUTPUT/'deploy/configuration-before.json');assert config['generation']==18 and before['generation']==17
    assert config['project']==before['project']=='mp-r0-r1lifef99acae9d906' and config['sites']==before['sites']
    reader=DockerObserver(config);business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));project=config['project'];name='mp-g5-worker-old-live-e9bbc910'
    assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0
    record=dict(state='creating',name=name,old_image_id=before['image_id'],database=config['sites'][0]['database']);_write_new(marker,record)
    command=['docker','create','--name',name,'--label','com.modular.qualification=G5-worker-fence','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--memory','768m','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular,readonly','-e','MP_EXPECTED_DATABASE='+config['sites'][0]['database'],'-e','MP_EXPECTED_INVENTORY_DIGEST='+before['published_release']['core_inventory_digest'],before['image_id']]
    r=subprocess.run(command,capture_output=True,check=True,timeout=30);cid=r.stdout.decode().strip();record.update(state='starting',container_id=cid);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    subprocess.run(['docker','start',cid],capture_output=True,check=True,timeout=30)
    r=subprocess.run(['docker','wait',cid],capture_output=True,check=True,timeout=90);assert int(r.stdout.decode().strip())!=0
    r=subprocess.run(['docker','logs',cid],capture_output=True,check=True,timeout=30);logs=r.stdout+r.stderr;(LOCAL/'worker-fence-old-live.log').write_bytes(logs)
    assert b'Database release inventory differs; controlled maintenance required' in logs and b'odoo.modules.loading' not in logs
    item=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
    assert not item['State']['Running'] and not item['HostConfig']['PortBindings'] and 'app' not in (item['NetworkSettings']['Networks'][project+'_runtime'].get('Aliases') or [])
    assert item['Config']['Entrypoint']==['/venv/bin/python','/opt/modular/tools/start_worker.py']
    subprocess.run(['docker','network','disconnect',project+'_runtime',cid],capture_output=True,check=True,timeout=30)
    assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema and load(LOCAL/'operator/target.json')==config
    record.update(state='completed_verified');marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    report=dict(result='passed',container_id=cid,old_image_id=before['image_id'],active_image_id=config['image_id'],active_generation=18,actual_active_database=config['sites'][0]['database'],default_entrypoint=True,exit_code=item['State']['ExitCode'],reason='Database release inventory differs; controlled maintenance required',native_registry_import_log_absent=True,current_business_schema_configuration_exact=True,old_probe_stopped_disconnected=True,no_public_port_or_app_alias=True,private_log_sha256=hashlib.sha256(logs).hexdigest())
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))


if __name__=='__main__':main()
