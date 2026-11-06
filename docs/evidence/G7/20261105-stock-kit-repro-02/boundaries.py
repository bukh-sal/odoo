"""Check local HTTP and network boundaries on the exact stock kit site."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'release'))
from check_reference import Client
from initialize_reference import Reference, load


def docker(*args):
    return subprocess.check_output(['docker', *args], timeout=45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18107)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Fresh evidence path required')
    reference = Reference(args)
    state = reference.state()
    target = load(reference.local / 'operator/target.json')
    assert state['phase'] == 'kit_backend_worker_reference_qualified'
    assert target['image_id'] == reference.manifest['images']['application']['image_id']
    assert state['project'] == target['project'] and state['port'] == args.port
    alice = Client(reference, 'alice')
    host = state['hostname'] + ':' + str(state['port'])
    base = 'http://127.0.0.1:' + str(state['port'])

    def http(path, **headers):
        request = urllib.request.Request(base + path, headers={'Host': host, **headers})
        try:
            response = alice.http.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, dict(response.headers), response.geturl(), response.read()

    status, headers, url, body = http('/')
    assert status == 200 and url.endswith('/odoo') and b'mp_stock_profile' in body
    assert 'no-store' in headers['Cache-Control']
    assert http('/web/database/manager')[0] == 403
    assert http('/odoo', Origin='https://example.invalid')[0] == 403
    assert http('/odoo', Host='example.invalid')[0] == 421
    assert http('/web/database/list')[0] == 403

    def dataset(token, workspace):
        request = urllib.request.Request(base + '/web/dataset/call_kw/mp.example.note/search_count',
            headers={'Host': host, 'Content-Type': 'application/json',
                     'X-MP-Client-Release': token, 'X-MP-Workspace': workspace},
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {
                'model': 'mp.example.note', 'method': 'search_count', 'args': [[]], 'kwargs': {}}}).encode())
        with alice.http.open(request, timeout=15) as response:
            return json.load(response)

    workspace = alice.fixture['workspaces']['A']['public_id']
    assert dataset(alice.token, workspace)['result'] == 1
    for token in ('', 'sha256:' + '0' * 64):
        denial = dataset(token, workspace)['error']['data']
        assert denial['name'].endswith('.ClientReleaseMismatch') and 'debug' not in denial
    assert dataset(alice.token, '00000000-0000-0000-0000-000000000001')['error']['data']['name'].endswith('.AccessError')

    project = state['project']
    module_id = int(docker('exec', project + '-db-1', 'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1',
        '-U', 'postgres', '-d', state['database'], '-c',
        "SELECT id FROM ir_module_module WHERE name='mp_example_notes' AND state='installed';"))
    status, module_attempt = alice.request('/web/dataset/call_kw/ir.module.module.button_immediate_install',
        {'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {
            'model': 'ir.module.module', 'method': 'button_immediate_install', 'args': [[module_id]], 'kwargs': {}}}, 'A')
    assert status == 200 and module_attempt['error']['data']['name'] == 'odoo.exceptions.AccessDenied'
    assert set(module_attempt['error']['data']) == {'name', 'message', 'request_id'}
    network, = json.loads(docker('network', 'inspect', project + '_runtime'))
    assert network['Internal'] is True
    worker_state = load(reference.local / 'worker/state.json')
    worker_id = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + worker_state['project']).decode().strip()
    app_id = target['worker_id']
    app, worker = json.loads(docker('inspect', app_id, worker_id))
    for runtime in (app, worker):
        assert set(runtime['NetworkSettings']['Networks']) == {project + '_runtime'}
        assert not runtime['HostConfig']['Privileged']
    assert {mount['Destination'] for mount in worker['Mounts']} == {'/run/worker'}
    probe = '''import json, socket
routes = open('/proc/net/route').read().splitlines()[1:]
assert not any(row.split()[1] == '00000000' for row in routes)
with socket.create_connection(('db', 5432), timeout=3): pass
try:
    with socket.create_connection(('198.51.100.1', 443), timeout=3): pass
except OSError: print(json.dumps({'database_tcp': True, 'default_ipv4_route': False, 'external_tcp': False}))
else: raise AssertionError('External connection succeeded')
'''
    egress = json.loads(docker('exec', app_id, '/venv/bin/python', '-c', probe))
    receipt = {'result': 'passed', 'image': target['image_id'], 'generation': target['generation'],
               'stock_default': True, 'foreign_origin_and_host_denied': True, 'database_manager_denied': True,
               'missing_and_stale_release_and_foreign_workspace_denied': True, 'jsonrpc_errors_redacted': True,
               'workspace_administrator_native_install_denied': True,
               'application_and_worker_on_internal_network_only': True, 'worker_public_config_only': True,
               'application_egress': egress}
    with args.receipt.open('x', encoding='utf8') as handle:
        json.dump(receipt, handle, indent=2)
        handle.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
