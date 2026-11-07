"""Exercise event archive introduction and coordinated native recovery."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from background_event_retention import RUN, SEED, native
from background_lifecycle import shell
from background_retention_lifecycle import approved, fail_after_publish
from background_site import Catalog, configuration, load, write
from background_workers import Probe
from modular_platform.dispatch_lifecycle import EVENT_HISTORY
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.lifecycle_planning import installation_id, prepare_current_install_targets
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor


def fresh_executor(native):
    return type(native)(native.store, native.target_path, native.catalog_root, native.validator)


def recover(probe, operation, native, expected):
    executor = RestoreExecutor(fresh_executor(native))
    decision = executor.prepare(operation)
    assert decision['source_dispatch']['tables'][EVENT_HISTORY] == expected
    restored = executor.execute(decision, exact_hash=data_digest(decision), noninteractive=True)
    assert restored['keep_traffic_closed'] and restored['fresh_database'] != probe.target['sites'][0]['database']
    after = fresh_executor(native)
    assert after.config['image_id'] == probe.target['image_id']
    executor = RestoreExecutor(after)
    resume = executor.prepare_resume(operation)
    executor.resume(resume, exact_hash=data_digest(resume), noninteractive=True)
    return dict(restore=data_digest(decision), resume=data_digest(resume), source=expected)


def current_image_install(probe):
    private = probe.site.private
    validator = configuration(private / 'trust.json')
    catalog = Catalog(private / 'catalog', validator, readonly=True).snapshot()
    store = OperatorStore(private / 'control')
    executor = NativeExecutor(store, private / 'target.json', private / 'catalog', validator)
    observed = executor.observer.read()
    site, = observed['sites']
    plugin = 'org.example.canvas'
    target = dict(installation_id=installation_id(site, plugin), site_id=site['site_id'],
                  workspace_id=probe.fixture['workspaces']['A']['public_id'], plugin_id=plugin, action='install')
    operation = str(uuid4())
    bundle = prepare_current_install_targets(executor.observer.state(observed, catalog), observed['sites'], catalog,
        activation_targets=[target], operation_id=operation,
        created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    validate = executor._validate()
    store.register(bundle, validate)
    store.review(operation, validate)
    store.approve(operation, exact_hash=bundle['plan_hash'], noninteractive=True, revalidate=validate,
        acknowledgments={'destructive': False, 'trust_expansion': True, 'permission_expansion': True})
    return operation, executor


def populated_restore():
    probe = Probe(RUN)
    native_result = load(probe.site.local / 'event-retention-result.json')
    assert native_result['native_consumption_deduplicated']
    seed = load(probe.site.local / 'event-retention-seed.json')
    receipt = probe.site.local / 'event-populated-restore.json'
    assert not receipt.exists()
    assert probe.sql('SELECT count(*) FROM mp_event_history') == '5'
    probe.sql("""INSERT INTO mp_event_history(site_id,workspace_id,kind,public_id,metadata,archived_at)
        SELECT site_id,workspace_id,'event',gen_random_uuid()::text,'{}'::jsonb,timezone('UTC',now())
        FROM (SELECT site_id,workspace_id FROM mp_event_history ORDER BY id LIMIT 1) sample
        CROSS JOIN generate_series(1,100002)""")
    operation, executor = current_image_install(probe)
    before = DispatchMaintenance(executor).inspect()['tables'][EVENT_HISTORY]
    assert before['rows'] == 100007
    record = dict(phase='applying', operation=operation, image=probe.target['image_id'], before=before)
    write(receipt, record)
    fail_after_publish(operation, executor)
    record.update(phase='restoring')
    write(receipt, record)
    record.update(recover(probe, operation, executor, before))
    after = Probe(RUN)
    restored = DispatchMaintenance(fresh_executor(executor)).inspect()['tables'][EVENT_HISTORY]
    checkpoint = load(executor.store.root / 'checkpoints' / operation / 'manifest.json')
    assert restored == before == checkpoint['dispatch_profile']['tables'][EVENT_HISTORY]
    assert after.sql(f"SELECT event_count FROM mp_example_note_event_summary WHERE note_id='{seed['note']}'") == '2'
    assert after.sql(f"SELECT scope_key IS NOT NULL FROM mp_event_history WHERE kind='consumption' AND public_id='{seed['consumption']}'") == 't'
    record.update(phase='passed', restored=restored, native_projection_preserved=True, consumed_receipt_preserved=True)
    write(receipt, record)
    print(json.dumps(record), flush=True)


def core_upgrade(candidate):
    run = 'bx-01-event-upgrade-01'
    probe = Probe(run)
    assert probe.sql("SELECT to_regclass('mp_event_history') IS NULL") == 't'
    receipt = probe.site.local / 'event-core-upgrade.json'
    assert not receipt.exists()
    seed = native(probe, 'bx01-old-event-seed', SEED)
    image = load(candidate)['image_id']
    operation, executor = approved(probe, image, 'core_upgrade')
    record = dict(phase='applying-fault', fault_operation=operation, original=probe.target['image_id'], target=image)
    write(receipt, record)
    fail_after_publish(operation, executor)
    record.update(recover(probe, operation, executor, dict(rows=0, sha256=sha256(b'').hexdigest())))
    old = Probe(run)
    assert old.sql("SELECT to_regclass('mp_event_history') IS NULL") == 't'
    assert old.sql(f"SELECT count(*) FROM mp_event_consumption WHERE public_id='{seed['consumption']}'") == '1'
    operation, executor = approved(old, image, 'core_upgrade')
    record.update(phase='applying-upgrade', upgrade_operation=operation)
    write(receipt, record)
    result = executor.apply(operation)
    assert result['state'] == 'completed' and result['traffic_resumed']
    after = Probe(run)
    assert after.target['image_id'] == image and after.sql("SELECT count(*) FROM mp_event_history") == '0'
    assert after.sql(f"SELECT event_count FROM mp_example_note_event_summary WHERE note_id='{seed['note']}'") == '1'
    assert after.sql(f"SELECT count(*) FROM mp_event_consumption WHERE public_id='{seed['consumption']}'") == '1'
    record.update(phase='passed', native_projection_preserved=True, live_consumed_receipt_preserved=True,
                  **check_policy(after))
    write(receipt, record)
    print(json.dumps(record), flush=True)


def check_policy(probe):
    source = f'EXPECTED_DB={probe.state["database"]!r}\n' + """
from datetime import datetime, timedelta, timezone
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable, event_retention
assert env.cr.dbname == EXPECTED_DB and EXPECTED_DB.startswith('mp_disposable_r0_r1_restore_')
release=current_release(env)
site,digest=release['site_id'],release['release_digest']
now=datetime.now(timezone.utc)

def denied(cutoff,limit):
    try:event_retention.candidates(env.cr,site,digest,'event',cutoff,limit)
    except durable.QueueError:return
    raise AssertionError('Event archive policy allowed an ineligible request')

denied(now-timedelta(days=7),1)
denied(now-timedelta(days=9),26)
env.cr.execute("UPDATE mp_plugin_installation SET runtime='external_service' WHERE plugin_id='org.example.notes_labels'")
assert env.cr.rowcount == 1
denied(now-timedelta(days=9),1)
env.cr.rollback()
print('BX_EVENT_POLICY_DENIED')
"""
    assert 'BX_EVENT_POLICY_DENIED' in shell(probe, 'bx01-event-policy', source)
    return dict(early_cutoff_refused=True, oversized_batch_refused=True, external_profile_refused=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('large-restore', 'upgrade'))
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    if args.phase == 'large-restore':
        populated_restore()
    else:
        core_upgrade(args.candidate)
