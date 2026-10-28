"""Current-image nomination cannot invent code, scopes or installation IDs."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.lifecycle_planning import prepare_current_image_install, validate_install_targets, installation_id
from modular_platform.plans import data_digest, plan_hash
from modular_platform.approval_validation import IndependentValidator
from modular_platform.resolution import PlanningError
from test_plans import base_state, ident, STAMP, PROVENANCE
from test_resolution import plugin, ENVIRONMENT, provide, require


class CurrentImageInstallation(unittest.TestCase):
    def setUp(self):
        self.catalog = [plugin('a', depends={'b': '>=1'}), plugin('b')]
        self.document = {'state': base_state(self.catalog), 'environment': ENVIRONMENT,
                         'provenance': PROVENANCE, 'python_metadata': []}
        self.document['state'].update(bindings=[], endpoints=[])
        self.site = {'site_id': ident(20), 'installations': [],
                     'workspaces': [{'workspace_id': ident(30), 'state': 'active'},
                                    {'workspace_id': ident(31), 'state': 'active'}]}
        self.args = dict(site_id=ident(20), workspace_ids=[ident(30), ident(31)],
            plugin_id='org.test.a', version='1.0.0', artifact_digest=self.catalog[0]['digest'],
            operation_id=ident(500), created_at=STAMP)

    def prepare(self, **kwargs):
        return prepare_current_image_install(self.document, [self.site], self.catalog, **(self.args | kwargs))

    def validator(self):
        validator = object.__new__(IndependentValidator)
        class Snapshot:
            def snapshot(inner): return copy.deepcopy(self.catalog)
        class Observer:
            def read(inner): return {'sites': [copy.deepcopy(self.site)]}
            def state(inner, observation, catalog): return copy.deepcopy(self.document)
        validator.catalog, validator.observer = Snapshot(), Observer()
        return validator

    def test_transitive_install_shared_site_identity_and_independent_reconstruction(self):
        bundle = self.prepare()
        targets = bundle['operation_lock']['targets']
        self.assertEqual(len(targets), 4)
        self.assertEqual(len({item['installation_id'] for item in targets}), 2)
        self.assertEqual(bundle['plan']['artifacts'][0]['migration_digests'], [])
        self.assertTrue(bundle['plan']['backup']['required'])
        self.assertEqual(self.validator()(bundle), self.document['state'])
        self.assertEqual(self.prepare(), bundle)

    def test_unavailable_code_workspace_and_identity_fail_before_any_mutation(self):
        for kwargs in ({'version': '2.0.0'}, {'artifact_digest': 'sha256:'+'f'*64},
                       {'workspace_ids': [ident(999)]}, {'workspace_ids': [ident(30), ident(30)]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(PlanningError): self.prepare(**kwargs)
        targets = self.prepare()['operation_lock']['targets']
        targets[0]['installation_id'] = ident(999)
        with self.assertRaisesRegex(PlanningError, 'derived site installation'):
            validate_install_targets(self.document, [self.site], targets)
        targets = [item for item in self.prepare()['operation_lock']['targets'] if item['plugin_id'] != 'org.test.b']
        with self.assertRaisesRegex(PlanningError, 'omits a required'):
            validate_install_targets(self.document, [self.site], targets)

    def test_current_independent_workspace_state_and_immutable_release_rechecked(self):
        bundle = self.prepare()
        self.site['workspaces'][0]['state'] = 'archived'
        with self.assertRaisesRegex(PlanningError, 'active workspace'): self.validator()(bundle)
        self.site['workspaces'][0]['state'] = 'active'
        changed = copy.deepcopy(bundle)
        changed['operation_lock']['release']['core_inventory_digest'] = 'sha256:'+'f'*64
        changed['plan']['target_release_digest'] = data_digest(changed['operation_lock']['release'])
        changed['plan']['dependency_lock_digest'] = data_digest(changed['operation_lock'])
        changed['plan_hash'] = plan_hash(changed['plan'])
        with self.assertRaisesRegex(ValueError, 'independently staged'): self.validator()(changed)

    def test_existing_site_identity_reused_and_suspended_provider_requires_explicit_enable(self):
        self.site['installations'] = [{'plugin_id': 'org.test.b', 'installation_id': ident(200), 'metadata_state': 'installed'}]
        self.document['state']['installations'] = [{'installation_id': ident(200), 'site_id': ident(20),
            'workspace_id': ident(30), 'plugin_id': 'org.test.b', 'state': 'installed',
            'metadata_state': 'installed', 'feature_state': 'enabled'}]
        bundle = self.prepare()
        self.assertEqual(len(bundle['operation_lock']['targets']), 3)
        self.assertEqual(installation_id(self.site, 'org.test.b'), ident(200))
        self.document['state']['installations'][0]['feature_state'] = 'suspended'
        with self.assertRaisesRegex(PlanningError, 'explicitly enabled'): self.prepare()

    def test_new_binding_scopes_are_in_the_approved_release_before_install(self):
        # Reproduce the live readiness mismatch: before installation the source
        # contains a global provider choice; afterwards DB bindings are scoped.
        self.catalog = [plugin('a', provides=[provide('a')], requires=[require()])]
        self.document['state'] = base_state(self.catalog) | {'bindings': [], 'endpoints': []}
        bundle = self.prepare(artifact_digest=self.catalog[0]['digest'])
        selected = bundle['operation_lock']['release']['service_selection']
        self.assertEqual(selected[0]['scopes'], [[ident(20), ident(30)], [ident(20), ident(31)]])
        self.assertNotIn('excluded_scopes', selected[0])
        self.assertEqual(self.validator()(bundle), self.document['state'])

    def test_install_into_another_workspace_extends_an_existing_scoped_provider(self):
        self.catalog=[plugin('a',provides=[provide('a')],requires=[require()])]
        self.document['state']=base_state(self.catalog)|{'bindings':[],'endpoints':[]}
        first=self.prepare(workspace_ids=[ident(30)],artifact_digest=self.catalog[0]['digest'])
        installed=first['operation_lock']['targets'][0]
        self.site['installations']=[{'installation_id':installed['installation_id'],'plugin_id':'org.test.a','metadata_state':'installed'}]
        self.document['state'].update(release_lock=first['operation_lock']['release'],generation=2,
            release_digest=first['plan']['target_release_digest'],bindings=first['operation_lock']['bindings'],
            installations=[{key:value for key,value in installed.items() if key!='action'}|
                {'state':'installed','feature_state':'enabled','metadata_state':'installed'}])
        next_plan=self.prepare(workspace_ids=[ident(31)],artifact_digest=self.catalog[0]['digest'])
        self.assertEqual(len(next_plan['operation_lock']['bindings']),2)
        self.assertEqual(next_plan['operation_lock']['release']['service_selection'][0]['scopes'],
            [[ident(20),ident(30)],[ident(20),ident(31)]])


if __name__ == '__main__': unittest.main()
