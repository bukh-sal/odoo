"""Run independently approved lifecycle transitions on the two stress sites."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import patch
from uuid import uuid4

from stress_sites import ADDONS, ROOT, StressSite, load, write
from initialize_reference import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_planning import installation_id
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore, prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor
from qualify_release_reader_rollout import files


NOTES = 'org.example.notes'
BUSINESS_TABLES = {
    'aurora': ['mp_aurora_task', 'mp_aurora_task_list', 'mp_aurora_task_stage',
               'mp_aurora_task_list_res_users_rel'],
    'maintenance': ['maintenance_equipment', 'maintenance_request', 'maintenance_stage'],
}


def snapshot(target, site, *, notes, policy_advanced=False):
    reader = DockerObserver(target)
    tables = BUSINESS_TABLES[site] + ['mp_workspace', 'mp_membership', 'res_groups_users_rel']
    if notes:
        tables += ['mp_example_note']
    pairs = []
    for table in tables:
        row = 'to_jsonb(r)'
        if table == 'mp_workspace' and policy_advanced:
            row += " || jsonb_build_object('policy_generation', r.policy_generation - 1)"
        pairs.append(f"'{table}', (SELECT jsonb_agg({row} ORDER BY to_jsonb(r)) FROM {table} r)")
    sql = 'SELECT jsonb_build_object(' + ', '.join(pairs) + ');'
    rows = subprocess.check_output(['docker', 'exec', reader._container('db'), 'psql', '-XqAt', '-U',
        'postgres', '-v', 'ON_ERROR_STOP=1', '-d', target['sites'][0]['database'], '-c', sql], timeout=30)
    return data_digest(json.loads(rows))


def checkpoint_files(control, operation, database):
    root = 'filestore/' + database + '/'
    with tarfile.open(control / 'checkpoints' / operation / 'filestore.tar.gz', 'r:gz') as archive:
        return {member.name.removeprefix(root): hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest()
                for member in archive if member.isfile() and member.name.startswith(root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['install', 'verify-install', 'upgrade', 'fault-recover', 'resume-restored'])
    parser.add_argument('site', choices=ADDONS)
    parser.add_argument('--candidate', required=True, type=Path)
    args = parser.parse_args()
    if args.phase in ('fault-recover', 'resume-restored') and args.site != 'aurora':
        raise ValueError('Only the nominated Aurora test deployment may receive a fault')

    site = StressSite(args)
    local = site.local
    private = local / 'operator'
    target_path = private / 'target.json'
    target = load(target_path)
    assert target['project'] == site.state()['project']
    candidate = load(args.candidate)
    image = candidate['image_id']
    if args.phase == 'resume-restored':
        receipt = local / 'fault-recover.json'
        state = load(receipt)
        assert state['phase'] == 'recovery_required' and state['candidate'] == image
        control = private / 'control'
        operation = state['operation_id']
        previous = load(control / 'stages' / operation / 'configuration.json')
        result = load(control / 'recoveries' / operation / 'result.json')
        review = load(control / 'recoveries' / operation / 'decision.json')['decision']
        assert result['configuration'] == target and result['keep_traffic_closed']
        assert target['image_id'] == previous['image_id'] and target['sites'][0]['database'] != previous['sites'][0]['database']
        assert snapshot(target, args.site, notes=True, policy_advanced=True) == state['business_before']
        restored_files = files(DockerObserver(target))
        assert restored_files == checkpoint_files(control, operation, previous['sites'][0]['database'])
        peer_local = local.parent / 'maintenance'
        peer = load(peer_local / 'operator/target.json')
        peer_before = load(peer_local / 'upgrade.json')
        assert peer_before['generation'] == peer['generation'] and peer['image_id'] == image
        assert load(peer_local / 'http-peer-during-recovery.json')['image'] == image
        assert snapshot(peer, 'maintenance', notes=True) == peer_before['business_before']
        store = OperatorStore(control)
        validator = configuration(private / 'trust.json')
        recovery = RestoreExecutor(StagedNativeExecutor(store, target_path, private / 'catalog', validator))
        decision = recovery.prepare_resume(operation)
        resume_digest = data_digest(decision)
        recovery.resume(decision, exact_hash=resume_digest, noninteractive=True)
        assert store.status(operation)['state'] == 'revoked'
        assert load(peer_local / 'operator/target.json') == peer
        state.update(phase='verified', generation=target['generation'], result_image=target['image_id'],
                     fresh_database=True, app_and_authority_rows_preserved=True, restored_policy_advanced_once=True,
                     retained_files_preserved=True, restored_files=len(restored_files), peer_image=image,
                     peer_worker_unchanged=True, restore_digest=data_digest(review), resume_digest=resume_digest)
        write(receipt, state)
        print(json.dumps({'site': args.site, 'phase': 'restored_and_resumed'}))
        return
    if args.phase == 'verify-install':
        record = load(local / 'install.json')
        assert record['phase'] == 'applied' and target['image_id'] == record['candidate'] == image
        store = OperatorStore(private / 'control')
        assert store.status(record['operation_id'])['state'] == 'completed'
        assert snapshot(target, args.site, notes=False, policy_advanced=True) == record['business_before']
        validator = configuration(private / 'trust.json')
        catalog = Catalog(private / 'catalog', validator, readonly=True)
        observer = DockerObserver(target)
        before = observer.state(observer.read(), catalog.snapshot())['state']
        assert len(before['installations']) == 2
        assert all(row['plugin_id'] == NOTES and row['feature_state'] == 'enabled' for row in before['installations'])
        write(local / 'verify-install.json', {'operation_id': record['operation_id'], 'generation': target['generation'],
            'image': image, 'business_preserved': True, 'activation_advanced_each_workspace_policy_once': True})
        print(json.dumps({'site': args.site, 'phase': 'install_verified'}))
        return
    receipt = local / (args.phase + '.json')
    if receipt.exists():
        raise ValueError('Inspect the recorded lifecycle attempt before further mutation')
    install = args.phase == 'install'
    state = {'phase': 'preparing', 'site': args.site, 'candidate': image, 'base_image': target['image_id']}

    def phase(name, **details):
        state.update(phase=name, **details)
        write(receipt, state)
        print(json.dumps({'site': args.site, 'phase': name}), flush=True)

    phase('preparing')
    trust_path = private / 'trust.json'
    catalog_path = private / 'catalog'
    digest = candidate['artifacts'][NOTES]['digest']
    if install:
        trust = load(trust_path)
        assert trust['approved_digests'] == []
        trust['approved_digests'] = [digest]
        trust['generation'] += 1
        write(trust_path, trust)
        archive = ROOT / '.local/release-kit-rehearsal/private/catalog/blobs' / (digest[7:] + '.mplug')
        Catalog(catalog_path, configuration(trust_path)).add(archive, expected_digest=digest)
    validator = configuration(trust_path)
    catalog = Catalog(catalog_path, validator, readonly=True)
    store = OperatorStore(private / 'control')
    observer = DockerObserver(target)
    observed = observer.read()
    before = observer.state(observed, catalog.snapshot())
    business_before = snapshot(target, args.site, notes=not install)
    files_before = files(observer)
    stages = StageStore(store, target, catalog)
    descriptor = stages.stage(image)
    _, staged = stages.load(descriptor)
    observed_site = observed['sites'][0]
    if install:
        fixtures = load(local / 'fixtures.json')
        targets = [{'installation_id': installation_id(observed_site, NOTES), 'site_id': observed_site['site_id'],
                    'workspace_id': workspace['public_id'], 'plugin_id': NOTES, 'action': 'install'}
                   for workspace in fixtures['workspaces'].values()]
    else:
        targets = [{key: row[key] for key in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')}
                   | {'action': 'deploy'} for row in before['state']['installations']]
    bundle = prepare_staged_plan(before, observed['sites'], catalog.snapshot(), staged['runtime'], descriptor,
        targets=targets, operation_type='install' if install else 'core_upgrade', operation_id=str(uuid4()),
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), base_runtime=observed['runtime'])
    operation = bundle['plan']['operation_id']
    assert bundle['plan']['backup']['required']
    if not install:
        assert bundle['plan']['destructive'] and not bundle['plan']['permission_changes']
    executor = StagedNativeExecutor(store, target_path, catalog_path, validator)
    validate = executor._validate()
    phase('registering', operation_id=operation, plan_hash=bundle['plan_hash'], business_before=business_before,
          app_tables=BUSINESS_TABLES[args.site], retained_files=len(files_before))
    store.register(bundle, validate)
    review = store.review(operation, validate)
    approval = store.approve(operation, exact_hash=bundle['plan_hash'], noninteractive=True, revalidate=validate,
        acknowledgments={'destructive': not install, 'trust_expansion': True, 'permission_expansion': install})
    phase('applying', review_digest=data_digest(review), approval_digest=data_digest(approval))

    if args.phase == 'fault-recover':
        peer_path = local.parent / 'maintenance/operator/target.json'
        peer = load(peer_path)
        assert peer['image_id'] == image and peer['project'] != target['project']
        peer_data = snapshot(peer, 'maintenance', notes=True)
        advance = store.advance

        def fault(selected, locks, selected_phase, **details):
            result = advance(selected, locks, selected_phase, **details)
            if selected == operation and selected_phase == 'release_published':
                raise OperatorError('Disposable stress fault after publication before traffic')
            return result

        with patch.object(store, 'advance', side_effect=fault):
            try:
                executor.apply(operation)
            except OperatorError as error:
                if 'Disposable stress fault' not in str(error):
                    raise
            else:
                raise AssertionError('The nominated fault did not run')
        failed = store.status(operation)
        assert failed['state'] == 'recovery_required' and failed['mutation_started'] and not failed['traffic_resumed']
        phase('recovery_required', failure=failed)
        subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('stress_http.py')),
                        'maintenance', 'peer-during-recovery'], check=True, timeout=60)
        recovery = RestoreExecutor(StagedNativeExecutor(store, target_path, catalog_path, validator))
        decision = recovery.prepare(operation)
        restored = recovery.execute(decision, exact_hash=data_digest(decision), noninteractive=True)
        restored_target = load(target_path)
        assert restored_target['image_id'] == target['image_id']
        assert restored_target['sites'][0]['database'] != target['sites'][0]['database']
        assert snapshot(restored_target, args.site, notes=True, policy_advanced=True) == business_before
        assert files(DockerObserver(restored_target)) == files_before
        phase('restored', restore_digest=data_digest(decision), restore=restored)
        recovery = RestoreExecutor(StagedNativeExecutor(store, target_path, catalog_path, validator))
        resume = recovery.prepare_resume(operation)
        recovery.resume(resume, exact_hash=data_digest(resume), noninteractive=True)
        assert store.status(operation)['state'] == 'revoked'
        assert load(peer_path) == peer and snapshot(peer, 'maintenance', notes=True) == peer_data
        phase('resumed', peer_image=image, peer_worker_unchanged=True, resume_digest=data_digest(resume))
    else:
        applied = executor.apply(operation)
        assert applied['state'] == 'completed' and applied['traffic_resumed']
        phase('applied', apply_result=applied)

    current = load(target_path)
    if args.phase != 'fault-recover':
        assert current['image_id'] == image
    assert snapshot(current, args.site, notes=not install, policy_advanced=install or args.phase == 'fault-recover') == business_before
    reader = DockerObserver(current)
    after_observation = reader.read()
    after = reader.state(after_observation, catalog.snapshot())['state']
    new_files = files(reader)
    assert all(new_files.get(name) == value for name, value in files_before.items())
    if not install:
        assert after['installations'] == before['state']['installations']
        assert after['bindings'] == before['state']['bindings']
    modules = {row['addon']: row['version'] for row in after_observation['sites'][0]['native_modules']}
    assert ADDONS[args.site] in modules and ADDONS[next(key for key in ADDONS if key != args.site)] not in modules
    phase('verified', generation=current['generation'], result_image=current['image_id'],
          app_and_authority_rows_preserved=True, retained_files_preserved=True, native_modules=modules)


if __name__ == '__main__':
    main()
