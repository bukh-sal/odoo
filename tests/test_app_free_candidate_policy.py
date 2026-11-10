"""Materialized minimal app-free probe and observed platform/native identity guard."""
import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'tests')]
from build_distribution import build
from modular_platform.projection import PLATFORM_VERSION,runtime_inputs
from modular_platform.resolution import PlanningError
from source_layout import addon_source
from test_release_staging import staged_runtime

POLICY='deploy/distribution-r1-appfree-probe.json'
EXPECTED_ADDONS={'base','web','base_setup','auth_password_policy','bus','mp_compat','mp_identity','mp_core'}
EXCLUDED_ADDONS={'maintenance','mp_discuss','mp_mail_gateway','mp_example_notes','mp_example_notes_labels','mp_example_canvas','mp_example_notes_stats','mp_example_background','mp_shell','mail','html_editor'}


class AppFreeCandidateMaterialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((ROOT/POLICY).read_text(encoding='utf8'))
        cls.temporary=tempfile.TemporaryDirectory(prefix='mp-appfree-probe-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.target=Path(cls.temporary.name)/'release'
        cls.inventory=build(ROOT,cls.target,POLICY)

    def emitted_addons(self):
        found=[]
        for root in (self.target/'addons',self.target/'odoo/addons'):
            if not root.is_dir():
                continue
            found.extend(path.name for path in root.iterdir()
                         if path.is_dir() and (path/'__manifest__.py').is_file())
        return found

    def test_materialized_addons_are_closed_and_only_from_framework_sources(self):
        self.assertEqual(set(self.inventory['native_addons']),EXPECTED_ADDONS)
        for name in EXPECTED_ADDONS:
            source=addon_source(ROOT,name)
            self.assertEqual(source.parent,ROOT/'framework_addons',name)
            self.assertTrue(source.is_relative_to(ROOT/'framework_addons'),name)
        for name,manifest in self.inventory['native_addons'].items():
            self.assertLessEqual(set(manifest['depends']),EXPECTED_ADDONS,name)
        emitted=self.emitted_addons()
        self.assertEqual(sorted(emitted),sorted(EXPECTED_ADDONS))
        self.assertEqual(len(emitted),len(set(emitted)))
        self.assertTrue((self.target/'odoo/addons/base/__manifest__.py').is_file())

    def test_emitted_addon_scan_detects_an_unexpected_engine_tree_addon(self):
        unexpected=self.target/'odoo/addons/mp_unexpected_probe'
        unexpected.mkdir()
        (unexpected/'__manifest__.py').write_text("{'name':'Unexpected probe'}",encoding='utf8')
        try:
            emitted=self.emitted_addons()
            self.assertIn('mp_unexpected_probe',emitted)
            self.assertNotEqual(sorted(emitted),sorted(EXPECTED_ADDONS))
        finally:
            shutil.rmtree(unexpected)
        self.assertEqual(sorted(self.emitted_addons()),sorted(EXPECTED_ADDONS))

    def test_materialized_source_has_no_app_packages_or_app_sources(self):
        self.assertFalse((self.target/'artifacts').exists())
        self.assertFalse(any(self.target.rglob('*.mplug')))
        for name in ('applications','examples','plugins','services','release','tests'):
            self.assertFalse((self.target/name).exists(),name)
        self.assertNotIn('artifacts',self.inventory)
        self.assertNotIn('reference_composition',self.inventory)
        self.assertNotIn('package_composition',self.inventory)
        self.assertFalse(set(self.emitted_addons())&EXCLUDED_ADDONS)

    def test_sdk_and_stock_webclient_are_shipped(self):
        self.assertIs(self.policy['stock_webclient'],True)
        self.assertIn('web',self.policy['addons'])
        self.assertNotIn('mp_shell',self.policy['addons'])
        self.assertTrue((self.target/'packages/platform_sdk/modular_platform/projection.py').is_file())
        self.assertTrue((self.target/'packages/platform_sdk/modular_platform/worker_start.py').is_file())
        self.assertTrue((self.target/'packages/contracts/v1').is_dir())
        self.assertTrue((self.target/'addons/web/__manifest__.py').is_file())

    def test_emitted_core_version_agrees_with_current_platform(self):
        manifest=ast.literal_eval((self.target/'addons/mp_core/__manifest__.py').read_text(encoding='utf8'))
        self.assertEqual(manifest['version'],'19.0.'+PLATFORM_VERSION)

    def test_observed_platform_and_native_core_must_match(self):
        runtime=staged_runtime([])
        runtime.update(platform_version=PLATFORM_VERSION,native_manifests={'mp_core':{'version':'19.0.'+PLATFORM_VERSION}})
        _,environment,provenance=runtime_inputs(runtime,[])
        self.assertEqual(environment['platform_version'],PLATFORM_VERSION)
        self.assertEqual(provenance['platform_version'],PLATFORM_VERSION)

        mismatched=staged_runtime([])
        mismatched.update(platform_version=PLATFORM_VERSION,native_manifests={'mp_core':{'version':'19.0.0.1.49'}})
        with self.assertRaisesRegex(PlanningError,'platform/native core'):
            runtime_inputs(mismatched,[])

        historical=staged_runtime([])
        historical.update(platform_version='0.1.49',native_manifests={'mp_core':{'version':'19.0.0.1.49'}})
        _,environment,provenance=runtime_inputs(historical,[])
        self.assertEqual(environment['platform_version'],'0.1.49')
        self.assertEqual(provenance['platform_version'],'0.1.49')


if __name__=='__main__':
    unittest.main()
