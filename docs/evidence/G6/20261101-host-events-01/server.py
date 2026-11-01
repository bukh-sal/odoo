"""Loopback test-only page registration; deployed bundles/backend stay exact.

Ordinary Alice authentication bootstraps a fixture cookie, never logged. The
proxy injects only a test script into the otherwise native bootstrap. WebSocket
bytes are relayed unmodified so the actual Odoo bus remains testable.
"""
import hashlib,http.client,json,select,socket,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
import r1_probe
f=j.f;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=j.LOCAL
state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='notes7_native_qualified_needs_host'
target=f.load(j.LOCAL/'operator/target.json');assert target['generation']==8 and target['image_id']==state['image_id']
fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture);cookie=next(c for c in client.jar if c.name=='session_id')
marker=j.LOCAL/'host-event-proxy-01.json';assert not marker.exists()
assets={};metrics=dict(websocket_tunnels=0);host='g6events.localhost:18089'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def local(self,data,kind='application/json'):
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):self.proxy()
    def do_POST(self):self.proxy()
    def proxy(self):
        if self.headers.get('Host')!=host:self.send_error(421);return
        if self.path=='/__g6_host__/fixture.js':self.local((OUT/'fixture.js').read_bytes(),'text/javascript');return
        if self.path=='/__g6_host__/config':self.local(json.dumps({name:fixture['workspaces'][name]['public_id'] for name in ['A','B','C']}).encode());return
        if self.path=='/__g6_host__/report' and self.command=='POST':
            size=int(self.headers.get('Content-Length',0));assert 0<size<=16384
            report=json.loads(self.rfile.read(size));assert set(report)<={'checks','counts','notes','subscription_ids','failures','phase','context','bus_payload_minimized','actual_host_facade','native_Odoo_default','disposals'}
            f.write(j.LOCAL/'host-events-browser-report.json',report);self.local(b'{"recorded":true}');return
        if self.path.startswith('/websocket') and self.headers.get('Upgrade','').lower()=='websocket':
            upstream=socket.create_connection(('127.0.0.1',state['port']),timeout=30)
            try:
                request=(self.command+' '+self.path+' HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in self.headers.items())+'\r\n').encode('latin1');upstream.sendall(request)
                metrics['websocket_tunnels']+=1;f.write(j.LOCAL/'host-event-proxy-metrics.json',metrics);self.close_connection=True
                while True:
                    readable,_,_=select.select([upstream,self.connection],[],[],30)
                    if not readable:continue
                    for source in readable:
                        data=source.recv(65536)
                        if not data:return
                        (self.connection if source is upstream else upstream).sendall(data)
            except (OSError,ConnectionError):pass
            finally:upstream.close()
            return
        headers={k:v for k,v in self.headers.items() if k.lower() not in {'connection','content-length','accept-encoding'}}
        # Only the native bootstrap gets the already-authenticated test cookie.
        bootstrap=self.command=='GET' and self.path.startswith('/app/')
        if bootstrap:headers['Cookie']='session_id='+cookie.value
        size=int(self.headers.get('Content-Length',0));assert 0<=size<=65536
        conn=http.client.HTTPConnection('127.0.0.1',state['port'],timeout=30)
        try:
            conn.request(self.command,self.path,body=self.rfile.read(size) if size else None,headers=headers)
            response=conn.getresponse();body=response.read();original=body
            if bootstrap and response.status==200:
                assert body.count(b'</head>')==1;body=body.replace(b'</head>',b'<script defer src="/__g6_host__/fixture.js"></script></head>')
            self.send_response(response.status)
            for key,value in response.getheaders():
                if key.lower() not in {'transfer-encoding','connection','content-length','content-encoding'}:self.send_header(key,value)
            if bootstrap:self.send_header('Set-Cookie','session_id='+cookie.value+'; Path=/; HttpOnly; SameSite=Lax')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            if self.path.startswith('/web/assets/') and response.status==200:
                assert body==original;assets[self.path]=dict(sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),response_unchanged=True)
                f.write(j.LOCAL/'host-event-proxy-assets.json',assets)
        except (BrokenPipeError,ConnectionResetError):pass
        finally:conn.close()

server=ThreadingHTTPServer(('127.0.0.1',18089),Handler);server.daemon_threads=True
f.write(marker,dict(state='serving',port=18089,project=state['project'],generation=8,image_id=state['image_id'],bootstrap='ordinary Alice login; test script registration injected; actual bundle/API/WebSocket bytes unchanged'))
f.phase(state,'host_event_proxy_serving');print('Test-only actual-host page proxy ready on loopback18089; no product source or dispatch state change.',flush=True)
try:server.serve_forever()
finally:server.server_close();record=f.load(marker);record['state']='stopped';f.write(marker,record)
