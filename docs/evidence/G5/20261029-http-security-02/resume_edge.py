"""Replace only failed owned TLS edge; never replay account/DB setup."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity';SOURCE=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from http_profile import render
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');source=load(SOURCE/'operator/target.json');assert state['project']=='mp-r0-r1http9669f0969d1d' and state['phase']=='starting_production_edge' and len(state['containers'])==3
    project=state['project'];database=state['active_db'];site=state['site_id'];origin=state['origin'];reader=DockerObserver(source);business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));own=DockerObserver(dict(source,project=project,sites=[dict(database=database,site_id=site)]));assert json.loads(sql(own,SCHEMA))==schema
    assert json.loads(sql(own,"SELECT to_jsonb(count(*)) FROM res_users WHERE active AND (login='admin' OR login LIKE 'g5_%%');"))==0
    deployment=json.loads(sql(own,"SELECT to_jsonb(value) FROM ir_config_parameter WHERE key='mp.deployment_id';"));assert str(UUID(deployment))==deployment
    def phase(value):state.update(phase=value,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'edge-resume.stderr').write_bytes(r.stderr);raise RuntimeError('Reconcile current owned TLS edge before any further action')
        return r.stdout
    old=next(r for r in state['containers'] if r['purpose']=='production-edge');item=json.loads(command(['docker','inspect',old['container_id']]))[0];assert not item['State']['Running'] and item['State']['ExitCode']==1
    logs=subprocess.run(['docker','logs',old['container_id']],capture_output=True,check=True).stderr;assert b'cannot load certificate "/run/mp-tls/server.crt"' in logs
    for network in list(item['NetworkSettings']['Networks']):assert network in (project+'_runtime',project+'_edge');command(['docker','network','disconnect',network,old['container_id']])
    old['purpose']='failed-TLS-run-mount-hidden';prior=(LOCAL/'production.conf').read_text(encoding='utf8').encode();production=render('production',origin);assert prior.decode().replace('/run/mp-tls','/etc/mp-tls')==production
    (LOCAL/'production-before-tls-path.conf').write_bytes(prior)
    seed="import hashlib,json,sys;from pathlib import Path;d=json.load(sys.stdin);p=Path('/proxy/default.conf');assert p.is_file() and not p.is_symlink() and p.stat().st_nlink==1 and hashlib.sha256(p.read_bytes()).hexdigest()==d['prior'];p.chmod(0o644);p.write_text(d['new']);p.chmod(0o444)"
    command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+project+'_prodproxy,target=/proxy','--entrypoint','/venv/bin/python',state['image_id'],'-c',seed],input=json.dumps(dict(prior=hashlib.sha256(prior).hexdigest(),new=production)).encode());(LOCAL/'production.conf').write_text(production,encoding='utf8',newline='\n')
    spec=importlib.util.spec_from_file_location('mp_http_setup',OUTPUT/'setup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    args=['docker','create','--name',project+'-edge-production-etc-tls','--label','com.modular.qualification=G5-HTTP-security','--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--memory','128m','--tmpfs','/tmp','--tmpfs','/var/cache/nginx:uid=101,gid=101,mode=0755','--tmpfs','/var/run:uid=101,gid=101,mode=0755','--mount','type=volume,source='+project+'_prodproxy,target=/etc/nginx/conf.d,readonly','--mount','type=volume,source='+project+'_tls,target=/etc/mp-tls,readonly','-p','127.0.0.1:18083:8069','-p','127.0.0.1:18443:8443','--entrypoint','nginx',module.NGINX,'-g','daemon off;']
    cid=command(args).decode().strip();state['containers'].append(dict(purpose='production-edge',container_id=cid));command(['docker','network','connect',project+'_edge',cid]);phase('starting_corrected_TLS_edge');command(['docker','start',cid]);command(['docker','exec',cid,'nginx','-t'])
    (OUTPUT/'setup/tls-mount-reconciliation.json').write_text(json.dumps(dict(result='corrected_owned_TLS_edge_running',diagnosis='Stock nginx /var/run symlinks /run; tmpfs hid nested /run/mp-tls mount',old_container=old['container_id'],new_container=cid,old_retained_stopped_disconnected=True,only_owned_proxy_volume_changed=True,old_config_sha256=hashlib.sha256(prior).hexdigest(),new_config_sha256=hashlib.sha256(production.encode()).hexdigest(),TLS_path='/etc/mp-tls',database_or_account_provisioning_repeated=False,TLS_regenerated=False),indent=2)+'\n',encoding='utf8')
    app=next(r['container_id'] for r in state['containers'] if r['purpose']=='application');module.finalize_setup(state,source,production,project,database,origin,site,deployment,reader,business,schema,app,phase,command)


if __name__=='__main__':main()
