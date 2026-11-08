"""Application composition guards preserve the pinned core before any writes."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import test_application_package as fixtures
from application_layer import apply_layer
from modular_platform.plans import data_digest
from package_materialization import materialize_archive


class ApplicationLayerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ApplicationPackage();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.tmp=tempfile.TemporaryDirectory(prefix='mp-layer-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'image';self.root.mkdir();self.inputs=Path(self.tmp.name)/'inputs';self.inputs.mkdir()
        meta,raw,_=self.fixture.build();descriptor,_,native=materialize_archive(raw,self.root/'addons')
        (self.root/'artifacts').mkdir();(self.root/'artifacts'/descriptor['file']).write_bytes(raw)
        core=self.root/'addons/mp_core/__manifest__.py';core.parent.mkdir();core.write_text("{'version':'19.0.0.1.49'}",encoding='utf-8')
        source=ast.literal_eval((native/'__manifest__.py').read_text(encoding='utf-8'))
        self.inventory=dict(policy=dict(addons=['base','web','mp_core','mp_aurora_tasks']),
            native_addons=dict(base=dict(depends=[]),web=dict(depends=['base']),mp_core=dict(depends=['web']),
                mp_aurora_tasks=dict(depends=source['depends'],auto_install=False,license=source['license'])),
            generated_patches=[],artifacts={'dev.aurora.tasks':descriptor},
            files={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})
        (self.root/'distribution-inventory.json').write_text(json.dumps(self.inventory),encoding='utf-8')
        self.fixture.manifest['plugin']['version']='0.1.1'
        p=self.fixture.addon/'__manifest__.py';p.write_text(p.read_text(encoding='utf-8').replace('19.0.0.1.0','19.0.0.1.1'),encoding='utf-8')
        self.fixture.write_manifest();self.make_input()

    def make_input(self):
        _,raw,_=self.fixture.build();(self.inputs/'application.mplug').write_bytes(raw)
        self.request=dict(schema_version=1,foundation_image_id='sha256:'+'a'*64,
            foundation_inventory_digest=data_digest(self.inventory),application_digest='sha256:'+hashlib.sha256(raw).hexdigest(),application_file='application.mplug')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def refused_unchanged(self,request=None):
        before=self.snapshot()
        with self.assertRaises(ValueError):apply_layer(self.root,self.inputs,request or self.request)
        self.assertEqual(self.snapshot(),before)

    def test_verified_archive_replaces_only_app_and_does_not_import_native_source(self):
        before=self.snapshot();result=apply_layer(self.root,self.inputs,self.request)
        self.assertEqual(result['version'],'0.1.1');self.assertTrue(result['policy_unchanged'])
        self.assertFalse(result['application_code_executed'])
        self.assertEqual((self.root/'addons/mp_core/__manifest__.py').read_bytes(),before['addons/mp_core/__manifest__.py'])
        self.assertFalse((self.root/'artifacts/dev.aurora.tasks-0.1.0.mplug').exists())
        self.assertTrue((self.root/'artifacts/dev.aurora.tasks-0.1.1.mplug').exists())
        # Fixture __init__ raises immediately if assembly imports it.

    def test_unknown_fields_boolean_schema_or_traversal_refused_before_writes(self):
        for changes in [dict(sql='anything'),dict(schema_version=True),dict(application_file='../application.mplug')]:
            with self.subTest(changes=changes):self.refused_unchanged(dict(self.request,**changes))

    def test_wrong_base_inventory_refused_before_writes(self):
        self.refused_unchanged(dict(self.request,foundation_inventory_digest='sha256:'+'b'*64))

    def test_core_source_drift_refused_before_writes(self):
        (self.root/'addons/mp_core/__manifest__.py').write_text("{'version':'19.0.0.1.50'}",encoding='utf-8')
        self.refused_unchanged()

    def test_undeclared_application_identity_refused_before_writes(self):
        self.fixture.manifest['plugin']['id']='dev.aurora.other';self.fixture.write_manifest();self.make_input();self.refused_unchanged()

    def test_missing_native_dependency_refused_before_writes(self):
        p=self.fixture.addon/'__manifest__.py';native=ast.literal_eval(p.read_text(encoding='utf-8'));native['depends'].append('missing_native')
        p.write_text(repr(native),encoding='utf-8');self.make_input();self.refused_unchanged()

    def test_same_version_and_downgrade_are_not_new_application_layers(self):
        self.fixture.manifest['plugin']['version']='0.1.0';self.fixture.write_manifest()
        p=self.fixture.addon/'__manifest__.py';p.write_text(p.read_text(encoding='utf-8').replace('19.0.0.1.1','19.0.0.1.0'),encoding='utf-8')
        self.make_input();self.refused_unchanged()

    def test_incompatible_foundation_version_refused_before_writes(self):
        self.fixture.manifest['compatibility']['platform']='>=9,<10';self.fixture.write_manifest();self.make_input();self.refused_unchanged()


if __name__=='__main__':unittest.main()
