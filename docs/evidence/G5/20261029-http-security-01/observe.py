"""Bounded anonymous read-only SEC02 baseline; does not qualify the check."""
from datetime import datetime,timezone
import hashlib
from http.cookies import SimpleCookie
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));target=ROOT/'.local/g5-dispatch/operator/target.json';config=load(target);assert config['generation']==20 and config['project']=='mp-r0-r1dispefb95a06d78f';dest=OUTPUT/'baseline.json';assert not dest.exists()
    reader=DockerObserver(config);before=json.loads(sql(reader,BUSINESS_SQL));http=urllib.request.build_opener(urllib.request.ProxyHandler({}));reports=[]
    for name,path,method,headers in [
        ('normal_release','/api/v1/client-release','GET',{}),
        ('unknown_host','/api/v1/client-release','GET',{'Host':'attacker.invalid'}),
        ('cross_origin_read','/api/v1/client-release','GET',{'Origin':'https://attacker.invalid'}),
        ('cross_origin_preflight','/api/v1/services/org.example.notes.documents/create','OPTIONS',{'Origin':'https://attacker.invalid','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type,x-csrftoken'}),
        ('anonymous_session_cookie','/web/login','GET',{}),
        ('forged_forwarded_headers','/api/v1/client-release','GET',{'X-Forwarded-Host':'attacker.invalid','X-Forwarded-Proto':'https'}),
        ('database_manager','/web/database/manager','GET',{})]:
        request=urllib.request.Request('http://127.0.0.1:18081'+path,method=method,headers=headers)
        try:response=http.open(request,timeout=20)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read();row=dict(case=name,status=response.status,access_control_allow_origin=response.headers.get('Access-Control-Allow-Origin'),access_control_allow_credentials=response.headers.get('Access-Control-Allow-Credentials'),body_sha256=hashlib.sha256(raw).hexdigest())
            flags=[]
            for text in response.headers.get_all('Set-Cookie',[]):
                cookie=SimpleCookie();cookie.load(text)
                for key,value in cookie.items():flags.append(dict(name=key,host_only=not bool(value['domain']),http_only=bool(value['httponly']),secure=bool(value['secure']),same_site=value['samesite'] or None))
            row['cookie_flags']=flags
            if path=='/api/v1/client-release' and response.status==200:row['site_id']=json.loads(raw)['data']['site_id']
            reports.append(row)
    worker=reader._container('app');check="import configparser,json;c=configparser.ConfigParser();c.read('/run/secrets/odoo_config');o=c['options'];print(json.dumps({k:o.get(k) for k in ['proxy_mode','list_db','dbfilter','max_cron_threads','http_interface']}))"
    options=json.loads(subprocess.check_output(['docker','exec',worker,'/venv/bin/python','-c',check],timeout=15))
    assert json.loads(sql(reader,BUSINESS_SQL))==before and load(target)==config
    value=dict(result='observed_SEC02_not_qualified',utc=datetime.now(timezone.utc).isoformat(),target_project=config['project'],generation=20,cases=reports,nonsecret_runtime_options=options,business_configuration_unchanged=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['deploy/nginx-r0.conf','deploy/compose.yaml','odoo/http.py','platform_addons/mp_core/controllers.py']},findings=['Explicit allowed-host enforcement is missing in source; anonymous release401 alone does not prove any site metadata disclosure. A separate login-host observation is required (host-counterexample.json).','Pinned upstream session cookie is host-only and HttpOnly; local HTTP has no explicit SameSite or Secure. Separate HTTPS/production policy must be implemented/tested rather than inferred from local HTTP.','No dedicated production profile exists yet; SEC04 cannot pass from the development proxy database-manager denial alone.'],next='Implement/test explicit development allowed-host policy and a separate operator-configured production proxy/profile with trusted proxy, TLS cookie and endpoint defaults; preserve Odoo session/CSRF/native-view behavior.',limits=['Anonymous read-only seven-request baseline; no complete CSRF/authenticated-cookie/rate-limit/production qualification.','No production deployment or existing proxy mutation.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=value['result'],unknown_host_status=next(r['status'] for r in reports if r['case']=='unknown_host'),database_manager_status=next(r['status'] for r in reports if r['case']=='database_manager'),business_unchanged=True)))


if __name__=='__main__':main()
