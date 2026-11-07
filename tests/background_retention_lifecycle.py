"""Qualify the retention schema through approved upgrade and fresh restore."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from background_lifecycle import assert_stale, queue, seed_jobs, shell
from background_retention_site import PROBE
from background_site import Catalog, configuration, load, write
from background_workers import Probe
from modular_platform.dispatch_lifecycle import JOB_IDENTITY
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore, prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor


RUN = 'bx-01-retention-upgrade-01'


def approved(probe, image, kind):
    private = probe.site.private
    target_path, catalog_path = private / 'target.json', private / 'catalog'
    validator = configuration(private / 'trust.json')
    catalog = Catalog(catalog_path, validator, readonly=True)
    store = OperatorStore(private / 'control')
    native = StagedNativeExecutor(store, target_path, catalog_path, validator)
    observed = native.observer.read()
    current = native.observer.state(observed, catalog.snapshot())
    stages = StageStore(store, probe.target, catalog)
    descriptor = stages.stage(image)
    _, staged = stages.load(descriptor)
    targets = [{key: row[key] for key in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')}
               | {'action': 'deploy'} for row in current['state']['installations']]
    operation = str(uuid4())
    bundle = prepare_staged_plan(current, observed['sites'], catalog.snapshot(), staged['runtime'], descriptor,
        targets=targets, operation_type=kind, operation_id=operation,
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), base_runtime=observed['runtime'])
    validate = native._validate()
    store.register(bundle, validate)
    store.review(operation, validate)
    store.approve(operation, exact_hash=bundle['plan_hash'], noninteractive=True, revalidate=validate,
        acknowledgments={'destructive': kind == 'core_upgrade', 'trust_expansion': True, 'permission_expansion': False})
    return operation, native


def fail_after_publish(operation, native):
    advance = native.store.advance

    def inject(selected, locks, state, **details):
        result = advance(selected, locks, state, **details)
        if selected == operation and state == 'release_published':
            raise OperatorError('BX retention qualification fault after publish')
        return result

    with patch.object(native.store, 'advance', side_effect=inject):
        try:
            native.apply(operation)
        except OperatorError as error:
            assert 'BX retention qualification fault' in str(error), str(error)
        else:
            raise AssertionError('Post-publish fault did not run')
    journal = native.store.status(operation)
    assert journal['state'] == 'recovery_required' and not journal['traffic_resumed']


def restore(probe, operation, native, *, first_schema_change):
    # Re-read the target after publication and between restore and resume.
    def recovery():
        return RestoreExecutor(StagedNativeExecutor(native.store, native.target_path,
                                                     native.catalog_root, native.validator))

    executor = recovery()
    decision = executor.prepare(operation)
    registry = decision['source_dispatch']['tables'][JOB_IDENTITY]
    assert registry['rows'] == (0 if first_schema_change else 100002)
    executor.execute(decision, exact_hash=data_digest(decision), noninteractive=True)
    current = load(native.target_path)
    assert current['image_id'] == probe.target['image_id']
    assert current['sites'][0]['database'] != probe.target['sites'][0]['database']
    executor = recovery()
    resume = executor.prepare_resume(operation)
    executor.resume(resume, exact_hash=data_digest(resume), noninteractive=True)
    return {'restore': data_digest(decision), 'resume': data_digest(resume), 'source_identity': registry}


def seed_large_history(probe):
    source = (f'FIXTURE_DB = {probe.state["database"]!r}\nFIXTURE = {probe.fixture!r}\n' + PROBE)
    assert 'MP_BX_RESULT=' in shell(probe, 'bx01-upgrade-native-archive', source)
    probe.sql("""INSERT INTO mp_job_identity
        (site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key,
         job_public_id,input_digest,release_digest,effect_mode,terminal_state,finished_at,archived_at)
        SELECT site_id,workspace_id,actor_id,installation_id,handler,handler_version,'bx01-populated-'||n,
            gen_random_uuid()::text,input_digest,release_digest,effect_mode,terminal_state,
            finished_at - n * interval '8 seconds',archived_at
        FROM mp_job_identity CROSS JOIN generate_series(1,100001) n
        WHERE idempotency_key='bx01-archive-native' AND job_public_id IS NOT NULL""")
    return probe.sql("SELECT job_public_id FROM mp_job_identity WHERE idempotency_key='bx01-archive-native'")


def run(phase, candidate_path):
    probe = Probe(RUN)
    assert not probe.operator._lanes()
    receipt = probe.site.local / 'bx01-retention-lifecycle.json'
    record = load(receipt) if receipt.exists() else {}
    image = load(candidate_path)['image_id']
    if phase == 'legacy-fault':
        assert not record
        assert probe.sql("SELECT to_regclass('mp_job_identity') IS NULL") == 't'
        seed = seed_jobs(probe, report_version=2)
        record.update(seed=seed, original=queue(probe, seed), original_image=probe.target['image_id'])
    else:
        assert record['phase'] == {'upgrade': 'legacy-fault', 'large-restore': 'upgrade'}[phase]
        seed = record['seed']
    if phase == 'large-restore':
        record['retained_job'] = seed_large_history(probe)
    operation, native = approved(probe, image, 'deploy' if phase == 'large-restore' else 'core_upgrade')
    record[phase] = {'operation': operation, 'candidate': image}
    record['phase'] = 'applying-' + phase
    write(receipt, record)
    if phase == 'upgrade':
        result = native.apply(operation)
        assert result['state'] == 'completed' and result['traffic_resumed']
    else:
        fail_after_publish(operation, native)
        record[phase].update(restore(probe, operation, native, first_schema_change=phase == 'legacy-fault'))
    after = Probe(RUN)
    assert after.target['image_id'] == (image if phase == 'upgrade' else probe.target['image_id'])
    assert_stale(after, seed, 'bx01-stale-' + phase)
    if phase == 'large-restore':
        restored = DispatchMaintenance(StagedNativeExecutor(native.store, native.target_path,
            native.catalog_root, native.validator)).inspect()['tables'][JOB_IDENTITY]
        assert restored == record[phase]['source_identity']
        assert after.sql("SELECT job_public_id FROM mp_job_identity WHERE idempotency_key='bx01-archive-native'") == record['retained_job']
        record[phase]['restored_identity'] = restored
    else:
        before_rows, after_rows = record['original'], queue(after, seed)
        assert before_rows.keys() == after_rows.keys()
        for job, row in after_rows.items():
            assert all(row[field] == before_rows[job][field] for field in ('deadline', 'actor', 'workspace'))
            if job != seed['running']:
                assert row['at'] == before_rows[job]['at']
        assert after_rows[seed['reminder']]['state'] == 'pending'
        assert after.sql("SELECT to_regclass('mp_job_identity') IS NULL") == ('t' if phase == 'legacy-fault' else 'f')
        record[phase]['timing_and_scope_preserved'] = True
    record[phase]['stale_claim_denied'] = True
    record['phase'] = phase
    write(receipt, record)
    print({'phase': phase, **record[phase]}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('legacy-fault', 'upgrade', 'large-restore'))
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    run(args.phase, args.candidate)
