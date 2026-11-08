"""Portable build producer rejects unpinned or escaping artifact recipes."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import test_application_package as packages
from reference_package import toml_value
from compose_application_set import read_recipe


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.app=packages.ApplicationPackage();self.app.setUp();self.addCleanup(self.app.doCleanups)
        self.tmp=tempfile.TemporaryDirectory(prefix='mp-set-recipe-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'artifacts').mkdir()
        raw=self.app.build()[1];(self.root/'artifacts/app.mplug').write_bytes(raw)
        self.value=dict(schema_version=2,foundation={k:'sha256:'+c*64 for k,c in [('kit_manifest','a'),('image_id','b'),('inventory_digest','c')]},
            applications=[dict(artifact='artifacts/app.mplug',digest='sha256:'+hashlib.sha256(raw).hexdigest())])

    def recipe(self):
        path=self.root/'release.toml';path.write_text('\n'.join(k+' = '+toml_value(v) for k,v in self.value.items())+'\n',encoding='utf-8',newline='\n');return path

    def test_portable_digest_pinned_recipe_reads_without_importing_native_code(self):
        value,rows,digest=read_recipe(self.recipe());self.assertEqual(value,self.value);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['plugin_id'],'dev.aurora.tasks');self.assertTrue(digest.startswith('sha256:'))

    def test_unknown_top_level_or_foundation_keys_are_not_override_channels(self):
        self.value['command']='anything'
        with self.assertRaisesRegex(ValueError,'recipe2'):read_recipe(self.recipe())
        self.value.pop('command');self.value['foundation']['extra']='anything'
        with self.assertRaisesRegex(ValueError,'recipe2'):read_recipe(self.recipe())

    def test_absolute_and_parent_artifact_paths_cannot_escape_recipe_root(self):
        for name in ['../outside.mplug','C:/outside.mplug','/outside.mplug']:
            self.value['applications'][0]['artifact']=name
            with self.subTest(name=name),self.assertRaises(ValueError):read_recipe(self.recipe())

    def test_duplicate_identity_and_path_are_rejected_before_build(self):
        self.value['applications'].append(dict(self.value['applications'][0]))
        with self.assertRaises(ValueError):read_recipe(self.recipe())
        (self.root/'artifacts/copy.mplug').write_bytes((self.root/'artifacts/app.mplug').read_bytes())
        self.value['applications'][1]['artifact']='artifacts/copy.mplug'
        with self.assertRaisesRegex(ValueError,'Duplicate release package'):read_recipe(self.recipe())

    def test_changed_archive_bytes_do_not_keep_the_selected_digest(self):
        (self.root/'artifacts/app.mplug').write_bytes(b'changed')
        with self.assertRaises(ValueError):read_recipe(self.recipe())

if __name__=='__main__':unittest.main()
