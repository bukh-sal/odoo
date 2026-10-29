"""Guard real partial-commit semantics before any native registry import."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.worker_start import validate_installations


class InstallationGuardTests(unittest.TestCase):
    def setUp(self):
        self.artifact=dict(addon='mp_test_guard',version='0.2.2',digest='sha256:'+'a'*64)
        self.inventory=dict(artifacts={'org.test.guard':self.artifact})
        self.modules=[('mp_test_guard','installed','19.0.0.2.2')]
        self.row=['org.test.guard','native','installed','0.2.2',self.artifact['digest'],{'runtime':{'kind':'native','addon_name':'mp_test_guard'}}]

    def test_installed_and_suspended_features_retain_native_registration(self):
        for state in ['installed','suspended']:
            row=copy.deepcopy(self.row);row[2]=state
            validate_installations(self.inventory,self.modules,[row])

    def test_actual_post_uninstall_pre_metadata_shape_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'differs from native registration'):
            validate_installations(self.inventory,[],[self.row])

    def test_post_install_pre_metadata_shape_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'lacks installed platform metadata'):
            validate_installations(self.inventory,self.modules,[])

    def test_removed_metadata_requires_native_unregistration(self):
        row=copy.deepcopy(self.row);row[2]='removed'
        validate_installations(self.inventory,[],[row])
        validate_installations({},[],[row])
        with self.assertRaisesRegex(ValueError,'still has native registration'):
            validate_installations(self.inventory,self.modules,[row])

    def test_never_installed_packaged_artifact_does_not_require_installation(self):
        validate_installations(self.inventory,[],[])

    def test_package_identity_and_native_version_mismatches_are_rejected(self):
        for column,value in [(0,'org.test.other'),(3,'0.2.1'),(4,'sha256:'+'b'*64)]:
            row=copy.deepcopy(self.row);row[column]=value
            with self.subTest(column=column),self.assertRaises(ValueError):validate_installations(self.inventory,self.modules,[row])
        with self.assertRaises(ValueError):validate_installations(self.inventory,[('mp_test_guard','installed','19.0.0.2.1')],[self.row])

    def test_unrelated_core_native_modules_do_not_need_plugin_metadata(self):
        validate_installations(self.inventory,self.modules+[('base','installed','19.0.1.0')],[self.row])

    def test_malformed_installation_is_rejected(self):
        for column,value in [(1,'external_service'),(2,'unknown'),(5,{}),(5,None)]:
            row=copy.deepcopy(self.row);row[column]=value
            with self.subTest(column=column),self.assertRaises(ValueError):validate_installations(self.inventory,self.modules,[row])


if __name__=='__main__':unittest.main()
