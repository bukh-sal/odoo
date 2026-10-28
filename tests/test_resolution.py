"""G5 pure whole-release solver: conflicts, real backtracking and target markers."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tools'))
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.resolution import PlanningError, dependent_closure, resolve_release
from reference_package import assemble

ENVIRONMENT = {'platform_version': '0.1.0', 'native_runtime': 'odoo-19',
    'accepted_wheel_tags': ['py3-none-any'], 'core_addons': ['mp_core', 'mp_shell'],
    'markers': {'implementation_name': 'cpython', 'implementation_version': '3.12.16',
        'os_name': 'posix', 'platform_machine': 'x86_64', 'platform_release': '6.12',
        'platform_system': 'Linux', 'platform_version': 'qualification',
        'python_full_version': '3.12.16', 'platform_python_implementation': 'CPython',
        'python_version': '3.12', 'sys_platform': 'linux'}}


def plugin(name, version='1.0.0', *, depends=None, python=(), optional=None, provides=(), requires=()):
    ident = 'org.test.' + name
    addon = 'test_' + name
    dependencies = {'org.test.' + key: value or '>=0' for key, value in (depends or {}).items()}
    manifest = {'schema_version': 1,
        'plugin': {'id': ident, 'version': version, 'name': name, 'description': 'test', 'publisher': 'test', 'license': 'LGPL-3.0-only'},
        'compatibility': {'platform': '>=0.1,<0.2', 'host_api_major': 1, 'ui_api_major': 1},
        'runtime': {'kind': 'native', 'addon_name': addon, 'native_compatibility': 'odoo-19', 'python': '>=3.12,<3.13', 'python_dependencies': list(python)},
        'activation': {'scopes': ['site', 'workspace'], 'supports_feature_suspension': True},
        'dependencies': {'plugins': dependencies},
        'integrations': {'optional': {'org.test.' + key: value for key, value in (optional or {}).items()}},
        'services': {'provides': list(provides), 'requires': list(requires)},
        'permissions': {'defines': {}, 'requests': []},
        'data': {'models': [], 'extension_targets': [], 'contributions': []},
        'ui': {'mode': 'none', 'design': 'standard', 'pages': [], 'navigation': []},
        'upgrade': {'strategy': 'native_migrations', 'requires_maintenance': True, 'destructive': False, 'transitions': []}}
    return {'manifest': manifest, 'digest': 'sha256:' + hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            'native_manifest': {'depends': ['mp_core'] + ['test_' + key for key in (depends or {})]},
            'inventory': {}, 'trust': {'model': 'operator-approved-exact-digest', 'signature_verified': False, 'policy_generation': 1, 'warnings': []}}


def wheel(name, version='1.0', *, requires=(), requires_python='>=3.12', tags=('py3-none-any',)):
    return {'name': name, 'version': version, 'kind': 'wheel', 'requires_dist': list(requires),
            'requires_python': requires_python, 'tags': list(tags),
            'digest': 'sha256:' + hashlib.sha256((name + version + repr(requires)).encode()).hexdigest()}


def provide(addon, api='1.0'):
    return {'id': 'org.test.shared.documents', 'api_version': api, 'schema': 'schemas/documents.json',
            'handler': 'test_' + addon + '.services:Service', 'methods': ['get']}


def require(alias='documents', version='>=1.0,<2.0', major=1, optional=False):
    return {'alias': alias, 'id': 'org.test.shared.documents', 'contract_major': major,
            'version': version, 'optional': optional}


def locked(*candidates):
    return {'plugin:' + item['manifest']['plugin']['id']: {'version': item['manifest']['plugin']['version'], 'digest': item['digest']} for item in candidates}


def versions(solution):
    return {item['manifest']['plugin']['id']: item['manifest']['plugin']['version'] for item in solution['plugins']}


class Resolution(unittest.TestCase):
    def solve(self, catalog, requested, wheels=(), **kwargs):
        return resolve_release(catalog, wheels, ENVIRONMENT, {'org.test.' + key: value for key, value in requested.items()}, **kwargs)

    def test_transitive_missing_dependency_and_constraint_explanation(self):
        catalog = [plugin('a', depends={'b': '>=1'}), plugin('b', depends={'c': '>=2'})]
        original = copy.deepcopy(catalog)
        with self.assertRaisesRegex(PlanningError, 'org.test.c>=2.*plugin:org.test.b'):
            self.solve(catalog, {'a': ''})
        self.assertEqual(catalog, original)
        with self.assertRaisesRegex(PlanningError, 'Plugin dependency conflict.*>=2'):
            self.solve(catalog + [plugin('c')], {'a': ''})

    def test_complete_backtracking_finds_older_non_greedy_solution(self):
        catalog = [plugin('a', '2.0.0', depends={'b': '>=2'}), plugin('a', depends={'b': '<2'}),
                   plugin('b'), plugin('b', '2.0.0'), plugin('c', depends={'b': '<2'})]
        solution = self.solve(catalog, {'a': '', 'c': ''})
        self.assertEqual(versions(solution)['org.test.a'], '1.0.0')
        self.assertEqual(versions(solution)['org.test.b'], '1.0.0')
        self.assertLess(solution['native_order'].index('test_b'), solution['native_order'].index('test_a'))
        self.assertIn('plugin:org.test.a==1.0.0 <2', solution['reasons']['plugin:org.test.b'])

    def test_exact_hard_cycle(self):
        with self.assertRaisesRegex(PlanningError, 'org.test.a -> org.test.b -> org.test.c -> org.test.a'):
            self.solve([plugin('a', depends={'b': ''}), plugin('b', depends={'c': ''}), plugin('c', depends={'a': ''})], {'a': ''})

    def test_locked_compatible_preserved_explicit_update_and_no_downgrade(self):
        old, new = plugin('a'), plugin('a', '2.0.0')
        solution = self.solve([old, new], {'a': ''}, locked=locked(old))
        self.assertEqual(versions(solution)['org.test.a'], '1.0.0')
        solution = self.solve([old, new], {'a': ''}, locked=locked(old), update=['org.test.a'])
        self.assertEqual(versions(solution)['org.test.a'], '2.0.0')
        with self.assertRaises(PlanningError):
            self.solve([old, new], {'a': '<2'}, locked=locked(new), update=['org.test.a'])

    def test_retains_every_installed_root_and_rechecks_transitive_compatibility(self):
        a, b = plugin('a'), plugin('b', depends={'a': '<2'})
        with self.assertRaises(PlanningError):
            self.solve([a, plugin('a', '2.0.0'), b], {'a': '>=2'}, locked=locked(a, b))

    def test_python_conflict_is_distinct_and_backtracks_plugin_candidate(self):
        catalog = [plugin('a', python=['shared<2']), plugin('b', python=['shared>=2'])]
        with self.assertRaisesRegex(PlanningError, 'Python dependency conflict.*shared'):
            self.solve(catalog, {'a': '', 'b': ''}, [wheel('shared'), wheel('shared', '2.0')])
        catalog = [plugin('a', '2.0.0', python=['shared>=2']), plugin('a', python=['shared<2'])]
        solution = self.solve(catalog, {'a': ''}, [wheel('shared')])
        self.assertEqual(versions(solution)['org.test.a'], '1.0.0')

    def test_complete_target_markers_extras_and_wheel_compatibility(self):
        catalog = [plugin('a', python=['shared[fast]>=1', 'winonly; sys_platform == "win32"'])]
        wheels = [wheel('shared', requires=['speed>=2; extra == "fast"', 'winonly; sys_platform == "win32"']),
                  wheel('speed', '2.0'), wheel('speed', '3.0', tags=['cp311-cp311-win_amd64'])]
        solution = self.solve(catalog, {'a': ''}, wheels)
        self.assertEqual([(item['name'], item['version']) for item in solution['python']], [('shared', '1.0'), ('speed', '2.0')])
        self.assertEqual(solution['python'][0]['extras'], ['fast'])
        env = copy.deepcopy(ENVIRONMENT)
        del env['markers']['sys_platform']
        with self.assertRaisesRegex(PlanningError, 'host defaults'):
            resolve_release(catalog, wheels, env, {'org.test.a': ''})
        with self.assertRaisesRegex(PlanningError, 'Python dependency conflict'):
            self.solve([plugin('a', python=['oldpython'])], {'a': ''}, [wheel('oldpython', requires_python='<3.12')])

    def test_no_dynamic_metadata_or_direct_url_resolution(self):
        with self.assertRaisesRegex(PlanningError, 'static metadata'):
            self.solve([plugin('a', python=['x @ https://example.invalid/pkg.whl'])], {'a': ''})
        with self.assertRaisesRegex(PlanningError, 'static wheel/runtime metadata'):
            self.solve([], {}, [{**wheel('a'), 'kind': 'source_build', 'command': 'execute'}])

    def test_multiple_providers_require_explicit_alias_and_exact_major(self):
        catalog = [plugin('consumer', requires=[require()]), plugin('one', provides=[provide('one')]),
                   plugin('two', provides=[provide('two')])]
        with self.assertRaisesRegex(PlanningError, 'Explicit provider binding.*org.test.one.*org.test.two'):
            self.solve(catalog, {'consumer': ''})
        solution = self.solve(catalog, {'consumer': ''}, provider_choices={('org.test.consumer', 'documents'): 'org.test.two'})
        self.assertEqual(solution['bindings'][0]['provider'], 'org.test.two')
        self.assertNotIn('org.test.one', versions(solution))
        self.assertEqual(solution['bindings'][0]['api_version'], '1.0')

    def test_service_constraints_backtrack_provider_version_and_parallel_majors(self):
        catalog = [plugin('consumer', requires=[require()]), plugin('one', provides=[provide('one')]),
                   plugin('one', '2.0.0', provides=[provide('one', '2.0')])]
        solution = self.solve(catalog, {'consumer': ''})
        self.assertEqual(versions(solution)['org.test.one'], '1.0.0')
        self.assertEqual(solution['bindings'][0]['api_version'], '1.0')
        with self.assertRaises(PlanningError):
            self.solve([catalog[0], catalog[-1]], {'consumer': ''})

    def test_optional_absent_incompatible_or_undeclared_native_coupling(self):
        consumer = plugin('consumer', optional={'one': '>=2'}, requires=[require(optional=True)])
        provider = plugin('one', provides=[provide('one')])
        solution = self.solve([consumer, provider], {'consumer': ''})
        self.assertEqual(len(solution['plugins']), 1)
        self.assertFalse(solution['optional_integrations'][0]['available'])
        self.assertEqual(solution['bindings'], [])
        solution = self.solve([consumer, provider], {'consumer': '', 'one': ''})
        self.assertFalse(solution['optional_integrations'][0]['available'])
        consumer['native_manifest']['depends'].append('test_one')
        with self.assertRaisesRegex(PlanningError, 'Native dependency mapping'):
            self.solve([consumer, provider], {'consumer': '', 'one': ''})

    def test_shared_runtime_sites_reject_different_native_versions(self):
        with self.assertRaisesRegex(PlanningError, 'shared-runtime site'):
            self.solve([plugin('a'), plugin('a', '2.0.0')], {'a': ''},
                       site_requirements={'siteA': {'org.test.a': '==1.0.0'}, 'siteB': {'org.test.a': '==2.0.0'}})

    def test_conflicting_native_addons_and_unmapped_extension_owner(self):
        first, second = plugin('a'), plugin('b')
        second['manifest']['runtime']['addon_name'] = first['manifest']['runtime']['addon_name']
        with self.assertRaisesRegex(PlanningError, 'native addon ownership'):
            self.solve([first, second], {'a': '', 'b': ''})
        second = plugin('b')
        second['manifest']['data']['extension_targets'] = ['mp.example.note']
        with self.assertRaisesRegex(PlanningError, 'extension target'):
            self.solve([second], {'b': ''})

    def test_provider_dependent_closure_needs_explicit_cascade(self):
        provider = plugin('a')
        consumer = plugin('b', depends={'a': ''})
        remote_consumer = plugin('c')
        remote_consumer['required_providers'] = ['org.test.b']
        with self.assertRaisesRegex(PlanningError, 'org.test.b, org.test.c'):
            dependent_closure([provider, consumer, remote_consumer], ['org.test.a'])
        self.assertEqual(dependent_closure([provider, consumer, remote_consumer], ['org.test.a'], cascade=True),
                         ['org.test.a', 'org.test.b', 'org.test.c'])

    def test_actual_three_reference_artifacts_resolve_without_import(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = []
            for name in ('notes', 'notes_labels', 'canvas'):
                _, raw, _ = assemble(ROOT, 'plugins/' + name + '/plugin.toml')
                path = Path(directory) / (name + '.mplug')
                path.write_bytes(raw)
                catalog.append(ArtifactValidator(TrustPolicy('development', allow_unsigned_development=True)).verify(path).descriptor())
            solution = resolve_release(catalog, [], ENVIRONMENT, {'org.example.canvas': '', 'org.example.notes_labels': ''})
            self.assertEqual(solution['native_order'], ['mp_example_notes', 'mp_example_canvas', 'mp_example_notes_labels'])
            self.assertEqual({item['contract_major'] for item in solution['bindings']}, {1, 2})
            self.assertEqual(len(solution['plugins']), 3)


if __name__ == '__main__':
    unittest.main()
