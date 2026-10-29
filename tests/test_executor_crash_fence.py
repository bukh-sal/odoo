"""Lost-executor reconciliation must precede any running-app or stage lookup."""
from contextlib import nullcontext
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.native_executor import NativeExecutor,StagedNativeExecutor
from modular_platform.operator_os import OperatorError


class ExecutorCrashFenceTests(unittest.TestCase):
    def executor(self,*,staged=False,started=True,completed=False):
        native=(StagedNativeExecutor if staged else NativeExecutor).__new__(StagedNativeExecutor if staged else NativeExecutor)
        native.store=Mock();native.store.root=Path('unused-private-store')
        native.store.bundle.return_value={'plan':{'operation_type':'remove' if staged else 'uninstall','deployment_id':'test','site_ids':['site']},'operation_lock':{'staged_image':{}} if staged else {}}
        native.store.status.return_value={'state':'completed' if completed else ('running' if started else 'approved'),'mutation_started':started}
        native.store.reserve.side_effect=OperatorError('recovery_required: previous executor may have committed')
        native.observer=Mock();native.observer.read.side_effect=AssertionError('running application was observed before crash reconciliation')
        native._validate=Mock(return_value=object());native.mirror_progress=Mock()
        return native

    def test_current_image_stopped_app_does_not_mask_possible_commit(self):
        native=self.executor()
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('held-locks')):
            with self.assertRaisesRegex(OperatorError,'recovery_required'):native.apply('operation')
        native.store.reserve.assert_called_once()
        self.assertEqual(native.store.reserve.call_args.args[:2],('operation','held-locks'))
        native._validate.assert_not_called()
        native.observer.read.assert_not_called()

    def test_staged_removal_stale_stage_does_not_mask_possible_commit(self):
        native=self.executor(staged=True)
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('held-locks')):
            with self.assertRaisesRegex(OperatorError,'recovery_required'):native.apply('operation')
        native.store.reserve.assert_called_once();native.observer.read.assert_not_called()

    def test_completed_replay_remains_read_only_without_running_app(self):
        native=self.executor(completed=True)
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('held-locks')):
            result=native.apply('operation')
        self.assertEqual(result['state'],'completed');native.store.reserve.assert_not_called();native.observer.read.assert_not_called()

    def test_started_operation_cannot_fall_through_even_if_reservation_returns(self):
        native=self.executor();native.store.reserve.side_effect=None
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('held-locks')):
            with self.assertRaisesRegex(OperatorError,'explicit reconciliation'):native.apply('operation')
        native.observer.read.assert_not_called();native._validate.assert_not_called()

    def test_fresh_operation_still_requires_compatible_runtime_before_reservation(self):
        native=self.executor(started=False);native.observer.read.side_effect=None;native.observer.read.return_value={'runtime':{'published_release_protocol':0}}
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('held-locks')):
            with self.assertRaisesRegex(OperatorError,'compatible candidate'):native.apply('operation')
        native.store.reserve.assert_not_called();native.observer.read.assert_called_once()


if __name__=='__main__':unittest.main()
