"""Coordinated native feature selection and conservative legacy compatibility."""
import copy,sys,unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
from contextlib import nullcontext
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_feature_executor as fixture
from test_resolution import ENVIRONMENT
from test_plans import PROVENANCE,ident,STAMP
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.native_feature_executor import NativeFeatureExecutor
from modular_platform.feature_executor import FeatureExecutor
from modular_platform.operator_store import OperatorStore,_steps,STEPS,FEATURE_STEPS
from modular_platform.operator_os import OperatorError,OperationLocks
from modular_platform.plans import check_bundle


class NativeFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.FeatureJournal();self.f.setUp()
        self.document=dict(state=self.f.state,environment=ENVIRONMENT,provenance=PROVENANCE,python_metadata=[])
        self.site=dict(site_id=ident(20),workspaces=[dict(workspace_id=ident(30),state='active')],grants=[])
        self.bundle=prepare_current_feature(self.document,[self.site],self.f.catalog,targets=[self.f.target],
            operation_type='suspend',operation_id=ident(500),created_at=STAMP)
        self.native=NativeFeatureExecutor.__new__(NativeFeatureExecutor)
        self.native.config=dict(published_release=self.f.state['release_lock'])
        self.native.store=Mock();self.native.store.bundle.return_value=self.bundle
        self.native.store.root=Path('unused-control')
        self.native.store.status.return_value=dict(state='approved',mutation_started=False)
        self.native.observer=Mock();self.native.observer.read.return_value=dict(runtime=dict(inventory=dict(files={})))

    def test_new_plan_uses_full_checkpoint_sequence_without_changing_release(self):
        check_bundle(self.bundle,self.f.state)
        self.assertTrue(self.bundle['plan']['backup']['required']);self.assertTrue(self.bundle['display']['restart_required'])
        self.assertEqual(_steps(self.bundle['plan']),STEPS)
        self.assertEqual(self.bundle['operation_lock']['release'],self.f.state['release_lock'])
        self.assertEqual(_steps(self.f.bundle['plan']),FEATURE_STEPS)

    def test_adapter_skips_native_maintenance_and_refuses_wrong_profile(self):
        self.assertIsNone(self.native._native_flags(self.bundle,{}))
        for case in ['no_backup','external','staged','wrong_action']:
            value=copy.deepcopy(self.bundle)
            if case=='no_backup':value['plan']['backup']['required']=False
            elif case=='external':value['plan']['artifacts'][0]['runtime']='external_service'
            elif case=='staged':value['operation_lock']['staged_image']={}
            else:value['operation_lock']['targets'][0]['action']='upgrade'
            with self.subTest(case=case),self.assertRaises(OperatorError):self.native._check_operation(value)

    def test_old_image_refused_before_reserve_or_drain(self):
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext(Mock())):
            with self.assertRaisesRegex(OperatorError,'compatible independently staged'):self.native.apply(ident(500))
        self.native.store.reserve.assert_not_called()

    def test_changed_release_refused_before_image_inspection(self):
        self.native.config['published_release']=dict(self.f.state['release_lock'],generation=99)
        with self.assertRaisesRegex(OperatorError,'cannot change'):self.native._runtime_preflight(self.bundle)
        self.native.observer.read.assert_not_called()

    def test_legacy_executor_refuses_queue_bearing_plan_before_reservation(self):
        self.native.store.bundle.return_value=self.f.bundle
        self.native.store.status.return_value=dict(state='approved')
        with patch('modular_platform.feature_executor.OperationLocks',return_value=nullcontext(Mock())),patch('modular_platform.dispatch_operator.DispatchMaintenance') as helper:
            helper.return_value.present.return_value=True
            with self.assertRaisesRegex(OperatorError,'fresh checkpointed'):FeatureExecutor(self.native).apply(ident(500))
        self.native.store.reserve.assert_not_called()

    def test_new_native_feature_journal_requires_checkpoint_and_preserves_traffic_fence(self):
        with tempfile.TemporaryDirectory() as folder:
            store=OperatorStore.initialize(Path(folder)/'control',{self.f.state['deployment_id']:self.f.state['site_ids']})
            validate=lambda bundle:copy.deepcopy(self.f.state)
            operation=store.register(self.bundle,validate)
            store.approve(operation,exact_hash=self.bundle['plan_hash'],
                acknowledgments=dict(destructive=False,trust_expansion=False,permission_expansion=False),revalidate=validate)
            with OperationLocks(store.root/'locks',self.f.state['deployment_id'],self.f.state['site_ids']) as locks:
                store.reserve(operation,locks,validate)
                for phase in ['staged','maintenance','drained']:store.advance(operation,locks,phase)
                with self.assertRaises(OperatorError):store.before_mutation(operation,locks,validate)
                store.advance(operation,locks,'checkpointed',backup_id='source-fixture-not-real-backup')
                store.before_mutation(operation,locks,validate)
                self.assertFalse(store.status(operation)['traffic_resumed'])
                for phase in ['migrated','workers_replaced','ready','release_published','traffic_resumed','completed']:store.advance(operation,locks,phase)
            self.assertEqual(store.status(operation)['state'],'completed')
            self.assertTrue(store.status(operation)['traffic_resumed'])


if __name__=='__main__':unittest.main()
