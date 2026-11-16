"""Actual native asset include/remove/path consumer; ORM/manifest lookup is fake.

This does not initialize Odoo, import an application or compile a browser bundle.
The installed029 lazy-bundle counterexample is retained separately.
"""
import ast
import copy
import hashlib
import json
import logging
import os
import sys
from glob import glob
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'framework_addons/base/models/ir_asset.py'
ADDONS = ['base', 'web', 'base_setup', 'auth_password_policy', 'bus', 'mp_compat', 'mp_identity', 'mp_core']
ICON_PATHS = ['web/static/src/interface/' + path for path in ['icons/lucide.js', 'icon.js', 'icon.xml', 'icon.scss']]


def native_asset_paths(bundle, web_manifest=None):
    manifests = {}
    for addon in ADDONS:
        data = ast.literal_eval((ROOT / 'framework_addons' / addon / '__manifest__.py').read_text(encoding='utf-8'))
        if addon == 'web' and web_manifest is not None:
            data = web_manifest
        class ManifestData(dict):
            pass
        item = ManifestData(data)
        item.setdefault('assets', {})
        item.addons_path = str(ROOT / 'framework_addons')
        item.path = str(ROOT / 'framework_addons' / addon)
        manifests[addon] = item

    namespace = dict(os=os, glob=glob, urls=SimpleNamespace(url_parse=urlsplit),
        Manifest=SimpleNamespace(for_addon=lambda name, **_kwargs: manifests.get(name)),
        _logger=logging.getLogger(__name__))
    constants = ast.parse((ROOT / 'engine/odoo/tools/constants.py').read_text(encoding='utf-8'))
    wanted = {'SCRIPT_EXTENSIONS', 'STYLE_EXTENSIONS', 'TEMPLATE_EXTENSIONS', 'ASSET_EXTENSIONS', 'EXTERNAL_ASSET'}
    nodes = [node for node in constants.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<native asset constants>', 'exec'), namespace)

    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    methods = {'_fill_asset_paths', '_process_path', '_process_command', '_get_paths'}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper():
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {'fs2web', 'can_aggregate', 'is_wildcard_glob', '_glob_static_file'}:
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == 'AssetPaths':
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == 'IrAsset':
            body = [method for method in node.body if isinstance(method, ast.FunctionDef) and method.name in methods]
            for method in body:
                method.decorator_list = []
            nodes.append(ast.ClassDef(name='NativeAssets', bases=[], keywords=[], body=body, decorator_list=[]))
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(SOURCE), 'exec'), namespace)
    class NoDatabaseAssets(list):
        def filtered(self, _predicate):
            return self
    engine = namespace['NativeAssets']()
    engine._get_related_assets = lambda *_args, **_kwargs: NoDatabaseAssets()
    paths = namespace['AssetPaths']()
    engine._fill_asset_paths(bundle, paths, [], ADDONS, ADDONS)
    return [path.lstrip('/') for path, _filename, _bundle, _mtime in paths.list]


class SharedIconAssetClosure(unittest.TestCase):
    def test_shared_sidebar_badge_and_record_patterns_are_backend_only_exactly_once(self):
        backend = native_asset_paths('web.assets_backend')
        frontend = native_asset_paths('web.assets_frontend_lazy')
        for name in ['badge.js', 'badge.xml', 'context_nav.js', 'context_nav.xml',
                     'record_layout.js', 'record_layout.xml', 'patterns.css']:
            path = 'web/static/src/interface/' + name
            self.assertEqual(backend.count(path), 1)
            self.assertNotIn(path, frontend)
            self.assertTrue((ROOT / 'framework_addons' / path).is_file())

    def test_native_identity_field_has_its_actual_editing_and_template_dependencies(self):
        paths = native_asset_paths('web.assets_backend')
        for path in ['web/static/src/views/fields/identity/identity_field.' + suffix
                for suffix in ['js', 'xml', 'scss']]:
            self.assertEqual(paths.count(path), 1)
        self.assertIn('web/static/src/views/fields/char/char_field.js', paths)

    def test_current_frontend_and_backend_supply_the_actual_palette_dependency_once(self):
        for bundle in ['web.assets_frontend_lazy', 'web.assets_backend']:
            with self.subTest(bundle=bundle):
                paths = native_asset_paths(bundle)
                self.assertIn('web/static/src/core/commands/command_palette.js', paths)
                for path in ICON_PATHS:
                    self.assertEqual(paths.count(path), 1, (bundle, path))
                    self.assertTrue((ROOT / 'framework_addons' / path).is_file())

    def test_captured029_manifest_reproduces_backend_only_dependency(self):
        captured = json.loads((ROOT / 'tests/fixtures/ui-shell029-backend-only-manifest.json').read_bytes())
        frontend = native_asset_paths('web.assets_frontend_lazy', captured['manifest'])
        backend = native_asset_paths('web.assets_backend', captured['manifest'])
        self.assertIn('web/static/src/core/commands/command_palette.js', frontend)
        self.assertIn('from "@web/interface/icon"', (ROOT / 'framework_addons/web/static/src/core/commands/command_palette.js').read_text(encoding='utf-8'))
        self.assertNotIn('web/static/src/interface/icon.js', frontend)
        self.assertIn('web/static/src/interface/icon.js', backend)

    def test_minimal_login_and_frontend_do_not_import_backend_application_chrome(self):
        minimal = native_asset_paths('web.assets_frontend_minimal')
        frontend = native_asset_paths('web.assets_frontend_lazy')
        self.assertNotIn('web/static/src/interface/icon.js', minimal)
        for path in ['interface/context_preference.js', 'interface/app_layout.js', 'webclient/shell/shell.js']:
            self.assertNotIn('web/static/src/' + path, frontend)

    def test_native_creation_closure_is_backend_only_in_existing_native_glob(self):
        backend = native_asset_paths('web.assets_backend')
        frontend = native_asset_paths('web.assets_frontend_lazy')
        minimal = native_asset_paths('web.assets_frontend_minimal')
        additions = ['record_creation.js', 'record_create_dialog.js', 'record_create_dialog.xml', 'record_create_dialog.scss']
        for name in additions:
            path = 'web/static/src/views/view_dialogs/' + name
            self.assertIn(path, backend)
            self.assertNotIn(path, frontend)
            self.assertNotIn(path, minimal)
        for dependency in ['views/view_dialogs/form_view_dialog.js', 'views/form/form_controller.js',
                           'core/dialog/dialog.js', 'core/network/rpc.js', 'interface/icon.js']:
            self.assertIn('web/static/src/' + dependency, backend)
        self.assertNotIn('web/static/src/webclient/actions/action_service.js', frontend)

    def test_shared_record_composition_closure_is_available_to_native_apps_only(self):
        backend = native_asset_paths('web.assets_backend')
        frontend = native_asset_paths('web.assets_frontend_lazy')
        minimal = native_asset_paths('web.assets_frontend_minimal')
        for name in ['record_sections.js', 'record_sections.xml', 'record_sections.css']:
            path = 'web/static/src/interface/' + name
            self.assertEqual(backend.count(path), 1)
            self.assertNotIn(path, frontend)
            self.assertNotIn(path, minimal)
        self.assertIn('web/static/src/interface/icon.js', backend)


