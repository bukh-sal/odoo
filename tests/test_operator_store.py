"""Actual private SQLite approval/journal effects; native execution is G5 E-01d."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.operator_os import OperationLocks, OperatorError, protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import prepare_plan, release_lock
from test_plans import base_state, solution, target, ident, PROVENANCE, STAMP
from test_resolution import plugin

ACKS = {'destructive': True, 'trust_expansion': True, 'permission_expansion': True}


class OperatorStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = base_state()
        self.root = Path(self.temporary.name) / 'control'
        self.store = OperatorStore.initialize(self.root, {self.state['deployment_id']: self.state['site_ids']})
        self.bundle = self.bundle_for(500)
        self.operation = self.store.register(self.bundle, self.revalidate)

    def bundle_for(self, value):
        resolved = solution([plugin('a')])
        lock = release_lock(resolved, PROVENANCE, generation=2, created_at=STAMP)
        return prepare_plan(self.state, lock, resolved, [target()], operation_id=ident(value), created_at=STAMP)

    def revalidate(self, bundle):
        return copy.deepcopy(self.state)

    def approve(self, **kwargs):
        return self.store.approve(self.operation, exact_hash=self.bundle['plan_hash'], acknowledgments=ACKS, revalidate=self.revalidate, **kwargs)

    def locks(self, bundle=None):
        plan = (bundle or self.bundle)['plan']
        return OperationLocks(self.root / 'locks', plan['deployment_id'], plan['site_ids'])

    def ready_to_mutate(self, locks):
        self.store.reserve(self.operation, locks, self.revalidate)
        for phase in ('staged', 'maintenance', 'drained'):
            self.store.advance(self.operation, locks, phase)
        self.store.advance(self.operation, locks, 'checkpointed', backup_id='disposable-verified-checkpoint')

    def test_exact_hash_required_idempotent_approval_and_no_app_flag_authority(self):
        self.assertEqual(self.store.status(self.operation)['state'], 'awaiting_operator_approval')
        with self.assertRaisesRegex(OperatorError, 'Exact reviewed'):
            self.store.approve(self.operation, exact_hash='sha256:' + '0' * 64, acknowledgments=ACKS, revalidate=self.revalidate)
        first = self.approve()
        second = self.approve(now=datetime.now(timezone.utc) + timedelta(seconds=1))
        self.assertEqual(first, second)
        self.assertEqual(first['consumed_operation_id'], None)
        self.assertEqual((datetime.fromisoformat(first['expires_at'].replace('Z', '+00:00')) - datetime.fromisoformat(first['issued_at'].replace('Z', '+00:00'))).total_seconds(), 900)
        forged = {**self.bundle, 'approved': True}
        with self.assertRaisesRegex(ValueError, 'bundle fields'):
            self.store.register(forged, self.revalidate)
        other = self.bundle_for(501)
        operation = self.store.register(other, self.revalidate)
        with self.locks(other) as held:
            with self.assertRaisesRegex(OperatorError, 'without reconciliation'):
                self.store.reserve(operation, held, self.revalidate)
        unrelated = protect_directory(Path(self.temporary.name) / 'unrelated-locks')
        with OperationLocks(unrelated, self.state['deployment_id'], self.state['site_ids']) as forged_locks:
            with self.assertRaisesRegex(OperatorError, 'exact independent store'):
                self.store.reserve(self.operation, forged_locks, self.revalidate)

    def test_missing_acknowledgments_stale_state_and_generation_change(self):
        with self.assertRaisesRegex(OperatorError, 'explicit acknowledgment'):
            self.store.approve(self.operation, exact_hash=self.bundle['plan_hash'], acknowledgments={key: False for key in ACKS}, revalidate=self.revalidate)
        with self.assertRaisesRegex(ValueError, 'Stale plan'):
            self.store.approve(self.operation, exact_hash=self.bundle['plan_hash'], acknowledgments=ACKS,
                revalidate=lambda _: {**self.state, 'generation': 2})
        self.approve()
        path = self.root / 'policy.json'
        policy = json.loads(path.read_text())
        policy['authorization_generation'] += 1
        path.write_text(json.dumps(policy))
        with self.locks() as held:
            with self.assertRaisesRegex(OperatorError, 'authority generation changed'):
                self.store.reserve(self.operation, held, self.revalidate)
        self.assertEqual(self.store.status(self.operation)['state'], 'authorization_changed')

    def test_verified_restore_retires_original_approval_and_conservative_traffic_fence(self):
        self.approve()
        with self.locks() as held:
            self.ready_to_mutate(held)
            self.store.before_mutation(self.operation,held,self.revalidate)
            self.store.fail(self.operation,held,code='MUTATION_FAILED')
        with self.locks() as recovery:
            self.store.record_restore(self.operation,recovery,code='restore_authorized',details={'decision_hash':'sha256:'+'d'*64})
            self.store.record_restore(self.operation,recovery,code='restore_target_created',details={})
            self.store.record_restore(self.operation,recovery,code='restore_verified',details={})
            self.assertEqual(self.store.status(self.operation)['state'],'revoked')
        with self.locks() as repeated:
            with self.assertRaisesRegex(OperatorError,'Retired or completed'):
                self.store.reserve(self.operation,repeated,self.revalidate)
            self.assertEqual(self.store.status(self.operation)['state'],'revoked')
            with self.assertRaisesRegex(OperatorError,'revocation is final'): self.approve()
            self.store.record_restore_resume(self.operation,repeated,decision_hash='sha256:'+'e'*64)
            self.assertTrue(self.store.status(self.operation)['traffic_resumed'])
            with self.assertRaises(OperatorError):
                self.store.record_restore(self.operation,repeated,code='restore_authorized',details={})

    def test_expiry_and_independent_revocation_are_not_reusable(self):
        approved = self.approve()
        expired = datetime.fromisoformat(approved['expires_at'].replace('Z', '+00:00')) + timedelta(seconds=1)
        with self.locks() as held:
            with self.assertRaisesRegex(ValueError, 'Approval unavailable'):
                self.store.reserve(self.operation, held, self.revalidate, now=expired)
        self.store.revoke(self.operation)
        self.assertEqual(self.store.status(self.operation)['state'], 'revoked')
        with self.assertRaisesRegex(OperatorError, 'revocation is final'):
            self.approve()
        with self.locks() as held:
            with self.assertRaisesRegex(OperatorError, 'revoked'):
                self.store.reserve(self.operation, held, self.revalidate)

    def test_backup_phase_and_one_mutation_reservation_then_expiry_does_not_kill_started_work(self):
        self.approve()
        with self.locks() as held:
            self.store.reserve(self.operation, held, self.revalidate)
            with self.assertRaisesRegex(OperatorError, 'skipped'):
                self.store.advance(self.operation, held, 'ready')
            for phase in ('staged', 'maintenance', 'drained'):
                self.store.advance(self.operation, held, phase)
            with self.assertRaisesRegex(OperatorError, 'drained/checkpointed'):
                self.store.before_mutation(self.operation, held, self.revalidate)
            self.store.advance(self.operation, held, 'checkpointed', backup_id='disposable-verified-checkpoint')
            self.store.before_mutation(self.operation, held, self.revalidate)
            with self.assertRaisesRegex(OperatorError, 'one reservation'):
                self.store.before_mutation(self.operation, held, self.revalidate)
            future = datetime.now(timezone.utc) + timedelta(days=1)
            with patch('modular_platform.operator_store._utc', side_effect=lambda value=None: future):
                for phase in ('migrated', 'workers_replaced', 'ready', 'release_published', 'traffic_resumed', 'completed'):
                    self.store.advance(self.operation, held, phase)
        status = self.store.status(self.operation)
        self.assertEqual(status['state'], 'completed')
        self.assertTrue(status['mutation_started'])
        self.assertTrue(status['traffic_resumed'])
        self.assertEqual([event['code'] for event in status['history']].count('mutation_started'), 1)
        with self.locks() as held:
            with self.assertRaisesRegex(OperatorError, 'cannot start or continue'):
                self.store.reserve(self.operation, held, self.revalidate)

    def test_new_lock_owner_after_possible_commit_records_recovery_before_stale_state_check(self):
        self.approve()
        with self.locks() as held:
            self.ready_to_mutate(held)
            self.store.before_mutation(self.operation, held, self.revalidate)
        reopened = OperatorStore(self.root)
        # A newly authorized generation may still record uncertainty from its
        # predecessor; it cannot use the old approval to continue native work.
        path = self.root / 'policy.json'
        policy = json.loads(path.read_text())
        policy['authorization_generation'] += 1
        path.write_text(json.dumps(policy))
        def should_not_repeat_initial_validation(_):
            self.fail('A changed/committed native database is expected; detect old executor loss first')
        with self.locks() as replacement:
            with self.assertRaisesRegex(OperatorError, 'recovery_required'):
                reopened.reserve(self.operation, replacement, should_not_repeat_initial_validation)
        status = reopened.status(self.operation)
        self.assertEqual(status['state'], 'recovery_required')
        self.assertEqual(status['phase'], 'mutation_started')
        self.assertEqual(status['backup_id'], 'disposable-verified-checkpoint')
        # A restored application snapshot cannot reset this outside-store journal.
        self.state = base_state()
        self.assertEqual(OperatorStore(self.root).status(self.operation)['state'], 'recovery_required')

    def test_revocation_after_mutation_preserves_uncertainty_and_safe_bounded_errors(self):
        self.approve()
        with self.locks() as held:
            self.ready_to_mutate(held)
            self.store.before_mutation(self.operation, held, self.revalidate)
            self.store.revoke(self.operation)
            with self.assertRaisesRegex(OperatorError, 'revoked'):
                self.store.advance(self.operation, held, 'migrated')
            with self.assertRaisesRegex(OperatorError, 'Bounded redacted'):
                self.store.fail(self.operation, held, code='private contents must never be journaled')
        self.assertEqual(self.store.status(self.operation)['state'], 'recovery_required')


if __name__ == '__main__':
    unittest.main()
