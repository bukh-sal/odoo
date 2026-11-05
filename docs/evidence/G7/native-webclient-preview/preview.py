"""Loopback-only, read-only Notes preview using the stock Odoo WebClient."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from xml.etree import ElementTree


REFERENCE = Path('.local/release-kit-core26-rehearsal/private/reference')
state = json.loads((REFERENCE / 'state.json').read_bytes())
fixture = json.loads((REFERENCE / 'fixtures.json').read_bytes())
project = 'mp-r0-r1release1c1f3b9c7a85'
if state['project'] != project or state['url'] != 'http://release-1c1f3b9c7a85.localhost:18101':
    raise ValueError('Expected the exact disposable developer rehearsal')

UPSTREAM = urlsplit(state['url'])
PORT = 18103
HOST = f'{UPSTREAM.hostname}:{PORT}'
ORIGIN = f'http://{HOST}'
WORKSPACE = fixture['workspaces']['A']['public_id']
ACTION = 'mp_example_notes.action_notes'
ACTION_ID = 88  # Observed on the pinned generation5 rehearsal.
NOTES_PATH = re.compile(rf'/odoo/action-(?:{re.escape(ACTION)}|{ACTION_ID})(?:/[1-9][0-9]*)?')
MAX_BODY = 1 << 20
READS = {'get_views', 'web_search_read', 'web_read', 'web_read_group', 'web_name_search',
         'search_count', 'search_read', 'read', 'name_search'}
HOP_HEADERS = {'connection', 'content-length', 'keep-alive', 'proxy-authenticate',
               'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade'}


def connection():
    return HTTPConnection('127.0.0.1', UPSTREAM.port, timeout=20)


def release_pin():
    sys.path.insert(0, str(Path('packages/platform_sdk').resolve()))
    from modular_platform.plans import data_digest

    target = json.loads((REFERENCE / 'operator/target.json').read_bytes())
    candidate = json.loads((Path(__file__).resolve().parent.parent /
                            '20261105-core26-developer-install-01/candidate-build.json').read_bytes())
    if (target['project'], target['generation'], target['image_id']) != (project, 5, candidate['image_id']):
        raise ValueError('Expected the qualified developer generation')
    release = target['published_release']
    return data_digest({'protocol': 1, 'site_id': target['sites'][0]['site_id'],
                        'generation': release['generation'], 'release_digest': data_digest(release),
                        'inventory_digest': candidate['inventory_digest']})


def allowed(method, path, body):
    if method == 'GET':
        return (path in {'/odoo', '/web/login', '/web/webclient/load_menus', '/web/favicon.ico',
                         '/web/webclient/translations'}
                or NOTES_PATH.fullmatch(path) is not None
                or path.startswith(('/web/assets/', '/web/static/', '/web/bundle/')))
    if path == '/web/login':
        return True
    try:
        params = json.loads(body)['params']
        if path == '/web/action/load':
            return params['action_id'] in (ACTION, ACTION_ID)
        if path.startswith('/web/dataset/call_kw/'):
            model, operation = params['model'], params['method']
            return (model == 'mp.example.note' and operation in READS
                    and path == f'/web/dataset/call_kw/{model}/{operation}')
    except (KeyError, TypeError, ValueError):
        return False
    return False


def readonly_views(data):
    envelope = json.loads(data)
    if 'result' not in envelope:
        return data
    for kind, view in envelope['result']['views'].items():
        if kind in {'list', 'form'}:
            arch = ElementTree.fromstring(view['arch'])
            for action in ('create', 'edit', 'delete', 'duplicate', 'import', 'export_xlsx'):
                arch.set(action, '0')
            view['arch'] = ElementTree.tostring(arch, encoding='unicode')
        view.pop('toolbar', None)
    return json.dumps(envelope).encode()


class Preview(BaseHTTPRequestHandler):
    def log_message(self, *_):
        # No browser request metadata, credentials, cookies or bodies in logs.
        pass

    def forward(self):
        if self.headers.get('Host') != HOST or self.headers.get('Origin', ORIGIN) != ORIGIN:
            self.send_error(403)
            return
        path = urlsplit(self.path)
        if path.netloc or path.scheme or self.headers.get('Transfer-Encoding'):
            self.send_error(400)
            return
        length = self.headers.get('Content-Length', '0')
        if not length.isdecimal() or int(length) > MAX_BODY:
            self.send_error(413)
            return
        body = self.rfile.read(int(length))
        if not allowed(self.command, path.path, body):
            self.send_error(403, 'Read-only Notes preview')
            return
        headers = {name: self.headers[name] for name in ('Cookie', 'Content-Type', 'Accept')
                   if name in self.headers}
        headers['Host'] = UPSTREAM.netloc
        if 'Origin' in self.headers:
            headers['Origin'] = state['url']
        if path.path.startswith('/web/dataset/call_kw/'):
            headers.update({'X-MP-Workspace': WORKSPACE, 'X-MP-Client-Release': PIN})
        upstream = connection()
        try:
            upstream.request(self.command, self.path, body=body or None, headers=headers)
            response = upstream.getresponse()
            data = response.read()
            view_response = path.path == '/web/dataset/call_kw/mp.example.note/get_views' and response.status == 200
            if view_response:
                data = readonly_views(data)
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() in HOP_HEADERS or (view_response and name.lower() in {'etag', 'cache-control'}):
                    continue
                if name.lower() == 'location' and value.startswith(state['url'] + '/'):
                    value = ORIGIN + value[len(state['url']):]
                self.send_header(name, value)
            if view_response:
                self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        finally:
            upstream.close()

    do_GET = forward
    do_POST = forward


if __name__ == '__main__':
    PIN = release_pin()
    with ThreadingHTTPServer(('127.0.0.1', PORT), Preview) as server:
        print(f'{ORIGIN}/odoo/action-{ACTION}', flush=True)
        server.serve_forever()
