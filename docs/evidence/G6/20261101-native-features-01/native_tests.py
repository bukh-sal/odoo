"""Real PostgreSQL feature writer with populated queues; all changes roll back."""
import copy,unittest
from modular_platform.metadata_sql import METADATA_SELECT
from modular_platform.projection import project_deployment
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.plans import data_digest
from modular_platform.coordinated_feature_metadata import apply_coordinated_feature as APPLY
from modular_platform.feature_metadata import apply_legacy_feature


class FeatureSQL(unittest.TestCase):
    def setUp(self):
        CONNECTION.rollback();self.before=snapshot();CONNECTION.rollback();self.cr=CONNECTION.cursor()
        self.cr.execute("UPDATE mp_dispatch_control SET state='paused' WHERE site_id=%s",[CONFIG['sites'][0]['site_id']])

    def tearDown(self):
        CONNECTION.rollback();self.cr.close();self.assertEqual(snapshot(),self.before);CONNECTION.rollback()

    def site(self):self.cr.execute(METADATA_SELECT);return self.cr.fetchone()[0]

    def payload(self,action='suspend',plugin='org.example.notes',*,reapprove=False,workspace=None):
        site=self.site();installation=next(i for i in site['installations'] if i['plugin_id']==plugin)
        workspace=workspace or WORKSPACE
        if action=='enable':
            self.cr.execute("UPDATE mp_workspace_plugin SET availability='suspended' WHERE installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s) AND workspace_id=(SELECT id FROM mp_workspace WHERE public_id=%s)",[installation['installation_id'],workspace])
        if reapprove:
            self.cr.execute("UPDATE mp_plugin_grant SET state='revoked' WHERE installation_id=(SELECT id FROM mp_plugin_installation WHERE public_id=%s) AND workspace_id=(SELECT id FROM mp_workspace WHERE public_id=%s)",[installation['installation_id'],workspace])
        site=self.site();document=project_deployment(CONFIG,dict(runtime=RUNTIME,image_id=CONFIG['image_id'],sites=[site]),CATALOG)
        target=dict(site_id=site['site_id'],workspace_id=workspace,installation_id=installation['installation_id'],plugin_id=plugin,action=action)
        bundle=prepare_current_feature(document,[site],CATALOG,targets=[target],operation_type=action,operation_id=OPERATION,created_at=STAMP)
        return dict(bundle=bundle,base_state=document['state'],metadata_digest=data_digest(site),site_id=site['site_id'],
            deployment_id=CONFIG['deployment_id'],database=DATABASE,inventory_digest=RUNTIME['inventory_digest'])

    def test_suspend_and_enable_change_only_availability_policy_and_audit(self):
        for action in ['suspend','enable']:
            self.cr.execute('SAVEPOINT phase')
            data=self.payload(action);before=self.site();result=APPLY(self.cr,data);after=self.site()
            self.assertEqual(result,dict(feature_metadata_published=True,operation_id=OPERATION,native_maintenance=False,runtime_control=False))
            for key in ['installations','native_modules','bindings','grants','release_digest','release_generation','active_inventory_digest']:
                self.assertEqual(before[key],after[key])
            target=data['bundle']['operation_lock']['targets'][0]
            feature=next(f for f in after['features'] if (f['installation_id'],f['workspace_id'])==(target['installation_id'],WORKSPACE))
            self.assertEqual(feature['feature_state'],'enabled' if action=='enable' else 'suspended')
            self.cr.execute('ROLLBACK TO SAVEPOINT phase')

    def test_enable_reapproves_only_declared_exact_grants(self):
        data=self.payload('enable','org.example.notes_labels',reapprove=True,workspace=GRANT_WORKSPACE)
        self.assertTrue(data['bundle']['plan']['permission_changes'])
        APPLY(self.cr,data);after=self.site()
        target=data['bundle']['operation_lock']['targets'][0]
        grants=[g for g in after['grants'] if g['installation_id']==target['installation_id'] and g['workspace_id']==target['workspace_id']]
        self.assertTrue(grants);self.assertTrue(all(g['state']=='approved' for g in grants))

    def test_legacy_writer_still_refuses_existing_queue_tables(self):
        data=self.payload();bundle=data['bundle']
        legacy=dict(site_id=data['site_id'],operation_id=OPERATION,plan_hash=bundle['plan_hash'],
            security_metadata_digest=data['base_state']['security_metadata_digest'],targets=bundle['operation_lock']['targets'])
        with self.assertRaisesRegex(AssertionError,'Dispatch drain adapter'):apply_legacy_feature(self.cr,legacy)

    def test_live_dispatch_refused(self):
        data=self.payload();self.cr.execute("UPDATE mp_dispatch_control SET state='enabled'")
        with self.assertRaisesRegex(ValueError,'paused dispatch'):APPLY(self.cr,data)

    def test_running_or_uncertain_job_refused(self):
        for state in ['running','outcome_unknown']:
            self.cr.execute('SAVEPOINT phase');data=self.payload()
            self.cr.execute('UPDATE mp_job SET state=%s WHERE id=(SELECT min(id) FROM mp_job)',[state])
            with self.subTest(state=state),self.assertRaisesRegex(ValueError,'Unreconciled'):APPLY(self.cr,data)
            self.cr.execute('ROLLBACK TO SAVEPOINT phase')

    def test_leased_event_refused(self):
        data=self.payload();self.cr.execute("UPDATE mp_event_delivery SET state='leased' WHERE id=(SELECT min(id) FROM mp_event_delivery)")
        with self.assertRaisesRegex(ValueError,'event leases'):APPLY(self.cr,data)

    def test_wrong_database_deployment_or_inventory_refused(self):
        data=self.payload()
        for key in ['database','deployment_id','inventory_digest']:
            changed=copy.deepcopy(data);changed[key]='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):APPLY(self.cr,changed)

    def test_stale_feature_preimage_and_replay_refused(self):
        data=self.payload();APPLY(self.cr,data)
        with self.assertRaises((AssertionError,ValueError)):APPLY(self.cr,data)

    def test_missing_checkpoint_flag_refused(self):
        from modular_platform.contracts import plan_hash
        data=self.payload();data['bundle']['plan']['backup']['required']=False
        data['bundle']['plan_hash']=plan_hash(data['bundle']['plan'])
        with self.assertRaises(ValueError):APPLY(self.cr,data)

    def test_late_sql_error_propagates_to_caller_transaction(self):
        data=self.payload();actual=self.cr
        class Cursor:
            def execute(inner,sql,*args):
                if sql.startswith('UPDATE mp_workspace SET policy_generation'):raise RuntimeError('Injected after feature/audit SQL')
                return actual.execute(sql,*args)
            def __getattr__(inner,name):return getattr(actual,name)
        with self.assertRaisesRegex(RuntimeError,'Injected'):APPLY(Cursor(),data)


suite=unittest.defaultTestLoader.loadTestsFromTestCase(FeatureSQL)
result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
print('MP_NATIVE_FEATURE='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,
    errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures],original_rows_restored=not result.errors and not result.failures)))
raise SystemExit(0 if result.wasSuccessful() else 1)
