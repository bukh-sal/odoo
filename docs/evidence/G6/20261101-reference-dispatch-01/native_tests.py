"""Typed reference profile on real owned PG; all table mutations roll back."""
exec(compile(SOURCE_HELPERS,'qualified_metadata_helpers','exec'),globals())
from modular_platform import dispatch_lifecycle as lifecycle
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.operator_os import OperatorError,OperationLocks
from modular_platform.operator_store import OperatorStore
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.contracts import plan_hash
from modular_platform.plans import _display
from pathlib import Path
import tempfile
import types,json
from types import SimpleNamespace
from unittest.mock import patch


class ReferenceDispatchTests(unittest.TestCase):
    setUp=ExternalMetadataTests.setUp
    tearDown=ExternalMetadataTests.tearDown
    site=ExternalMetadataTests.site
    payload=ExternalMetadataTests.payload
    apply=ExternalMetadataTests.apply
    row=ExternalMetadataTests.row

    def scope(self):
        site=self.site();rows=[]
        for row in site['installations']:
            if row['runtime']=='native':continue
            rows.append(dict(installation_id=row['installation_id'],plugin_id=row['plugin_id'],version=row['version'],
                artifact_digest=row['digest'],manifest_digest=data_digest(row['manifest']),state=row['metadata_state'],
                features=sorted([{k:f[k] for k in ['workspace_id','feature_state']} for f in site['features']
                    if f['installation_id']==row['installation_id']],key=lambda f:f['workspace_id'])))
        reference=dict(profile='r1-reference-stateless-v1',site_id=site['site_id'],runtime_image=CATALOG[-1]['manifest']['external_service']['expected_image'],
            publication_digest='sha256:'+'a'*64,registrations=sorted(rows,key=lambda r:r['installation_id']))
        return lifecycle.LifecycleScope(site['site_id'],site['release_digest'],reference=reference)

    def guard(self,scope):
        guard=ReferenceDispatchMaintenance.__new__(ReferenceDispatchMaintenance)
        guard.policies={data_digest(scope.reference):scope.reference};return guard

    def test_native_default_footprint_and_resume_remain_native(self):
        scope=self.scope();native=lifecycle.LifecycleScope(scope.site_id,scope.release_digest)
        snapshot=lifecycle.observe(self.cr,native)
        self.assertEqual(snapshot['profile'],'r1-native-dispatch-v1');self.assertNotIn('reference_policy_digest',snapshot)
        result=lifecycle.fence(self.cr,native,str(uuid4()));DispatchMaintenance.require_native(result['after'],closed=True)
        self.assertTrue(lifecycle.enable(self.cr,native,result['after']['state_digest'])['dispatch_enabled'])

    def test_native_default_still_refuses_external_metadata(self):
        self.apply('install');scope=self.scope();native=lifecycle.LifecycleScope(scope.site_id,scope.release_digest)
        snapshot=lifecycle.observe(self.cr,native)
        with self.assertRaises(OperatorError):DispatchMaintenance.require_native(snapshot)
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.fence(self.cr,native,str(uuid4()))
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.enable(self.cr,native,snapshot['state_digest'])

    def test_reference_fence_and_resume_preserve_metadata_and_history(self):
        self.apply('install');scope=self.scope();metadata=copy.deepcopy(self.site())
        result=lifecycle.fence(self.cr,scope,str(uuid4()));guard=self.guard(scope)
        guard.require_profile(result['after'],closed=True)
        self.assertEqual(result['after']['profile'],'r1-reference-stateless-dispatch-v1')
        self.assertTrue(lifecycle.enable(self.cr,scope,result['after']['state_digest'])['dispatch_enabled'])
        self.assertEqual(self.site(),metadata)

    def test_reference_tombstone_is_inert_and_can_resume_native_work(self):
        self.apply('install');self.external['endpoints'][0].update(state='revoked',generation=2);self.apply('unregister')
        scope=self.scope();result=lifecycle.fence(self.cr,scope,str(uuid4()))
        self.guard(scope).require_profile(result['after'],closed=True)
        self.assertTrue(lifecycle.enable(self.cr,scope,result['after']['state_digest'])['dispatch_enabled'])

    def test_missing_or_forged_reference_footprint_refused(self):
        self.apply('install');original=self.scope()
        for mutation in ['empty','image','manifest','artifact','workspace','plugin']:
            policy=copy.deepcopy(original.reference)
            if mutation=='empty':policy['registrations']=[]
            elif mutation=='image':policy['runtime_image']='modular-document-stats@sha256:'+'b'*64
            elif mutation=='workspace':policy['registrations'][0]['features'][0]['workspace_id']=str(uuid4())
            elif mutation=='plugin':policy['registrations'][0]['plugin_id']='org.example.unknown'
            else:policy['registrations'][0][mutation+'_digest']='sha256:'+'b'*64
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                lifecycle.observe(self.cr,lifecycle.LifecycleScope(original.site_id,original.release_digest,reference=policy))

    def test_new_unknown_registration_or_wrong_feature_namespace_refused(self):
        self.apply('install');scope=self.scope()
        self.cr.execute('UPDATE mp_workspace_plugin SET plugin_id=%s WHERE installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s)',
            ['org.example.unknown',self.target['installation_id']])
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.observe(self.cr,scope)
        self.cr.execute('UPDATE mp_workspace_plugin SET plugin_id=%s WHERE installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s)',
            [self.target['plugin_id'],self.target['installation_id']])
        self.cr.execute('''INSERT INTO mp_plugin_installation(public_id,plugin_id,version,artifact_digest,runtime,state,manifest)
            SELECT %s,'org.example.unknown',version,artifact_digest,runtime,state,manifest FROM mp_plugin_installation WHERE public_id=%s''',
            [str(uuid4()),self.target['installation_id']])
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.fence(self.cr,scope,str(uuid4()))

    def test_publication_change_cannot_reuse_old_ready_digest(self):
        self.apply('install');scope=self.scope();result=lifecycle.fence(self.cr,scope,str(uuid4()))
        policy=copy.deepcopy(scope.reference);policy['publication_digest']='sha256:'+'b'*64
        with self.assertRaises(lifecycle.DispatchLifecycleError):
            lifecycle.enable(self.cr,lifecycle.LifecycleScope(scope.site_id,scope.release_digest,reference=policy),result['after']['state_digest'])

    def test_uncertain_effects_remain_paused_without_automatic_retry(self):
        self.apply('install');scope=self.scope()
        self.cr.execute("UPDATE mp_job SET state='retry',effect_mode='reconcile',effect_started=true WHERE id=(SELECT min(id) FROM mp_job)")
        result=lifecycle.fence(self.cr,scope,str(uuid4()));self.assertGreater(result['after']['uncertain_jobs'],0)
        with self.assertRaises(OperatorError):self.guard(scope).require_profile(result['after'],closed=True)
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.enable(self.cr,scope,result['after']['state_digest'])

    def test_active_host_credential_still_requires_other_reconciliation(self):
        self.apply('install');scope=self.scope()
        self.cr.execute("SELECT id FROM mp_principal WHERE kind='service' ORDER BY id LIMIT 1");principal=self.cr.fetchone()[0]
        self.cr.execute('SELECT id FROM mp_workspace WHERE public_id=%s',[self.target['workspace_id']]);workspace=self.cr.fetchone()[0]
        self.cr.execute("""INSERT INTO mp_service_credential(name,principal_id,workspace_id,token_digest,installation_public_id,audience,actions,expires_at,state)
            VALUES('rollback profile',%s,%s,%s,%s,'mp-host-v1','read',timezone('UTC',now())+interval '5 minutes','active')""",
            [principal,workspace,str(uuid4()),self.target['installation_id']])
        snapshot=lifecycle.observe(self.cr,scope)
        with self.assertRaises(OperatorError):self.guard(scope).require_profile(snapshot)
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.fence(self.cr,scope,str(uuid4()))

    def test_current_release_idempotency_gate_is_not_bypassed(self):
        self.apply('install');scope=self.scope();lifecycle.fence(self.cr,scope,str(uuid4()))
        self.cr.execute("UPDATE mp_job SET state='pending',release_digest=%s WHERE id=(SELECT min(id) FROM mp_job)",['sha256:'+'c'*64])
        snapshot=lifecycle.observe(self.cr,scope)
        with self.assertRaises(lifecycle.DispatchLifecycleError):lifecycle.enable(self.cr,scope,snapshot['state_digest'])


