"""Real protected OS store refuses forward work on incomplete recovery evidence."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk'),str(ROOT)]
from modular_platform.operator_os import OperatorError,protect_directory
import test_operator_store as store_fixture
from test_plans import ident


class CheckpointStoreFence(unittest.TestCase):
    setUp=store_fixture.OperatorStoreTests.setUp
    bundle_for=store_fixture.OperatorStoreTests.bundle_for
    revalidate=store_fixture.OperatorStoreTests.revalidate
    locks=store_fixture.OperatorStoreTests.locks

    def test_real_store_incomplete_binding_refuses_all_forward_entries_history_unchanged(self):
        original=copy.deepcopy(self.store.status(self.operation))
        # A crash can leave the protected recovery root before binding was
        # durably published. Missing evidence must not be treated as no recovery.
        protect_directory(self.root/'checkpoint-restores'/ident(501))
        for call in (
            lambda:self.store.register(self.bundle_for(502),self.revalidate),
            lambda:self.store.review(self.operation,self.revalidate),
            lambda:self.store.approve(self.operation,exact_hash=self.bundle['plan_hash'],acknowledgments=store_fixture.ACKS,revalidate=self.revalidate),
        ):
            with self.subTest(entry=call),self.assertRaises(OperatorError):call()
        with self.locks() as locks:
            for call in (
                lambda:self.store.reserve(self.operation,locks,self.revalidate),
                lambda:self.store.before_mutation(self.operation,locks,self.revalidate),
            ):
                with self.subTest(entry=call),self.assertRaises(OperatorError):call()
        self.assertEqual(self.store.status(self.operation),original)
        self.assertEqual(self.store.bundle(self.operation),self.bundle)


if __name__=='__main__':unittest.main()
