"""AT-01 data-only non-example assembly, admission and byte stability probes."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'packages/platform_sdk')]
from application_package import assemble_application
from modular_platform.artifacts import ArtifactValidator, TrustPolicy, ArtifactError
from reference_package import assemble, toml_value, validate_reference_composition


class ApplicationPackage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mp-at-authoring-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.addon = self.root/'applications/mp_aurora_tasks'
        shutil.copytree(ROOT/'tests/fixtures/application_authoring/mp_aurora_tasks', self.addon,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        # If the builder imported native source, this raises immediately.
        (self.addon/'__init__.py').write_text('raise RuntimeError("native import forbidden in packaging")\n',
                                             encoding='utf8')
        template, _, _ = assemble(ROOT, 'plugins/background/plugin.toml')
        self.manifest = copy.deepcopy(template)
        self.manifest['plugin'].update(id='dev.aurora.tasks', version='0.1.0', name='Aurora Tasks',
                                       publisher='aurora', description='Shared list-bound tasks')
        self.manifest['runtime']['addon_name'] = 'mp_aurora_tasks'
        self.manifest['activation']['scopes'] = ['site']
        self.manifest['activation']['supports_feature_suspension'] = False
        self.manifest['permissions'] = dict(defines={}, requests=[])
        self.manifest['services'] = dict(provides=[], requires=[])
        self.manifest['ui'] = dict(mode='none',design='standard',pages=[],navigation=[])
        models = ['mp.aurora.task', 'mp.aurora.task.list', 'mp.aurora.task.stage']
        self.manifest['data'] = dict(models=models, extension_targets=[], contributions=[
            dict(kind='model', id=model, target='site', delete_policy='owned') for model in models])
        self.write_manifest()
        (self.root/'LICENSE').write_bytes((ROOT/'LICENSE').read_bytes())
        (self.root/'application.toml').write_text('''schema_version = 1
manifest = "plugin.toml"
addon = "applications/mp_aurora_tasks"
[resources]
"notices/LICENSE" = "LICENSE"
''', encoding='utf8')

    def write_manifest(self):
        (self.root/'plugin.toml').write_text('\n'.join(
            json.dumps(k)+' = '+toml_value(v) for k, v in self.manifest.items())+'\n', encoding='utf8')

    def build(self):
        return assemble_application(self.root, 'application.toml')

    def test_non_example_repeatable_validated_and_ownership_checked(self):
        manifest, raw, files = self.build()
        self.assertEqual(raw, self.build()[1])
        self.assertEqual(manifest['plugin']['id'], 'dev.aurora.tasks')
        self.assertIn('backend/odoo_addons/mp_aurora_tasks/models.py', files)
        self.assertIn('notices/LICENSE', files)
        composition = validate_reference_composition([raw])
        self.assertEqual(set(composition['models']), set(manifest['data']['models']))
        artifact = self.root/'app.mplug'
        artifact.write_bytes(raw)
        # Structural preflight is not curated operator approval.
        with self.assertRaises(ArtifactError):
            ArtifactValidator(TrustPolicy()).verify(artifact)
        digest = 'sha256:'+hashlib.sha256(raw).hexdigest()
        verified = ArtifactValidator(TrustPolicy(approved_digests=frozenset({digest}))).verify(
            artifact, expected_digest=digest)
        self.assertEqual(verified.manifest['plugin']['id'], 'dev.aurora.tasks')

    def test_native_version_mismatch_rejected(self):
        self.manifest['plugin']['version'] = '0.1.1'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'versions must agree'):
            self.build()

    def test_parent_traversal_rejected(self):
        recipe = self.root/'application.toml'
        recipe.write_text(recipe.read_text().replace('"LICENSE"', '"../LICENSE"'), encoding='utf8')
        with self.assertRaises(ValueError):
            self.build()

    def test_explicit_notice_required(self):
        recipe = self.root/'application.toml'
        recipe.write_text(recipe.read_text().replace('"notices/LICENSE" = "LICENSE"', ''), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'notices required'):
            self.build()

    def test_resources_cannot_override_code(self):
        recipe = self.root/'application.toml'
        recipe.write_text(recipe.read_text().replace('notices/LICENSE', 'backend/replacement'), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'cannot replace'):
            self.build()

    def test_symlink_source_refused(self):
        link = self.addon/'linked.py'
        try:
            link.symlink_to(self.root/'LICENSE')
        except OSError:
            self.skipTest('Windows symlink privilege unavailable')
        with self.assertRaisesRegex(ValueError, 'Linked application source'):
            self.build()


if __name__ == '__main__':
    unittest.main()
