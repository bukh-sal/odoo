"""Bounded factory isolation and fail-closed public asset preflight.

Host tests use fake Odoo objects; actual native compilation/HTTP retention is
separately required on a populated disposable candidate clone.
"""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.prepare_assets import prepare,validate_configuration
from modular_platform.native_executor import NativeExecutor


class FakeBundle:
    def __init__(self, *args, **kwargs):self.args,self.kwargs,self.deleted,self.name=args,kwargs,False,args[0]
    def _clean_attachments(self, extension, keep_url):self.deleted=True;return True
    def get_checksum(self,kind):return 'native-descriptor-'+kind


class FakeQWeb:
    def __init__(self):self.env={'ir.asset':SimpleNamespace(_get_asset_params=lambda:{'locale':'fixed'})}
    def _get_asset_content(self,name,params):return [{'url':'fixed/source.js'}],['https://example.invalid/fixed.js']
    def _get_asset_bundle(self,name,**kwargs):return FakeBundle(name,delegated=True,**kwargs)


class FactoryTests(unittest.TestCase):
    def setUp(self):
        odoo=ModuleType('odoo');odoo.models=SimpleNamespace(AbstractModel=FakeQWeb)
        native=ModuleType('odoo.addons.base.models.assetsbundle');native.AssetsBundle=FakeBundle
        release=ModuleType('odoo.addons.mp_identity.release');release.image_inventory_digest=lambda:'sha256:'+'a'*64
        with patch.dict(sys.modules,{'odoo':odoo,'odoo.addons.base.models.assetsbundle':native,'odoo.addons.mp_identity.release':release}):
            self.adapter=runpy.run_path(str(ROOT/'platform_addons/mp_shell/models/assets.py'))
        self.qweb=self.adapter['IrQWeb']()

    def test_release_host_keeps_old_attachments_and_preserves_factory_parameters(self):
        bundle=self.qweb._get_asset_bundle('mp_shell.assets_host',css=True,js=False,rtl=True,autoprefix=True)
        self.assertIsInstance(bundle,self.adapter['RetainedHostBundle'])
        self.assertEqual(bundle.kwargs['assets_params'],{'locale':'fixed'})
        self.assertTrue(bundle.kwargs['rtl']);self.assertFalse(bundle.kwargs['js'])
        bundle._clean_attachments('min.css','/web/assets/new/host.css')
        self.assertFalse(bundle.deleted)

    def test_other_bundle_and_debug_keep_native_cleanup(self):
        for name,debug in [('web.assets_web',False),('mp_shell.assets_host',True),('mp_shell.assets_host_private',False)]:
            with self.subTest(name=name,debug=debug):
                bundle=self.qweb._get_asset_bundle(name,debug_assets=debug,assets_params={'custom':'fixed'})
                self.assertIs(type(bundle),FakeBundle);self.assertTrue(bundle.kwargs['delegated'])
                bundle._clean_attachments('min.js','keep');self.assertTrue(bundle.deleted)

    def test_explicit_asset_parameters_are_not_replaced(self):
        params={'fixed':1};bundle=self.qweb._get_asset_bundle('mp_shell.assets_host',assets_params=params)
        self.assertIs(bundle.kwargs['assets_params'],params)

    def test_full_release_identity_changes_even_with_identical_native_timestamps(self):
        bundle=self.qweb._get_asset_bundle('mp_shell.assets_host');before=bundle.get_version('js')
        self.assertEqual(len(before),64);self.assertEqual(before,bundle.get_version('js'))
        with patch.dict(bundle.get_version.__globals__,image_inventory_digest=lambda:'sha256:'+'b'*64):
            self.assertNotEqual(before,bundle.get_version('js'))
        self.assertNotEqual(before,bundle.get_version('css'))

    def test_native_variant_descriptor_is_part_of_identity(self):
        bundle=self.qweb._get_asset_bundle('mp_shell.assets_host');before=bundle.get_version('js')
        bundle.get_checksum=lambda kind:'different-native-variant'
        self.assertNotEqual(before,bundle.get_version('js'))


def attachment(kind):
    raw=('public '+kind).encode()
    return SimpleNamespace(public=True,res_model='ir.ui.view',res_id=0,create_uid=SimpleNamespace(id=1),
        url='/web/assets/abcdef0/mp_shell.assets_host.min.'+kind,
        mimetype='text/css' if kind=='css' else 'application/javascript',raw=raw,
        checksum=hashlib.sha1(raw).hexdigest())


