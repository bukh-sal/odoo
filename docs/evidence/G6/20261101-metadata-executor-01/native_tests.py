"""Shared executor ordering/fail-closed behavior with actual OS journal/locks."""
exec(compile(SOURCE_HELPERS,'qualified_metadata_helpers','exec'),globals())
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile,json
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError


class ExecutorTests(unittest.TestCase):
    setUp=ExternalMetadataTests.setUp
    tearDown=ExternalMetadataTests.tearDown
    site=ExternalMetadataTests.site
    payload=ExternalMetadataTests.payload
    apply=ExternalMetadataTests.apply
    row=ExternalMetadataTests.row

    def executor(self,data,folder,fault=None):
        bundle=data['bundle'];base=data['base_state'];config=copy.deepcopy(self.config);site=copy.deepcopy(self.site())
        trace=[];store=OperatorStore.initialize(Path(folder)/'control',{base['deployment_id']:base['site_ids']},allow_noninteractive=True)
        validate=lambda _:copy.deepcopy(base)
        operation=store.register(bundle,validate);store.approve(operation,exact_hash=bundle['plan_hash'],
            acknowledgments={'destructive':True,'trust_expansion':True,'permission_expansion':True},revalidate=validate,noninteractive=True)
        expected=copy.deepcopy(base);expected.update(release_lock=bundle['operation_lock']['release'],release_digest=bundle['plan']['target_release_digest'],
            bindings=bundle['operation_lock']['bindings'],endpoints=bundle['operation_lock']['endpoints'])
        rows={(r['installation_id'],r['workspace_id']):r for r in expected['installations']}
        features={(r['installation_id'],r['workspace_id']):r['availability'] for r in bundle['operation_lock'].get('feature_states',[])}
        for target in bundle['operation_lock']['targets']:
            key=target['installation_id'],target['workspace_id'];action=target['action']
            if action=='install':rows[key]={k:v for k,v in target.items() if k!='action'}|dict(state='installed',metadata_state='installed',feature_state=features[key])
            elif action=='unregister':rows[key].update(state='not_installed',metadata_state='removed',feature_state='suspended')
            elif action in ('enable','suspend'):rows[key]['feature_state']='enabled' if action=='enable' else 'suspended'
        expected['installations']=list(rows.values())
        class Scripted(ReferenceMetadataExecutor):
            def _runtime_preflight(self,bundle):trace.append('runtime_preflight')
            def _validate(self,**kwargs):return validate
            def mirror_progress(self,operation):pass
            def _topology(self):return 'app','database','edge'
            def _inspect(self,container):return {'State':{'Running':False,'ExitCode':0}}
            def _observer_for(self,configuration):
                return SimpleNamespace(config=configuration,external_reader=lambda:{},
                    read=lambda **kwargs:dict(runtime=RUNTIME,sites=[site]),state=lambda obs,cat:dict(state=copy.deepcopy(expected if self.executed else base)))
            def _dispatch(self):
                def run(action,op,directory,**kwargs):
                    trace.append('dispatch_'+action)
                    if action=='enable':
                        assert store.status(operation)['traffic_resumed']
                        return dict(dispatch_enabled=True)
                    return dict(after={'profile':'fixture','state_digest':'sha256:'+'a'*64})
                return SimpleNamespace(present=lambda **kwargs:True,require_runtime=lambda runtime:None,run=run,
                    require_profile=lambda value,**kwargs:value,inspect=lambda **kwargs:{'profile':'fixture','state_digest':'sha256:'+'a'*64},
                    reconcile_jobs=lambda *args,**kwargs:dict(resume_allowed=True))
            def _checkpoint(self,op,bundle,database,directory):
                trace.append('checkpoint');path=store.root/'checkpoints'/op;path.mkdir(parents=True)
                (path/'manifest.json').write_text(json.dumps(dict(previous_release=base)))
                return op
            def _child(self,operation,suffix,**kwargs):return ['docker','run','fixture'],suffix
            def _private_command(self,arguments,log,**kwargs):
                self_test.assertEqual(arguments[-2:],['-m','modular_platform.external_metadata'])
                payload=json.loads(kwargs['input']);self_test.assertEqual(payload['base_state'],base)
                self_test.assertEqual(store.status(operation)['phase'],'mutation_started')
                self.executed=True;self.calls+=1;trace.append('metadata')
                if fault=='after_metadata':raise RuntimeError('injected uncertain metadata exit')
                log.write_text(json.dumps(dict(metadata_published=True,operation_id=str(uuid4()) if fault=='wrong_result' else operation,
                    native_maintenance=False,runtime_control=False)))
            def _replace_workers(self,app,bundle,directory):
                trace.append('replace_workers')
                target={**config,'generation':bundle['operation_lock']['release']['generation'],
                    'release_created_at':bundle['operation_lock']['release']['created_at'],'published_release':bundle['operation_lock']['release']}
                return 'app-new',target
            def _prepare_assets(self,*args,**kwargs):trace.append('assets')
        self_test=self;native=Scripted.__new__(Scripted);native.executed=False;native.calls=0
        native.store=store;native.config=config;native.catalog_root=Path(folder)/'catalog';native.validator=None
        native.target_path=store.root/'target.json';native.target_path.write_text(json.dumps(config));native.observer=native._observer_for(config)
        def docker(arguments,**kwargs):
            trace.append(' '.join(arguments))
            if arguments[:2]==['docker','exec']:return b'0'
            if fault=='traffic' and arguments[:3]==['docker','start','edge']:raise RuntimeError('injected ingress exit')
            return b''
        self.enterContext(patch('modular_platform.native_executor._run',side_effect=docker))
        self.enterContext(patch('modular_platform.native_executor.Catalog',return_value=SimpleNamespace(snapshot=lambda:copy.deepcopy(self.catalog))))
        self.enterContext(patch('modular_platform.metadata_executor.read_metadata',return_value=site))
        self.enterContext(patch('modular_platform.workers.wait_ready',return_value=None))
        self.enterContext(patch('modular_platform.profile_channel.publish_profile',return_value=dict(profile_published=True)))
        return native,operation,trace

    def test_metadata_registration_uses_shared_checkpoint_publication_and_resume_loop(self):
        data=self.payload('install')
        with tempfile.TemporaryDirectory() as folder:
            native,operation,trace=self.executor(data,folder);result=native.apply(operation)
            self.assertEqual(result['state'],'completed');self.assertTrue(result['traffic_resumed'])
            self.assertEqual(native.calls,1)
            self.assertLess(trace.index('dispatch_fence'),trace.index('checkpoint'))
            self.assertLess(trace.index('checkpoint'),trace.index('metadata'))
            self.assertLess(trace.index('metadata'),trace.index('dispatch_enable'))
            self.assertEqual(native.apply(operation)['state'],'completed');self.assertEqual(native.calls,1)

    def test_external_enable_suspend_and_unregister_use_same_full_loop(self):
        self.apply('install')
        for action in ['enable','suspend','unregister']:
            if action=='unregister':self.external['endpoints'][0].update(state='revoked',generation=2)
            data=self.payload(action)
            with self.subTest(action=action),tempfile.TemporaryDirectory() as folder:
                native,operation,trace=self.executor(data,folder)
                self.assertEqual(native.apply(operation)['state'],'completed')
                self.assertIn('checkpoint',trace)

    def test_uncertain_metadata_exit_is_recovery_required_without_replay(self):
        data=self.payload('install')
        with tempfile.TemporaryDirectory() as folder:
            native,operation,trace=self.executor(data,folder,'after_metadata')
            with self.assertRaisesRegex(RuntimeError,'uncertain metadata'):native.apply(operation)
            self.assertEqual(native.store.status(operation)['state'],'recovery_required')
            self.assertFalse(native.store.status(operation)['traffic_resumed'])
            self.assertNotIn('dispatch_enable',trace)
            with self.assertRaises(OperatorError):native.apply(operation)
            self.assertEqual(native.calls,1)

    def test_ingress_uncertainty_keeps_durable_traffic_fence(self):
        data=self.payload('install')
        with tempfile.TemporaryDirectory() as folder:
            native,operation,trace=self.executor(data,folder,'traffic')
            with self.assertRaisesRegex(RuntimeError,'ingress exit'):native.apply(operation)
            status=native.store.status(operation);self.assertEqual(status['state'],'recovery_required');self.assertTrue(status['traffic_resumed'])
            self.assertEqual(native.calls,1)

    def test_successful_exit_with_wrong_operation_result_keeps_traffic_closed(self):
        data=self.payload('install')
        with tempfile.TemporaryDirectory() as folder:
            native,operation,trace=self.executor(data,folder,'wrong_result')
            with self.assertRaisesRegex(OperatorError,'result differs'):native.apply(operation)
            status=native.store.status(operation);self.assertEqual(status['state'],'recovery_required');self.assertFalse(status['traffic_resumed'])
            self.assertNotIn('dispatch_enable',trace)


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExecutorTests));CONNECTION.rollback()
print('MP_METADATA_EXECUTOR='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,
    errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures],original_rows_restored=True)))
raise SystemExit(0 if result.wasSuccessful() else 1)
