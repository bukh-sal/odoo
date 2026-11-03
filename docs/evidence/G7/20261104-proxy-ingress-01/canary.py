"""Actual proxy-only canary; existing app/data/control/worker preserved."""
import base64,hashlib,http.cookiejar,json,re,socket,subprocess,sys,time,urllib.error,urllib.request
from datetime import datetime,timezone
from http.cookies import SimpleCookie
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-ingress-01'
sys.path[:0]=[str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from lifecycle import f,context,snapshot,worker,LOCAL
from modular_platform.operator_os import protect_directory
import r1_probe
assert not PRIVATE.exists();protect_directory(PRIVATE);f.OUTPUT=OUT
state,native=context('connector');assert native.config['generation']==4
fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL
candidate=f.load(ROOT/'docs/evidence/G7/20261104-support-images-01/proxy-candidate-build.json')['image_id']
name='mp-g7-proxy-ingress-canary-01';port=18091
s=socket.socket();s.bind(('127.0.0.1',port));s.close()
def run(label,args,check=True):
 r=subprocess.run(args,capture_output=True,timeout=60);(PRIVATE/(label+'.stdout')).write_bytes(r.stdout);(PRIVATE/(label+'.stderr')).write_bytes(r.stderr)
 if check:assert r.returncode==0,'Inspect retained diagnostics before retrying'
 return r
edge=json.loads(run('original-edge',['docker','inspect',state['project']+'-edge-1']).stdout)[0]
assert edge['Image']=='sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951'
assert edge['Config']['User']=='101:101' and edge['HostConfig']['ReadonlyRootfs']
assert len(edge['Mounts'])==1;mount=edge['Mounts'][0]
assert mount['Type']=='volume' and mount['Name']==state['project']+'_proxyconfig' and not mount['RW'] and mount['Destination']=='/etc/nginx/conf.d'
networks=list(edge['NetworkSettings']['Networks']);assert set(networks)=={state['project']+'_edge',state['project']+'_runtime'}
before=snapshot(state,'proxy-canary-data-before');identity=worker(native,'proxy-canary-worker-before')
(PRIVATE/'data-before.json').write_text(json.dumps(before));(PRIVATE/'worker-before.json').write_text(json.dumps(identity))
checks=[];created=False
record=dict(phase='starting',name=name,candidate=candidate,port=port)
def save_state(): (PRIVATE/'state.json').write_text(json.dumps(record,indent=2))
def passed(name,**extra):
 checks.append(dict(case=name,result='passed',**extra));(OUT/'progress.json').write_text(json.dumps(dict(state='in_progress',checks=checks),indent=2))
def request(client,path,body=None,headers=None):
 h=dict(headers or {})
 if body is not None:h['Content-Type']='application/json'
 req=urllib.request.Request(client.base+path,headers=h,data=json.dumps(body).encode() if body is not None else None)
 try:r=client.http.open(req,timeout=20)
 except urllib.error.HTTPError as error:r=error
 with r:return r.status,r.headers,r.read()
try:
 save_state()
 args=['docker','create','--name',name,'--label','com.modular.disposable=mp-g7-proxy-ingress','--read-only','--user','101:101','--network',state['project']+'_runtime','--publish','127.0.0.1:'+str(port)+':8069','--mount','type=volume,source='+mount['Name']+',target=/etc/nginx/conf.d,readonly']
 for path,opts in edge['HostConfig']['Tmpfs'].items():args+=['--tmpfs',path+(':'+opts if opts else '')]
 args+=[candidate];run('create',args);created=True
 run('connect-edge',['docker','network','connect',state['project']+'_edge',name]);run('start',['docker','start',name]);record['phase']='started';save_state()
 health=type('C',(),dict(base='http://127.0.0.1:'+str(port),http=urllib.request.build_opener(urllib.request.ProxyHandler({}))))()
 for n in range(30):
  try:
   if request(health,'/web/login')[0]==200:break
  except (OSError,urllib.error.URLError):pass
  time.sleep(.3)
 else:raise AssertionError('Candidate login readiness missing')
 observation=json.loads(run('candidate-observation',['docker','inspect',name]).stdout)[0]
 assert observation['Image']==candidate and observation['State']['Running'] and observation['Mounts']==edge['Mounts']
 passed('candidate_nonroot_readonly_existing_config_and_networks',user='101:101',mounts=1,private_authority_mounts=0)
 code,headers,html=request(health,'/web/login');cookies=SimpleCookie()
 for value in headers.get_all('Set-Cookie',[]):cookies.load(value)
 cookie=cookies['session_id'];assert cookie['httponly'] and cookie['samesite'].lower()=='lax' and not cookie['domain'] and not cookie['secure']
 assert headers['X-Content-Type-Options']=='nosniff' and headers['Referrer-Policy']=='same-origin'
 passed('development_cookie_and_browser_headers',HttpOnly=True,SameSite='Lax',host_only=True)
 for host in ['attacker.invalid','evil.localhost.attacker.invalid']:
  assert request(health,'/web/login',headers={'Host':host})[0]==421
 passed('unrecognized_host_rejected')
 for path in ['/web/database/manager','/web/database/list','/web/database/selector']:
  assert request(health,path)[0]==403
 passed('database_endpoints_blocked_at_proxy')
 assert request(health,'/api/v1/session',headers={'Origin':'http://attacker.invalid'})[0]==403
 code,headers,_=request(health,'/api/v1/session',headers={'X-Forwarded-Host':'attacker.invalid','X-Forwarded-Proto':'https'});assert code==401 and not headers.get('Access-Control-Allow-Origin')
 passed('foreign_origin_and_forged_forwarding_cannot_create_session')
 canarystate=dict(state,port=port);alice=r1_probe.Client(canarystate,fixture,'alice');bob=r1_probe.Client(canarystate,fixture,'bob')
 passed('independent_native_login_and_client_release_pins')
 for client,scope in [(alice,'A'),(bob,'B')]:
  listing=client.call('list',{'limit':25},scope);assert len(listing['items'])==1
  views=client.native('get_views',workspace=scope,kwargs=dict(views=[[False,'list'],[False,'form']],options={}))
  assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
  assert client.native('search_count',args=[[]],workspace=scope)==1
 passed('default_native_list_form_and_scoped_gateway_reads')
 wid=fixture['workspaces']['A']['public_id'];baseheaders={'X-MP-Client-Release':alice.release_token,'X-MP-Workspace':wid,'X-MP-Binding':fixture['bindings']['A']['binding_id']}
 body=dict(api_version='1.0',request_id=str(uuid4()),input={'limit':25})
 for csrf in [None,'invalid-csrf']:
  h=dict(baseheaders)
  if csrf:h['X-CSRFToken']=csrf
  code,_,raw=request(alice,'/api/v1/services/org.example.notes.documents/list',body,h)
  assert code==403 and json.loads(raw)['error']['code']=='FORBIDDEN'
 passed('supported_gateway_missing_and_invalid_csrf_rejected')
 code,_,raw=request(alice,'/app/');assert code==200
 (PRIVATE/'app.html').write_bytes(raw)
 assets=sorted(set(re.findall(r'(?:src|href)=["\'](/web/assets/[^"\']+)["\']',raw.decode())))
 assert assets,'Rendered shell must have actual served production assets'
 asset_records=[]
 for url in assets[:4]:
  code,h,raw=request(alice,url);assert code==200 and raw
  asset_records.append(dict(path=url,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),content_type=h.get('Content-Type')))
 passed('production_shell_asset_bytes_served',assets=asset_records)
 code,info=alice.request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',id=1,params={}))
 assert code==200 and 'websocket_worker_version' in info['result'];version=info['result']['websocket_worker_version']
 session='; '.join(c.name+'='+c.value for c in alice.jar);key=base64.b64encode(b'proxycanarytest01').decode()
 handshake=('GET /websocket?version='+version+' HTTP/1.1\r\nHost: 127.0.0.1:'+str(port)+'\r\nOrigin: http://127.0.0.1:'+str(port)+'\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\nCookie: '+session+'\r\n\r\n').encode()
 with socket.create_connection(('127.0.0.1',port),timeout=10) as connection:
  connection.sendall(handshake);response=connection.recv(16384)
 (PRIVATE/'websocket-response.bin').write_bytes(response)
 assert response.startswith(b'HTTP/1.1 101 ') and b'upgrade: websocket' in response.lower()
 accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
 assert accept.lower() in response.lower()
 passed('actual_native_Odoo_WebSocket_upgrade',version=version,status=101,accept_digest_verified=True)
 assert snapshot(state,'proxy-canary-data-after')==before and worker(native,'proxy-canary-worker-after')==identity;f.guard(state)
 original=json.loads(run('original-edge-after',['docker','inspect',edge['Id']]).stdout)[0];assert original['Id']==edge['Id'] and original['State']['StartedAt']==edge['State']['StartedAt'] and original['State']['Running']
 passed('seventeen_business_tables_worker_original_edge_and_protected_configs_preserved')
 record['phase']='qualified';save_state()
finally:
 if created:
  run('logs',['docker','logs',name],check=False)
  observed=json.loads(run('cleanup-observe',['docker','inspect',name]).stdout)[0]
  assert observed['Name']=='/'+name and observed['Image']==candidate and observed['Config']['Labels']['com.modular.disposable']=='mp-g7-proxy-ingress'
  run('stop',['docker','stop','--time','5',observed['Id']]);run('remove',['docker','rm',observed['Id']]);record['canary_removed']=True;save_state()
assert record['phase']=='qualified'
result=dict(result='passed_candidate_actual_ingress_not_selected_for_release',utc=datetime.now(timezone.utc).isoformat(),candidate_image=candidate,application_image=state['image_id'],configuration_generation=4,checks=checks,canary_removed=True,new_volumes=0,new_networks=0,limits=['Development profile on fresh fixture only; production TLS/rate/security fixture and final release selection remain separate.','Real HTTP/native/asset/socket transport; not browser rendering/accessibility/performance qualification.','Original/fresh active edges remain old official pin; no application/native lifecycle/key/worker mutation.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as dest:json.dump(result,dest,indent=2)
print(json.dumps(dict(result=result['result'],checks=len(checks),canary_removed=True)))
