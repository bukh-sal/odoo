"""Actual parser/routing; host adapters are mocked, no Docker or OS stores."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT/'packages/platform_sdk'),str(ROOT)]
from modular_platform.plans import data_digest


class CheckpointCLI(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        spec=importlib.util.spec_from_file_location('checkpoint_cli_under_test',ROOT/'tools/modular.py')
        self.cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.cli)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(self.cli,'configuration',return_value=Mock()))
        self.store=Mock();self.native=Mock();self.recovery=Mock()
        self.stack.enter_context(patch('modular_platform.operator_store.OperatorStore',return_value=self.store))
        self.native_factory=self.stack.enter_context(patch('modular_platform.native_executor.NativeExecutor',return_value=self.native))
        self.stack.enter_context(patch('modular_platform.completed_checkpoint.CompletedCheckpointRecovery',return_value=self.recovery))
        self.progress=self.stack.enter_context(patch('operation_progress.observe_execution',side_effect=AssertionError('No original operation progress row')))
        self.recovery_id='00000000-0000-4000-8000-000000000500'
        self.source='00000000-0000-4000-8000-000000000400'
        self.decision=dict(action='restore_completed_checkpoint',operation_id=self.recovery_id,checkpoint_operation_id=self.source)
        self.decision_path=self.root/'decision.json';self.decision_path.write_text(json.dumps(self.decision))
        self.recovery.prepare.return_value=self.decision
        self.recovery.prepare_continue.return_value=self.decision
        self.recovery.prepare_resume.return_value=self.decision
        for name in ('execute','continue_restore','resume','status','revoke_review'):
            getattr(self.recovery,name).return_value={'state':'fake-boundary'}

    def invoke(self,action,op=None,*options):
        args=['--config',str(self.root/'trust.json'),'plugin','checkpoint',action,op or self.recovery_id,
            '--store',str(self.root/'store'),'--deployment-config',str(self.root/'target.json'),
            '--catalog',str(self.root/'catalog'),*options]
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):code=self.cli.main(args)
        return code,out.getvalue(),err.getvalue()

    def test_prepare_actions_route_source_vs_recovery_without_original_operation_lookup(self):
        for action,method,op in [('prepare-restore','prepare',self.source),('prepare-continue','prepare_continue',self.recovery_id),
                ('prepare-resume','prepare_resume',self.recovery_id)]:
            with self.subTest(action=action):
                code,out,err=self.invoke(action,op)
                self.assertEqual((code,err),(0,''));self.assertEqual(json.loads(out)['decision_hash'],data_digest(self.decision))
                getattr(self.recovery,method).assert_called_once_with(op)
        self.store.bundle.assert_not_called();self.progress.assert_not_called()

    def test_execute_actions_use_exact_hash_and_do_not_create_original_progress(self):
        for action,method in [('restore','execute'),('continue','continue_restore'),('resume','resume')]:
            with self.subTest(action=action):
                code,_,err=self.invoke(action,None,'--decision',str(self.decision_path),'--decision-hash',data_digest(self.decision),'--noninteractive')
                self.assertEqual((code,err),(0,''))
                getattr(self.recovery,method).assert_called_once_with(self.decision,exact_hash=data_digest(self.decision),noninteractive=True)
        self.store.bundle.assert_not_called();self.progress.assert_not_called()

    def test_missing_review_foreign_id_and_nonterminal_interactive_refuse_before_execute(self):
        code,_,_=self.invoke('restore');self.assertEqual(code,2)
        code,_,_=self.invoke('restore',self.source,'--decision',str(self.decision_path),'--decision-hash',data_digest(self.decision),'--noninteractive')
        self.assertEqual(code,2)
        with patch('sys.stdin.isatty',return_value=False):
            code,_,_=self.invoke('restore',None,'--decision',str(self.decision_path),'--decision-hash',data_digest(self.decision))
        self.assertEqual(code,2);self.recovery.execute.assert_not_called()

    def test_noncanonical_id_refuses_before_constructing_native(self):
        code,_,_=self.invoke('status','../source');self.assertEqual(code,2)
        self.native_factory.assert_not_called()

    def test_status_and_review_revocation_have_distinct_routes(self):
        self.assertEqual(self.invoke('status')[0],0)
        self.recovery.status.assert_called_once_with(self.recovery_id)
        self.assertEqual(self.invoke('revoke-review',None,'--decision',str(self.decision_path),'--decision-hash',data_digest(self.decision),'--noninteractive')[0],0)
        self.recovery.revoke_review.assert_called_once_with(self.decision,exact_hash=data_digest(self.decision))


if __name__=='__main__':unittest.main()
