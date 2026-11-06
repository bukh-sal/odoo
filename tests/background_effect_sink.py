"""Deterministic private qualification sink: accept a UUID, delay its ACK."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from uuid import UUID


class Sink(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        if self.path != '/effect' or self.headers.get('Content-Length') != '36':
            self.send_error(400)
            return
        try:
            value = self.rfile.read(36).decode('ascii')
            assert str(UUID(value)) == value
        except (AssertionError, ValueError):
            self.send_error(400)
            return
        print(f'accepted:{value}', flush=True)
        time.sleep(25)
        self.send_response(204)
        self.end_headers()


ThreadingHTTPServer(('0.0.0.0',8077),Sink).serve_forever()
