"""Partial native restore must bind current state and never replay its dump."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'))
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.restore_continuation import RestoreContinuation,canonical_dump_digest
from modular_platform.restore_executor import RestoreExecutor


class RestoreContinuationTests(unittest.TestCase):
    def test_dump_digest_ignores_only_generated_psql_guards_and_comments(self):
        a=b'-- generated date\n\\restrict abc\nCOPY x FROM stdin;\nvalue\n\\.\n\\unrestrict abc\n'
        b=a.replace(b'generated date',b'different date').replace(b'abc',b'xyz')
        self.assertEqual(canonical_dump_digest(a),canonical_dump_digest(b))
        self.assertNotEqual(canonical_dump_digest(a),canonical_dump_digest(a.replace(b'value',b'changed')))

    def test_completed_or_unknown_partial_phase_cannot_be_adopted(self):
        with tempfile.TemporaryDirectory() as folder:
            recovery=Mock();recovery.store.root=Path(folder);recovery._restore_state.return_value={}
            target=Path(folder)/'recoveries'/'operation';target.mkdir(parents=True);(target/'result.json').write_text('{}')
            with self.assertRaises(OperatorError):RestoreContinuation(recovery).state('operation')
            recovery._complete_restore.assert_not_called()

    def continuation(self,root):
        recovery=Mock();recovery.store.root=root;recovery.store.policy={'allow_noninteractive':True}
        recovery.store.bundle.return_value={'plan':dict(deployment_id='deployment',site_ids=['site'])}
        recovery.config={'sites':[{'database':'failed'}]};recovery._authority.return_value=({'native_auth_digest':'current'},'private')
        directory=root/'checkpoints'/'operation';directory.mkdir(parents=True);(directory/'manifest.json').write_text('{}')
        value=RestoreContinuation(recovery)
        value.state=Mock(return_value=dict(action='restore_to_fresh_database',operation_id='operation',fresh_database='fresh',authority={'native_auth_digest':'current'},continuation={'restored_database_digest':'exact'}))
        decision=dict(copy.deepcopy(value.state.return_value),review=dict(review_id='review'))
        return recovery,value,decision

    def test_changed_target_snapshot_refuses_before_journal_or_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            recovery,value,decision=self.continuation(Path(folder))
            reviews=Mock();reviews.verify.side_effect=OperatorError('Target changed')
            with patch('modular_platform.restore_continuation.OperationLocks'),patch('modular_platform.restore_continuation.RecoveryReviews',return_value=reviews):
                with self.assertRaises(OperatorError):value.execute(decision,exact_hash=data_digest(decision))
            self.assertNotIn('review',reviews.verify.call_args.kwargs['current_payload'])
            recovery.store.record_restore.assert_not_called();recovery._complete_restore.assert_not_called()

    def test_exact_continuation_only_calls_existing_completion_on_same_target(self):
        with tempfile.TemporaryDirectory() as folder:
            recovery,value,decision=self.continuation(Path(folder))
            with patch('modular_platform.restore_continuation.OperationLocks'),patch('modular_platform.restore_continuation.RecoveryReviews'),patch('modular_platform.restore_continuation.protect_directory',side_effect=lambda p:(p.mkdir(parents=True,exist_ok=True) or p)),patch('modular_platform.restore_continuation._run') as run:
                value.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
            run.assert_not_called()
            recovery._complete_restore.assert_called_once()
            kwargs=recovery._complete_restore.call_args.kwargs
            self.assertEqual(kwargs['fresh'],'fresh')
            self.assertEqual(kwargs['dispatch_directory'],Path(folder)/'recoveries'/'operation'/'continuations'/'review')
            self.assertEqual(kwargs['private_native_auth'],'private')

    def test_authority_change_after_review_refuses_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            recovery,value,decision=self.continuation(Path(folder));recovery._authority.return_value=({'native_auth_digest':'changed'},'private')
            with patch('modular_platform.restore_continuation.OperationLocks'),patch('modular_platform.restore_continuation.RecoveryReviews'),patch('modular_platform.restore_continuation.protect_directory',side_effect=lambda p:(p.mkdir(parents=True,exist_ok=True) or p)):
                with self.assertRaises(OperatorError):value.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
            recovery._complete_restore.assert_not_called()

    def test_restored_fence_uses_review_specific_child_namespace(self):
        recovery=object.__new__(RestoreExecutor);recovery.config={};recovery._supported_effects=Mock();recovery.native=Mock()
        helper=Mock();helper.run.side_effect=RuntimeError('Stop after inspected fence call')
        decision=dict(operation_id='same-operation',restore_configuration={'sites':[{'database':'source'}]},restored_release_lock={'generation':5},review=dict(review_id='fresh-review'))
        manifest=dict(dispatch_profile=dict(control=dict(release_digest='prior-tag')))
        with patch('modular_platform.dispatch_operator.DispatchMaintenance',return_value=helper):
            with self.assertRaisesRegex(RuntimeError,'Stop after'):
                recovery._complete_restore(decision,exact_hash='hash',locks=Mock(),directory=Path('restore'),checkpoint=Path('checkpoint'),manifest=manifest,fresh='fresh',private_native_auth='private')
        self.assertEqual(helper.run.call_args.kwargs['review_id'],'fresh-review')
        self.assertEqual(helper.run.call_args.kwargs['control_release'],'prior-tag')
        self.assertEqual(helper.run.call_args.kwargs['configuration']['sites'][0]['database'],'fresh')
