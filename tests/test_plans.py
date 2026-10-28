"""G5 exact targets, hash closure, migration selection and stale-plan checks."""
import copy
from pathlib import Path
import sys
import unittest
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.plans import applicable_migrations, check_bundle, data_digest, prepare_plan, release_lock
from modular_platform.resolution import PlanningError, resolve_release
from modular_platform.contracts import canonical_plan
from test_resolution import ENVIRONMENT, plugin, provide, require

STAMP = '2026-10-28T05:00:00Z'


def ident(value):
    return str(UUID(int=value))


PROVENANCE = {'platform_version': '0.1.0', 'upstream_commit': '5c7defb49e020fec8b6bb82403a2f54eb79e92e1',
    'native_patch_set_digest': 'sha256:' + 'a' * 64, 'python_lock_digest': 'sha256:' + 'b' * 64,
    'core_inventory_digest': 'sha256:' + 'c' * 64,
    'python_runtime': {'version': '3.12.16', 'architecture': 'linux/amd64', 'marker_environment': ENVIRONMENT['markers']}}


def solution(catalog):
    return resolve_release(catalog, [], ENVIRONMENT, {item['manifest']['plugin']['id']: '==' + item['manifest']['plugin']['version'] for item in catalog})


def base_state(catalog=()):
    resolved = solution(catalog)
    lock = release_lock(resolved, PROVENANCE, generation=1, created_at=STAMP)
    return {'deployment_id': ident(10), 'site_ids': [ident(20)], 'generation': 1,
        'release_lock': lock, 'release_digest': data_digest(lock), 'installations': [],
        'policy_version': 1, 'operator_authorization_generation': 1}


def target(name='a', value=100, action='install', workspace=30):
    return {'installation_id': ident(value), 'site_id': ident(20), 'workspace_id': ident(workspace),
            'plugin_id': 'org.test.' + name, 'action': action}


def binding(consumer, provider, value=200):
    return {'schema_version': 1, 'binding_id': ident(value), 'site_id': consumer['site_id'],
        'workspace_id': consumer['workspace_id'], 'consumer_installation_id': consumer['installation_id'],
        'alias': 'documents', 'service_id': 'org.test.shared.documents', 'contract_major': 1, 'api_version': '1.0',
        'provider_plugin_id': provider['plugin_id'], 'provider_installation_id': provider['installation_id'],
        'generation': 1, 'optional': False}


