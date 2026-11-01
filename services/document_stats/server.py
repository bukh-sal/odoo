"""Bounded JSON/HTTP adapter for the separately operated reference worker."""
import argparse
import json
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
import time
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from .engine import Engine, WorkerError


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, engine):
        self.engine = engine
        self.slots = BoundedSemaphore(16)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, address):
        # Never dump request data, exception strings, headers or credentials.
        print(json.dumps(dict(event='connection_error')), flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'DocumentStats/1'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *args):
        pass

    def respond(self, status, value):
        body = json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)
        print(json.dumps(dict(event='request', status=status)), flush=True)

    def do_GET(self):
        if self.path == '/health':
            self.respond(200, dict(status='ok', api_version='1.0'))
        else:
            self.respond(404, dict(error=dict(code='NOT_FOUND')))

    def do_POST(self):
        try:
            if self.path != '/analyze':
                raise WorkerError('NOT_FOUND', 404)
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                raise WorkerError('VALIDATION_FAILED', 400)
            length = self.headers['Content-Length']
            if not length.isascii() or not length.isdecimal() or not 0 < int(length) <= 131072:
                raise WorkerError('VALIDATION_FAILED', 400)
            if self.headers.get('Content-Type') != 'application/json':
                raise WorkerError('VALIDATION_FAILED', 400)
            authorization = self.headers.get('Authorization', '')
            if len(self.headers.get_all('Authorization', [])) != 1 or not authorization.startswith('Bearer ') or len(authorization) > 8192:
                raise WorkerError('UNAUTHENTICATED', 401)
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                raise WorkerError('VALIDATION_FAILED', 400)
            value = json.loads(raw.decode('utf8'), object_pairs_hook=strict_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            result = self.server.engine.analyze(authorization[7:], value)
            self.respond(200, result)
        except WorkerError as error:
            self.respond(error.status, dict(error=dict(code=error.code)))
        except (ValueError, UnicodeError, RecursionError):
            self.respond(400, dict(error=dict(code='VALIDATION_FAILED')))
        except TimeoutError:
            self.respond(408, dict(error=dict(code='DEADLINE_EXCEEDED')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(), object_pairs_hook=strict_object)
    if set(config) != {'public_key_file', 'key_id', 'site_id', 'workspace_id', 'installation_id', 'endpoint_generation'}:
        raise ValueError('Exact operator-owned worker configuration required')
    for field in ['site_id', 'workspace_id', 'installation_id']:
        if str(UUID(config[field])) != config[field]:
            raise ValueError('Canonical configured scope required')
    if type(config['endpoint_generation']) is not int or not 1 <= config['endpoint_generation'] <= 9007199254740991:
        raise ValueError('Positive endpoint generation required')
    if not isinstance(config['key_id'], str) or not 1 <= len(config['key_id']) <= 80:
        raise ValueError('Configured verification key identity required')
    public_key = Path(config.pop('public_key_file')).read_bytes()
    parsed = serialization.load_pem_public_key(public_key)
    if not isinstance(parsed, RSAPublicKey) or parsed.key_size < 2048:
        raise ValueError('Public-only RSA verification key required')
    server = Server((args.host, args.port), Engine(public_key, **config))
    # Linux PID1 ignores the default SIGTERM disposition. Explicitly finish
    # through finally so an operator stop does not require Docker SIGKILL.
    # An interrupted pure computation can be retried; the host owns effects.
    def stop(_signum, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    print(json.dumps(dict(event='ready', port=server.server_port, api_version='1.0')), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
