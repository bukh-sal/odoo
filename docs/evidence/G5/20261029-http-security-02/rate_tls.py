"""Bounded real shared-edge rate, protocol and safe-log checks."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4
import warnings

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.contracts import validate
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');dest=OUTPUT/'rate-TLS-qualification.json';assert not dest.exists()
    assert load(OUTPUT/'HTTP-qualification.json')['result']=='passed_HTTP_matrix'
    spec=importlib.util.spec_from_file_location('mp_http_security_probe',OUTPUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);client=m.Client('production');client.login(state,fixture,'alice');reader=DockerObserver(load(LOCAL/'operator/target.json'));baseline=json.loads(sql(reader,BUSINESS_SQL));requests_before=json.loads(sql(reader,'SELECT to_jsonb(count(*)) FROM mp_operation_request;'));reports=[]
    context=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));cookie='; '.join(c.name+'='+c.value for c in client.jar)
    def request(index,path,body=None):
        headers={'Host':client.authority,'Cookie':cookie,'Origin':client.origin,'X-MP-Client-Release':client.release,'X-CSRFToken':client.csrf,'X-MP-Workspace':fixture['workspaces']['A']['public_id'],'X-MP-Binding':fixture['bindings']['A']['binding_id'],'X-Forwarded-For':'198.51.100.'+str(index%250+1)}
        if body is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(client.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers);http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
        try:r=http.open(req,timeout=30)
        except urllib.error.HTTPError as error:r=error
        with r:
            raw=r.read();value=json.loads(raw) if r.headers.get_content_type()=='application/json' else None
            if r.status==429:
                validate('service-response',value);assert value['error']['code']=='RATE_LIMITED' and value['error']['retryable'] and value['error']['details']==dict(outcome='not_started')
                assert r.headers['Retry-After']=='12' and r.headers['Cache-Control']=='no-store' and r.headers['Strict-Transport-Security']=='max-age=31536000' and r.headers['X-Content-Type-Options']=='nosniff'
            return r.status
    for name,path,count,body,allowed in [
        ('service','/api/v1/services/org.example.notes.documents/list',96,dict(api_version='1.0',request_id=str(uuid4()),input={'limit':1}),{200,429}),
        ('operator','/api/v1/operations/prepare',40,{}, {403,429}),
        ('public','/api/v1/client-release',240,None,{200,429})]:
        started=time.monotonic()
        with ThreadPoolExecutor(max_workers=16) as pool:statuses=list(pool.map(lambda i:request(i,path,body),range(count)))
        counts=dict(Counter(statuses));assert set(counts)<=allowed and counts.get(429,0)>0,(name,counts)
        reports.append(dict(category=name,requests=count,concurrency=16,statuses=counts,elapsed_seconds=round(time.monotonic()-started,3),forged_forwarded_addresses_cannot_bypass=True,rate_errors_match_frozen_DTO=True))
        (OUTPUT/'rate-progress.json').write_text(json.dumps(dict(state='in_progress',cases=reports),indent=2)+'\n',encoding='utf8')
    time.sleep(3)
    code,_,_,_=client.request('/api/v1/session');assert code==200
    code,value,_,_=client.service(fixture,'list',{'limit':1});assert code==200
    # Each secure protocol is negotiated independently with certificate and
    # hostname verification enabled. Never change global TLS policy.
    protocols=[]
    for version in [ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3]:
        ctx=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));ctx.minimum_version=ctx.maximum_version=version
        with socket.create_connection(('127.0.0.1',18443),timeout=10) as stream:
            with ctx.wrap_socket(stream,server_hostname='security.localhost') as secure:protocols.append(secure.version())
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning);legacy=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));legacy.minimum_version=legacy.maximum_version=ssl.TLSVersion.TLSv1_1;legacy.set_ciphers('ALL:@SECLEVEL=0')
    try:
        with socket.create_connection(('127.0.0.1',18443),timeout=10) as stream:
            with legacy.wrap_socket(stream,server_hostname='security.localhost'):raise AssertionError('Legacy TLS negotiated')
    except ssl.SSLError as error:assert error.reason=='TLSV1_ALERT_PROTOCOL_VERSION';legacy_reason=error.reason
    # Safe logs: canaries go in a query and a valid service-read body, then logs
    # must retain operational metadata without storing either value.
    query_canary='query_'+uuid4().hex;body_canary='body_'+uuid4().hex
    (LOCAL/'log-canaries.json').write_text(json.dumps(dict(query=query_canary,body=body_canary)),encoding='utf8')
    code,_,_,_=client.request('/api/v1/session?credential_canary='+query_canary);assert code==200
    code,value,_,_=client.service(fixture,'list',{'limit':1,'query':body_canary});assert code==200 and not value['data']['items']
    log_results=[]
    for row in state['containers']:
        if row['purpose'] not in ('application','development-edge','production-edge'):continue
        r=subprocess.run(['docker','logs',row['container_id']],capture_output=True,check=True,timeout=30);raw=r.stdout+r.stderr
        assert query_canary.encode() not in raw and body_canary.encode() not in raw
        if row['purpose']=='application':assert b'from:203.0.113.250' not in raw and b'from: 203.0.113.250' not in raw
        log_results.append(dict(purpose=row['purpose'],canaries_absent=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    statuses=[]
    for i in range(20):statuses.append(request(i,'/web/login'))
    assert set(statuses)<={200,429} and 429 in statuses
    reports.append(dict(category='login',requests=20,statuses=dict(Counter(statuses)),forged_forwarded_addresses_cannot_bypass=True,rate_errors_match_frozen_DTO=True))
    assert json.loads(sql(reader,BUSINESS_SQL))==baseline and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup/schema-before.json') and json.loads(sql(reader,'SELECT to_jsonb(count(*)) FROM mp_operation_request;'))==requests_before
    report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),cases=reports,public_service_recover_after_refill=True,TLS_protocols=protocols,TLS11_rejected=legacy_reason,certificate_and_hostname_verified=True,log_canaries_absent=log_results,existing_business_schema_and_operation_count_exact=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/http_profile.py','deploy/nginx-r0.conf','deploy/compose-production.yaml']},limits=['Bounded local edge load, not final G7 performance/capacity qualification.','Safe-log canaries are scoped evidence; full artifact/log/secret release scan remains SEC03.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',categories=4,requests=sum(r['requests'] for r in reports),TLS_protocols=protocols,legacy_TLS_denied=True)))


if __name__=='__main__':main()
