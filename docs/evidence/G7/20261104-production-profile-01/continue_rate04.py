"""Bounded continuation: native login429 uses native JSON-RPC, not service DTO."""
from rate_tls import *

def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');dest=OUTPUT/'rate-TLS-qualification.json';assert not dest.exists()
    spec=importlib.util.spec_from_file_location('current_probe',OUTPUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);client=m.Client('production');client.login(state,fixture,'alice');reader=DockerObserver(load(LOCAL/'operator/target.json'))
    baseline=load(OUTPUT/'setup/business-before.json');requests_before=json.loads(sql(reader,'SELECT to_jsonb(count(*)) FROM mp_operation_request;'));assert requests_before==0
    reports=load(OUTPUT/'rate-progress.json')['cases'];assert len(reports)==3
    def request(index,path):
        code,value,headers,raw=client.request(path,headers={'X-Forwarded-For':'198.51.100.'+str(index%250+1)})
        assert code in (200,429)
        if code==429:
            assert value['jsonrpc']=='2.0' and value['error']['code']==429 and value['error']['data']['name']=='odoo.exceptions.UserError'
            assert headers['Retry-After']=='12' and headers['Cache-Control']=='no-store'
            (OUTPUT/'native-login-rate-example.json').write_text(json.dumps(value,indent=2)+'\n')
        return code
    time.sleep(3)
    code,_,_,_=client.request('/api/v1/session');assert code==200
    code,value,_,_=client.service(fixture,'list',{'limit':1});assert code==200
    # Each secure protocol is negotiated independently with certificate and
    # hostname verification enabled. Never change global TLS policy.
    protocols=[]
    for version in [ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3]:
        ctx=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));ctx.minimum_version=ctx.maximum_version=version
        with socket.create_connection(('127.0.0.1',18445),timeout=10) as stream:
            with ctx.wrap_socket(stream,server_hostname='security.localhost') as secure:protocols.append(secure.version())
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning);legacy=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));legacy.minimum_version=legacy.maximum_version=ssl.TLSVersion.TLSv1_1;legacy.set_ciphers('ALL:@SECLEVEL=0')
    try:
        with socket.create_connection(('127.0.0.1',18445),timeout=10) as stream:
            with legacy.wrap_socket(stream,server_hostname='security.localhost'):raise AssertionError('Legacy TLS negotiated')
    except ssl.SSLError as error:assert error.reason=='TLSV1_ALERT_PROTOCOL_VERSION';legacy_reason=error.reason
    # Safe logs: canaries go in a query and a valid service-read body, then logs
    # must retain operational metadata without storing either value.
    query_canary='query_'+uuid4().hex;body_canary='body_'+uuid4().hex
    (LOCAL/'log-canaries02.json').write_text(json.dumps(dict(query=query_canary,body=body_canary)),encoding='utf8')
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
    reports.append(dict(category='login',requests=20,statuses=dict(Counter(statuses)),forged_forwarded_addresses_cannot_bypass=True,native_JSON_RPC_UserError=True))
    assert json.loads(sql(reader,BUSINESS_SQL))==baseline and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup/schema-before.json') and json.loads(sql(reader,'SELECT to_jsonb(count(*)) FROM mp_operation_request;'))==requests_before
    report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),cases=reports,public_service_recover_after_refill=True,TLS_protocols=protocols,TLS11_rejected=legacy_reason,certificate_and_hostname_verified=True,log_canaries_absent=log_results,existing_business_schema_and_operation_count_exact=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/http_profile.py','deploy/nginx-r0.conf','deploy/compose-production.yaml']},limits=['Bounded local edge load, not final G7 performance/capacity qualification.','Safe-log canaries are scoped evidence; full artifact/log/secret release scan remains SEC03.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',categories=4,requests=sum(r['requests'] for r in reports),TLS_protocols=protocols,legacy_TLS_denied=True)))


if __name__=='__main__':main()
