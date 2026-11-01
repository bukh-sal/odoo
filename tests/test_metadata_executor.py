"""Metadata adapter boundaries; full real journal/PG coverage lives in G6."""
import copy,hashlib,json,sys,tempfile,unittest
import importlib.util,io
from pathlib import Path
from unittest.mock import Mock,patch
from contextlib import nullcontext,redirect_stdout,redirect_stderr
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_external_planning as fixtures
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.native_executor import verify_native_state
from modular_platform.operator_os import OperatorError


class MetadataExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ExternalPlanning.setUpClass()

    def setUp(self):
        self.f=fixtures.ExternalPlanning();self.f.setUp();self.f.unregistered();self.bundle=self.f.prepare('install')
        self.native=ReferenceMetadataExecutor.__new__(ReferenceMetadataExecutor)
        self.native.config={**self.f.f.config,'project':'mp-r0-r1metadataunit'}
        self.native.store=Mock();self.native.store.root=Path('unused-control');self.native.store.bundle.return_value=self.bundle
        self.native.observer=Mock();self.native.mirror_progress=Mock()

    def test_only_checkpointed_metadata_without_staged_image_is_accepted(self):
        self.native._check_operation(self.bundle);self.assertIsNone(self.native._native_flags(self.bundle,{}))
        for mutation in ['native','no_backup','staged','unsupported']:
            bundle=copy.deepcopy(self.bundle)
            if mutation=='native':bundle['plan']['artifacts'][0]['runtime']='native'
            elif mutation=='no_backup':bundle['plan']['backup']['required']=False
            elif mutation=='staged':bundle['operation_lock']['staged_image']={}
            else:bundle['plan']['operation_type']='remove'
            with self.subTest(mutation=mutation),self.assertRaises(OperatorError):self.native._check_operation(bundle)

    def test_unready_runtime_is_refused_before_reservation_or_mutation(self):
        self.native.store.status.return_value=dict(state='approved',mutation_started=False)
        self.native.observer.read.return_value={'runtime':self.f.f.runtime}
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('locks')):
            with self.assertRaisesRegex(OperatorError,'immutable image'):self.native.apply(self.bundle['plan']['operation_id'])
        self.native.store.reserve.assert_not_called()

    def test_current_exact_component_hashes_are_required(self):
        runtime=copy.deepcopy(self.f.f.runtime)
        names=['metadata_executor','external_metadata','external_planning','native_executor','dispatch_lifecycle','dispatch_operator',
            'dispatch_maintenance','reference_dispatch','operator_store','projection','planning_cli','plans']
        for name in names:runtime['inventory']['files']['packages/platform_sdk/modular_platform/'+name+'.py']=hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform'/f'{name}.py').read_bytes()).hexdigest()
        self.native.observer.read.return_value=dict(runtime=runtime);self.native._runtime_preflight(self.bundle)
        runtime['inventory']['files']['packages/platform_sdk/modular_platform/external_metadata.py']='0'*64
        with self.assertRaises(OperatorError):self.native._runtime_preflight(self.bundle)

    def test_completed_replay_and_lost_executor_do_not_observe_current_runtime(self):
        self.native.observer.read.side_effect=AssertionError('Must not inspect before journal classification')
        with patch('modular_platform.native_executor.OperationLocks',return_value=nullcontext('locks')):
            self.native.store.status.return_value=dict(state='completed',mutation_started=True)
            self.assertEqual(self.native.apply(self.bundle['plan']['operation_id'])['state'],'completed')
            self.native.store.status.return_value=dict(state='running',mutation_started=True)
            self.native.store.reserve.side_effect=OperatorError('recovery_required')
            with self.assertRaisesRegex(OperatorError,'recovery_required'):self.native.apply(self.bundle['plan']['operation_id'])
        self.native.observer.read.assert_not_called()

    def test_publisher_uses_fixed_module_and_checkpoint_base(self):
        with tempfile.TemporaryDirectory() as folder:
            self.native.store.root=Path(folder);checkpoint=Path(folder)/'checkpoints'/self.bundle['plan']['operation_id']
            checkpoint.mkdir(parents=True);(checkpoint/'manifest.json').write_text(json.dumps(dict(previous_release=self.f.document['state'])))
            self.native._child=Mock(return_value=(['docker','run','image'],'test-child'));self.native._private_command=Mock()
            self.native._private_command.side_effect=lambda args,log,**kwargs:log.write_text(json.dumps(dict(metadata_published=True,operation_id=self.bundle['plan']['operation_id'],native_maintenance=False,runtime_control=False)))
            metadata=copy.deepcopy(self.f.f.site)
            with patch('modular_platform.metadata_executor.read_metadata',return_value=metadata):
                self.native._publish_metadata(self.bundle,dict(plugins={}),Path(folder),self.native.config['image_id'])
            args,kwargs=self.native._private_command.call_args
            self.assertEqual(args[0][-2:],['-m','modular_platform.external_metadata'])
            data=json.loads(kwargs['input']);self.assertEqual(data['base_state'],self.f.document['state']);self.assertEqual(data['bundle'],self.bundle)

    def test_metadata_readiness_covers_feature_and_retained_unregistration(self):
        previous=copy.deepcopy(self.f.document['state']);target=self.bundle['operation_lock']['targets'][0]
        state=copy.deepcopy(previous);state.update(release_digest=self.bundle['plan']['target_release_digest'],bindings=self.bundle['operation_lock']['bindings'],endpoints=self.bundle['operation_lock']['endpoints'])
        state['installations'].append({k:v for k,v in target.items() if k!='action'}|dict(state='installed',metadata_state='installed',feature_state='suspended'))
        verify_native_state(self.bundle,state,previous,dict(sites=[self.f.f.site]))
        state['installations'][-1]['feature_state']='enabled'
        with self.assertRaises(OperatorError):verify_native_state(self.bundle,state,previous,dict(sites=[self.f.f.site]))
        state['installations'][-1]['feature_state']='suspended';state['endpoints']=[]
        with self.assertRaisesRegex(OperatorError,'endpoints'):verify_native_state(self.bundle,state,previous,dict(sites=[self.f.f.site]))

    def test_replacement_preserves_release_timestamp_for_unchanged_feature_epoch(self):
        bundle=copy.deepcopy(self.bundle);bundle['operation_lock']['release']['created_at']='2026-10-31T00:00:00Z'
        self.native.observer.read.return_value=dict(runtime=self.f.f.runtime)
        with tempfile.TemporaryDirectory() as folder,patch('modular_platform.workers.ensure',return_value='a'*64),patch('modular_platform.native_executor._run'):
            app,target=self.native._replace_workers('old-app',bundle,Path(folder))
        self.assertEqual(target['release_created_at'],'2026-10-31T00:00:00Z')

    def test_cli_external_feature_uses_full_metadata_adapter(self):
        spec=importlib.util.spec_from_file_location('metadata_cli_under_test',ROOT/'tools/modular.py')
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        bundle=copy.deepcopy(self.bundle);bundle['plan']['operation_type']='enable'
        store=Mock();store.bundle.return_value=bundle;executor=Mock();executor.apply.return_value=dict(state='completed')
        with tempfile.TemporaryDirectory() as folder:
            trust=Path(folder)/'trust.json';trust.write_text(json.dumps(dict(schema_version=1,mode='development',approved_digests=[],allow_unsigned_development=True,generation=1)))
            args=['--config',str(trust),'plugin','apply',bundle['plan']['operation_id'],'--store',str(Path(folder)/'control'),
                '--deployment-config',str(Path(folder)/'target.json'),'--catalog',str(Path(folder)/'catalog')]
            with patch('modular_platform.operator_store.OperatorStore',return_value=store),patch('modular_platform.metadata_executor.ReferenceMetadataExecutor',return_value=executor),\
                    patch('modular_platform.feature_executor.FeatureExecutor',side_effect=AssertionError('Metadata must not use legacy short feature execution')),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(args),0)
        executor.apply.assert_called_once_with(bundle['plan']['operation_id'])


if __name__=='__main__':unittest.main()
