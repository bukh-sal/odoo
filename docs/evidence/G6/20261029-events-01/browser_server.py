"""Temporary loopback-only test harness/proxy; no product endpoint or source edits.

An ordinary native Alice login is performed server-side solely to bootstrap the
browser fixture session. This is not evidence of browser login UI behavior.
All subsequent browser CSRF, release, binding, subscription and event requests
cross the unchanged deployed edge/backend. No passwords/headers/bodies logged.
"""
import hashlib,http.client,json,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import fixture as j
import r1_probe
f=j.f;r1_probe.r1.r0.LOCAL=j.LOCAL
source_fix=sys.argv[1:]==['--source-fix'];assert not sys.argv[1:] or source_fix
state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']==('browser-dispatch-enable-01' if source_fix else 'event_http_verified')
fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture)
cookie=next(c for c in client.jar if c.name=='session_id')
out=Path(__file__).resolve().parent;marker=j.LOCAL/('browser-server-source-fix-01.json' if source_fix else 'browser-server-01.json');assert not marker.exists()
f.write(marker,dict(state='starting',port=18089,project=state['project']))
# Fixture-only trusted operator control; no generic lifecycle/recovery claim.
code="from modular_platform import durable\nenv.cr.rollback()\nenv.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.site_id'\");site=env.cr.fetchone()[0]\nenv.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'\");release=env.cr.fetchone()[0]\ndurable.set_control(env.cr,site,release,'enabled');env.cr.commit();print('MP_BROWSER_DISPATCH_ENABLED')"
if not source_fix:assert b'MP_BROWSER_DISPATCH_ENABLED' in f.native(state,'browser-dispatch-enable-01',[],code)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,body,kind='text/html',*,bootstrap=False):
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        if bootstrap:self.send_header('Set-Cookie','session_id='+cookie.value+'; Path=/; HttpOnly; SameSite=Lax')
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.proxy()
    def do_POST(self):self.proxy()
    def proxy(self):
        if self.headers.get('Host')!='g6events.localhost:18089':self.send_error(421);return
        if self.path=='/__events__/':
            html=(out/'browser_harness.html').read_bytes()
            if source_fix:html=html.replace(b"from '/mp_shell/static/src/event_client.js'",b"from '/__events__/event_client.js'").replace(b'Uses the deployed event client',b'Uses corrected worktree event client (not yet deployed)')
            self.send(html,bootstrap=True);return
        if source_fix and self.path=='/__events__/event_client.js':
            self.send((f.ROOT/'platform_addons/mp_shell/static/src/event_client.js').read_bytes(),'text/javascript');return
        if source_fix and self.path=='/__events__/event_contract':
            self.send((f.ROOT/'platform_addons/mp_shell/static/src/event_contract.js').read_bytes(),'text/javascript');return
        if self.path=='/__events__/fixture.json':self.send(json.dumps(dict(workspaceA=fixture['workspaces']['A']['public_id'],workspaceB=fixture['workspaces']['B']['public_id'])).encode(),'application/json');return
        path=self.path
        if path=='/mp_shell/static/src/event_contract':path+='.js'
        # Preserve actual browser Host/Origin, cookie and CSRF checks at edge.
        headers={k:v for k,v in self.headers.items() if k.lower() not in {'connection','content-length','accept-encoding'}}
        size=int(self.headers.get('Content-Length',0));assert size<=65536
        conn=http.client.HTTPConnection('127.0.0.1',state['port'],timeout=30)
        try:
            conn.request(self.command,path,body=self.rfile.read(size) if size else None,headers=headers)
            response=conn.getresponse();body=response.read();self.send_response(response.status)
            for key,value in response.getheaders():
                if key.lower() not in {'transfer-encoding','connection','content-length','content-encoding'}:self.send_header(key,value)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            if path in ['/mp_shell/static/src/event_client.js','/mp_shell/static/src/event_contract.js']:
                expected=f.ROOT/'platform_addons'/path.lstrip('/');assert response.status==200 and body==expected.read_bytes()
                dest=j.LOCAL/(Path(path).stem+'-browser-source.json');f.write(dest,dict(status=response.status,path=path,sha256=hashlib.sha256(body).hexdigest(),exact_current_source=True))
        except (BrokenPipeError,ConnectionResetError):pass
        finally:conn.close()
server=ThreadingHTTPServer(('127.0.0.1',18089),Handler)
f.write(marker,dict(state='serving',port=18089,project=state['project'],fixture_session_actor='alice',bootstrap='ordinary native authentication; session cookie not logged',source_mode='corrected worktree; not immutable deployment qualification' if source_fix else 'exact deployed JS',source_transform='extensionless relative validator URL routed to exact JS bytes'))
print('Browser harness ready on loopback18089; Canvas and deployed source unchanged',flush=True)
server.serve_forever()
