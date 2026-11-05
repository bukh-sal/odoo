"""Apply only the reviewed developer upgrade and qualify its live backend."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.request import Request

ROOT = Path.cwd()
OUT = Path(__file__).parent
WORK = ROOT / '.local/release-kit-core26-rehearsal'
PRIVATE = ROOT / '.local/g7-core26-developer-install/upgrade'
REFERENCE = WORK / 'private/reference'
TARGET = REFERENCE / 'operator/target.json'
STORE = REFERENCE / 'operator/control'
CATALOG = WORK / 'private/catalog'
TRUST = PRIVATE / 'trust.json'
KIT = ROOT / '.local/releases/r1-0.1.26'
sys.path.insert(0, str(WORK / 'source/release'))
from check_reference import Client, Reference


def load(path):
    return json.loads(path.read_bytes())


def create(path, value):
    with path.open('x', encoding='utf8') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def capture(label, args, timeout=90):
    output = PRIVATE / (label + '.stdout')
    with output.open('xb') as out, (PRIVATE / (label + '.stderr')).open('xb') as err:
        result = subprocess.run(args, stdout=out, stderr=err, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Inspect protected ' + label + ' diagnostics and actual state before continuation')
    return load(output)


def docker_query(label, target):
    tables = ('mp_example_note', 'mp_example_canvas_board', 'mp_job')
    sql = ('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT jsonb_build_object('
           + ','.join(f"'{table}', (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM {table} t)" for table in tables)
           + '); ROLLBACK;')
    return capture(label, ['docker', 'exec', target['project'] + '-db-1', 'psql', '-X', '-qAt',
                           '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', target['sites'][0]['database'], '-c', sql])


def worker(label):
    attestation = load(REFERENCE / 'worker/job-qualified.json')['worker_attestation']
    item, = capture(label, ['docker', 'inspect', attestation['container_id']])
    assert item['State']['Running'] and item['Image'] == attestation['image_digest']
    return {key: item[key] for key in ('Id', 'Image', 'RestartCount', 'Mounts', 'NetworkSettings')} | {
        'started_at': item['State']['StartedAt']
    }


def retired_refused_image():
    refused = load(OUT / 'candidate-omitted-connector.json')
    tag, image = refused['tag'], refused['image_id']
    known = subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'],
                                    text=True, timeout=30).strip()
    assert known == image
    assert not subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'ancestor=' + image], timeout=30).strip()
    assert load(OUT / 'review.json')['candidate_image'] != image
    subprocess.run(['docker', 'image', 'rm', tag], capture_output=True, check=True, timeout=60)
    create(OUT / 'refused-image-retired.json', {'tag': tag, 'image': image, 'containers': 0})


args = argparse.ArgumentParser(description=__doc__)
args.add_argument('action', choices=('apply', 'verify'))
action = args.parse_args().action
receipt = load(OUT / 'review.json')
operation, plan_hash = receipt['operation_id'], receipt['plan_hash']
candidate = load(OUT / 'candidate-build.json')
initial = load(PRIVATE / 'target-before.json')
cli = [sys.executable, '-I', str(WORK / 'source/tools/modular.py'), '--config', str(TRUST)]
validation = ['--deployment-config', str(TARGET), '--catalog', str(CATALOG)]
if action == 'apply':
    assert load(TARGET) == initial
    assert not (PRIVATE / 'approve.stdout').exists() and not (PRIVATE / 'apply.stdout').exists()
    before = docker_query('data-before', initial)
    assert [len(before[table]) for table in ('mp_example_note', 'mp_example_canvas_board', 'mp_job')] == [2, 1, 1]
    assert before['mp_job'][0]['state'] == 'completed'
    create(PRIVATE / 'worker-before.json', worker('worker-before-inspect'))
    retired_refused_image()
    result = capture('approve', cli + ['operations', '--store', str(STORE), 'approve', operation,
                                    '--plan-hash', plan_hash, '--noninteractive', '--ack-trust', *validation])
    assert result['state'] == 'approved'
    result = capture('apply', cli + ['plugin', 'apply', operation, '--store', str(STORE), *validation], timeout=600)
    assert result['state'] == 'completed' and result['traffic_resumed']
    target = load(TARGET)
    assert target['generation'] == initial['generation'] + 1 and target['image_id'] == candidate['image_id']
    create(OUT / 'apply.json', {'result': 'completed', 'operation_id': operation, 'plan_hash': plan_hash,
                               'generation': target['generation'], 'image': target['image_id']})
    print('Reviewed developer upgrade completed')
    raise SystemExit

assert load(OUT / 'apply.json')['result'] == 'completed'
target = load(TARGET)
assert target['image_id'] == candidate['image_id'] and target['generation'] == initial['generation'] + 1
before = load(PRIVATE / 'data-before.stdout')
after = docker_query('data-after', target)
for table in ('mp_example_note', 'mp_example_canvas_board'):
    assert after[table] == before[table]
assert worker('worker-after-inspect') == load(PRIVATE / 'worker-before.json')
before_job, = before['mp_job']
after_job, = after['mp_job']
for field in ('id', 'public_id', 'state', 'attempts', 'result'):
    assert after_job[field] == before_job[field]

reference = Reference(SimpleNamespace(kit=KIT, workdir=WORK))
alice = Client(reference, 'alice')
bob = Client(reference, 'bob')
status, contributions = alice.request('/api/v1/ui/slot?slot_id=org.example.notes%3Aslot%3Adetail_actions&major=1', workspace='A')
assert status == 200 and any(item['label'] == 'Edit labels (developer example)' for item in contributions['data'])
status, viewer = alice.request('/api/v1/ui/slot?slot_id=org.example.notes%3Aslot%3Adetail_actions&major=1', workspace='B')
assert status == 200 and not any(item['label'] == 'Edit labels (developer example)' for item in viewer['data'])
views = alice.native('mp.example.note', 'get_views', kwargs={'views': [(False, 'list'), (False, 'form')], 'options': {}})
assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
note = load(REFERENCE / 'reference-checks.json')['notes']['A']
assert alice.service('org.example.notes', 'documents', 'get', {'note_id': note['id']}) == note
assert bob.service('org.example.notes', 'documents', 'get', {'note_id': note['id']}, 'B', expect=404)['code'] == 'NOT_FOUND'
assert len(alice.service('org.example.canvas', 'boards', 'get', {})['cards']) == 1

# Fetch the installed custom-page asset through the authenticated Odoo host.
status, navigation = alice.request('/api/v1/navigation', workspace='A')
assert status == 200
canvas = next(item for item in navigation['data'] if item['plugin_id'] == 'org.example.canvas')
assert any(page['id'] == 'board' and page['kind'] == 'custom' for page in canvas['pages'])
host = reference.state()['hostname'] + ':' + str(reference.state()['port'])
base = 'http://127.0.0.1:' + str(reference.state()['port'])
with alice.http.open(Request(base + '/app/org.example.canvas/', headers={'Host': host}), timeout=30) as response:
    assert response.status == 200
    shell = response.read()
bundle = re.search(rb'/web/assets/[0-9a-f]+/mp_shell\.assets_host(?:\.rtl)?\.min\.js', shell)
assert bundle is not None
path = bundle[0].decode()
assert not urlsplit(path).netloc
with alice.http.open(Request(base + path, headers={'Host': host}), timeout=30) as response:
    assert response.status == 200
    script = response.read()
assert b'Developer reference page' in script
create(OUT / 'backend-verification.json', {
    'result': 'passed_installed_developer_examples_backend', 'operation_id': operation,
    'app_image': target['image_id'], 'app_generation': target['generation'],
    'native_list_form_descriptors': True, 'developer_labels_contribution_visible_to_editor_only': True,
    'canvas_registered_custom_page_and_changed_asset_served': True, 'canvas_asset_sha256': hashlib.sha256(script).hexdigest(),
    'foreign_record_denied': True, 'notes_and_board_rows_exact': True, 'completed_job_outcome_preserved': True,
    'independent_worker_unchanged': True, 'browser_rendering_deferred': True,
})
print('Installed developer examples passed backend verification')
