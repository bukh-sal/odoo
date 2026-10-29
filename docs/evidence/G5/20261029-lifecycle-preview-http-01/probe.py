"""Bounded actual HTTP preview qualification; no request/approval/native apply."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local/g5-lifecycle'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tools'))
from modular_platform.catalog import Catalog
from modular_platform.contracts import validate
from modular_platform.deployment import DockerObserver
from modular_platform.plans import check_bundle, data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql
import r1_probe


def main():
    assert set(p.name for p in OUTPUT.iterdir()) == {'probe.py'}
    config_path = LOCAL / 'operator/target.json'
    state = json.loads((LOCAL / 'state.json').read_text(encoding='utf8'))
    fixture = json.loads((LOCAL / 'fixtures.json').read_text(encoding='utf8'))
    config = json.loads(config_path.read_text(encoding='utf8'))
    assert state['phase'] == 'lifecycle_core_ready' and config['generation'] == 4
    assert config['project'] == state['project'] == 'mp-r0-r1lifef99acae9d906'
    protected = [ROOT / '.local/operator/targets/g5.json', ROOT / '.local/g5-manager-upgrade/operator/target.json', config_path]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    reader = DockerObserver(config)
    catalog = Catalog(ROOT / '.local/operator/catalog', configuration(ROOT / '.local/operator/trust.json'), readonly=True).snapshot()
    before = reader.state(reader.read(), catalog)['state']
    business = json.loads(sql(reader, BUSINESS_SQL)); schema = json.loads(sql(reader, SCHEMA))
    count_before = int(sql(reader, 'SELECT count(*) FROM mp_operation_request;'))
    r1_probe.r1.r0.LOCAL = LOCAL
    operator = r1_probe.Client(state, fixture, 'operator')
    checks = []
    def write(name, value):
        with (OUTPUT / name).open('x', encoding='utf8') as f: f.write(json.dumps(value, indent=2) + '\n')
    def nomination(plugin, cascade=False, workspaces=None):
        return dict(schema_version=1, operation='prepare', operation_type='uninstall', site_id=state['site_id'],
                    plugin_id='org.example.' + plugin, workspace_ids=workspaces or [], cascade=cascade)
    for name, body in [('partial-site', nomination('notes_labels', workspaces=[fixture['workspaces']['A']['public_id']])),
                       ('missing-cascade', nomination('notes'))]:
        code, value = operator.request('/api/v1/operations/prepare', body, headers={'X-CSRFToken': operator.csrf})
        write(name + '.json', dict(status=code, response=value))
        assert code == 400 and value['error']['code'] == 'VALIDATION_FAILED', (name, code, value)
        checks.append(name + ' rejected before creation')
    for plugin, expected in [('notes', {'org.example.notes', 'org.example.canvas', 'org.example.notes_labels'}),
                             ('notes_labels', {'org.example.notes_labels'})]:
        code, prepared = operator.request('/api/v1/operations/prepare', nomination(plugin, True), headers={'X-CSRFToken': operator.csrf})
        write(plugin + '-prepare.json', dict(status=code, response=prepared))
        assert code == 200, (plugin, code, prepared)
        prepared = prepared['data']; validate('operations-view', prepared)
        op = prepared['operation_id']
        code, result = operator.request('/api/v1/operations/bundle/' + op)
        assert code == 200; bundle = result['data']; check_bundle(bundle, before)
        write(plugin + '-bundle.json', bundle)
        assert {t['plugin_id'] for t in bundle['operation_lock']['targets']} == expected
        assert len(bundle['operation_lock']['targets']) == len(expected) * 2
        assert bundle['plan']['destructive'] and bundle['plan']['backup']['required']
        path = '/api/v1/operations/impact/' + op
        with operator.http.open(Request(operator.base + path, headers={'X-MP-Client-Release': operator.release_token}), timeout=30) as response:
            assert response.code == 200 and 'no-store' in response.headers['Cache-Control']
            impact = json.load(response)['data']
            write(plugin + '-impact.json', impact)
        validate('lifecycle-impact', impact)
        assert impact['operation_id'] == op and impact['plan_hash'] == bundle['plan_hash']
        assert impact['impact'] == bundle['operation_lock']['native_uninstall_impact']
        assert impact['completeness'] == 'known_effects_only' and impact['artifact_action'] == 'retain_in_runtime'
        if plugin == 'notes_labels':
            fields = impact['impact']['fields']
            assert any(f['field'] == 'x_notes_labels' and f['non_null_records'] == 2 for f in fields)
        for actor in ['alice', 'bob', 'worker']:
            other = r1_probe.Client(state, fixture, actor)
            code, denied = other.request(path)
            assert code == 403, (actor, code, denied)
        assert operator.request('/api/v1/operations/impact/' + str(uuid4()))[0] == 404
        assert operator.request(path)[1]['data'] == impact
        checks.append(plugin + ': exact closure/all scopes/hash/no-store/known effects/actor denial/immutable preview')
    assert int(sql(reader, 'SELECT count(*) FROM mp_operation_request;')) == count_before + 2
    assert int(sql(reader, "SELECT count(*) FROM mp_operation_request WHERE requested AND public_id IN ('" +
                          "','".join(json.loads((OUTPUT / (p + '-bundle.json')).read_text())['plan']['operation_id'] for p in ['notes','notes_labels']) + "');")) == 0
    assert before == reader.state(reader.read(), catalog)['state']
    assert business == json.loads(sql(reader, BUSINESS_SQL)) and schema == json.loads(sql(reader, SCHEMA))
    assert hashes == {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    write('qualification.json', dict(result='passed_http_preview_only', utc=datetime.now(timezone.utc).isoformat(),
          generation=4, image_id=config['image_id'], base_digest=data_digest(before), checks=checks,
          prepared_only=2, requests_approvals_mutations=0, business_schema_state_protected_configs_exact=True,
          limits=['Browser behavior and actual native uninstall/reinstall remain unqualified; no LIFE acceptance credit.']))
    print(json.dumps(dict(result='passed_http_preview_only', checks=len(checks), prepared_only=2)))


if __name__ == '__main__': main()
