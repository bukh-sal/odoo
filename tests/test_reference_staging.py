"""Native staging retains independently pinned code-free external roots."""
import copy
from pathlib import Path
import sys
import unittest

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'),str(Path(__file__).resolve().parent)]
import test_external_projection as external
from test_resolution import plugin
from test_release_staging import staged_runtime
from test_plans import ident,STAMP
from modular_platform.release_staging import prepare_staged_plan
from modular_platform.manager_planning import prepare_manager_native
from modular_platform.lifecycle_planning import prepare_current_install_targets
from modular_platform.plans import data_digest,check_bundle
from modular_platform.resolution import PlanningError
from modular_platform.operator_os import OperatorError
from modular_platform.approval_validation import IndependentValidator


class ReferenceStaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):external.ExternalProjection.setUpClass()

    def setUp(self):
        self.f=external.ExternalProjection();self.f.setUp()
        self.f.site['workspaces']=[dict(workspace_id=ident(30),state='active')]
        self.new=plugin('a','1.1.0');self.catalog=self.f.catalog+[self.new]
        self.f.catalog=self.catalog
        self.document=self.f.project();self.base=copy.deepcopy(self.f.runtime)
        self.runtime=staged_runtime([self.new])
        self.runtime.update(platform_version='0.1.13',native_manifests=copy.deepcopy(self.base['native_manifests']))
        self.target=dict(installation_id=ident(100),site_id=ident(20),workspace_id=ident(30),plugin_id='org.test.a',action='upgrade')
        self.descriptor=dict(stage_digest='sha256:'+'c'*64,base_image_id=self.f.config['image_id'],
            target_image_id='sha256:'+'b'*64,inventory_digest=self.runtime['inventory_digest'],runtime_digest=data_digest(self.runtime))

    def prepare(self,action='upgrade',targets=None):
        self.descriptor['runtime_digest']=data_digest(self.runtime)
        return prepare_staged_plan(self.document,[self.f.site],self.catalog,self.runtime,self.descriptor,
            targets=targets if targets is not None else [self.target],operation_type=action,operation_id=ident(500),created_at=STAMP,base_runtime=self.base)

    def external_pin(self,lock):return next(p for p in lock['plugins'] if p['runtime']=='external_service')

    def assert_retained(self,bundle):
        self.assertTrue(check_bundle(bundle,self.document['state']))
        self.assertEqual(self.external_pin(bundle['operation_lock']['release']),self.external_pin(self.document['state']['release_lock']))
        self.assertEqual(bundle['operation_lock']['endpoints'],self.document['state']['endpoints'])
        self.assertEqual(bundle['operation_lock']['bindings'],self.document['state']['bindings'])
        self.assertTrue(all(p['runtime']=='native' for p in bundle['plan']['artifacts']))
        self.assertNotIn('org.example.document_stats',self.runtime['inventory']['artifacts'])

    def test_native_upgrade_retains_external_root_without_fake_addon_or_target(self):
        self.assert_retained(self.prepare())

    def test_current_catalog_generation_does_not_rewrite_retained_metadata_trust(self):
        for p in self.catalog:p['trust']['policy_generation']+=1
        self.document=self.f.project()
        self.assert_retained(self.prepare())

    def test_current_image_new_scope_preserves_published_trust_after_catalog_refresh(self):
        for p in self.catalog:p['trust']['policy_generation']+=1
        self.f.site['workspaces'].append(dict(workspace_id=ident(31),state='active'))
        self.document=self.f.project()
        target=dict(self.target,action='install',workspace_id=ident(31))
        bundle=prepare_current_install_targets(self.document,[self.f.site],self.catalog,
            activation_targets=[target],operation_id=ident(500),created_at=STAMP)
        self.assert_retained(bundle)
        before=self.document['state']['release_lock'];after=copy.deepcopy(bundle['operation_lock']['release'])
        after.update(generation=before['generation'],created_at=before['created_at'])
        self.assertEqual(after,before)

    def test_missing_untrusted_or_substituted_metadata_fails_closed(self):
        original=copy.deepcopy(self.catalog)
        for case in ['missing','version','manifest']:
            self.catalog=copy.deepcopy(original)
            if case=='missing':self.catalog=[p for p in self.catalog if p['manifest']['runtime']['kind']=='native']
            elif case=='version':self.catalog[1]['manifest']['plugin']['version']='0.2.0'
            else:self.catalog[1]['manifest']['plugin']['description']='substituted'
            with self.subTest(case=case),self.assertRaises(PlanningError):self.prepare()

    def test_external_target_cannot_be_smuggled_into_native_upgrade(self):
        target=dict(self.target,installation_id=ident(101),plugin_id='org.example.document_stats')
        with self.assertRaisesRegex(OperatorError,'target differs'):self.prepare(targets=[target])

    def test_manager_upgrade_retains_external_root_and_reconstructs_same_bundle(self):
        nomination=dict(schema_version=1,operation='prepare',operation_type='upgrade',plugin_id='org.test.a',artifact_version='1.1.0',
            artifact_digest=self.new['digest'],site_id=ident(20),workspace_ids=[ident(30)],cascade=False)
        result=prepare_manager_native(self.document,[self.f.site],self.catalog,self.base,
            dict(descriptor=self.descriptor,runtime=self.runtime),nomination,operation_id=ident(500),created_at=STAMP)
        self.assertEqual(result,self.prepare());self.assert_retained(result)

    def core(self):
        self.runtime=copy.deepcopy(self.base)
        for runtime in [self.base,self.runtime]:
            runtime['native_manifests']['mp_shell']={'version':'19.0.0.1.1'}
            runtime['inventory']['files']['addons/mp_shell/__manifest__.py']='a'*64
        self.runtime['native_manifests']['mp_shell']['version']='19.0.0.1.2'
        self.runtime['inventory']['files']['addons/mp_shell/__manifest__.py']='b'*64
        self.runtime['inventory']['files']['addons/mp_shell/models.py']='c'*64
        self.f.site['native_modules'].extend(dict(addon=name,state='installed',version=m['version']) for name,m in self.base['native_manifests'].items())
        self.target['action']='deploy'

    def test_core_upgrade_requires_native_scopes_and_preserves_enabled_external_metadata(self):
        self.core();bundle=self.prepare('core_upgrade');self.assert_retained(bundle)
        self.assertEqual(bundle['operation_lock']['targets'],[self.target])
        self.assertEqual(bundle['operation_lock']['native_core_changes'][0]['addon'],'mp_shell')

    def test_core_cannot_skip_native_scope_or_target_external_as_native(self):
        self.core()
        with self.assertRaises(PlanningError):self.prepare('core_upgrade',targets=[])
        external_target=dict(self.target,plugin_id='org.example.document_stats',installation_id=ident(101))
        with self.assertRaises(OperatorError):self.prepare('core_upgrade',targets=[self.target,external_target])

    def test_core_retains_unregistered_metadata_tombstone_with_no_endpoint(self):
        self.core();self.f.site['installations'][1]['metadata_state']='removed'
        self.f.site['features'][1]['feature_state']='suspended'
        self.document=self.f.project()
        self.assertEqual(self.document['state']['endpoints'],[])
        self.assert_retained(self.prepare('core_upgrade'))

    def test_independent_staged_validator_reconstructs_external_pin_from_current_state(self):
        bundle=self.prepare();v=object.__new__(IndependentValidator)
        class Catalog:
            def snapshot(inner):return copy.deepcopy(self.catalog)
        class Observer:
            def read(inner):return dict(sites=[copy.deepcopy(self.f.site)],runtime=copy.deepcopy(self.base))
            def state(inner,*args):return copy.deepcopy(self.document)
        class Stages:
            def load(inner,descriptor):
                if descriptor!=self.descriptor:raise OperatorError('Stage changed')
                return descriptor,dict(runtime=copy.deepcopy(self.runtime))
        v.catalog=Catalog();v.observer=Observer();v.stage_store=Stages()
        self.assertEqual(v(bundle),self.document['state'])
        self.catalog=[p for p in self.catalog if p['manifest']['runtime']['kind']=='native']
        with self.assertRaises(PlanningError):v(bundle)


if __name__=='__main__':unittest.main()
