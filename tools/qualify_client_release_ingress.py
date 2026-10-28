"""Bounded current-pin regression on the existing populated clone, never setup.

The private write-ahead preimage supports reconciliation; a terminal attempt
cannot be replayed. All fixture changes are confined to that disposable clone.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL, command
import r1
from r1_probe import Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/evidence/G5') and not output.exists()
    clone_path = ROOT / '.local/g5/client-release-clones/20261028-client-release-clone-01.json'
    clone = json.loads(clone_path.read_text(encoding='utf-8'))
    assert clone['state'] == 'browser_qualified_subset' and clone['generation'] == 18
    assert clone['database'] == 'mp_disposable_r0_r1_client_d44f98595a294031'
    private = clone_path.with_name(output.name + '.json')
    assert not private.exists()
    target = json.loads((ROOT / '.local/operator/targets/g5.json').read_text(encoding='utf-8'))
    observer = DockerObserver(target)
    catalog = Catalog(ROOT / '.local/operator/catalog', configuration(ROOT / '.local/operator/trust.json'), readonly=True).snapshot()
    source = observer.state(observer.read(), catalog)['state']
    assert data_digest(source) == clone['source_state_digest']
    database = clone['database']; db = observer._container('db')

    def sql(statement, name=database):
        return command(['docker', 'exec', '-i', db, 'psql', '-X', '-qAt', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', '-d', name], input=statement.encode())

    business = json.loads(sql(BUSINESS_SQL))
    assert data_digest(business) == clone['business_digest']
    memberships = json.loads(sql('SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m;'))
    groups = sql('SELECT jsonb_agg(to_jsonb(g) ORDER BY uid,gid) FROM res_groups_users_rel g;').decode().strip()
    fixture = json.loads((ROOT / '.local/g5/fixtures.json').read_text(encoding='utf-8'))
    fixture['bindings'] = {}; objects = {}
    bindings = {}
    for key, space in fixture['workspaces'].items():
        for installation in source['installations']:
            if installation['workspace_id'] != space['public_id']: continue
            plugin = installation['plugin_id']
            for binding in source['bindings']:
                if binding['workspace_id'] == space['public_id'] and binding['consumer_installation_id'] == installation['installation_id']:
                    bindings[(key, plugin, binding['alias'])] = binding
        fixture['bindings'][key] = bindings[(key, 'org.example.notes', 'documents')]
        objects[key] = next(row for row in business['notes'] if row['workspace_id'] == space['id'])
    r1.r0.LOCAL = ROOT / '.local/g5'
    state = {'active_db': database, 'port': clone['port']}
    nonce = uuid4().hex; prefix = 'Ingress ' + nonce + ' '
    secondary = clone['volume'] + '-ingress-worker'; edge = clone['volume'] + '-ingress-edge'
    record = {'state': 'prepared', 'database': database, 'memberships': memberships, 'business': business,
              'prefix': prefix, 'secondary': secondary, 'edge': edge, 'port': 18075, 'image_id': clone['image_id']}
    report = {'result': 'in_progress', 'utc': datetime.now(timezone.utc).isoformat(), 'image_id': clone['image_id'],
              'inventory_digest': clone['inventory_digest'], 'database': database, 'generation': 18,
              'checks': [], 'acceptance_subset': [], 'limits': ['No independent executor/deployment qualification.',
              'Actual postcommit crash/cancellation and browser two-tab cache checks are separate.']}
    output.mkdir(parents=True)

    def save():
        private.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        (output / 'ingress.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def passed(name, ids=(), **details):
        report['checks'].append({'name': name, 'result': 'passed', **details})
        report['acceptance_subset'] = sorted(set(report['acceptance_subset']) | set(ids)); save()

    def member(operator, actor, workspace, role=None, remove=False):
        body = {'operation': 'remove' if remove else 'add', 'principal_id': fixture['users'][actor]['principal_id']}
        if not remove: body['role'] = role
        status, value = operator.request('/api/v1/workspace/members', body, workspace, {'X-CSRFToken': operator.csrf})
        assert status == 200 and value['data']['changed'], (status, value)

    def call(client, plugin, alias, method, values, key=None, expect=200, code=None, version=None, headers=None):
        binding = bindings[('A', 'org.example.' + plugin, alias)]
        body = {'api_version': version or binding['api_version'], 'request_id': uuid4().hex, 'input': values}
        if key: body['idempotency_key'] = key
        status, value = client.request('/api/v1/services/' + binding['service_id'] + '/' + method, body, 'A',
                                      {'X-CSRFToken': client.csrf, 'X-MP-Binding': binding['binding_id'], **(headers or {})})
        assert status == expect, (method, status, value)
        if code: assert value['error']['code'] == code, value
        return value.get('data', value)

    save(); alice = None; fixture_changed = False
    try:
        # Write-ahead record exists before any test authority change.
        fixture_changed = True; record['state'] = 'fixtures_changing'; save()
        sql("UPDATE mp_workspace_plugin SET availability='enabled' WHERE plugin_id='org.example.notes' AND workspace_id=2; UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=2;")
        operator = Client(state, fixture, 'operator')
        member(operator, 'alice', 'A', 'editor'); member(operator, 'bob', 'B', 'editor')
        alice = Client(state, fixture); bob = Client(state, fixture, 'bob')
        for key in ['A', 'B']:
            status, value = alice.request('/api/v1/context?plugin_id=org.example.notes', workspace=key)
            assert status == 200 and value['data']['context']['workspace_id'] == fixture['workspaces'][key]['public_id']
            visible = {row['id'] for row in alice.call('list', {'limit': 100}, key)['items']}
            assert objects[key]['public_id'] in visible and objects['B' if key == 'A' else 'A']['public_id'] not in visible
            native = alice.native('search_read', [[]], {'fields': ['workspace_id', 'public_id']}, key)
            assert native and all(row['workspace_id'][0] == fixture['workspaces'][key]['id'] for row in native)
        for method, values in [('create', {'title': prefix+'denied', 'body': ''}), ('update', {'note_id': objects['B']['public_id'], 'expected_revision': 1, 'title': 'Denied'}), ('delete', {'note_id': objects['B']['public_id'], 'expected_revision': 1})]:
            alice.call(method, values, 'B', expect=403, code='FORBIDDEN', headers={'X-MP-Consumer': 'administrator', 'X-MP-Actor': 'root'})
        for method, arguments in [('read', [[objects['A']['id']], ['title']]), ('write', [[objects['A']['id']], {'title': 'Denied'}]), ('unlink', [[objects['A']['id']]]), ('create', [{'workspace_id': 1, 'title': 'Denied', 'body': ''}])]:
            bob.native(method, arguments, workspace='B', deny=True)
        for method in ['get', 'update', 'delete']:
            values = {'note_id': objects['A']['public_id']}
            if method != 'get': values['expected_revision'] = objects['A']['revision']
            if method == 'update': values['title'] = 'Denied'
            bob.call(method, values, 'B', expect=404, code='NOT_FOUND')
        own = bob.call('create', {'title': prefix+'legitimate B', 'body': 'Synthetic'}, 'B')
        bob.call('delete', {'note_id': own['id'], 'expected_revision': 1}, 'B')
        alice.native('write', [[objects['B']['id']], {'title': 'Denied'}], workspace='B', deny=True)
        alice.native('create', [{'workspace_id': 2, 'title': 'Denied', 'body': ''}], deny=True)
        passed('positive editor A/viewer B, independent editor B CRUD and cross-owner denials', ['ID-01', 'ID-09'])

        for context in [{'uid': 1, 'su': True, 'allowed_company_ids': [1], 'force_company': 1, 'db': clone['source_database']}, {'mp_workspace_id': 2}, {'_mp_scope': {'role': 'administrator'}}, {'_mp_call_frame': {'principal_id': 'administrator'}}]:
            alice.native('write', [[objects['B']['id']], {'title': 'Denied'}], {'context': context}, workspace='B', deny=True)
        for workspace in [None, str(uuid4()), fixture['workspaces']['A']['public_id'].upper()]:
            alice.native('search_read', [[]], {'fields': ['title']}, workspace=workspace, deny=True)
        alice.call('create', {'title': 'Denied', 'body': '', 'workspace_id': 2}, expect=400, code='VALIDATION_FAILED')
        passed('forged actor/database/company/private-context/workspace cannot grant access', ['ID-02'])

        worker = Client(state, fixture, 'worker')
        worker.call('list', {'limit': 10}, expect=403, code='FORBIDDEN')
        worker.native('search_read', [[]], {'fields': ['title']}, deny=True)
        status, denied = worker.request('/api/v1/workspace/members', workspace='A')
        assert status == 403 and denied['error']['code'] == 'FORBIDDEN'
        status, denied = operator.request('/api/v1/workspace/members', {'operation': 'add', 'principal_id': fixture['users']['worker']['principal_id'], 'role': 'administrator'}, 'A', {'X-CSRFToken': operator.csrf})
        assert status == 400 and denied['error']['code'] == 'VALIDATION_FAILED'
        passed('service session has no credential-derived data or administrator authority', ['ID-04'])

        alice.call('sudo', {}, expect=404, code='NOT_FOUND')
        alice.call('create', {'title': 'Bad', 'body': '', 'actor_id': 'administrator'}, expect=400, code='VALIDATION_FAILED')
        denied = alice.native('read', [[objects['B']['id']], ['title']], deny=True)
        assert set(denied['error']['data']) == {'name', 'message', 'request_id'}
        passed('declared dispatch/strict schemas and redacted native/public errors', ['API-01', 'API-04'])

        key = 'ingress-' + nonce; values = {'title': prefix+'concurrent', 'body': 'One effect'}
        clients = [Client(state, fixture) for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda client: client.call('create', values, key=key), clients))
        assert all(item == results[0] for item in results)
        assert alice.native('search_count', [[('title', '=', values['title'])]]) == 1
        assert alice.call('create', values, key=key) == results[0]
        alice.call('create', {**values, 'body': 'Different'}, key=key, expect=409, code='CONFLICT')
        note = results[0]
        passed('eight concurrent same-key writes commit one record; replay exact, changed input conflicts', ['API-02'], note_id=note['id'], clients=8)

        v1 = alice.call('get', {'note_id': note['id']})
        v2 = call(alice, 'canvas', 'documents', 'get', {'document_id': note['id']})
        assert v2['document_id'] == v1['id'] and v2['content'] == {'headline': v1['title'], 'text': v1['body']} and 'id' not in v2
        call(alice, 'canvas', 'documents', 'get', {'note_id': note['id']}, expect=400, code='VALIDATION_FAILED')
        call(alice, 'canvas', 'documents', 'get', {'document_id': note['id']}, version='1.0', expect=400, code='VALIDATION_FAILED')
        call(alice, 'canvas', 'documents', 'update', {}, expect=404, code='NOT_FOUND')
        for invalid in ['', str(uuid4())]:
            call(alice, 'canvas', 'documents', 'get', {'document_id': note['id']}, headers={'X-MP-Binding': invalid}, expect=503, code='DEPENDENCY_UNAVAILABLE')
        passed('explicit consumer documents v1/v2 coexist; wrong/missing binding or DTO never selects latest', ['API-06'])

        label_values = {'note_id': note['id'], 'expected_revision': 1, 'labels': ['ingress', 'scoped']}
        labeled = call(alice, 'notes_labels', 'labels', 'set_labels', label_values, key='labels-'+nonce)
        assert labeled['revision'] == 2 and labeled['labels'] == label_values['labels']
        assert call(alice, 'notes_labels', 'labels', 'set_labels', label_values, key='labels-'+nonce) == labeled
        # Exact approved integration grant is a clone-only authority fault fixture.
        grant = next(row for row in business['grants'] if row['workspace_id'] == 1 and row['capability'] == 'org.example.notes:notes.read' and row['installation_id'] != next(i['id'] for i in json.loads(sql('SELECT jsonb_agg(to_jsonb(i)) FROM mp_plugin_installation i;')) if i['plugin_id'] == 'org.example.canvas'))
        sql(f"UPDATE mp_plugin_grant SET state='revoked' WHERE id={grant['id']};")
        try:
            call(alice, 'notes_labels', 'labels', 'set_labels', {'note_id': note['id'], 'expected_revision': 2, 'labels': ['Denied']}, expect=403, code='FORBIDDEN', headers={'X-MP-Consumer': 'org.modularplatform.operator', 'X-MP-Actor': 'root'})
            assert alice.call('get', {'note_id': note['id']}) == labeled
        finally: sql(f"UPDATE mp_plugin_grant SET state='approved' WHERE id={grant['id']};")
        passed('actor-preserving Labels provider chain and live revoked integration grant resist forged attribution', ['API-07'])

        deadline = alice.call('create', {'title': prefix+'deadline', 'body': ''}, expect=504, code='DEADLINE_EXCEEDED', headers={'X-MP-Deadline-Ms': '0'})
        assert deadline['error']['details']['outcome'] == 'not_started'
        assert alice.native('search_count', [[('title', '=', prefix+'deadline')]]) == 0
        passed('zero deadline rejected before dispatch without claiming rollback')

        for table, field, denied_status, denied_code in [('mp_workspace_plugin', 'availability', 403, 'FORBIDDEN'), ('mp_plugin_installation', 'state', 409, 'PLUGIN_SUSPENDED')]:
            where = "plugin_id='org.example.notes'" + (' AND workspace_id=1' if table == 'mp_workspace_plugin' else '')
            original = 'enabled' if field == 'availability' else 'installed'
            sql(f"UPDATE {table} SET {field}='suspended' WHERE {where}; UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=1;")
            try:
                alice.call('get', {'note_id': note['id']}, expect=denied_status, code=denied_code)
                alice.native('read', [[objects['A']['id']], ['title']], deny=True)
            finally: sql(f"UPDATE {table} SET {field}='{original}' WHERE {where}; UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=1;")
        passed('native RPC and gateway enforce feature/global installation suspension with current pin', ['ID-07'])

        # A separately guarded worker gets its own nonroot loopback edge. No
        # schema/migration/setup replay, operator mount, Docker socket or cron.
        record['state'] = 'starting_secondary'; save()
        with socket.socket() as check: check.bind(('127.0.0.1', 18075))
        nginx = 'server {listen 8069; server_name _; location ^~ /web/database {return 403;} location / {proxy_set_header Host $http_host; proxy_pass http://'+secondary+':8069;}}'
        command(['docker', 'run', '--rm', '--network', 'none', '--user', '0:0', '--cap-drop', 'ALL', '--mount', 'type=volume,source='+clone['volume']+',target=/probe', '--entrypoint', '/venv/bin/python', clone['image_id'], '-c', "import pathlib,sys;p=pathlib.Path('/probe/ingress-edge');p.mkdir();(p/'clone.conf').write_text(sys.argv[1]);(p/'clone.conf').chmod(0o444)", nginx])
        command(['docker', 'run', '-d', '--name', secondary, '--read-only', '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--network', target['project']+'_runtime', '--memory', '1g', '--pids-limit', '256', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777', '--mount', 'type=volume,source='+clone['volume']+',target=/run/secrets,volume-subpath=config,readonly', '--mount', 'type=volume,source='+clone['volume']+',target=/var/lib/modular,volume-subpath=data', '-e', 'MP_EXPECTED_DATABASE='+database, '-e', 'MP_EXPECTED_INVENTORY_DIGEST='+clone['inventory_digest'], clone['image_id']])
        edge_image = command(['docker', 'inspect', clone['edge'], '--format', '{{.Image}}']).decode().strip()
        command(['docker', 'create', '--name', edge, '--read-only', '--user', '101:101', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--network', clone['edge_network'], '--publish', '127.0.0.1:18075:8069', '--tmpfs', '/var/cache/nginx:rw,nosuid,nodev,noexec,mode=1777', '--tmpfs', '/var/run:rw,nosuid,nodev,noexec,mode=1777', '--mount', 'type=volume,source='+clone['volume']+',target=/etc/nginx/conf.d,volume-subpath=ingress-edge,readonly', edge_image])
        command(['docker', 'network', 'connect', target['project']+'_runtime', edge]); command(['docker', 'start', edge])
        secondary_state = {**state, 'port': 18075}
        deadline = time.monotonic()+35
        while True:
            try: other = Client(secondary_state, fixture); break
            except (OSError, AssertionError):
                if time.monotonic() >= deadline: raise
                time.sleep(.3)
        primary_worker_id = command(['docker', 'inspect', clone['app'], '--format', '{{.Id}}']).decode().strip()
        secondary_worker_id = command(['docker', 'inspect', secondary, '--format', '{{.Id}}']).decode().strip()
        assert primary_worker_id != secondary_worker_id
        for client in [alice, other]:
            client.native('read', [[objects['A']['id']], ['title']]); client.call('get', {'note_id': objects['A']['public_id']})
        member(operator, 'alice', 'A', 'viewer')
        for client in [alice, other]:
            client.native('write', [[objects['A']['id']], {'title': 'Denied warmed viewer'}], deny=True)
            client.call('create', {'title': prefix+'denied viewer', 'body': ''}, expect=403, code='FORBIDDEN')
        member(operator, 'alice', 'A', remove=True)
        for client in [alice, other, Client(state, fixture), Client(secondary_state, fixture)]:
            client.native('read', [[objects['A']['id']], ['title']], deny=True)
            client.call('get', {'note_id': objects['A']['public_id']}, expect=403, code='FORBIDDEN')
        member(operator, 'alice', 'A', 'editor')
        for client in [alice, other]: client.native('read', [[objects['A']['id']], ['title']])
        passed('committed demotion/revocation affects warmed and new clients on two distinct guarded worker processes', ['ID-05', 'ID-10'], workers=[primary_worker_id, secondary_worker_id], delay='first post-commit request')
        report['result'] = 'passed_backend_subset'
    except Exception as error:
        report.update(result='failed', error_type=type(error).__name__)
        raise
    finally:
        if fixture_changed:
            # Reconcile effects by unique recorded title even if an HTTP result
            # was uncertain. Restore fixture authority preimage, not generations.
            member(Client(state, fixture, 'operator'), 'alice', 'A', 'editor')
            cleanup = Client(state, fixture)
            rows = cleanup.native('search_read', [[('title', '=like', prefix+'%')]], {'fields': ['public_id', 'revision']})
            for row in rows: cleanup.call('delete', {'note_id': row['public_id'], 'expected_revision': row['revision']})
            for row in memberships:
                sql(f"UPDATE mp_membership SET role='{row['role']}',state='{row['state']}',write_uid={row['write_uid']},write_date='{row['write_date']}' WHERE id={row['id']};")
            for row in business['features']:
                sql(f"UPDATE mp_workspace_plugin SET availability='{row['availability']}' WHERE id={row['id']};")
            sql('UPDATE mp_workspace SET policy_generation=policy_generation+1;')
            assert json.loads(sql(BUSINESS_SQL)) == business
            assert json.loads(sql('SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m;')) == memberships
            assert sql('SELECT jsonb_agg(to_jsonb(g) ORDER BY uid,gid) FROM res_groups_users_rel g;').decode().strip() == groups
            assert observer.state(observer.read(), catalog)['state'] == source
            record['state'] = 'fixtures_restored'
            report['original_business_memberships_groups_restored'] = True
            report['source_state_unchanged'] = True
            report['policy_generations_monotonic'] = True
        report['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        save()
    print(json.dumps({'result': report['result'], 'checks': len(report['checks']), 'acceptance_subset': report['acceptance_subset'], 'evidence': output.relative_to(ROOT).as_posix()}))


if __name__ == '__main__': main()