class JournalTests(ReferenceDispatchTests):
    # Only the phase tests below are loaded; inherited PG cases are not repeated.
    def store_for(self,data,folder):
        state=data['base_state'];bundle=data['bundle']
        store=OperatorStore.initialize(Path(folder)/'control',{state['deployment_id']:state['site_ids']},allow_noninteractive=True)
        validate=lambda _:copy.deepcopy(state);operation=store.register(bundle,validate)
        store.approve(operation,exact_hash=bundle['plan_hash'],acknowledgments={'destructive':True,'trust_expansion':True,'permission_expansion':True},revalidate=validate,noninteractive=True)
        return store,operation,validate

    def test_external_enable_and_suspend_require_full_checkpoint_chain(self):
        self.apply('install')
        for action in ['enable','suspend']:
            data=self.payload(action);self.assertTrue(data['bundle']['plan']['backup']['required'])
            with tempfile.TemporaryDirectory() as folder:
                store,operation,validate=self.store_for(data,folder)
                with OperationLocks(store.root/'locks',data['deployment_id'],[data['site_id']]) as locks:
                    store.reserve(operation,locks,validate);store.advance(operation,locks,'staged')
                    with self.assertRaises(OperatorError):store.before_mutation(operation,locks,validate)
                    for phase in ['maintenance','drained']:store.advance(operation,locks,phase)
                    with self.assertRaises(OperatorError):store.before_mutation(operation,locks,validate)
                    with self.assertRaises(OperatorError):store.advance(operation,locks,'checkpointed')
                    store.advance(operation,locks,'checkpointed',backup_id='source-journal-fixture')
                    store.before_mutation(operation,locks,validate)
                    self.assertFalse(store.status(operation)['traffic_resumed'])
                    with self.assertRaises(OperatorError):store.advance(operation,locks,'metadata_published')
                    for phase in ['migrated','workers_replaced','ready','release_published','traffic_resumed','completed']:store.advance(operation,locks,phase)
                    self.assertEqual(store.status(operation)['state'],'completed')

    def test_missing_external_backup_cannot_register_even_with_rehashed_envelope(self):
        data=self.payload('install');bundle=data['bundle'];bundle['plan']['backup']['required']=False
        bundle['plan_hash']=plan_hash(bundle['plan']);bundle['display']=_display(bundle['plan'],bundle['operation_lock'])
        with tempfile.TemporaryDirectory() as folder:
            state=data['base_state'];store=OperatorStore.initialize(Path(folder)/'control',{state['deployment_id']:state['site_ids']})
            with self.assertRaisesRegex(OperatorError,'coordinated checkpoint'):store.register(bundle,lambda _:state)

    def test_native_feature_keeps_existing_short_journal(self):
        site=self.site();document=project_deployment(self.config,dict(runtime=RUNTIME,image_id=self.config['image_id'],sites=[site],external_state=self.external),self.catalog)
        notes=next(i for i in site['installations'] if i['plugin_id']=='org.example.notes')
        target=dict(installation_id=notes['installation_id'],site_id=site['site_id'],workspace_id=self.target['workspace_id'],plugin_id=notes['plugin_id'],action='suspend')
        bundle=prepare_current_feature(document,[site],self.catalog,targets=[target],operation_type='suspend',operation_id=str(uuid4()),created_at='2026-11-01T06:10:00Z')
        self.assertFalse(bundle['plan']['backup']['required'])
        data=dict(base_state=document['state'],bundle=bundle)
        with tempfile.TemporaryDirectory() as folder:
            store,operation,validate=self.store_for(data,folder)
            with OperationLocks(store.root/'locks',self.config['deployment_id'],[site['site_id']]) as locks:
                store.reserve(operation,locks,validate);store.advance(operation,locks,'staged');store.before_mutation(operation,locks,validate)
                self.assertTrue(store.status(operation)['traffic_resumed'])
                for phase in ['metadata_published','ready','completed']:store.advance(operation,locks,phase)


