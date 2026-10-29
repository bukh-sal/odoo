"""Read-only preservation/authority checks before opening this disposable restore."""
import argparse
import copy
import hashlib
import json
from clean_recovery_fixture import LOCAL, OUTPUT, load, save, guard
from clean_recovery_data import context
from lifecycle_data_probe import BUSINESS_SQL, SCHEMA, sql
from qualify_release_reader_rollout import files
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.deployment import DockerObserver, _run
from modular import configuration


def closed():
    state, target, reader, observed, fixture = context()
    assert state['phase'] == 'restored_verified_traffic_closed'
    record = load(LOCAL/'fault-operation.json')
    operation = record['operation_id']
    store = OperatorStore(LOCAL/'operator/control')
    recovery = RestoreExecutor(NativeExecutor(store, LOCAL/'operator/target.json', LOCAL/'operator/catalog', configuration(LOCAL/'operator/trust.json')))
    source = record['configuration']['sites'][0]['database']
    current_auth, private = recovery._authority(source)
    restored_auth, restored_private = recovery._authority(state['active_db'])
    assert current_auth == restored_auth and private == restored_private
    assert current_auth == load(OUTPUT/'current-authority-for-restore.json')
    probe = load(OUTPUT/'post-checkpoint-native-auth.json')
    user = next(u for u in restored_private['users'] if u['id'] == probe['probe_user_id'])
    assert user['totp_secret'] and user['totp_last_counter'] == 20
    assert [k['id'] for k in restored_private['passkeys']] == [probe['current_passkey_id']]
    assert restored_private['passkeys'][0]['sign_count'] == 17
    counts = json.loads(sql(reader, "SELECT jsonb_build_array((SELECT count(*) FROM auth_totp_device),(SELECT count(*) FROM mp_service_credential WHERE state='active'),(SELECT count(*) FROM mp_example_note),(SELECT count(*) FROM mp_example_canvas_board));"))
    assert counts == [0, 0, 4, 2]
    assert json.loads(sql(reader, BUSINESS_SQL)) == load(OUTPUT/'business-before-fault.json')
    assert json.loads(sql(reader, SCHEMA)) == load(OUTPUT/'schema-before-fault.json')
    baseline_files = load(OUTPUT/'files-before-fault.json')
    current_files = files(reader)
    assert all(current_files.get(name) == digest for name, digest in baseline_files.items())
    before = load(OUTPUT/'state-before-fault.json')
    assert observed['installations'] == before['installations'] and observed['bindings'] == before['bindings']
    old_lock = before['release_lock']; new_lock = copy.deepcopy(observed['release_lock'])
    assert new_lock.pop('generation') > old_lock['generation']; new_lock.pop('created_at')
    assert new_lock == {k:v for k,v in old_lock.items() if k not in ['generation','created_at']}
    assert target['generation'] == 4 and target['image_id'] == state['image_id'] == record['configuration']['image_id']
    source_reader = DockerObserver(record['configuration'])
    old_secret = sql(source_reader, "SELECT value FROM ir_config_parameter WHERE key='database.secret';")
    new_secret = sql(reader, "SELECT value FROM ir_config_parameter WHERE key='database.secret';")
    assert old_secret and new_secret and old_secret != new_secret
    edge = reader._container('edge', stopped=True)
    assert not recovery.native._inspect(edge)['State']['Running']
    old_worker = recovery.native._inspect(record['configuration']['worker_id'])
    assert not old_worker['State']['Running']
    assert not old_worker['NetworkSettings']['Networks']
    status = store.status(operation)
    assert status['state'] == 'revoked' and status['phase'] == 'restore_verified' and not status['traffic_resumed']
    guard(state)
    save('closed-preservation.json', dict(result='passed', database=state['active_db'], failed_database=source, source_retained=True, generation=4, previous_executable_release_exact=True, business_schema_installations_bindings_grants_exact=True, old_filestore_members=len(baseline_files), retained_old_file_hashes_exact=True, total_files=len(current_files), native_auth_current_digest=current_auth['native_auth_digest'], native_auth_material_emitted=False, passwords_TOTP_counters_groups_passkeys_current=True, remembered_devices=0, active_technical_credentials=0, session_secret_rotated=True, original_operation_retired=True, old_worker_stopped_disconnected=True, public_traffic_closed=True))
    print(json.dumps(dict(result='passed_closed_preservation', files=len(baseline_files))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['closed']); args = parser.parse_args()
    closed()
