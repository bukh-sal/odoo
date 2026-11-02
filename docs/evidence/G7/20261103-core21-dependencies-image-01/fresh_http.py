"""Actual native login/session/assets on the one recorded fresh core database.

Temporary loopback-only bootstrap server; not production/startup-guard proof.
"""
import hashlib,html.parser,http.cookiejar,json,re,secrets,socket,subprocess,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core21-fresh-registry-01'
state=json.loads((PRIVATE/'state.json').read_text());assert state['state']=='fresh_core_registry_passed_retained_for_http_and_release_rehearsal'
def phase(value):state['state']=value;(PRIVATE/'state.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(dict(phase=value)),flush=True)
def call(label,args,raw=None,timeout=120):
 with (PRIVATE/(label+'.stdout')).open('xb') as out,(PRIVATE/(label+'.stderr')).open('xb') as err:r=subprocess.run(args,input=raw,stdout=out,stderr=err,timeout=timeout)
 assert r.returncode==0,'Inspect exact '+label+' and recorded server before continuing'
 return (PRIVATE/(label+'.stdout')).read_bytes()
port=18090
with socket.socket() as check:check.bind(('127.0.0.1',port))
password=secrets.token_urlsafe(32)
with (PRIVATE/'admin-password').open('x',encoding='utf8') as f:f.write(password+'\n')
state.update(http_container=state['project']+'-http',http_port=port)
common=['--label','com.modular.disposable='+state['project'],'--log-driver','none','--network',state['network'],'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1536m','--cpus','2','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+state['volume']+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+state['volume']+',target=/var/lib/modular,volume-subpath=data','--entrypoint','/venv/bin/python']
phase('setting_nondefault_fresh_admin_via_native_ORM')
code="assert env.cr.dbname=="+repr(state['database'])+"\nassert not env['mp.principal'].search_count([])\nenv.ref('base.user_admin').with_context(no_reset_password=True).write({'password':"+repr(password)+"})\nenv.cr.commit()\nprint('MP_FRESH_ADMIN_PASSWORD_SET')\n"
raw=call('http-admin-password',['docker','run','--rm','-i',*common,state['image_id'],'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['database'],'--no-http','--workers=0','--max-cron-threads=0'],code.encode())
assert b'MP_FRESH_ADMIN_PASSWORD_SET' in raw
phase('starting_loopback_native_bootstrap_http')
state['http_container_id']=call('http-start',['docker','run','-d','--name',state['http_container'],'--publish','127.0.0.1:'+str(port)+':8069',*common,state['image_id'],'odoo-bin','-c','/run/secrets/odoo_config','-d',state['database'],'--workers=2','--max-cron-threads=0','--http-port=8069','--http-interface=0.0.0.0','--logfile=/var/lib/modular/http-probe.log','--log-level=info']).strip().decode()
phase('native_http_checks_running')
base='http://127.0.0.1:'+str(port);jar=http.cookiejar.CookieJar();http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))
deadline=time.monotonic()+60
while True:
 try:
  with http.open(base+'/web/login?db='+urllib.parse.quote(state['database']),timeout=4) as response:body=response.read();assert response.status==200
  break
 except (OSError,urllib.error.URLError):
  if time.monotonic()>deadline:raise RuntimeError('Inspect exact recorded native server/log; no restart or recreation')
  time.sleep(1)
class Inputs(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.csrf=None
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='input' and attrs.get('name')=='csrf_token':self.csrf=attrs.get('value')
parser=Inputs();parser.feed(body.decode());assert parser.csrf
login_page_sha=hashlib.sha256(body).hexdigest()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
form=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar),NoRedirect())
payload=urllib.parse.urlencode(dict(db=state['database'],login='admin',password=password,csrf_token=parser.csrf,redirect='/web')).encode()
try:
 response=form.open(urllib.request.Request(base+'/web/login',data=payload),timeout=20);login_status=response.status;login_headers=dict(response.headers);response.close()
except urllib.error.HTTPError as response:
 login_status=response.code;login_headers=dict(response.headers);response.close()
assert login_status in (302,303),'Inspect private HTTP state; native login did not redirect'
request=urllib.request.Request(base+'/web/session/get_session_info',data=json.dumps(dict(jsonrpc='2.0',id=1,method='call',params={})).encode(),headers={'Content-Type':'application/json'})
with http.open(request,timeout=20) as response:session=json.load(response)
assert not session.get('error') and session['result']['uid']==2
assert any(cookie.name=='session_id' for cookie in jar)
assets=[]
for path in sorted(set(re.findall(r'/web/assets/[^\s\"\'<>]+',body.decode()))):
 if not path.endswith(('.js','.css')):continue
 if any(a['kind']==path.rsplit('.',1)[1] for a in assets):continue
 with http.open(base+path,timeout=45) as response:
  raw=response.read();assert response.status==200 and len(raw)>100
  assets.append(dict(path=path,kind=path.rsplit('.',1)[1],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),content_type=response.headers.get('Content-Type')))
assert {a['kind'] for a in assets}=={'js','css'}
phase('native_http_checks_passed_stopping_temporary_server')
call('http-log-archive',['docker','exec',state['http_container_id'],'cat','/var/lib/modular/http-probe.log'])
call('http-stop',['docker','stop','--time','20',state['http_container_id']])
info=json.loads(call('http-terminal-inspect',['docker','inspect','--type','container',state['http_container_id']]))[0]
assert info['Config']['Labels']['com.modular.disposable']==state['project'] and not info['State']['Running'] and info['State']['Status']=='exited'
call('http-retire',['docker','rm',state['http_container_id']])
absent=subprocess.run(['docker','inspect','--type','container',state['http_container_id']],capture_output=True,timeout=30);assert absent.returncode!=0 and b'no such' in absent.stderr.lower()
phase('fresh_core_native_login_assets_passed_http_server_retired')
report=dict(result='passed_fresh_native_login_session_and_assets',database=state['database'],image_id=state['image_id'],loopback_port=port,login_http_status=login_status,authenticated_native_uid=2,nondefault_private_password=True,csrf_form_token_used=True,login_page_sha256=login_page_sha,assets=assets,temporary_http_server_removed=True,
 limits=['Native bootstrap server only: explicit local operator entrypoint, no production/startup-guard or platform-site/plugin acceptance claim.',
 'No custom frontend or Canvas changes. Full HTTPS/security/permissions/plugin lifecycle/recovery and fresh release remain.'])
with (OUT/'fresh-http.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],uid=2,asset_kinds=[a['kind'] for a in assets],temporary_server_removed=True)))