class SharedIconMaintenanceFence(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
        from modular_platform.release_staging import require_web_presentation_manifest
        from modular_platform.operator_os import OperatorError
        self.require = require_web_presentation_manifest
        self.error = OperatorError
        self.previous = json.loads((ROOT / 'tests/fixtures/ui-shell029-backend-only-manifest.json').read_bytes())['manifest']
        self.target = json.loads((ROOT / 'tests/fixtures/ui-shell030-shared-icon-manifest.json').read_bytes())['manifest']
        self.files = {'addons/' + path: hashlib.sha256((ROOT / 'framework_addons' / path).read_bytes()).hexdigest() for path in ICON_PATHS}

    def test_exact_relocation_accepts_without_mutating_manifest_or_inventory(self):
        before = copy.deepcopy((self.previous, self.target, self.files))
        self.require(self.previous, self.target, self.files)
        self.assertEqual((self.previous, self.target, self.files), before)

    def test_external_substitution_extra_graph_or_reordered_includes_refuse(self):
        group = 'web._assets_interface_icons'
        variants = []
        external = copy.deepcopy(self.target)
        external['assets'][group][0] = 'https://icons.invalid/icons.js'
        variants.append(external)
        extra = copy.deepcopy(self.target)
        extra['assets']['web.assets_frontend'].append('web/static/src/interface/unreviewed.js')
        variants.append(extra)
        duplicate = copy.deepcopy(self.target)
        duplicate['assets']['web._assets_core'].append(['include', group])
        variants.append(duplicate)
        reorder = copy.deepcopy(self.target)
        values = reorder['assets']['web.assets_frontend']
        values.remove(['include', group])
        values.insert(0, ['include', group])
        variants.append(reorder)
        deletion = copy.deepcopy(self.target)
        deletion['assets']['web.assets_backend'].remove('web/static/src/interface/foundation.css')
        variants.append(deletion)
        native = copy.deepcopy(self.target)
        native['depends'].append('unreviewed_addon')
        variants.append(native)
        for variant in variants:
            with self.subTest(assets=variant['assets'].get(group)):
                with self.assertRaises(self.error):
                    self.require(self.previous, variant, self.files)

    def test_missing_malformed_source_or_changed_prior_shape_refuse(self):
        for files in [{}, self.files | {'addons/' + ICON_PATHS[-1]: 'sha256:' + 'a' * 64}]:
            with self.assertRaises(self.error):
                self.require(self.previous, self.target, files)
        prior = copy.deepcopy(self.previous)
        prior['assets']['web.assets_backend'].append(ICON_PATHS[0])
        with self.assertRaises(self.error):
            self.require(prior, self.target, self.files)

    def test_existing_backend_append_and_non_asset_metadata_fences_remain(self):
        target = copy.deepcopy(self.previous)
        path = 'web/static/src/interface/another_component.js'
        target['assets']['web.assets_backend'].append(path)
        self.require(self.previous, target, {'addons/' + path: 'a' * 64})
        target['data'].append('unreviewed/native-data.xml')
        with self.assertRaises(self.error):
            self.require(self.previous, target, {'addons/' + path: 'a' * 64})

    def test_current_shared_component_append_uses_existing_inventory_fence(self):
        target = json.loads(json.dumps(ast.literal_eval((ROOT / 'framework_addons/web/__manifest__.py').read_text(encoding='utf-8'))))
        previous_backend = self.target['assets']['web.assets_backend']
        paths = target['assets']['web.assets_backend'][len(previous_backend):]
        self.assertEqual(target['assets']['web.assets_backend'][:len(previous_backend)], previous_backend)
        files = {'addons/' + path: hashlib.sha256((ROOT / 'framework_addons' / path).read_bytes()).hexdigest() for path in paths}
        self.require(self.target, target, files)
        with self.assertRaises(self.error):
            self.require(self.target, target, {})
        for path in paths:
            missing = dict(files)
            del missing['addons/' + path]
            with self.subTest(missing=path), self.assertRaises(self.error):
                self.require(self.target, target, missing)


if __name__ == '__main__':
    unittest.main()
