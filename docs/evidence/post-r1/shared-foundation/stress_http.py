"""Check live stock dataset access on the disposable stress deployments."""

import argparse
import http.cookiejar
import json
import urllib.request

from stress_sites import ADDONS, StressSite, load, write
from modular_platform.plans import data_digest
from r1_probe import Client


class StressClient(Client):
    def __init__(self, site, actor):
        self.fixture = load(site.local / 'fixtures.json')
        identity = self.fixture['users'][actor]
        password = load(site.local / 'account-passwords.json')[actor]
        self.base = f"http://127.0.0.1:{site.state()['port']}"
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        target = load(site.local / 'operator/target.json')
        status, response = self.request('/web/session/authenticate', {'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'db': target['sites'][0]['database'], 'login': identity['login'], 'password': password}})
        assert status == 200 and response.get('result', {}).get('uid') == identity['id']
        status, response = self.request('/api/v1/client-release')
        assert status == 200 and response['data']['generation'] == target['generation']
        self.release_token = response['data']['token']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', choices=ADDONS)
    parser.add_argument('label', choices=['baseline', 'restored', 'successor', 'peer-during-recovery'])
    args = parser.parse_args()
    site = StressSite(args)
    target = load(site.local / 'operator/target.json')
    alice, bob, operator = [StressClient(site, role) for role in ('alice', 'bob', 'operator')]
    marker = site.local / ('http-' + args.label + '.json')
    if marker.exists():
        raise ValueError('Use a fresh verification label')

    for workspace, client in [('A', alice), ('B', bob)]:
        title = 'Scoped foundation fixture ' + workspace
        if args.label == 'baseline' and not client.native('search_count', [[('title', '=', title)]], workspace=workspace):
            client.native('create', [{'title': title, 'body': 'Synthetic scoped fixture'}], workspace=workspace)
    visible = {space: alice.native('search_read', [[]], {'fields': ['title']}, workspace=space) for space in ('A', 'B')}
    for space, rows in visible.items():
        assert len(rows) == 1 and rows[0]['title'] == 'Scoped foundation fixture ' + space
    alice.native('create', [{'title': 'Denied viewer write'}], workspace='B', deny=True)
    bob.native('read', [[visible['A'][0]['id']], ['title']], workspace='B', deny=True)
    alice.native('read', [[visible['B'][0]['id']], ['title']], workspace='A', deny=True)
    app = load(site.local / 'app-fixtures.json')
    if args.site == 'aurora':
        row = alice.native('read', [[app['task']], ['stage_id', 'assignee_id']], workspace=None, model='mp.aurora.task')[0]
        assert row['stage_id'][0] == app['done'] and row['assignee_id'][0] == alice.fixture['users']['bob']['id']
        operator.native('read', [[app['task']], ['name']], workspace=None, deny=True, model='mp.aurora.task')
    else:
        row = alice.native('read', [[app['request']], ['stage_id', 'equipment_id']], workspace=None, model='maintenance.request')[0]
        assert row['stage_id'][1] == 'In Progress' and row['equipment_id'][0] == app['equipment']
        bob.native('read', [[app['request']], ['name']], workspace=None, deny=True, model='maintenance.request')
    stale_denied = False
    if args.label != 'baseline':
        transition = 'fault-recover' if args.label == 'restored' else 'upgrade'
        operation = load(site.local / (transition + '.json'))['operation_id']
        previous = load(site.local / 'operator/control/stages' / operation / 'configuration.json')
        prior_inventory = previous['published_release']['core_inventory_digest']
        stale_token = data_digest({'protocol': 1, 'site_id': previous['sites'][0]['site_id'],
            'generation': previous['generation'], 'release_digest': data_digest(previous['published_release']),
            'inventory_digest': prior_inventory})
        assert stale_token != alice.release_token
        status, response = alice.request('/web/dataset/call_kw/mp.example.note.search_count',
            {'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {'model': 'mp.example.note',
                'method': 'search_count', 'args': [[]], 'kwargs': {}}}, 'A', {'X-MP-Client-Release': stale_token})
        assert status == 200 and response['error']['data']['name'].endswith('.ClientReleaseMismatch')
        stale_denied = True
    result = {'site': args.site, 'label': args.label, 'generation': target['generation'], 'image': target['image_id'],
              'native_workflow_record_preserved': True, 'outsider_read_denied': True,
              'notes_workspace_search_isolated': True, 'notes_cross_scope_read_and_viewer_create_denied': True,
              'prior_release_token_denied': stale_denied,
              'notes': {space: rows[0]['id'] for space, rows in visible.items()}}
    write(marker, result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