class CompileBundle:
    def __init__(self):
        self.files=[{'filename':__file__}];self.css_errors=[]
        self.outputs={'js':[attachment('js')],'css':[attachment('css')]};self.xml_failed=False
    def xml(self):
        if self.xml_failed:raise ValueError('Malformed native XML fixture')
        return []
    def js(self):return self.outputs['js']
    def css(self):return self.outputs['css']


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.bundle=CompileBundle();self.calls=[]
        def get(name,**kwargs):self.calls.append((name,kwargs));return self.bundle
        self.env={'ir.qweb':SimpleNamespace(_get_asset_bundle=get)}

    def test_regular_public_assets_have_exact_hashes_and_fixed_bundle(self):
        rows=prepare(self.env)
        self.assertEqual(len(rows),2)
        self.assertEqual(self.calls,[('mp_shell.assets_host',{'css':True,'js':True,'rtl':False})])
        self.assertEqual(rows[0]['sha256'],hashlib.sha256(b'public css').hexdigest())

    def test_private_payload_cannot_override_the_fixed_database_selector(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config'
            path.write_text('[options]\ndb_name = exact_fixture\n')
            validate_configuration(path,{'database':'exact_fixture'})
            for database in ['other_fixture','exact_fixture,other_fixture','']:
                with self.subTest(database=database),self.assertRaisesRegex(ValueError,'fixed configuration'):
                    validate_configuration(path,{'database':database})

    def test_missing_source_or_malformed_templates_fail(self):
        self.bundle.files=[{'filename':str(ROOT/'does-not-exist-asset-retention-fixture')}]
        with self.assertRaisesRegex(ValueError,'source missing'):prepare(self.env)
        self.bundle.files=[];self.bundle.xml_failed=True
        with self.assertRaisesRegex(ValueError,'XML'):prepare(self.env)

    def test_empty_or_failed_compile_is_not_green(self):
        self.bundle.outputs['css']=[]
        with self.assertRaisesRegex(ValueError,'output missing'):prepare(self.env)
        self.bundle.outputs['css']=[attachment('css')];self.bundle.css_errors=['Controlled compiler failure']
        with self.assertRaisesRegex(ValueError,'compilation failed'):prepare(self.env)

    def test_private_or_noncanonical_asset_metadata_is_rejected(self):
        for key,value in [('public',False),('res_model','mp.example.note'),('res_id',9),
                          ('create_uid',SimpleNamespace(id=2)),('mimetype','text/html'),
                          ('url','/web/content/123/private-document.js')]:
            with self.subTest(field=key):
                self.bundle.outputs['js']=[attachment('js')];setattr(self.bundle.outputs['js'][0],key,value)
                with self.assertRaisesRegex(ValueError,'metadata'):prepare(self.env)

    def test_changed_or_empty_bytes_are_rejected(self):
        for raw in [b'',b'changed bytes',None]:
            with self.subTest(raw=raw):
                self.bundle.outputs['js'][0].raw=raw
                with self.assertRaisesRegex(ValueError,'checksum'):prepare(self.env)

    def test_executor_child_uses_exact_target_and_propagates_failure(self):
        native=NativeExecutor.__new__(NativeExecutor);calls=[]
        native._child=lambda op,suffix,**kwargs:(['docker','run',kwargs['image_id']],suffix)
        native._private_command=lambda args,path,**kwargs:calls.append((args,path,kwargs))
        target={'image_id':'sha256:'+'a'*64,'sites':[{'database':'fresh_restore','site_id':'site'}],
                'deployment_id':'deployment','generation':23}
        native._prepare_assets('operation',target,{'release_digest':'release'},
            {'runtime':{'inventory_digest':'inventory'}},Path('private'),suffix='restored-assets')
        args,path,kwargs=calls[0];self.assertIn('-i',args);self.assertEqual(path,Path('private/assets.json'))
        self.assertEqual(json.loads(kwargs['input']),{'database':'fresh_restore','site_id':'site',
            'deployment_id':'deployment','generation':23,'release_digest':'release','inventory_digest':'inventory'})
        def fail(*args,**kwargs):raise ValueError('Controlled child failure')
        native._private_command=fail
        with self.assertRaisesRegex(ValueError,'child failure'):
            native._prepare_assets('op',target,{'release_digest':'r'},{'runtime':{'inventory_digest':'i'}},Path('private'))


if __name__=='__main__':unittest.main()