class PolicyBuilderTests(ReferenceDispatchTests):
    def fixture(self):
        self.apply('install')
        module=types.ModuleType('qualified_publication_helpers');module.__file__='/opt/modular/tests/test_worker_publication.py'
        exec(compile(PUBLICATION_HELPERS,module.__file__,'exec'),module.__dict__)
        module.WorkerPublicationTests.setUpClass();pub=module.WorkerPublicationTests();pub.setUp();self.addCleanup(pub.doCleanups)
        pub.endpoint.update(installation_id=self.target['installation_id'],workspace_id=self.target['workspace_id'],
            expected_image_digest=self.external['endpoints'][0]['expected_image_digest'])
        pub.observed['image_digest']=pub.endpoint['expected_image_digest'];pub.publish()
        path,worker,config=pub.configured_reader();target=json.loads(path.read_text())
        target['published_release']=self.config['published_release'];path.write_text(json.dumps(target))
        metadata=self.site();metadata['site_id']=pub.site
        native=SimpleNamespace(config=target,target_path=path,store=pub.store,observer=SimpleNamespace(),catalog_root=pub.store.root/'unused',validator=None)
        builder=ReferenceDispatchMaintenance(native)
        self.enterContext(patch('modular_platform.reference_dispatch.read_metadata',side_effect=lambda *args:copy.deepcopy(metadata)))
        self.enterContext(patch('modular_platform.reference_dispatch.Catalog',return_value=SimpleNamespace(snapshot=lambda:copy.deepcopy(self.catalog))))
        self.enterContext(patch('modular_platform.worker_operator.DockerWorkerObservation',return_value=pub.observer))
        return pub,target,metadata,builder

    def test_policy_uses_real_protected_publication_and_exact_selected_metadata(self):
        pub,target,metadata,builder=self.fixture();value=builder.reference_policy(target)
        self.assertEqual(value['publication_digest'],data_digest(pub.publisher._document()))
        self.assertEqual(value['registrations'][0]['installation_id'],self.target['installation_id'])
        original=copy.deepcopy(metadata)
        for field in ['digest','manifest','workspace']:
            metadata.clear();metadata.update(copy.deepcopy(original));row=next(r for r in metadata['installations'] if r['runtime']=='external_service')
            if field=='digest':row['digest']='sha256:'+'e'*64
            elif field=='manifest':row['manifest']['plugin']['description']='unselected metadata'
            else:next(f for f in metadata['features'] if f['installation_id']==row['installation_id'])['workspace_id']=str(uuid4())
            with self.subTest(field=field),self.assertRaises(OperatorError):builder.reference_policy(target)

    def test_removed_metadata_needs_suspended_scopes_and_revoked_publication(self):
        pub,target,metadata,builder=self.fixture()
        row=next(r for r in metadata['installations'] if r['runtime']=='external_service');row['metadata_state']='removed'
        for feature in metadata['features']:
            if feature['installation_id']==row['installation_id']:feature['feature_state']='suspended'
        with self.assertRaises(OperatorError):builder.reference_policy(target)
        pub.endpoint.update(state='revoked',generation=2);pub.publish()
        self.assertEqual(builder.reference_policy(target)['registrations'][0]['state'],'removed')

    def test_publication_race_in_os_reader_refuses_policy(self):
        pub,target,metadata,builder=self.fixture()
        def race(*args):
            pub.endpoint.update(state='revoked',generation=2);pub.publish()
            return copy.deepcopy(pub.observed)
        with patch('modular_platform.worker_operator.DockerWorkerObservation',return_value=race),self.assertRaises(OperatorError):builder.reference_policy(target)


suite=unittest.TestSuite()
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ReferenceDispatchTests))
suite.addTests(JournalTests(name) for name in ['test_external_enable_and_suspend_require_full_checkpoint_chain','test_missing_external_backup_cannot_register_even_with_rehashed_envelope','test_native_feature_keeps_existing_short_journal'])
suite.addTests(PolicyBuilderTests(name) for name in ['test_policy_uses_real_protected_publication_and_exact_selected_metadata','test_removed_metadata_needs_suspended_scopes_and_revoked_publication','test_publication_race_in_os_reader_refuses_policy'])
result=unittest.TextTestRunner(verbosity=2).run(suite);CONNECTION.rollback()
print('MP_REFERENCE_DISPATCH='+__import__('json').dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,
    errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures],original_rows_restored=True)))
raise SystemExit(0 if result.wasSuccessful() else 1)
