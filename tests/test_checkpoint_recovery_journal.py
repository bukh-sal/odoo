"""Real OS locks/private files/SQLite source history; no Docker/native effects."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
from modular_platform.checkpoint_recovery_journal import CheckpointRecoveryJournal, STEPS
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperationLocks, OperatorError
from modular_platform.plans import prepare_plan,release_lock,data_digest
from modular_platform.recovery_reviews import RecoveryReviews
from test_plans import base_state,solution,target,ident,PROVENANCE,STAMP
from test_resolution import plugin


class CheckpointJournal(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'control';self.state=base_state()
        self.store=OperatorStore.initialize(self.root,{self.state['deployment_id']:self.state['site_ids']})
        resolved=solution([plugin('a')]);lock=release_lock(resolved,PROVENANCE,generation=2,created_at=STAMP)
        self.bundle=prepare_plan(self.state,lock,resolved,[target()],operation_id=ident(590),created_at=STAMP)
        self.source=self.store.register(self.bundle,self.revalidate)
        self.store.approve(self.source,exact_hash=self.bundle['plan_hash'],acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=True),revalidate=self.revalidate)
        with self.locks() as locks:
            self.store.reserve(self.source,locks,self.revalidate)
            for step in ('staged','maintenance','drained'):self.store.advance(self.source,locks,step)
            self.store.advance(self.source,locks,'checkpointed',backup_id=self.source)
            self.store.before_mutation(self.source,locks,self.revalidate)
            for step in ('migrated','workers_replaced','ready','release_published','traffic_resumed','completed'):
                self.store.advance(self.source,locks,step)
        self.original=self.store.status(self.source)
        self.recovery=ident(591);self.journal=CheckpointRecoveryJournal(self.store,self.recovery)
        self.decision=self.review('restore_completed_checkpoint')
        self.exact=data_digest(self.decision)

    def revalidate(self,bundle):return copy.deepcopy(self.state)
    def locks(self,sites=None):return OperationLocks(self.root/'locks',self.state['deployment_id'],sites or self.state['site_ids'])
    def review(self,action,now=None):
        return RecoveryReviews(self.store).issue(dict(schema_version=1,action=action,operation_id=self.recovery,
            checkpoint_operation_id=self.source,plan_hash=self.bundle['plan_hash'],
            source_bundle_digest=data_digest(self.bundle),source_operation_digest=data_digest(self.store.status(self.source))),now=now)
    def create(self,locks):return self.journal.create(self.decision,exact_hash=self.exact,locks=locks)
    def step(self,name,locks,decision=None):
        decision=decision or self.decision;exact=data_digest(decision)
        self.journal.begin(name,{'command':'fake-external-boundary'},decision=decision,exact_hash=exact,locks=locks)
        self.journal.finish(name,{'observed':'fake-external-boundary'},decision=decision,exact_hash=exact,locks=locks)

    def test_full_order_separate_resume_and_original_sqlite_history_immutable(self):
        with self.locks() as locks:
            self.create(locks)
            for step in STEPS[:8]:self.step(step,locks)
            with self.assertRaisesRegex(OperatorError,'distinct reviewed'):
                self.step('resume_started',locks)
            resume=self.review('resume_completed_checkpoint')
            for step in STEPS[8:]:self.step(step,locks,resume)
            self.assertEqual(self.journal.status()['phase'],'resumed')
            self.assertEqual(self.store.status(self.source),self.original)
            with self.assertRaisesRegex(OperatorError,'already attempted'):self.create(locks)
            with self.assertRaisesRegex(OperatorError,'already completed'):self.step('resumed',locks,resume)

    def test_pending_intent_refuses_repetition_and_new_process_lock_completion(self):
        with self.locks() as locks:
            self.create(locks)
            self.journal.begin('traffic_closed',{},decision=self.decision,exact_hash=self.exact,locks=locks)
            with self.assertRaisesRegex(OperatorError,'pending'):self.step('traffic_closed',locks)
        with self.locks() as replacement:
            self.assertEqual(self.journal.status()['pending']['step'],'traffic_closed')
            with self.assertRaisesRegex(OperatorError,'same fenced executor'):
                self.journal.finish('traffic_closed',{},decision=self.decision,exact_hash=self.exact,locks=replacement)
        self.assertEqual(self.store.status(self.source),self.original)

    def test_wrong_site_locks_and_noncanonical_identity_refuse_before_create(self):
        with self.locks([ident(999)]) as wrong:
            with self.assertRaisesRegex(OperatorError,'exact independent store'):self.create(wrong)
        self.assertFalse(self.journal.root.exists())
        for value in ('../escape',self.recovery.upper(),None):
            # Decimal-only UUID fixtures have no uppercase variant.
            if value==self.recovery:continue
            with self.assertRaises(OperatorError):CheckpointRecoveryJournal(self.store,value)

    def test_changed_source_history_and_source_digest_forgery_refuse(self):
        with self.locks() as locks:
            self.create(locks)
            with self.store._connect(transaction=True) as database:
                self.store._event(database,self.source,'unexpected_history_change',{})
            with self.assertRaisesRegex(OperatorError,'source history changed'):self.journal.status()
            with self.assertRaisesRegex(OperatorError,'source operation or bundle changed'):self.step('traffic_closed',locks)

    def test_expired_and_fabricated_reviews_do_not_start_journal(self):
        expired=self.review('restore_completed_checkpoint',datetime.now(timezone.utc)-timedelta(seconds=1000))
        with self.locks() as locks:
            with self.assertRaisesRegex(OperatorError,'expired'):
                self.journal.create(expired,exact_hash=data_digest(expired),locks=locks)
            forged=copy.deepcopy(self.decision);forged['schema_version']=999
            with self.assertRaisesRegex(OperatorError,'Exact reviewed'):
                self.journal.create(forged,exact_hash=data_digest(forged),locks=locks)
        self.assertFalse(self.journal.root.exists())

    def test_revoked_review_status_readable_but_no_new_command(self):
        with self.locks() as locks:
            self.create(locks)
            RecoveryReviews(self.store).revoke(self.decision,exact_hash=self.exact)
            self.assertEqual(self.journal.status()['phase'],'started')
            with self.assertRaisesRegex(OperatorError,'revoked'):self.step('traffic_closed',locks)
        self.assertEqual(self.store.status(self.source),self.original)

    def test_completion_and_binding_tamper_and_unknown_records_refuse(self):
        with self.locks() as locks:
            self.create(locks);self.step('traffic_closed',locks)
        path=self.journal.root/'journal/00-traffic_closed.complete.json'
        original=path.read_bytes();value=json.loads(original);value['intent_digest']='forged'
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(OperatorError,'completion differs'):self.journal.status()
        path.write_bytes(original)
        extra=path.with_name('unknown.json');extra.write_text('{}')
        with self.assertRaisesRegex(OperatorError,'unknown or reordered'):self.journal.status()
        extra.unlink()
        binding=self.journal.root/'binding.json';value=json.loads(binding.read_bytes())
        value['decision']['schema_version']=999;value['decision_hash']=data_digest(value['decision'])
        binding.write_text(json.dumps(value))
        with self.assertRaisesRegex(OperatorError,'Exact reviewed'):self.journal.status()

    def test_fresh_reviewed_continuation_only_after_completed_quiesce_boundary(self):
        continuation=self.review('continue_completed_checkpoint')
        with self.locks() as locks:
            self.create(locks)
            with self.assertRaisesRegex(OperatorError,'distinct reviewed'):self.step('traffic_closed',locks,continuation)
            for step in STEPS[:4]:self.step(step,locks)
        with self.locks() as fresh:
            self.step('target_created',fresh,continuation)
        self.assertEqual(self.journal.status()['phase'],'target_created')
        self.assertEqual(self.store.status(self.source),self.original)

    def test_exact_late_adoption_uses_new_real_lock_and_preserves_original_intent(self):
        from modular_platform.operator_os import protect_directory
        from modular_platform.operator_store import _write_new
        with self.locks() as locks:
            self.create(locks)
            _write_new(self.journal.root/'decision.json',dict(decision=self.decision,hash=self.exact))
            for name in STEPS[:7]:self.step(name,locks)
            self.journal.begin('restore_verified',{},decision=self.decision,exact_hash=self.exact,locks=locks)
        old=(self.journal.root/'journal/07-restore_verified.intent.json').read_bytes()
        payload={k:v for k,v in self.decision.items() if k!='review'}
        pending=self.journal.status()['pending']['intent']
        payload.update(action='continue_completed_checkpoint',continuation=dict(
            phase='restored_before_first_dispatch_fence',reason='retained_source_fence_name_collision',
            pending_intent_digest=data_digest(pending),original_decision_digest=data_digest(json.loads((self.journal.root/'decision.json').read_bytes()))))
        decision=RecoveryReviews(self.store).issue(payload);exact=data_digest(decision)
        with self.locks() as locks:
            RecoveryReviews(self.store).verify(decision,exact_hash=exact,current_payload=payload)
            directory=protect_directory(self.journal.root/'continuations'/decision['review']['review_id'])
            _write_new(directory/'decision.json',decision)
            with self.assertRaises((OperatorError,FileNotFoundError)):
                self.journal.finish('restore_verified',{},decision=decision,exact_hash=exact,locks=locks)
            self.journal.adopt_unstarted_restored_fence(decision=decision,exact_hash=exact,locks=locks)
        with self.locks() as wrong:
            with self.assertRaisesRegex(OperatorError,'not adopted'):
                self.journal.finish('restore_verified',{},decision=decision,exact_hash=exact,locks=wrong)
        # A second adoption cannot replace the recorded fenced owner.
        with self.locks() as wrong:
            with self.assertRaises(OperatorError):
                self.journal.adopt_unstarted_restored_fence(decision=decision,exact_hash=exact,locks=wrong)
        self.assertEqual((self.journal.root/'journal/07-restore_verified.intent.json').read_bytes(),old)
        self.assertEqual(self.store.status(self.source),self.original)


if __name__=='__main__':unittest.main()
