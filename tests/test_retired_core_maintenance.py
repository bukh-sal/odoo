"""Retained removal history does not become executable maintenance scope."""
import copy
import unittest

from modular_platform.plans import check_bundle, prepare_plan, release_lock
import test_core_upgrade as core
import test_platform_deploy as deploy
from test_plans import base_state, ident, binding, solution, PROVENANCE, STAMP
import test_release_staging as staged


def fixture(*, source_removed=False, static=False):
    case = deploy.PlatformDeploy() if static else core.CoreUpgrade()
    case.setUp()
    row = copy.deepcopy(case.document['state']['installations'][0])
    row.update(state='not_installed', metadata_state='removed', feature_state='suspended')
    if source_removed:
        addon = case.old['manifest']['runtime']['addon_name']
        for runtime in (case.base, case.runtime):
            runtime['inventory']['artifacts'] = {}
            runtime['inventory']['native_addons'].pop(addon)
            runtime['native_manifests'].pop(addon)
            files = runtime['inventory']['files']
            runtime['inventory']['files'] = {
                p: digest for p, digest in files.items()
                if not p.startswith(('artifacts/', 'addons/' + addon + '/'))
            }
        case.catalog = []
        case.document['state'] = base_state()
        case.document['state'].update(bindings=[], endpoints=[])
        case.site['native_modules'] = [
            dict(addon=name, state='installed', version=manifest['version'])
            for name, manifest in case.base['native_manifests'].items()
        ]
    case.document['state']['installations'] = [row]
    case.site['installations'] = [
        dict(plugin_id=row['plugin_id'], installation_id=row['installation_id'], metadata_state='removed')
    ]
    return case, row


class RetiredCoreMaintenance(unittest.TestCase):
    def test_source_free_history_is_bound_and_independently_reconstructed(self):
        case, row = fixture(source_removed=True)
        before = copy.deepcopy(case.document)
        bundle = case.prepare(targets=[])
        self.assertEqual(bundle['operation_lock']['targets'], [])
        self.assertEqual(bundle['plan']['artifacts'], [])
        self.assertEqual(bundle['operation_lock']['release']['plugins'], [])
        self.assertTrue(bundle['plan']['backup']['required'])
        self.assertTrue(bundle['plan']['destructive'])
        check_bundle(bundle, case.document['state'])
        self.assertEqual(staged.StagedPlans.validator(case)(bundle), case.document['state'])
        self.assertEqual(case.document, before)
        self.assertEqual(case.document['state']['installations'], [row])

    def test_retained_archive_does_not_reactivate_its_retired_scope(self):
        case, row = fixture()
        bundle = case.prepare(targets=[])
        self.assertEqual(bundle['operation_lock']['targets'], [])
        self.assertEqual(bundle['plan']['artifacts'], [])
        self.assertEqual(bundle['operation_lock']['release']['plugins'],
                         case.document['state']['release_lock']['plugins'])
        self.assertEqual(case.document['state']['installations'], [row])
        check_bundle(bundle, case.document['state'])

    def test_live_scopes_still_require_every_explicit_target(self):
        case, retired = fixture()
        retired.update(plugin_id='org.test.retired', installation_id=ident(901))
        case.site['installations'][0].update(plugin_id=retired['plugin_id'],
                                             installation_id=retired['installation_id'])
        live = {k: v for k, v in case.target.items() if k != 'action'}
        live.update(state='installed', metadata_state='installed', feature_state='enabled')
        case.document['state']['installations'].append(live)
        case.site['installations'].append(dict(plugin_id=live['plugin_id'],
            installation_id=live['installation_id'], metadata_state='installed'))
        with self.assertRaises(ValueError):
            case.prepare(targets=[])
        bundle = case.prepare()
        self.assertEqual(bundle['operation_lock']['targets'], [case.target])
        check_bundle(bundle, case.document['state'])

    def test_partial_or_unknown_runtime_states_are_not_retired_history(self):
        for field, value in [('state', 'installed'), ('metadata_state', 'installed'),
                             ('feature_state', 'enabled'), ('state', None),
                             ('metadata_state', None), ('feature_state', None)]:
            with self.subTest(field=field, value=value):
                case, row = fixture(source_removed=True)
                if value is None:
                    row.pop(field)
                else:
                    row[field] = value
                with self.assertRaises(ValueError):
                    case.prepare(targets=[])

    def test_binding_to_retired_scope_refuses_in_both_directions(self):
        for field in ['consumer_installation_id', 'provider_installation_id']:
            with self.subTest(field=field):
                case, row = fixture(source_removed=True)
                current_binding = binding(row, row)
                current_binding[field] = row['installation_id']
                current_binding['provider_installation_id' if field == 'consumer_installation_id'
                                else 'consumer_installation_id'] = ident(999)
                case.document['state']['bindings'] = [current_binding]
                resolved = solution([])
                release = release_lock(resolved, PROVENANCE, generation=2, created_at=STAMP)
                with self.assertRaises(ValueError):
                    prepare_plan(case.document['state'], release, resolved, [],
                                 bindings=[current_binding], operation_type='core_upgrade',
                                 operation_id=ident(500), created_at=STAMP)

    def test_changed_historical_state_invalidates_the_reviewed_bundle(self):
        case, row = fixture(source_removed=True)
        bundle = case.prepare(targets=[])
        changed = copy.deepcopy(case.document['state'])
        changed['installations'][0]['feature_state'] = 'enabled'
        with self.assertRaises(ValueError):
            check_bundle(bundle, changed)

    def test_static_platform_deploy_observes_the_same_history_boundary(self):
        case, _ = fixture(static=True)
        bundle = case.prepare(targets=[])
        self.assertEqual(bundle['operation_lock']['targets'], [])
        self.assertFalse(bundle['plan']['destructive'])
        check_bundle(bundle, case.document['state'])


if __name__ == '__main__':
    unittest.main()
