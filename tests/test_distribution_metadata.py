"""Bootstrap must not depend on catalog entries for absent vendor apps."""
import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class DistributionMetadataTest(unittest.TestCase):
    def test_catalog_and_settings_resolve_only_available_capabilities(self):
        base = ROOT / 'framework_addons/base'
        catalog = ET.parse(base / 'data/ir_module_module.xml')
        self.assertEqual(list(catalog.iter('record')), [], 'Available manifests seed the catalog')
        views = ET.parse(base / 'views/ir_module_views.xml')
        self.assertFalse(any('odoo.com' in e.get('href', '') for e in views.iter('a')))
        self.assertFalse(any('apps.odoo.com' in (e.text or '') for e in views.iter('field')))
        settings = ET.parse(ROOT / 'framework_addons/base_setup/views/res_config_settings_views.xml')
        modules = {e.get('name') for e in settings.iter('field') if e.get('name', '').startswith('module_')}
        self.assertEqual(modules, {'module_base_import'})

    def test_optional_app_boundaries(self):
        manifest = ast.literal_eval((ROOT / 'framework_addons/mail/__manifest__.py').read_text())
        self.assertFalse(manifest['application'])
        self.assertNotIn('web_tour', manifest['depends'])
        self.assertNotIn('views/fetchmail_views.xml', manifest['data'])
        self.assertNotIn('views/discuss_public_templates.xml', manifest['data'])
        self.assertNotIn('mail.assets_public', manifest['assets'])
        self.assertFalse((ROOT / 'framework_addons/mail/models/fetchmail.py').exists())
        self.assertTrue((ROOT / 'applications/mp_mail_gateway/tests/test_fetchmail.py').exists())
        tours=ast.literal_eval((ROOT/'framework_addons/web_tour/__manifest__.py').read_text())
        self.assertFalse(tours['auto_install'])

    def test_generic_service_data_does_not_require_extracted_application_ids(self):
        manifest=ast.literal_eval((ROOT/'framework_addons/mail/__manifest__.py').read_text())
        trees=[ET.parse(ROOT/'framework_addons/mail'/name) for name in manifest['data'] if name.endswith('.xml')]
        service_ids={node.get('id').removeprefix('mail.') for tree in trees for node in tree.iter() if node.get('id')}
        app_ids=set()
        for app in ('mp_discuss','mp_mail_gateway'):
            for path in (ROOT/'applications'/app).rglob('*.xml'):
                app_ids.update(node.get('id').split('.')[-1] for node in ET.parse(path).iter() if node.get('id'))
        extracted=app_ids-service_ids
        for tree in trees:
            for node in tree.iter():
                for name in ('parent','ref','action'):
                    value=node.get(name,'')
                    self.assertFalse(value.startswith(('mp_discuss.','mp_mail_gateway.')),value)
                    local=value.removeprefix('mail.')
                    self.assertNotIn(local,extracted,value)


if __name__ == "__main__":
    unittest.main()
