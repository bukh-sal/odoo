"""Once-only browser-requested Labels uninstall on the existing lifecycle site."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local/g5-lifecycle'
sys.path.insert(0, str(ROOT / 'packages/platform_sdk')); sys.path.insert(0, str(ROOT / 'tools'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import check_bundle, data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql
from qualify_manager_upgrade_operation import files
import r1_probe

OPERATION = 'b0797723-6b4d-4022-bcfb-8b286c09b7ef'
HASH = 'sha256:87f2a190779162ef72106d40513a754a724dd9a76722894b037841078be54789'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'apply'])
    parser.add_argument('--resume-before-import', action='store_true'); args = parser.parse_args()
    target = LOCAL / 'operator/target.json'; marker = LOCAL / 'native-uninstall-labels.json'
    state = json.loads((LOCAL / 'state.json').read_text(encoding='utf8'))
    config = json.loads(target.read_text(encoding='utf8')); fixture = json.loads((LOCAL / 'fixtures.json').read_text(encoding='utf8'))
    assert state['disposable'] and state['phase'] == 'lifecycle_core_ready'
    assert state['project'] == config['project'] == 'mp-r0-r1lifef99acae9d906' and config['generation'] == 4
    assert config['sites'][0]['database'] == state['active_db'] == 'mp_disposable_r0_r1_g5_life_f99acae9d906'
    protected = [ROOT / '.local/operator/targets/g5.json', ROOT / '.local/g5-manager-upgrade/operator/target.json']
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    def guard(): assert hashes == {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    validator = configuration(ROOT / '.local/operator/trust.json'); catalog_root = ROOT / '.local/operator/catalog'
    catalog = Catalog(catalog_root, validator, readonly=True).snapshot(); reader = DockerObserver(config)
    before = reader.state(reader.read(), catalog)['state']; business = json.loads(sql(reader, BUSINESS_SQL)); schema = json.loads(sql(reader, SCHEMA))
    assert len(business['notes']) == 4 and len(business['boards']) == 2 and len(before['installations']) == 6
    r1_probe.r1.r0.LOCAL = LOCAL; operator = r1_probe.Client(state, fixture, 'operator')
    code, response = operator.request('/api/v1/operations/bundle/' + OPERATION); assert code == 200
    bundle = response['data']; check_bundle(bundle, before); assert bundle['plan_hash'] == HASH
    assert bundle['plan']['operation_type'] == 'uninstall' and bundle['plan']['destructive'] and bundle['plan']['backup']['required']
    assert len(bundle['operation_lock']['targets']) == 2 and len(bundle['operation_lock']['bindings']) == 6
    assert {t['plugin_id'] for t in bundle['operation_lock']['targets']} == {'org.example.notes_labels'}
    assert len(bundle['plan']['permission_changes']) == 2 and all(c['action'] == 'revoke' for c in bundle['plan']['permission_changes'])
    control = LOCAL / 'operator/control'; store = OperatorStore(control); executor = NativeExecutor(store, target, catalog_root, validator)
    prefix = [sys.executable, 'tools/modular.py', '--config', str(ROOT / '.local/operator/trust.json')]
    ops = prefix + ['operations', '--store', str(control)]
    options = ['--deployment-config', str(target), '--catalog', str(catalog_root)]
    def invoke(command):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=600)
        if result.returncode:
            (LOCAL / ('native-uninstall-cli-' + args.action + '.log')).write_bytes(result.stderr)
            raise RuntimeError('CLI failed; reconcile existing journal/private diagnostics before another action; no blind replay')
        return json.loads(result.stdout)
    def write(name, value):
        with (OUTPUT / name).open('x', encoding='utf8') as f: f.write(json.dumps(value, indent=2) + '\n')
    if args.action == 'prepare':
        if args.resume_before_import:
            import sqlite3
            record = json.loads(marker.read_text(encoding='utf8'))
            assert record['state'] == 'importing' and record['base_digest'] == data_digest(before)
            with sqlite3.connect(control / 'control.sqlite3') as database:
                assert database.execute('SELECT count(*) FROM operations WHERE operation_id=?', [OPERATION]).fetchone()[0] == 0
            assert bundle == json.loads((OUTPUT / 'bundle.json').read_text(encoding='utf8'))
            assert business == json.loads((OUTPUT / 'business-before.json').read_text(encoding='utf8'))
            assert schema == json.loads((OUTPUT / 'schema-before.json').read_text(encoding='utf8'))
            write('preparation-correction.json', dict(previous_failure='Fixture expected phase=requested, but public phase remains prepared and history records requested.',
                  reconciliation='Exact operation not registered; saved base/business/schema unchanged. Resume only before import, no preparation/request replay.'))
        else:
            assert not marker.exists()
            record = dict(state='importing', operation_id=OPERATION, plan_hash=HASH, base_digest=data_digest(before), protected_config_hashes=hashes)
            marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
            write('bundle.json', bundle); write('state-before.json', before); write('business-before.json', business)
            write('schema-before.json', schema); write('files-before.json', files(reader)); write('configuration-before.json', config)
            (LOCAL / 'uninstall-old-client-pin.json').write_text(json.dumps({'token':operator.release_token}), encoding='utf8')
        code, requested = operator.request('/api/v1/operations/status/' + OPERATION)
        assert code == 200 and requested['data']['state'] == 'awaiting_operator_approval' and requested['data']['phase'] == 'prepared'
        assert any(e['code'] == 'requested' for e in requested['data']['history'])
        write('requested-status.json', requested['data'])
        write('registered.json', invoke(ops + ['import-request', OPERATION] + options))
        write('independent-review.json', store.review(OPERATION, executor._validate()))
        # The web checkbox never substitutes for OS approval. A missing destructive
        # acknowledgment must be rejected independently before reservation/drain.
        try:
            store.approve(OPERATION, exact_hash=HASH, acknowledgments=dict(destructive=False, trust_expansion=True, permission_expansion=True),
                          revalidate=executor._validate(), noninteractive=True)
        except Exception as error:
            assert 'Destructive operation requires explicit acknowledgment' in str(error), type(error).__name__
            write('missing-destructive-ack.json', dict(result='denied', reason=str(error)))
        else: raise AssertionError('Missing destructive acknowledgment accepted')
        assert store.status(OPERATION)['state'] == 'awaiting_operator_approval'
        assert before == reader.state(reader.read(), catalog)['state']; guard()
        record['state'] = 'independently_reviewed_not_approved'; marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
        print(json.dumps(record)); return
    record = json.loads(marker.read_text(encoding='utf8')); assert record['state'] == 'independently_reviewed_not_approved'
    assert record['base_digest'] == data_digest(before) and record['protected_config_hashes'] == hashes
    assert business == json.loads((OUTPUT / 'business-before.json').read_text(encoding='utf8'))
    assert schema == json.loads((OUTPUT / 'schema-before.json').read_text(encoding='utf8'))
    def phase(value):
        record.update(state=value, utc=datetime.now(timezone.utc).isoformat()); marker.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    phase('approving'); write('approved.json', invoke(ops + ['approve', OPERATION, '--plan-hash', HASH, '--noninteractive', '--ack-trust', '--ack-destructive'] + options))
    phase('applying'); status = executor.apply(OPERATION); write('completed.json', status)
    assert status['state'] == 'completed' and status['traffic_resumed']; phase('completed_needs_verification')
    current = json.loads(target.read_text(encoding='utf8')); assert current['generation'] == 5 and current['image_id'] == config['image_id']
    assert current['worker_id'] != config['worker_id']
    after_reader = DockerObserver(current); after = after_reader.state(after_reader.read(), catalog)['state']
    actual = json.loads(sql(after_reader, BUSINESS_SQL)); actual_schema = json.loads(sql(after_reader, SCHEMA))
    assert actual['notes'] == [{k:v for k,v in n.items() if k != 'x_notes_labels'} for n in business['notes']]
    assert actual['boards'] == business['boards']
    assert all(c[1] != 'x_notes_labels' for c in actual_schema['columns'])
    assert len(after['installations']) == 6 and len(after['bindings']) == 6 and after['bindings'] == bundle['operation_lock']['bindings']
    labels = [i for i in after['installations'] if i['plugin_id'] == 'org.example.notes_labels']
    assert len(labels) == 2 and all(i['state'] == 'not_installed' and i['metadata_state'] == 'removed' and i['feature_state'] == 'suspended' for i in labels)
    assert [i for i in after['installations'] if i['plugin_id'] != 'org.example.notes_labels'] == [i for i in before['installations'] if i['plugin_id'] != 'org.example.notes_labels']
    labels_internal_id = int(sql(after_reader, "SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.notes_labels';"))
    removed_grants = [g for g in actual['grants'] if g['installation_id'] == labels_internal_id]
    assert len(removed_grants) == 2 and all(g['state'] == 'revoked' for g in removed_grants)
    assert [g for g in actual['grants'] if g['installation_id'] != labels_internal_id] == [g for g in business['grants'] if g['installation_id'] != labels_internal_id]
    old_files = json.loads((OUTPUT / 'files-before.json').read_text(encoding='utf8')); now_files = files(after_reader)
    assert all(now_files[name] == digest for name,digest in old_files.items())
    release_dir = control / 'stages' / OPERATION
    effects = json.loads((release_dir / 'native-effects.json').read_text(encoding='utf8'))
    assert effects['surviving_native_versions_unchanged'] and effects['source_artifacts_retained']
    assert effects['before']['mp_example_note']['records'] == effects['after']['mp_example_note']['records'] == 4
    checkpoint = json.loads((control / 'checkpoints' / OPERATION / 'manifest.json').read_text(encoding='utf8'))
    for name,digest in checkpoint['files'].items():
        assert hashlib.sha256((control / 'checkpoints' / OPERATION / name).read_bytes()).hexdigest() == digest
    write('native-effects.json', effects); write('checkpoint-manifest.json', checkpoint)
    write('state-after.json', after); write('business-after.json', actual); write('schema-after.json', actual_schema); write('files-after.json', now_files)
    new_client = r1_probe.Client(state, fixture, 'operator')
    old_pin = json.loads((LOCAL / 'uninstall-old-client-pin.json').read_text(encoding='utf8'))['token']
    code, stale = new_client.request('/api/v1/navigation', workspace='A', headers={'X-MP-Client-Release':old_pin})
    assert code == 409 and stale['error']['code'] == 'CONFLICT'; write('old-client-rejected.json', stale)
    assert new_client.request('/api/v1/navigation', workspace='A')[0] == 200
    write('completed-mirror.json', invoke(ops + ['mirror-status', OPERATION] + options))
    guard(); state.update(phase='labels_uninstalled', generation=5, image_id=current['image_id'], worker_id=current['worker_id'])
    (LOCAL / 'state.json').write_text(json.dumps(state, indent=2) + '\n', encoding='utf8'); phase('completed_verified')
    write('qualification.json', dict(result='passed_native_labels_uninstall', operation_id=OPERATION, plan_hash=HASH,
          generation=5, image_id=current['image_id'], native_column_deleted_nonnull_records=2,
          notes_boards_retained=[4,2], survivor_native_versions_unchanged=True, tombstone_scopes=2,
          old_files_preserved=len(old_files), checkpoint_files_hash_verified=True, old_client_rejected=True,
          protected_config_hashes=hashes, limits=['Browser survivor regression, reinstall, artifact removal and permission-expansion upgrade remain pending.']))
    print(json.dumps(dict(result='passed_native_labels_uninstall', generation=5, operation_id=OPERATION)))


if __name__ == '__main__': main()
