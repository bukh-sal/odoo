"""Actual certificate-verified native WebSocket transport through current TLS edge."""
import base64,hashlib,importlib.util,json,socket,ssl,time
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
OUT=Path(__file__).parent;ROOT=Path.cwd();LOCAL=ROOT/'.local/g7-production-profile-01'
spec=importlib.util.spec_from_file_location('current_tls_probe',OUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state=json.loads((LOCAL/'state.json').read_text());fixture=json.loads((LOCAL/'fixtures.json').read_text());client=m.Client('production')
# Previous bounded login-rate test may still consume this exact edge's bucket.
# Honor explicit Retry-After once; never restart the edge/reset its limits.
for attempt in range(2):
 code,value,h,raw=client.request('/web/session/authenticate',dict(jsonrpc='2.0',method='call',id=1,params=dict(db=state['active_db'],login=fixture['users']['alice']['login'],password=(LOCAL/'password-alice').read_text().strip())),headers={'Origin':client.origin})
 if code==200:assert value.get('result',{}).get('uid')==fixture['users']['alice']['id'];break
 assert code==429 and h['Retry-After']=='12' and attempt==0;time.sleep(12)
else:raise AssertionError('Actual edge rate did not refill as declared')
code,info,_,_=client.request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',id=1,params={}),headers={'Origin':client.origin});assert code==200
version=info['result']['websocket_worker_version'];cookie='; '.join(c.name+'='+c.value for c in client.jar);context=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));responses=[]
for origin,expected in [(client.origin,101),('https://attacker.invalid',403)]:
 key=base64.b64encode(uuid4().bytes).decode();data=('GET /websocket?version='+version+' HTTP/1.1\r\nHost: '+client.authority+'\r\nOrigin: '+origin+'\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\nCookie: '+cookie+'\r\n\r\n').encode()
 with socket.create_connection(('127.0.0.1',state['https_port']),timeout=10) as stream:
  with context.wrap_socket(stream,server_hostname='security.localhost') as connection:
   connection.sendall(data);raw=connection.recv(16384);status=int(raw.split(b' ',2)[1]);assert status==expected
   if status==101:
    accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest());assert accept.lower() in raw.lower() and b'upgrade: websocket' in raw.lower()
    connection.sendall(bytes([0x88,0x82,0,0,0,0,0x03,0xE8]))
   responses.append(dict(origin='canonical' if expected==101 else 'foreign',status=status,TLS=connection.version(),certificate_verified=True,accept_digest_verified=status==101))
  (LOCAL/('tls-websocket-'+str(expected)+'.bin')).write_bytes(raw)
record=dict(result='passed_actual_TLS_native_WebSocket_and_foreign_origin_rejection',utc=datetime.now(timezone.utc).isoformat(),application_image=state['image_id'],proxy_image='sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f',version=version,checks=responses,limits=['Protocol transport/authenticated native session and browser-origin fence; no browser rendering/event subscription/lifecycle or accessibility claim.','Private two-day test certificate trusted only by this client; no external production deployment.'])
(OUT/'TLS-WebSocket-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(result=record['result'],statuses=[r['status'] for r in responses])))
