"""Minimal lifecycle data and read/deny probes; no Canvas product expansion."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/g5-lifecycle'
OUTPUT = ROOT / 'docs/evidence/G5/20261029-lifecycle-01'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from modular import configuration
from qualify_manager_upgrade_operation import sql
from qualify_client_release_clone import BUSINESS_SQL
import r1_probe

SCHEMA = """SELECT jsonb_build_object(
 'columns',(SELECT jsonb_agg(jsonb_build_array(c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull) ORDER BY c.relname,a.attnum) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid WHERE c.relname IN ('mp_example_note','mp_example_canvas_board') AND a.attnum>0 AND NOT a.attisdropped),
 'constraints',(SELECT jsonb_agg(jsonb_build_array(c.relname,p.conname,pg_get_constraintdef(p.oid),p.convalidated) ORDER BY c.relname,p.conname) FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid WHERE c.relname IN ('mp_example_note','mp_example_canvas_board')),
 'native',(SELECT jsonb_agg(jsonb_build_array(name,state,latest_version) ORDER BY name) FROM ir_module_module WHERE name IN ('mp_example_notes','mp_example_notes_labels','mp_example_canvas')));"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['seed', 'probe'])
    parser.add_argument('--mode', choices=['all-enabled', 'notes-A-suspended', 'labels-A-suspended', 'restored'])
    args = parser.parse_args()
    state = json.loads((LOCAL / 'state.json').read_text(encoding='utf-8'))
    config = json.loads((LOCAL / 'operator/target.json').read_text(encoding='utf-8'))
    fixture = json.loads((LOCAL / 'fixtures.json').read_text(encoding='utf-8'))
    assert state['disposable'] and state['project'] == config['project'] == 'mp-r0-r1lifef99acae9d906' and config['generation'] == 3
    assert hashlib.sha256((ROOT / '.local/operator/targets/g5.json').read_bytes()).hexdigest() == state['main_target_sha256']
    assert json.loads((LOCAL / 'install-labels.json').read_text(encoding='utf-8'))['state'] == 'completed_verified'
    reader = DockerObserver(config)
    catalog = Catalog(ROOT / '.local/operator/catalog', configuration(ROOT / '.local/operator/trust.json'), readonly=True)
    observed = reader.state(reader.read(), catalog.snapshot())['state']
    r1_probe.r1.r0.LOCAL = LOCAL
    alice = r1_probe.Client(state, fixture, 'alice')
    bob = r1_probe.Client(state, fixture, 'bob')
    baseline = LOCAL / 'lifecycle-data.json'
    def save(value):
        baseline.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    def call(client, plugin, alias, method, values, workspace='A', *, key=None, expect=200, code=None):
        installation = next(i['installation_id'] for i in observed['installations'] if i['plugin_id'] == 'org.example.' + plugin and i['workspace_id'] == fixture['workspaces'][workspace]['public_id'])
        binding = next(b for b in observed['bindings'] if b['consumer_installation_id'] == installation and b['workspace_id'] == fixture['workspaces'][workspace]['public_id'] and b['alias'] == alias)
        body = {'api_version': binding['api_version'], 'request_id': str(uuid4()), 'input': values}
        if key:
            body['idempotency_key'] = key
        status, value = client.request('/api/v1/services/' + binding['service_id'] + '/' + method, body, workspace,
            {'X-CSRFToken': client.csrf, 'X-MP-Binding': binding['binding_id']})
        assert status == expect, (plugin, method, status, value)
        if code:
            assert value['error']['code'] == code, (plugin, method, value)
        return value.get('data', value)
    if args.action == 'seed':
        assert not baseline.exists(), 'Existing non-idempotent board step requires explicit reconciliation, never reseed'
        assert all(i['feature_state'] == 'enabled' for i in observed['installations'])
        assert json.loads(sql(reader, 'SELECT jsonb_build_array((SELECT count(*) FROM mp_example_note),(SELECT count(*) FROM mp_example_canvas_board));')) == [0, 0]
        saved = {'state': 'seeding', 'run_id': str(uuid4()), 'database': state['active_db'], 'notes': {}, 'boards': {}}
        save(saved)
        for space, client in [('A', alice), ('B', bob)]:
            saved['notes'][space] = []
            for index in range(2):
                note = client.call('create', {'title': 'Lifecycle ' + space + '/' + str(index), 'body': 'Synthetic lifecycle data; retain identity and revision.'}, workspace=space, key=saved['run_id'] + '-note-' + space + str(index))
                if index == 0:
                    note = call(client, 'notes_labels', 'labels', 'set_labels', {'note_id': note['id'], 'expected_revision': note['revision'], 'labels': ['retained', space.casefold()]}, space, key=saved['run_id'] + '-labels-' + space)
                native = client.native('search_read', [[('public_id', '=', note['id'])]], {'fields': ['id', 'public_id', 'title', 'revision', 'x_notes_labels']}, space)
                assert len(native) == 1
                saved['notes'][space].append({'dto': note, 'native': native[0]})
                save(saved)
            saved['pending_nonretryable_step'] = 'native board create ' + space
            save(saved)
            board_id = client.native('create', [{'name': 'Lifecycle reference ' + space,
                'cards': [{'id': str(uuid4()), 'text': 'Retained reference card', 'lane': 'inbox', 'note_id': saved['notes'][space][0]['dto']['id']}]}], workspace=space, model='mp.example.canvas.board')
            board = client.native('read', [[board_id], ['public_id', 'name', 'revision', 'cards']], workspace=space, model='mp.example.canvas.board')[0]
            saved['boards'][space] = board
            saved.pop('pending_nonretryable_step')
            save(saved)
            assert call(client, 'canvas', 'boards', 'get', {}, space)['id'] == board['public_id']
        saved.update(state='completed', schema=json.loads(sql(reader, SCHEMA)), business=json.loads(sql(reader, BUSINESS_SQL)),
            configuration=config, worker_id=config['worker_id'], image_id=config['image_id'], release_digest=observed['release_digest'])
        save(saved)
        with (OUTPUT / 'data-baseline.json').open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(saved, indent=2) + '\n')
        print(json.dumps({'result': 'seeded_minimal_lifecycle_data', 'notes': 4, 'boards': 2, 'generation': 3}))
        return
    assert args.mode
    saved = json.loads(baseline.read_text(encoding='utf-8'))
    assert saved['state'] == 'completed' and config == saved['configuration']
    assert json.loads(sql(reader, SCHEMA)) == saved['schema']
    business = json.loads(sql(reader, BUSINESS_SQL))
    assert {k: v for k, v in business.items() if k != 'features'} == {k: v for k, v in saved['business'].items() if k != 'features'}
    assert observed['release_digest'] == saved['release_digest']
    checks = []
    def checked(value):
        checks.append(value)
    for space, client in [('A', alice), ('B', bob)]:
        notes_suspended = space == 'A' and args.mode == 'notes-A-suspended'
        labels_suspended = space == 'A' and args.mode in ('notes-A-suspended', 'labels-A-suspended')
        expected_plugins = {'org.example.notes', 'org.example.canvas'} if not notes_suspended else set()
        status, nav = client.request('/api/v1/navigation', workspace=space)
        assert status == 200 and {i['plugin_id'] for i in nav['data']} == expected_plugins
        for plugin in ('notes', 'canvas', 'notes_labels'):
            suspended = notes_suspended or plugin == 'notes_labels' and labels_suspended
            status, value = client.request('/api/v1/context?plugin_id=org.example.' + plugin, workspace=space)
            assert status == (409 if suspended else 200)
            if suspended:
                assert value['error']['code'] == 'PLUGIN_SUSPENDED'
            elif plugin == 'notes_labels':
                assert [c['id'] for c in value['data']['commands']] == ['org.example.notes_labels:command:set_labels']
        status, slots = client.request('/api/v1/ui/slot?slot_id=org.example.notes:slot:detail_actions&major=1', workspace=space)
        if notes_suspended:
            assert status == 409 and slots['error']['code'] == 'PLUGIN_SUSPENDED'
        else:
            assert status == 200 and len(slots['data']) == (0 if labels_suspended else 1)
        checked(space + ' navigation/context/registered commands/slot visibility follows live availability')
        first = saved['notes'][space][0]
        if notes_suspended:
            for _ in range(8):
                client.call('get', {'note_id': first['dto']['id']}, space, expect=403, code='FORBIDDEN')
                client.call('update', {'note_id': first['dto']['id'], 'expected_revision': first['dto']['revision'], 'title': 'MUST_NOT_CHANGE'}, space, expect=403, code='FORBIDDEN')
                client.native('read', [[first['native']['id']], ['title', 'revision']], workspace=space, deny=True)
            client.native('write', [[first['native']['id']], {'title': 'MUST_NOT_CHANGE'}], {'context': {'expected_revision': first['dto']['revision']}}, workspace=space, deny=True)
            call(client, 'canvas', 'boards', 'get', {}, space, expect=403, code='FORBIDDEN')
            board = saved['boards'][space]
            call(client, 'canvas', 'boards', 'save', {'board_id': board['public_id'], 'expected_revision': board['revision'], 'name': 'MUST_NOT_CHANGE', 'cards': board['cards']}, space, key=str(uuid4()), expect=403, code='FORBIDDEN')
            client.native('read', [[board['id']], ['public_id', 'cards']], workspace=space, model='mp.example.canvas.board', deny=True)
            checked(space + ' saved IDs, gateway/native reads and writes, Canvas get/save denied without changing data')
        else:
            visible = client.call('list', {'limit': 25}, space)['items']
            assert len(visible) == 2
            for row in visible:
                assert row['labels'] == ([] if labels_suspended else next(n['dto']['labels'] for n in saved['notes'][space] if n['dto']['id'] == row['id']))
            client.native('read', [[first['native']['id']], ['title', 'revision']], workspace=space)
            assert call(client, 'canvas', 'boards', 'get', {}, space)['id'] == saved['boards'][space]['public_id']
            if not labels_suspended:
                assert client.native('read', [[first['native']['id']], ['x_notes_labels']], workspace=space)[0]['x_notes_labels'] == first['dto']['labels']
            checked(space + ' native/base APIs/Canvas remain available; shared Labels field remains registered when enabled')
        if labels_suspended:
            call(client, 'notes_labels', 'labels', 'set_labels', {'note_id': first['dto']['id'], 'expected_revision': first['dto']['revision'], 'labels': ['MUST_NOT_CHANGE']}, space, key=str(uuid4()),
                expect=403 if notes_suspended else 409, code='FORBIDDEN' if notes_suspended else 'PLUGIN_SUSPENDED')
            client.native('read', [[first['native']['id']], ['x_notes_labels']], workspace=space, deny=True)
            client.native('write', [[first['native']['id']], {'x_notes_labels': ['MUST_NOT_CHANGE']}], {'context': {'expected_revision': first['dto']['revision']}}, workspace=space, deny=True)
            checked(space + ' cached command/service binding and explicit native extension field access denied')
    assert json.loads(sql(reader, SCHEMA)) == saved['schema']
    assert json.loads(sql(reader, BUSINESS_SQL)) == business
    report = {'result': 'passed_' + args.mode, 'utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'configuration_worker_image_release_unchanged': True, 'native_modules_schema_constraints_and_all_business_data_retained': True,
        'business_digest': data_digest(business), 'schema_digest': data_digest(saved['schema']),
        'main_target_unchanged': True, 'limits': ['Browser direct-page/terminology proof recorded separately.', 'Current G5 has no job/outbox tables; the executor rejects those tables until G6 drain/reconciliation support. Requalify LIFE-01 when G6 adds dispatch.']}
    with (OUTPUT / ('probe-' + args.mode + '.json')).open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'result': report['result'], 'checks': len(checks), 'data_preserved': True}))


if __name__ == '__main__':
    main()
