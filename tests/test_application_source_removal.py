"""Actual authored archives/materialization through the ordinary removal guard."""
import ast
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests'), str(ROOT / 'packages/platform_sdk')]
import test_application_distribution as authoring
from test_clean_removal_build import fixture
from build_clean_removal import subtract_inventory, prepare_payload
from modular_platform.artifact_removal import validate_removal_image
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest


class ApplicationSourceRemoval(unittest.TestCase):
    def setUp(self):
        self.app = authoring.ApplicationDistribution()
        self.app.setUp()
        self.addCleanup(self.app.doCleanups)
        self.app.extension()
        self.app.policy.update(explicit_install=['base', 'web'], server_wide_modules=['base'])
        inventory = self.app.compose()
        self.base, _ = fixture()
        self.base['inventory'] = inventory
        self.base['native_manifests'] = {
            addon: ast.literal_eval((self.app.root / 'distribution' / 'addons' / addon / '__manifest__.py').read_text())
            for addon in inventory['native_addons'] if addon != 'base'}
        self.base['native_manifests']['base'] = ast.literal_eval(
            (self.app.root / 'distribution/odoo/addons/base/__manifest__.py').read_text())
        self.mapping = {'application.toml': 'dev.example.tasks', 'authoring/labels.toml': 'dev.example.labels'}

    def candidate(self, removed):
        inventory, diff = subtract_inventory(self.base, removed, self.mapping)
        after = copy.deepcopy(self.base)
        after['inventory'] = inventory
        addons = {self.base['inventory']['artifacts'][p]['addon'] for p in removed}
        after['native_manifests'] = {a: m for a, m in after['native_manifests'].items() if a not in addons}
        return after, diff

    def check(self, after, packages):
        descriptor = dict(base_image_id='sha256:' + 'a' * 64, target_image_id='sha256:' + 'b' * 64,
            inventory_digest=after['inventory_digest'], runtime_digest=data_digest(after))
        return validate_removal_image(self.base, after, descriptor, packages)

    def test_partial_real_recipe_subtraction_preserves_provider_archive_and_ownership(self):
        before = copy.deepcopy(self.base)
        after, diff = self.candidate(['dev.example.labels'])
        self.assertEqual(self.base, before)
        self.assertEqual(self.check(after, ['dev.example.labels']), diff)
        self.assertEqual(after['inventory']['policy']['application_packages'], ['application.toml'])
        self.assertNotIn('reference_packages', after['inventory']['policy'])
        self.assertEqual(after['inventory']['artifacts']['dev.example.tasks'],
            before['inventory']['artifacts']['dev.example.tasks'])
        self.assertNotIn('mp.example.task.custom_label', after['inventory']['package_composition']['fields'])
        self.assertEqual(after['inventory']['package_composition']['models'],
            before['inventory']['package_composition']['models'])

    def test_full_real_recipe_subtraction_and_materialized_payload_contain_only_framework(self):
        packages = list(self.mapping.values())
        after, diff = self.candidate(packages)
        self.assertEqual(self.check(after, packages), diff)
        self.assertEqual(after['inventory']['policy']['application_packages'], [])
        self.assertNotIn('package_composition', after['inventory'])
        self.assertNotIn('artifacts', after['inventory'])
        self.assertEqual(set(after['inventory']['native_addons']), {'base', 'web'})
        release = self.app.root / 'distribution'
        (release / 'requirements.lock').write_bytes(b'fixed source lock\n')
        (release / 'startup-profile').write_bytes(b'r1\n')
        actual = prepare_payload(release, self.base['inventory'], after['inventory'])
        for name, digest in after['inventory']['files'].items():
            self.assertEqual(actual[name], digest)
        self.assertFalse((release / 'addons/mp_example_tasks').exists())
        self.assertFalse((release / 'addons/example_tasks_labels').exists())
        self.assertFalse((release / 'artifacts').exists())

    def test_required_provider_removal_refuses_before_touching_source(self):
        with self.assertRaisesRegex(OperatorError, 'still requires'):
            self.candidate(['dev.example.tasks'])
        self.assertTrue((self.app.root / 'distribution/addons/mp_example_tasks/__manifest__.py').is_file())

    def test_mixed_reference_and_application_sources_preserve_each_surviving_source_kind(self):
        inventory = self.base['inventory']
        inventory['policy']['reference_packages'] = ['authoring/labels-plugin.toml']
        inventory['policy']['application_packages'] = ['application.toml']
        inventory['reference_composition'] = dict(models={},
            fields={'mp.example.task.custom_label': 'dev.example.labels'}, ui_contributions=[])
        after, diff = subtract_inventory(self.base, ['dev.example.labels'], {
            'authoring/labels-plugin.toml': 'dev.example.labels', 'application.toml': 'dev.example.tasks'})
        self.assertEqual(after['policy']['reference_packages'], [])
        self.assertEqual(after['policy']['application_packages'], ['application.toml'])
        self.assertEqual(after['reference_composition'], dict(models={}, fields={}, ui_contributions=[]))
        self.assertEqual(after['package_composition']['models'], inventory['package_composition']['models'])
        self.assertTrue(diff)

    def test_recipe_transfer_duplicate_reordering_and_unrelated_policy_edits_refuse(self):
        for change in ('transfer', 'duplicate', 'reorder', 'profile'):
            with self.subTest(change=change):
                after, _ = self.candidate(['dev.example.labels'])
                policy = after['inventory']['policy']
                if change == 'transfer':
                    policy['reference_packages'] = policy.pop('application_packages')
                elif change == 'duplicate':
                    policy['application_packages'] *= 2
                elif change == 'reorder':
                    policy['application_packages'] = list(reversed(self.base['inventory']['policy']['application_packages']))
                else:
                    policy['profile'] = 'unrelated'
                with self.assertRaises(OperatorError):
                    self.check(after, ['dev.example.labels'])

    def test_forged_surviving_ownership_and_added_composition_refuse(self):
        for key in ('package_composition', 'reference_composition'):
            with self.subTest(key=key):
                after, _ = self.candidate(['dev.example.labels'])
                if key == 'package_composition':
                    after['inventory'][key]['models']['mp.example.task'] = 'dev.example.labels'
                else:
                    after['inventory'][key] = dict(models={}, fields={}, ui_contributions=[])
                with self.assertRaisesRegex(OperatorError, 'composition'):
                    self.check(after, ['dev.example.labels'])


if __name__ == '__main__':
    unittest.main()
