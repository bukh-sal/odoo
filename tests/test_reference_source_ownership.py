"""Generic SDK source ownership and optional reference-host composition."""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'tests')]
from modular_platform.dispatch_lifecycle import DispatchLifecycleError,reference_policy
from reference_operator.dispatch import ReferenceDispatchMaintenance
from modular_platform.worker_publication import DockerWorkerObservation
from modular_platform.native_executor import NativeExecutor,StagedNativeExecutor
from modular_platform.native_feature_executor import NativeFeatureExecutor
from modular_platform.restore_executor import RestoreExecutor
from reference_operator.executor import ReferenceNativeExecutor,ReferenceStagedNativeExecutor,ReferenceMetadataExecutor,ReferenceNativeFeatureExecutor,ReferenceRestoreExecutor


class ReferenceSourceOwnershipTests(unittest.TestCase):
    def test_sdk_reference_modules_are_absent(self):
        base=ROOT/'packages/platform_sdk/modular_platform'
        for name in ('reference_dispatch.py','reference_recovery.py','worker_transition.py','metadata_executor.py'):
            self.assertFalse((base/name).exists(),name)

    def test_generic_sdk_has_no_fixed_reference_lifecycle_or_worker_identity(self):
        projection=(ROOT/'packages/platform_sdk/modular_platform/dispatch_lifecycle.py').read_text(encoding='utf8')
        self.assertNotIn('document_stats',projection)
        self.assertNotIn('r1-reference',projection)
        self.assertNotIn('_reference(',projection)
        worker=(ROOT/'packages/platform_sdk/modular_platform/worker_publication.py').read_text(encoding='utf8')
        self.assertNotIn('services.document_stats.server',worker)
        self.assertNotIn("'document-stats'",worker)
        for name in ('reference_dispatch','reference_recovery','worker_transition','metadata_executor'):
            self.assertNotIn(name,worker)
            for path in (ROOT/'packages/platform_sdk/modular_platform').glob('*.py'):
                self.assertNotIn('from .'+name,path.read_text(encoding='utf8'),str(path))

    def test_optional_executor_classes_extend_generic_mro_and_keep_metadata_signature(self):
        import inspect
        self.assertTrue(issubclass(ReferenceNativeExecutor,NativeExecutor))
        self.assertTrue(issubclass(ReferenceStagedNativeExecutor,StagedNativeExecutor))
        self.assertTrue(issubclass(ReferenceNativeFeatureExecutor,NativeFeatureExecutor))
        self.assertTrue(issubclass(ReferenceMetadataExecutor,ReferenceNativeExecutor))
        self.assertTrue(issubclass(ReferenceRestoreExecutor,RestoreExecutor))
        self.assertEqual(list(inspect.signature(NativeExecutor._publish_metadata).parameters),['self','bundle','payload','directory','image'])
        self.assertEqual(list(inspect.signature(ReferenceMetadataExecutor._publish_metadata).parameters),['self','bundle','payload','directory','image'])
        self.assertEqual(list(inspect.signature(ReferenceNativeFeatureExecutor._publish_metadata).parameters),['self','bundle','payload','directory','image'])

    def test_reference_unchanged_recovery_helper_binds_actual_native(self):
        from types import SimpleNamespace
        from tempfile import TemporaryDirectory
        from reference_operator.executor import ReferenceUnchangedRecovery
        with TemporaryDirectory() as tmp:
            config=dict(project='mp-r0-r1review',deployment_id='00000000-0000-4000-8000-000000000001',
                sites=[dict(site_id='00000000-0000-4000-8000-000000000002',database='mp_disposable_r0_r1_review')],
                published_release=dict(plugins=[dict(runtime='external_service')]))
            native=SimpleNamespace(config=config,store=SimpleNamespace(root=Path(tmp)),observer=object(),
                target_path=Path(tmp)/'target.json',catalog_root=Path(tmp)/'catalog')
            recovery=ReferenceUnchangedRecovery(native);helper=recovery._dispatch()
            self.assertIs(helper.native,native);self.assertIsNot(helper.native,recovery)

    def test_native_reference_consumer_accepts_exact_three_key_scope_and_checkpoint_profile(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from modular_platform.native_uninstall import require_dispatch_snapshot
        expected={'profile':'r1-reference-stateless-dispatch-v1','control':{'state':'paused'},'active_credentials':0,
            'api_keys':0,'uncertain_jobs':0,'external_installations':1}
        expected['state_digest']=__import__('modular_platform.plans',fromlist=['data_digest']).data_digest(expected)
        scope={'site_id':'00000000-0000-4000-8000-000000000001','release_digest':'sha256:'+'a'*64,
            'reference':{'profile':'r1-reference-stateless-dispatch-v1','registrations':[{}]}}
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        class Connection:
            def cursor(self):return Cursor()
        with patch('modular_platform.dispatch_lifecycle.observe',return_value=expected):
            self.assertEqual(require_dispatch_snapshot(Connection(),expected,scope),expected)

    def test_optional_metadata_child_source_is_composed_only_for_reference(self):
        from reference_operator.executor import ReferenceMetadataExecutor
        helper=ReferenceMetadataExecutor.__new__(ReferenceMetadataExecutor)
        helper.config={'published_release':{'plugins':[{'runtime':'external_service'}]}}
        source=helper._metadata_script('uninstall_metadata.py','print(1)')
        self.assertIn('reference_operator.lifecycle_reference',source)
        self.assertIn('print(1)',source)
        generic=ReferenceMetadataExecutor.__new__(ReferenceMetadataExecutor)
        generic.config={'published_release':{'plugins':[]}}
        self.assertEqual(generic._metadata_script('uninstall_metadata.py','print(1)'),'print(1)')

    def test_native_uninstall_launch_uses_private_source_composition(self):
        source=(ROOT/'packages/platform_sdk/modular_platform/native_executor.py').read_text(encoding='utf8')
        launches=[node for node in ast.walk(ast.parse(source))
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
            and node.func.attr=='_private_command'
            and any(isinstance(value,ast.Constant) and value.value=='native_uninstall.py'
                    for value in ast.walk(node))]
        self.assertEqual(len(launches),1)
        self.assertTrue(any(isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute)
            and value.func.attr=='_metadata_script' for value in ast.walk(launches[0])))

    def test_composed_native_child_validator_matches_reference_snapshot_consumer(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import modular_platform.dispatch_lifecycle as lifecycle
        from modular_platform.plans import data_digest
        from reference_operator.executor import ReferenceNativeExecutor
        site='00000000-0000-4000-8000-000000000001'
        policy=dict(profile='r1-reference-stateless-v1',site_id=site,
            runtime_image='modular-document-stats@sha256:'+'a'*64,
            publication_digest='sha256:'+'b'*64,registrations=[])
        class Cursor:
            def execute(self,*args):pass
            def fetchall(self):return []
        native=ReferenceNativeExecutor.__new__(ReferenceNativeExecutor)
        native.config={'published_release':{'plugins':[{'runtime':'external_service'}]}}
        script=(ROOT/'packages/platform_sdk/modular_platform/native_uninstall.py').read_text(encoding='utf8')
        with patch.dict(lifecycle.__dict__,dict(lifecycle.__dict__),clear=True):
            namespace={'__name__':'verified_test_native_child'}
            exec(compile(native._metadata_script('native_uninstall.py',script),
                         'verified_test_native_child','exec'),namespace)
            self.assertIn('require_dispatch_snapshot',namespace)
            scope=SimpleNamespace(reference=policy,site_id=site)
            verdict=lifecycle.reference_policy(Cursor(),scope)
            self.assertEqual(verdict['profile'],'r1-reference-stateless-dispatch-v1')
            snapshot=dict(profile=verdict['profile'],reference_policy_digest=verdict['digest'],
                external_installations=0,active_credentials=0,api_keys=0,uncertain_jobs=0,
                control={'state':'paused'})
            snapshot['state_digest']=data_digest(snapshot)
            helper=ReferenceDispatchMaintenance.__new__(ReferenceDispatchMaintenance)
            helper.policies={data_digest(policy):policy}
            self.assertEqual(helper.require_profile(snapshot,closed=True),snapshot)
            bad=dict(policy,runtime_image='unapproved@sha256:'+'a'*64)
            with self.assertRaises(DispatchLifecycleError):
                lifecycle.reference_policy(Cursor(),SimpleNamespace(reference=bad,site_id=site))
        with self.assertRaises(DispatchLifecycleError):
            lifecycle.reference_policy(Cursor(),SimpleNamespace(reference=policy,site_id=site))

    def test_default_generic_reference_policy_is_closed(self):
        with self.assertRaises(DispatchLifecycleError):reference_policy(object(),object())

    def test_optional_dispatch_extends_private_source_and_compiles(self):
        helper=ReferenceDispatchMaintenance.__new__(ReferenceDispatchMaintenance)
        source=helper._lifecycle_source()
        self.assertIn('def reference_policy',source)
        self.assertIn('document_stats',source)
        self.assertIn('def observe',source)
        compile(source,'reference-composed-lifecycle','exec')

    def test_generic_worker_policy_requires_all_explicit_fields(self):
        legacy=dict(project='p',service='document-stats',network='n',public_config_volume='v',
            image='modular-document-stats@sha256:'+'a'*64,destination='http://document-stats:8080')
        with self.assertRaises(Exception):DockerWorkerObservation(legacy)
        explicit=dict(legacy,entrypoint=['/venv/bin/python','-m','x'],command=['--config','x'],network_alias='document-stats')
        DockerWorkerObservation(explicit)


if __name__=='__main__':
    unittest.main()
