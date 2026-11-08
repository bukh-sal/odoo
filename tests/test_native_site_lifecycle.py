"""Pure native site planning is explicit and never a wildcard workspace target."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_lifecycle_planning as existing
from modular_platform.lifecycle_planning import prepare_current_image_install
from modular_platform.plans import data_digest,plan_hash
from modular_platform.resolution import PlanningError
from modular_platform.operator_os import OperatorError
from test_plans import base_state
from modular_platform.native_executor import require_native_site_runtime
import test_projection_tombstones as projection_test
import test_release_staging as staging_test


class NativeSiteLifecycle(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.CurrentImageInstallation('test_transitive_install_shared_site_identity_and_independent_reconstruction')
        self.fixture.setUp()
        for descriptor in self.fixture.catalog:
            descriptor['manifest']['activation']=dict(scopes=['site'],supports_feature_suspension=False)
        self.fixture.document['state']=base_state(self.fixture.catalog)
        self.fixture.document['state'].update(bindings=[],endpoints=[])
        self.fixture.site.update(workspaces=[],native_modules=[],features=[])

    def prepare(self,**changes):
        return self.fixture.prepare(**({'workspace_ids':[],'site_native':True}|changes))

    def test_site_only_dependency_closure_and_independent_reconstruction(self):
        bundle=self.prepare()
        self.assertEqual(len(bundle['operation_lock']['targets']),2)
        self.assertTrue(all(row['workspace_id'] is None for row in bundle['operation_lock']['targets']))
        self.assertNotIn('feature_states',bundle['operation_lock'])
        self.assertEqual(bundle['plan']['permission_changes'],[])
        self.assertEqual(bundle['plan']['bindings'],[])
        self.assertTrue(bundle['plan']['backup']['required'])
        self.assertEqual(bundle['operation_lock']['native_site_scope_protocol'],1)
        self.assertEqual({row['scope'] for row in bundle['display']['native_site_targets']},{'site-native'})
        self.assertEqual(self.fixture.validator()(bundle),self.fixture.document['state'])

    def test_native_intent_cannot_mix_or_infer_workspace_scope(self):
        with self.assertRaisesRegex(PlanningError,'distinct'):
            self.prepare(workspace_ids=[existing.ident(30)])
        with self.assertRaisesRegex(PlanningError,'Explicit unique workspace'):
            self.prepare(site_native=False)
        self.fixture.site['workspaces']=[dict(workspace_id=existing.ident(30),state='active')]
        with self.assertRaisesRegex(PlanningError,'workspace-capable'):
            self.prepare(site_native=False,workspace_ids=[existing.ident(30)])

    def test_workspace_provider_cannot_be_silently_installed_at_site_scope(self):
        self.fixture.catalog[1]['manifest']['activation']['scopes']=['site','workspace']
        self.fixture.document['state']=base_state(self.fixture.catalog)
        self.fixture.document['state'].update(bindings=[],endpoints=[])
        with self.assertRaisesRegex(PlanningError,'site-only native'):
            self.prepare()

    def test_unregistered_installed_native_module_requires_separate_adoption(self):
        self.fixture.site['native_modules']=[dict(addon='test_a',state='installed',version='19.0.1.0.0')]
        with self.assertRaisesRegex(PlanningError,'adoption transition'):
            self.prepare()

    def test_scope_marker_tampering_rejected_after_rehash(self):
        for value in [None,True,2]:
            bundle=self.prepare();bundle['operation_lock']['native_site_scope_protocol']=value
            bundle['plan']['dependency_lock_digest']=data_digest(bundle['operation_lock'])
            bundle['plan_hash']=plan_hash(bundle['plan'])
            with self.assertRaises((PlanningError,OperatorError)):
                self.fixture.validator()(bundle)

    def test_projection_observes_real_site_installation_without_feature_rows(self):
        fixture=projection_test.TombstoneProjection('test_old_uninstalled_manifest_is_history_when_a_newer_source_is_present')
        fixture.setUp()
        fixture.active['manifest']['activation']=dict(scopes=['site'],supports_feature_suspension=False)
        fixture.site['installations']=fixture.site['installations'][:1]
        fixture.site['features']=[];fixture.catalog=[fixture.active]
        state=fixture.project(present=False)
        self.assertEqual(len(state['installations']),1)
        self.assertIsNone(state['installations'][0]['workspace_id'])
        self.assertEqual(state['installations'][0]['state'],'installed')
        original=copy.deepcopy(fixture.site)
        for field in ('features','grants','native_modules','version'):
            fixture.site=copy.deepcopy(original)
            if field=='features':fixture.site[field]=[dict(installation_id=existing.ident(100),workspace_id=existing.ident(30),feature_state='enabled')]
            elif field=='grants':fixture.site[field]=[dict(installation_id=existing.ident(100),state='approved')]
            elif field=='native_modules':fixture.site[field]=[]
            else:fixture.site['installations'][0]['version']='2.0.0'
            with self.assertRaisesRegex(PlanningError,'Site-native installation'):
                fixture.project(present=False)

    def test_old_runtime_bridge_is_rejected_before_native_metadata_mutation(self):
        with self.assertRaisesRegex(OperatorError,'runtime bridge'):
            require_native_site_runtime({'inventory':{'files':{}}})
        names=('native_scope.py','install_metadata.py','projection.py','plans.py','lifecycle_planning.py')
        runtime={'inventory':{'files':{'packages/platform_sdk/modular_platform/'+name:
            hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform'/name).read_bytes()).hexdigest() for name in names}}}
        require_native_site_runtime(runtime)
        runtime['inventory']['files']['packages/platform_sdk/modular_platform/install_metadata.py']='0'*64
        with self.assertRaises(OperatorError):require_native_site_runtime(runtime)

    def test_staged_native_application_upgrade_keeps_site_scope(self):
        fixture=staging_test.StagedPlans()
        fixture.setUp()
        for item in fixture.catalog:
            item['manifest']['activation']=dict(scopes=['site'],supports_feature_suspension=False)
        fixture.target['workspace_id']=None
        fixture.document['state']=base_state([fixture.old])
        fixture.document['state'].update(bindings=[],endpoints=[],installations=[
            {k:v for k,v in fixture.target.items() if k!='action'}|
            dict(state='installed',metadata_state='installed',feature_state='enabled')])
        fixture.site.update(workspaces=[],features=[],native_modules=[dict(addon='test_a',state='installed',version='19.0.1.0.0')])
        bundle=fixture.prepare()
        self.assertEqual(bundle['operation_lock']['native_site_scope_protocol'],1)
        self.assertIsNone(bundle['operation_lock']['targets'][0]['workspace_id'])
        self.assertEqual(bundle['plan']['artifacts'][0]['action'],'upgrade')
        self.assertEqual(bundle['plan']['permission_changes'],[])


if __name__=='__main__':unittest.main()
