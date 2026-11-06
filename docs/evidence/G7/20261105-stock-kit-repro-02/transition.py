"""Exercise a reviewed stock release update and fresh restore on the first kit site."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / part) for part in ('tools', 'packages/platform_sdk', 'release')]
from check_reference import Client
from initialize_reference import load, write
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore, prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor
from qualify_release_reader_rollout import files


OWNED = ROOT / '.local/stock-webclient-release'
BASE = 'sha256:07b16747d12c1ecbea2dd3eabf52d83fb256109e03b747622f15b4d817357e44'
SUCCESSOR = 'sha256:b9e0048bb366314fc0249fa398e7bc79d644c4d916cfa49be5b858c9e6c4b6d1'


def payload(native):
    tables = ('mp_example_note', 'mp_example_canvas_board', 'mp_membership')
    parts = [f"'{name}', (SELECT jsonb_agg(to_jsonb(r) ORDER BY r.id) FROM {name} r)" for name in tables]
    sql = 'SELECT jsonb_build_object(' + ','.join(parts) + ');'
    database = native.config['sites'][0]['database']
    data = subprocess.check_output(['docker', 'exec', native.observer._container('db'), 'psql',
        '-XqAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', database, '-c', sql], timeout=40)
    return data_digest(json.loads(data))


def worker_id(local):
    project = load(local / 'worker/state.json')['project']
    row = subprocess.check_output(['docker', 'ps', '--no-trunc', '--filter', 'label=com.docker.compose.project=' + project,
        '--filter', 'label=com.docker.compose.service=document-stats', '--format', '{{.ID}} {{.Image}}'], timeout=30).splitlines()
    assert len(row) == 1
    return row[0].decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-image', default=BASE)
    parser.add_argument('--successor', default=SUCCESSOR)
    parser.add_argument('--work', choices=['clean', 'clean-rtl', 'clean-final'], default='clean')
    parser.add_argument('--receipt', default='stock-release-transition.json',
        choices=['stock-release-transition.json', 'stock-rtl-transition.json',
                 'stock-final-transition.json', 'stock-bounded-transition.json', 'stock-qualified-transition.json'])
    parser.add_argument('--addon', action='append')
    args = parser.parse_args()
    local = OWNED / args.work / 'private/reference'
    target_path = local / 'operator/target.json'
    catalog_path = local.parent / 'catalog'
    output = local / args.receipt
    assert not output.exists()
    config = load(target_path)
    project = {'clean': 'mp-r0-r1release3822ff1a8b87', 'clean-rtl': 'mp-r0-r1released1976b2b20dd',
               'clean-final': 'mp-r0-r1releaseda690111ce97'}[args.work]
    assert config['project'] == project and config['image_id'] == args.base_image
    assert load(local / 'worker/integration.json')['phase'] == 'reference_job_qualified'
    store = OperatorStore(local / 'operator/control')
    validator = configuration(local / 'operator/trust.json')
    catalog = Catalog(catalog_path, validator, readonly=True)
    record = {'initial_generation': config['generation'], 'base_image': args.base_image, 'successor_image': args.successor}

    def phase(name, **extra):
        record.update(phase=name, **extra)
        write(output, record)
        print(json.dumps({'phase': name}), flush=True)

    def executor():
        return StagedNativeExecutor(store, target_path, catalog_path, validator)

    native = executor()
    business = payload(native)
    old_files = files(native.observer)
    worker = worker_id(local)
    phase('preparing', business_digest=business, checkpoint_files=len(old_files))

    def verify_scope(instance):
        state = load(local / 'state.json') | {'database': instance.config['sites'][0]['database']}
        client = Client(SimpleNamespace(local=local, state=lambda: state), 'alice')
        for workspace in ('A', 'B'):
            rows = client.native('mp.example.note', 'search_read', [[]], {'fields': ['title']}, workspace)
            assert [row['title'] for row in rows] == [f'Release reference {workspace}']
        return True

    def approve(instance):
        observation = instance.observer.read()
        snapshot = catalog.snapshot()
        before = instance.observer.state(observation, snapshot)
        stage = StageStore(store, instance.config, catalog)
        descriptor = stage.stage(args.successor)
        _, target = stage.load(descriptor)
        native_plugins = {row['plugin_id'] for row in before['state']['release_lock']['plugins'] if row['runtime'] == 'native'}
        targets = [{key: row[key] for key in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')}
            | {'action': 'deploy'} for row in before['state']['installations'] if row['plugin_id'] in native_plugins]
        bundle = prepare_staged_plan(before, observation['sites'], snapshot, target['runtime'], descriptor,
            targets=targets, operation_type='core_upgrade', operation_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), base_runtime=observation['runtime'])
        operation = bundle['plan']['operation_id']
        changes = bundle['operation_lock']['native_core_changes']
        assert {change['addon'] for change in changes} == set(args.addon or ['mp_shell'])
        assert bundle['plan']['backup']['required']
        validate = instance._validate()
        store.register(bundle, validate)
        review = store.review(operation, validate)
        approval = store.approve(operation, exact_hash=bundle['plan_hash'], revalidate=validate, noninteractive=True,
            acknowledgments={'destructive': True, 'trust_expansion': True, 'permission_expansion': False})
        return operation, {'plan_hash': bundle['plan_hash'], 'review_digest': data_digest(review),
            'approval_digest': data_digest(approval), 'changes': changes}

    operation, fault_plan = approve(native)
    phase('fault_approved', fault_operation=operation, fault_plan=fault_plan)
    advance = store.advance

    def inject(selected, locks, step, **details):
        result = advance(selected, locks, step, **details)
        if selected == operation and step == 'release_published':
            raise OperatorError('Stock release rehearsal pre-traffic fault')
        return result

    with patch.object(store, 'advance', side_effect=inject):
        try:
            native.apply(operation)
        except OperatorError as error:
            if 'Stock release rehearsal pre-traffic fault' not in str(error):
                raise
        else:
            raise AssertionError('Expected release fault')
    failed = store.status(operation)
    assert failed['state'] == 'recovery_required' and not failed['traffic_resumed']
    assert worker_id(local) == worker
    phase('fault_verified', failure=failed)
    recovery = RestoreExecutor(executor())
    decision = recovery.prepare(operation)
    restored = recovery.execute(decision, exact_hash=data_digest(decision), noninteractive=True)
    native = executor()
    assert native.config['image_id'] == args.base_image and native.config['sites'][0]['database'] != config['sites'][0]['database']
    restored_files = files(native.observer)
    assert payload(native) == business and all(restored_files.get(k) == v for k, v in old_files.items())
    phase('restore_verified', restore=restored, restore_decision_hash=data_digest(decision))
    recovery = RestoreExecutor(native)
    resume = recovery.prepare_resume(operation)
    recovery.resume(resume, exact_hash=data_digest(resume), noninteractive=True)
    assert worker_id(local) == worker
    phase('restored_traffic_open', resume_decision_hash=data_digest(resume), restored_native_scope=verify_scope(executor()))

    native = executor()
    retry, normal_plan = approve(native)
    phase('normal_approved', normal_operation=retry, normal_plan=normal_plan)
    result = native.apply(retry)
    native = executor()
    assert result['state'] == 'completed' and result['traffic_resumed'] and native.config['image_id'] == args.successor
    assert payload(native) == business and worker_id(local) == worker
    retained = files(native.observer)
    assert all(retained.get(k) == v for k, v in old_files.items())
    phase('passed', generation=native.config['generation'], record_rows_and_memberships_preserved=True,
        original_worker_preserved=True, original_filestore_preserved=True, successor_native_scope=verify_scope(native),
        normal_result=result)


if __name__ == '__main__':
    main()