class Plans(unittest.TestCase):
    def prepare(self, catalog, targets, *, state=None, **kwargs):
        state = copy.deepcopy(state or base_state())
        resolved = solution(catalog)
        lock = release_lock(resolved, PROVENANCE, generation=2, created_at=STAMP)
        return prepare_plan(state, lock, resolved, targets, operation_id=ident(500), created_at=STAMP, **kwargs)

    def test_install_exact_hash_targets_and_backup_no_state_mutation(self):
        state = base_state()
        previous = copy.deepcopy(state)
        bundle = self.prepare([plugin('a')], [target()], state=state)
        self.assertTrue(check_bundle(bundle, state))
        self.assertEqual(state, previous)
        self.assertTrue(bundle['plan']['backup']['required'])
        self.assertTrue(bundle['display']['native_code_requires_trust'])
        self.assertFalse(bundle['display']['feature_suspension_unloads_code'])
        self.assertEqual(bundle['plan']['dependency_lock_digest'], data_digest(bundle['operation_lock']))
        self.assertEqual(bundle, self.prepare([plugin('a')], [target()], state=state))
        canonical_plan(bundle['plan'])

    def test_stale_generation_permissions_policy_endpoint_and_operator_authority(self):
        state = base_state()
        bundle = self.prepare([plugin('a')], [target()], state=state)
        for key in ('generation', 'policy_version', 'operator_authorization_generation'):
            with self.subTest(key=key):
                changed = {**state, key: state[key] + 1}
                with self.assertRaisesRegex(PlanningError, 'Stale plan'):
                    check_bundle(bundle, changed)
        with self.assertRaisesRegex(PlanningError, 'Stale plan'):
            check_bundle(bundle, {**state, 'endpoint_generation': 2})

    def test_workspace_tamper_and_misleading_display_fail_closed(self):
        bundle = self.prepare([plugin('a')], [target()])
        changed = copy.deepcopy(bundle)
        changed['operation_lock']['targets'][0]['workspace_id'] = ident(999)
        with self.assertRaisesRegex(PlanningError, 'lock digest'):
            check_bundle(changed, base_state())
        for field, value in (('backup', {'required': False}), ('native_code_requires_trust', False), ('destructive', True)):
            changed = copy.deepcopy(bundle)
            changed['display'][field] = value
            with self.assertRaisesRegex(PlanningError, 'Displayed operation'):
                check_bundle(changed, base_state())

    def test_transitive_changes_and_all_shared_installations_need_explicit_targets(self):
        catalog = [plugin('a', depends={'b': '>=1'}), plugin('b')]
        with self.assertRaisesRegex(PlanningError, 'transitive artifact change'):
            self.prepare(catalog, [target()])
        self.prepare(catalog, [target(), target('b', 101)])
        old = plugin('a')
        state = base_state([old])
        state['installations'] = [{**target(), 'state': 'installed'}, {**target(value=101, workspace=31), 'state': 'installed'}]
        with self.assertRaisesRegex(PlanningError, 'untargeted installation'):
            self.prepare([plugin('a', '2.0.0')], [target(action='upgrade')], state=state, operation_type='upgrade')

    def test_installation_identity_unknown_action_duplicate_and_bad_site(self):
        for targets in ([target(), target()], [{**target(), 'site_id': ident(999)}],
                        [{**target(), 'action': 'uninstall'}], [{**target(), 'approved': True}]):
            with self.subTest(targets=targets):
                with self.assertRaises(PlanningError):
                    self.prepare([plugin('a')], targets)

    def test_scoped_alias_binding_cannot_cross_workspace_or_substitute_provider(self):
        catalog = [plugin('consumer', requires=[require()]), plugin('provider', provides=[provide('provider')])]
        consumer, provider = target('consumer'), target('provider', 101)
        correct = binding(consumer, provider)
        bundle = self.prepare(catalog, [consumer, provider], bindings=[correct])
        self.assertTrue(check_bundle(bundle, base_state()))
        for changed in ({**correct, 'workspace_id': ident(999)}, {**correct, 'provider_plugin_id': 'org.test.other'},
                        {**correct, 'api_version': '2.0'}, {**correct, 'alias': 'undeclared'}):
            with self.subTest(changed=changed):
                with self.assertRaises((PlanningError, ValueError)):
                    self.prepare(catalog, [consumer, provider], bindings=[changed])
        with self.assertRaisesRegex(PlanningError, 'Missing required scoped'):
            self.prepare(catalog, [consumer, provider])

    def test_adjacent_skipped_and_fresh_migration_selection_is_numeric(self):
        manifest = plugin('a', '0.3.0')['manifest']
        manifest['upgrade']['transitions'] = []
        for previous, version in [('0.1.0', '0.1.9'), ('0.1.9', '0.1.10'), ('0.1.10', '0.2.0'), ('0.2.0', '0.3.0')]:
            scripts = [{'phase': phase, 'path': 'migrations/19.0.' + version + '/' + phase + '-step.py',
                        'digest': 'sha256:' + 'd' * 64} for phase in ('end', 'pre', 'post')]
            manifest['upgrade']['transitions'].append({'from': previous, 'to': version, 'scripts': scripts})
        self.assertEqual(applicable_migrations(manifest, None), [])
        scripts = applicable_migrations(manifest, '0.1.9')
        self.assertEqual([item['target_version'] for item in scripts[::3]], ['0.1.10', '0.2.0', '0.3.0'])
        self.assertEqual([item['phase'] for item in scripts[:3]], ['pre', 'post', 'end'])
        self.assertEqual(len(applicable_migrations(manifest, '0.2.0')), 3)
        with self.assertRaisesRegex(PlanningError, 'strictly increase'):
            applicable_migrations(manifest, '0.3.0')

    def test_native_uninstall_is_destructive_preserves_source_and_covers_database(self):
        catalog = [plugin('a')]
        state = base_state(catalog)
        state['installations'] = [{**target(), 'state': 'installed'}, {**target(value=101, workspace=31), 'state': 'installed'}]
        resolved = solution(catalog)
        with self.assertRaisesRegex(PlanningError, 'every workspace'):
            prepare_plan(state, state['release_lock'], resolved, [target(action='uninstall')], operation_type='uninstall')
        bundle = prepare_plan(state, state['release_lock'], resolved,
            [target(action='uninstall'), target(value=101, workspace=31, action='uninstall')],
            operation_type='uninstall', created_at=STAMP)
        self.assertTrue(bundle['plan']['destructive'])
        self.assertTrue(bundle['plan']['backup']['required'])
        self.assertEqual(bundle['plan']['target_release_digest'], state['release_digest'])
        self.assertTrue(check_bundle(bundle, state))

    def test_artifact_removal_blocked_while_any_site_needs_it(self):
        state = base_state([plugin('a')])
        state['installations'] = [{**target(), 'state': 'installed'}]
        with self.assertRaisesRegex(PlanningError, 'still needed'):
            self.prepare([], [target(action='remove')], state=state, operation_type='remove')
        state['installations'][0]['state'] = 'not_installed'
        bundle = self.prepare([], [target(action='remove')], state=state, operation_type='remove')
        self.assertTrue(check_bundle(bundle, state))

    def test_permission_declaration_expansion_changes_approved_hash(self):
        first = plugin('a')
        state = base_state([first])
        state['installations'] = [{**target(), 'state': 'installed'}]
        second = plugin('a', '2.0.0')
        second['manifest']['permissions']['requests'] = [{'capability': 'org.example.notes:notes.read', 'scope': 'workspace', 'reason': 'new reviewed integration'}]
        bundle = self.prepare([second], [target(action='upgrade')], state=state, operation_type='upgrade')
        declarations = bundle['display']['declaration_changes']['org.test.a']
        self.assertEqual(len(declarations['target_permissions']['requests']), 1)
        self.assertNotEqual(bundle['plan']['base_release_digest'], bundle['plan']['target_release_digest'])


if __name__ == '__main__':
    unittest.main()
