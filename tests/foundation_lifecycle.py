"""Recorded common-core upgrade and separately resumed independent recovery."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

from foundation_release import FoundationSite, ROOT, load, write, configuration
from stress_lifecycle import BUSINESS_TABLES
from qualify_release_reader_rollout import files
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore, prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor


def sql(target, statement):
    reader = DockerObserver(target)
    return subprocess.check_output(['docker', 'exec', reader._container('db'), 'psql', '-XqAt', '-U',
        'postgres', '-v', 'ON_ERROR_STOP=1', '-d', target['sites'][0]['database'], '-c', statement], timeout=40).decode().strip()


def snapshot(target, site, *, restored=False):
    tables = BUSINESS_TABLES[site] + ['mp_workspace', 'mp_membership', 'res_groups_users_rel',
        'mp_example_note', 'mp_background_task', 'mp_background_notification', 'mp_background_report']
    pairs = []
    for table in tables:
        row = 'to_jsonb(r)'
        if table == 'mp_workspace' and restored:
            row += " || jsonb_build_object('policy_generation', r.policy_generation - 1)"
        pairs.append(f"'{table}',(SELECT jsonb_agg({row} ORDER BY to_jsonb(r)) FROM {table} r)")
    return data_digest(json.loads(sql(target, 'SELECT jsonb_build_object(' + ','.join(pairs) + ');')))


def executor(site):
    return StagedNativeExecutor(OperatorStore(site.private / 'control'), site.private / 'target.json',
                                site.private / 'catalog', configuration(site.private / 'trust.json'))


def prepare(site, candidate, label):
    path = site.local / (label + '.json')
    assert not path.exists(), 'Inspect the exact existing operation before another mutation'
    native = executor(site)
    observed = native.observer.read()
    catalog = Catalog(native.catalog_root, native.validator, readonly=True).snapshot()
    before = native.observer.state(observed, catalog)
    stage = StageStore(native.store, native.config, Catalog(native.catalog_root, native.validator, readonly=True))
    descriptor = stage.stage(candidate['image_id'])
    _, staged = stage.load(descriptor)
    targets = [{key: row[key] for key in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')}
               | {'action': 'deploy'} for row in before['state']['installations']]
    bundle = prepare_staged_plan(before, observed['sites'], catalog, staged['runtime'], descriptor,
        targets=targets, operation_type='core_upgrade', operation_id=str(uuid4()),
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), base_runtime=observed['runtime'])
    operation = bundle['plan']['operation_id']
    record = dict(phase='registering', operation=operation, plan_hash=bundle['plan_hash'], base=native.config,
        candidate=candidate['image_id'], business=snapshot(native.config, site.args.site),
        files=files(native.observer), installations=before['state']['installations'], bindings=before['state']['bindings'])
    write(path, record)
    validate = native._validate()
    native.store.register(bundle, validate)
    review = native.store.review(operation, validate)
    approval = native.store.approve(operation, exact_hash=bundle['plan_hash'], noninteractive=True,
        revalidate=validate, acknowledgments={'destructive': True, 'trust_expansion': True, 'permission_expansion': False})
    record.update(phase='approved', review_digest=data_digest(review), approval_digest=data_digest(approval))
    write(path, record)
    return path, record, native


def peer(site, label):
    assert site.args.site == 'aurora'
    suffix = '-' + site.args.attempt if site.args.attempt else ''
    label += suffix
    other = FoundationSite(argparse.Namespace(site='maintenance', run=site.args.run, label=label))
    target = load(other.private / 'target.json')
    original = load(other.local / ('upgrade' + suffix + '.json'))
    assert original['phase'] == 'verified' and target['image_id'] == original['candidate']
    assert snapshot(target, 'maintenance') == original['business']
    other.workflow()
    return dict(configuration_digest=data_digest(target), business=original['business'], image=target['image_id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['upgrade', 'fault', 'capture_fault', 'restore', 'resume'])
    parser.add_argument('site', choices=['aurora', 'maintenance'])
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--attempt', choices=['', 'core46'], default='')
    args = parser.parse_args()
    args.run = 'cf-01'
    site = FoundationSite(args)
    suffix = '-' + args.attempt if args.attempt else ''
    if args.phase != 'upgrade':
        assert args.site == 'aurora'
    if args.phase in ('upgrade', 'fault'):
        path, record, native = prepare(site, load(args.candidate), args.phase + suffix)
        record['phase'] = 'applying'
        write(path, record)
        if args.phase == 'fault':
            record['peer_before'] = peer(site, 'peer-before-fault')
            write(path, record)
            advance = native.store.advance
            def inject(operation, locks, selected, **details):
                result = advance(operation, locks, selected, **details)
                if operation == record['operation'] and selected == 'release_published':
                    raise OperatorError('CF controlled publication failure')
                return result
            with patch.object(native.store, 'advance', side_effect=inject):
                try:
                    native.apply(record['operation'])
                except OperatorError as error:
                    assert 'CF controlled publication failure' in str(error)
                else:
                    raise AssertionError('Fault was not reached')
            status = native.store.status(record['operation'])
            assert status['state'] == 'recovery_required' and status['mutation_started'] and not status['traffic_resumed']
            failed_target = load(native.target_path)
            # Demonstrate recovery with the failed application actually down.
            # PostgreSQL and independently scoped operator state remain available.
            subprocess.run(['docker', 'stop', failed_target['worker_id']], check=True,
                           stdout=subprocess.DEVNULL, timeout=45)
            # Independent host CLI reads the journal without connecting to Odoo.
            raw = subprocess.check_output([sys.executable, '-I', str(ROOT / 'tools/modular.py'), '--config', str(site.private / 'trust.json'),
                'operations', '--store', str(native.store.root), 'show', record['operation']], timeout=30)
            assert json.loads(raw)['state'] == 'recovery_required'
            record.update(phase='recovery_required', independent_cli=True, failed_app_stopped=True,
                          peer_closed=peer(site, 'peer-while-closed'))
        else:
            applied = native.apply(record['operation'])
            assert applied['state'] == 'completed' and applied['traffic_resumed']
            target = load(native.target_path)
            assert target['image_id'] == record['candidate']
            assert snapshot(target, args.site) == record['business']
            assert all(files(DockerObserver(target)).get(k) == v for k, v in record['files'].items())
            for name in ['mp_job_identity', 'mp_event_history', 'mp_job_schedule', 'mp_job_occurrence']:
                assert sql(target, f"SELECT to_regclass('{name}') IS NOT NULL;") == 't', name
            record.update(phase='verified', shared_schema=True, preserved_business=True)
        write(path, record)
    else:
        path = site.local / ('fault' + suffix + '.json')
        record = load(path)
        native = executor(site)
        recovery = RestoreExecutor(native)
        if args.phase == 'capture_fault':
            # The first CLI check omitted its required trust-config argument.
            # Capture the existing post-publication fault; never apply it again.
            assert record['phase'] == 'applying'
            status = native.store.status(record['operation'])
            assert status['state'] == 'recovery_required' and status['phase'] == 'release_published'
            assert status['mutation_started'] and not status['traffic_resumed']
            failed = load(native.target_path)
            state = json.loads(subprocess.check_output(['docker', 'inspect', failed['worker_id']]))[0]['State']
            assert not state['Running'] and state['ExitCode'] == 0
            raw = subprocess.check_output([sys.executable, '-I', str(ROOT / 'tools/modular.py'), '--config', str(site.private / 'trust.json'),
                'operations', '--store', str(native.store.root), 'show', record['operation']], timeout=30)
            assert json.loads(raw)['state'] == 'recovery_required'
            record.update(phase='recovery_required', independent_cli=True, failed_app_stopped=True,
                          peer_closed=peer(site, 'peer-while-closed'))
        elif args.phase == 'restore':
            assert record['phase'] == 'recovery_required'
            decision = recovery.prepare(record['operation'])
            record.update(phase='restoring', restore_digest=data_digest(decision))
            write(path, record)
            recovery.execute(decision, exact_hash=data_digest(decision), noninteractive=True)
            target = load(native.target_path)
            assert target['image_id'] == record['base']['image_id']
            assert target['sites'][0]['database'] != record['base']['sites'][0]['database']
            assert snapshot(target, args.site, restored=True) == record['business']
            assert files(DockerObserver(target)) == record['files']
            result = load(native.store.root / 'recoveries' / record['operation'] / 'result.json')
            assert result['keep_traffic_closed']
            record.update(phase='restored_closed', restore_digest=data_digest(decision), fresh_database=True,
                          exact_checkpoint_business=True, exact_checkpoint_files=True,
                          peer_restored=peer(site, 'peer-during-restore'))
        else:
            assert record['phase'] == 'restored_closed'
            decision = recovery.prepare_resume(record['operation'])
            recovery.resume(decision, exact_hash=data_digest(decision), noninteractive=True)
            assert native.store.status(record['operation'])['state'] == 'revoked'
            record.update(phase='verified', resume_digest=data_digest(decision), separate_resume=True,
                          peer_resumed=peer(site, 'peer-after-resume'))
        write(path, record)
    print(json.dumps(dict(phase=record['phase'], operation=record['operation'], site=args.site)), flush=True)


if __name__ == '__main__':
    main()
