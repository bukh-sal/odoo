"""Test-only non-idempotent recipient: commit a receipt, withhold HTTP response."""
import hashlib,json,os,signal,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from modular_platform.tokens import verify_worker_token

config=json.loads(Path('/run/worker/config.json').read_text())
public=Path(config['public_key_file']).read_bytes()
scope={k:config[k] for k in ('site_id','workspace_id','installation_id','endpoint_generation')}
root=Path('/tmp/job03');root.mkdir(mode=0o700);receipt=root/'receipt.json';lock=threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path!='/health':self.send_error(404);return
        body=b'{"status":"ok","api_version":"1.0"}'
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        try:
            assert self.path=='/analyze' and self.headers.get('Content-Type')=='application/json'
            size=int(self.headers['Content-Length']);assert 0<size<=65536
            request=json.loads(self.rfile.read(size));authorization=self.headers.get('Authorization','');assert authorization.startswith('Bearer ')
            verify_worker_token(authorization[7:],public,key_id=config['key_id'],request=request)
            assert all(request[k]==v for k,v in scope.items())
        except Exception:
            self.send_error(401);return
        with lock:
            old=json.loads(receipt.read_text()) if receipt.exists() else dict(count=0)
            result=dict(count=old['count']+1,operation_id=request['operation_id'],
                input_sha256=hashlib.sha256(json.dumps(request['input'],sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest(),
                committed_at=time.time(),response_sent=False)
            temporary=root/'receipt.next'
            with temporary.open('w') as stream:json.dump(result,stream);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,receipt)
        print(json.dumps(dict(event='effect_committed',operation_id=result['operation_id'],count=result['count'])),flush=True)
        # The caller never receives an acknowledgement, although another
        # process has committed the non-idempotent effect. This is deliberate.
        threading.Event().wait(120)

class Server(ThreadingHTTPServer):daemon_threads=True
server=Server(('0.0.0.0',8080),Handler)
def stop(*_):raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
print(json.dumps(dict(event='fixture_ready',pid=os.getpid())),flush=True)
try:server.serve_forever()
finally:server.server_close()
