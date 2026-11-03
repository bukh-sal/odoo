"""Actual HTTP/TLS/native CSRF, origin, cookie and production endpoint matrix."""
from datetime import datetime,timezone
from http.cookies import SimpleCookie
import http.cookiejar
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g7-production-profile-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Client:
    def __init__(self,mode):
        self.mode=mode;self.base='https://127.0.0.1:18445' if mode=='production' else 'http://127.0.0.1:18092';self.authority='security.localhost:18445' if mode=='production' else 'g5.localhost:18092';self.origin=('https://' if mode=='production' else 'http://')+self.authority;self.jar=http.cookiejar.CookieJar();context=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPCookieProcessor(self.jar),urllib.request.HTTPSHandler(context=context));self.release=None;self.csrf=None

    def request(self,path,body=None,*,method=None,headers=None,raw=None):
        h={'Host':self.authority,**(headers or {})}
        if body is not None:h.setdefault('Content-Type','application/json');raw=json.dumps(body).encode()
        if method is None:method='POST' if raw is not None else 'GET'
        req=urllib.request.Request(self.base+path,data=raw,method=method,headers=h)
        try:response=self.http.open(req,timeout=30)
        except urllib.error.HTTPError as error:response=error
        with response:
            data=response.read()
            try:value=json.loads(data)
            except ValueError:value=None
            return response.status,value,response.headers,data

    def rpc(self,model,method,args=None,kwargs=None,workspace=None,headers=None):
        h={'Origin':self.origin,'X-MP-Client-Release':self.release,**(headers or {})}
        if workspace:h['X-MP-Workspace']=workspace
        return self.request('/web/dataset/call_kw/'+model+'.'+method,dict(jsonrpc='2.0',id=1,method='call',params=dict(model=model,method=method,args=args or [],kwargs=kwargs or {})),headers=h)

    def login(self,state,fixture,actor,headers=None):
        code,value,h,raw=self.request('/web/session/authenticate',dict(jsonrpc='2.0',method='call',id=1,params=dict(db=state['active_db'],login=fixture['users'][actor]['login'],password=(LOCAL/('password-'+actor)).read_text(encoding='utf8').strip())),headers={'Origin':self.origin,**(headers or {})});assert code==200 and value.get('result',{}).get('uid')==fixture['users'][actor]['id']
        code,value,_,_=self.request('/api/v1/client-release');assert code==200 and value['data']['site_id']==state['site_id'];self.release=value['data']['token']
        code,value,_,_=self.request('/api/v1/session');assert code==200;self.csrf=value['data']['csrf_token']
        return h

    def service(self,fixture,method,values,*,workspace='A',csrf='valid',origin='valid',key=None):
        binding=fixture['bindings'][workspace];h={'X-MP-Client-Release':self.release,'X-MP-Workspace':fixture['workspaces'][workspace]['public_id'],'X-MP-Binding':binding['binding_id'],'Origin':self.origin if origin=='valid' else origin}
        if csrf is not None:h['X-CSRFToken']=self.csrf if csrf=='valid' else csrf
        payload=dict(api_version='1.0',request_id=str(uuid4()),input=values)
        if key:payload['idempotency_key']=key
        return self.request('/api/v1/services/org.example.notes.documents/'+method,payload,headers=h)


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');target=load(LOCAL/'operator/target.json');assert state['phase']=='profiles_started_ready';dest=OUTPUT/'HTTP-qualification.json';resume=sys.argv[1:]==['--resume-native'];assert sys.argv[1:] in ([],['--resume-native']) and not dest.exists();assert (OUTPUT/'HTTP-progress.json').exists()==resume;checks=load(OUTPUT/'HTTP-progress.json')['checks'] if resume else [];reader=DockerObserver(target)
    def passed(name,**details):
        checks.append(dict(case=name,result='passed',**details));(OUTPUT/'HTTP-progress.json').write_text(json.dumps(dict(state='in_progress',checks=checks),indent=2)+'\n',encoding='utf8')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup/business-before.json')
    dev=Client('development');prod=Client('production')
    if not resume:
        for client in [dev,prod]:
            code,_,headers,raw=client.request('/web/login');assert code==200 and b'name="login"' in raw
            cookies=SimpleCookie()
            for text in headers.get_all('Set-Cookie',[]):cookies.load(text)
            session=cookies['session_id'];assert session['httponly'] and session['samesite'].lower()=='lax' and not session['domain'] and bool(session['secure'])==(client.mode=='production')
            if client.mode=='production':assert headers['Strict-Transport-Security']=='max-age=31536000'
            passed(client.mode+'_native_login_and_cookie_policy',HttpOnly=True,SameSite='Lax',host_only=True,Secure=bool(session['secure']))
            for host in ['attacker.invalid','evil.localhost.attacker.invalid']:
                code,value,h,raw=client.request('/web/login',headers={'Host':host});assert code==421
            passed(client.mode+'_unknown_hosts_denied')
        for host in ['localhost:18092','127.0.0.1:18092','g5.localhost:18092','nested.g5.localhost:18092']:
            code,_,_,_=dev.request('/web/login',headers={'Host':host});assert code==200
        passed('development_loopback_aliases_preserved')
        redirect=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        for method in ['GET','POST']:
            req=urllib.request.Request('http://127.0.0.1:18093/web/login?continue=1',method=method,headers={'Host':'security.localhost:18093','X-Forwarded-Host':'attacker.invalid','X-Forwarded-Proto':'http'})
            try:r=redirect.open(req,timeout=10)
            except urllib.error.HTTPError as e:r=e
            with r:
                assert r.status==(308 if method=='GET' else 403)
                if method=='GET':assert r.headers['Location']=='https://security.localhost:18445/web/login?continue=1'
        passed('production_HTTP_fixed_canonical_redirect_and_mutation_refusal')
    # Authenticate before deliberately exercising login rate limits.
    prod.login(state,fixture,'alice',headers={'X-Forwarded-Host':'attacker.invalid','X-Forwarded-Proto':'http','X-Forwarded-For':'203.0.113.250','Forwarded':'host=attacker.invalid;proto=http'})
    dev.login(state,fixture,'alice');bob=Client('production');bob.login(state,fixture,'bob')
    for client in [dev,prod]:
        if not (resume and client.mode=='development'):
            code,value,_,_=client.service(fixture,'list',{'limit':25});assert code==200 and len(value['data']['items'])==1
            for bad in [None,'invalid-token',bob.csrf]:
                code,value,_,_=client.service(fixture,'create',{'title':'SEC02_MUST_NOT_CREATE','body':''},csrf=bad);assert code==403 and value['error']['code']=='FORBIDDEN'
            passed(client.mode+'_gateway_CSFR_missing_invalid_other_session_denied')
            for origin in ['https://attacker.invalid','null','https://security.localhost:18446']:
                for path,method,body in [('/api/v1/session','GET',None),('/web/session/authenticate','POST',{}),('/api/v1/services/org.example.notes.documents/create','OPTIONS',None)]:
                    h={'Origin':origin}
                    if method=='OPTIONS':h.update({'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type,x-csrftoken'})
                    code,_,headers,_=client.request(path,body,method=method,headers=h);assert code==403 and not headers.get('Access-Control-Allow-Origin') and not headers.get('Access-Control-Allow-Credentials')
            passed(client.mode+'_foreign_null_wrong_port_Origin_and_preflight_denied_no_CORS_credentials')
        wid=fixture['workspaces']['A']['public_id'];code,value,_,_=client.rpc('mp.example.note','search_read',[[]],{'fields':['public_id','title','revision']},workspace=wid);assert code==200 and len(value['result'])==1
        code,views,_,_=client.rpc('mp.example.note','get_views',kwargs={'views':[(False,'list'),(False,'form')],'options':{}},workspace=wid);assert code==200 and '<list' in views['result']['views']['list']['arch'] and '<form' in views['result']['views']['form']['arch']
        # A browser simple-form content type cannot dispatch JSON native writes,
        # even with a session. Foreign browser Origins are rejected at the edge.
        payload=dict(jsonrpc='2.0',method='call',id=1,params=dict(model='mp.example.note',method='create',args=[{'title':'SEC02_MUST_NOT_CREATE'}],kwargs={}))
        code,_,_,_=client.request('/web/dataset/call_kw/mp.example.note.create',raw=json.dumps(payload).encode(),headers={'Content-Type':'text/plain','X-MP-Client-Release':client.release,'X-MP-Workspace':wid});assert code==415
        passed(client.mode+'_native_Odoo_list_form_views_and_RPC_preserved_simple_form_write_denied')
    # Valid CSRF mutation + exact cleanup on a new synthetic record, never an
    # existing note. IDs are recorded immediately; uncertain outcomes stop.
    marker=LOCAL/'csrf-created-note.json';assert not marker.exists();title='SEC02_owned_'+uuid4().hex
    code,value,_,_=prod.service(fixture,'create',{'title':title,'body':'Owned temporary CSRF acceptance fixture'},key='sec02-create-'+uuid4().hex);assert code==200;created=value['data'];marker.write_text(json.dumps(dict(state='created',note=created),indent=2)+'\n',encoding='utf8')
    code,value,_,_=prod.service(fixture,'delete',{'note_id':created['id'],'expected_revision':created['revision']},key='sec02-delete-'+uuid4().hex);assert code==200 and value['data']['deleted'];marker.write_text(json.dumps(dict(state='deleted_verified',note_id=created['id']),indent=2)+'\n',encoding='utf8');passed('valid_session_CSFR_create_delete_succeeds_only_for_owned_temporary_record')
    # Preserve optional Canvas custom page, without expanding its behavior.
    wid=fixture['workspaces']['A']['public_id'];code,value,_,_=prod.request('/api/v1/context?plugin_id=org.example.canvas',headers={'X-MP-Client-Release':prod.release,'X-MP-Workspace':wid});assert code==200;bindings=value['data']['bindings'];binding=next(b for b in bindings if b['alias']=='boards')
    code,value,_,_=prod.request('/api/v1/services/'+binding['service_id']+'/get',dict(api_version=binding['api_version'],request_id=str(uuid4()),input={}),headers={'Origin':prod.origin,'X-CSRFToken':prod.csrf,'X-MP-Client-Release':prod.release,'X-MP-Workspace':wid,'X-MP-Binding':binding['binding_id']});assert code==200 and len(value['data']['cards'])==1;passed('minimal_Canvas_read_and_custom_page_capability_retained')
    # All database-manager variants are rejected before native handling.
    for path in ['/web/database/manager','/web/database/list','/web/database/selector','/web/database/create','/web/%64atabase/manager','/%77eb/database/manager','/web/database%2flist']:
        code,_,_,_=prod.request(path);assert code==403
    for path in ['/web/tests','/web/tests/legacy','/web/qunit','/web/tour','/web/assets/debug/missing.js','/_tests','/app?debug=assets','/web/login?debug=1','/web/login?debug=tests','/web/login?debug=0']:
        code,_,_,_=prod.request(path);assert code==403
    for path in ['/xmlrpc/2/common','/jsonrpc']:
        code,_,_,_=prod.request(path);assert code==404
    passed('production_database_debug_test_and_excluded_external_RPC_endpoints_unavailable')
    assets=[]
    for client in [dev,prod]:
        code,_,_,raw=client.request('/app/org.example.notes/?workspace='+wid);assert code==200
        paths=sorted(set(re.findall(rb'(?:src|href)=[\"\x27]([^\"\x27]*/web/assets/[^\"\x27]+)',raw)))
        for asset in paths:
            path=asset.decode()
            if not path.startswith('/'):continue
            code,_,headers,data=client.request(path);assert code==200 and data and b'## CSS error message ##' not in data
            assets.append(dict(mode=client.mode,path=path,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
        assert len([a for a in assets if a['mode']==client.mode])>=2
    passed('native_shell_and_regular_JS_CSS_assets_work_through_both_edges',assets=assets)
    # Source configurations and data, not merely status codes, stay coherent.
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup/business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup/schema-before.json')
    assert json.loads(sql(reader,"SELECT jsonb_build_object('fixture_users',(SELECT count(*) FROM res_users WHERE active AND (login='admin' OR login LIKE 'g5_%%')),'active_technical_credentials',(SELECT count(*) FROM mp_service_credential WHERE state='active'),'base_url',(SELECT value FROM ir_config_parameter WHERE key='web.base.url'));"))==dict(fixture_users=0,active_technical_credentials=0,base_url=state['origin'])
    passed('production_fixture_old_logins_disabled_and_exact_business_schema_retained')
    report=dict(result='passed_HTTP_matrix',utc=datetime.now(timezone.utc).isoformat(),checks=checks,application_image=state['image_id'],source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/http_profile.py','deploy/nginx-r0.conf','deploy/compose-production.yaml','tests/test_http_profile.py']},limits=['Local TLS uses a private two-day qualification certificate explicitly trusted only by this client.','TLS protocol-negative/rate/protected-target audits separate. External analysis intentionally unavailable; no SVC/job qualification.','Same-origin/native plugins remain trusted; no sandbox or remote production deployment.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed_HTTP_matrix',checks=len(checks),assets=len(assets))))


if __name__=='__main__':main()
