"""Uninstall source/epoch/impact proof using real curated reference archives."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.approval_validation import IndependentValidator
from modular_platform.artifacts import ArtifactError, ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.contracts import plan_hash
from modular_platform.planning_cli import prepare_document
from modular_platform.plans import _display, check_bundle, data_digest, release_lock
from modular_platform.projection import catalog_validation_digest
from modular_platform.resolution import PlanningError, resolve_release
from modular_platform.uninstall_planning import prepare_current_image_uninstall
import test_planning_cli
from test_plans import ident, STAMP, PROVENANCE


class UninstallPlanning(unittest.TestCase):
    def setUp(self):
        # Reuse the actual archive fixture without inheriting/repeating its tests.
        self.fixture = test_planning_cli.PlanningCLI()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.catalog = Catalog(self.fixture.store, ArtifactValidator(TrustPolicy(
            approved_digests=frozenset(self.fixture.configuration['approved_digests'])))).snapshot()
        self.document = copy.deepcopy(self.fixture.document)
        targets = self.document['request']['targets']
        targets.extend([{**row, 'workspace_id': ident(31)} for row in list(targets)])
        installed = prepare_document(self.document, self.catalog)
        self.document.pop('request')
        self.document['state'].update(release_lock=installed['operation_lock']['release'], generation=2,
            release_digest=installed['plan']['target_release_digest'], bindings=installed['operation_lock']['bindings'], endpoints=[],
            installations=[{k: v for k, v in row.items() if k != 'action'} | dict(
                state='installed', metadata_state='installed', feature_state='enabled') for row in targets])
        entries = self.document['state']['release_lock']['plugins']
        self.site = dict(site_id=ident(20),
            installations=[dict(installation_id=next(r['installation_id'] for r in targets if r['plugin_id'] == entry['plugin_id']),
                plugin_id=entry['plugin_id'], version=entry['version'], digest=entry['digest'], metadata_state='installed') for entry in entries],
            features=[dict(installation_id=r['installation_id'], plugin_id=r['plugin_id'], workspace_id=r['workspace_id'], feature_state='enabled') for r in targets],
            native_modules=[dict(addon=e['native_addon'], state='installed', version=e['native_version']) for e in entries])
        self.site['grants'] = [dict(installation_id=row['installation_id'], workspace_id=workspace,
                                    capability=capability['capability'], state='approved', policy_version=1)
            for row in self.site['installations'] for workspace in (ident(30), ident(31))
            for capability in next(d for d in self.catalog if d['plugin_id'] == row['plugin_id'])['manifest']['permissions']['requests']]
        self.impact = self.make_impact({'org.example.notes_labels'})

    def make_impact(self, names):
        value = json.loads((ROOT / 'packages/contracts/examples/v1/lifecycle-impact.json').read_text(encoding='utf8'))['impact']
        value.update(site_id=self.site['site_id'], plugins=[], models=[], fields=[], metadata_records=[], assets=[])
        entries = {r['plugin_id']: r for r in self.document['state']['release_lock']['plugins']}
        for plugin in sorted(names):
            entry = entries[plugin]
            row = next(r for r in self.site['installations'] if r['plugin_id'] == plugin)
            value['plugins'].append(dict(plugin_id=plugin, installation_id=row['installation_id'], native_addon=entry['native_addon'],
                version=entry['version'], artifact_digest=entry['digest'], workspace_ids=[ident(30), ident(31)]))
        value['native_closure'] = sorted(r['native_addon'] for r in value['plugins'])
        value['requested_addons'] = list(value['native_closure'])
        return value

    def targets(self, impact=None):
        return [dict(installation_id=p['installation_id'], site_id=self.site['site_id'], plugin_id=p['plugin_id'],
                     workspace_id=w, action='uninstall') for p in (impact or self.impact)['plugins'] for w in p['workspace_ids']]

    def prepare(self, **kwargs):
        args = dict(impact=self.impact, targets=self.targets(), operation_id=ident(600), created_at=STAMP)
        args.update(kwargs)
        return prepare_current_image_uninstall(self.document, [self.site], self.catalog, **args)

    def validator(self, catalog=None, document=None, site=None):
        validator = object.__new__(IndependentValidator)
        snapshot_catalog = self.catalog if catalog is None else catalog
        snapshot_document = self.document if document is None else document
        snapshot_site = self.site if site is None else site
        owner = self
        class Snapshot:
            def snapshot(self): return copy.deepcopy(snapshot_catalog)
        class Observer:
            def read(self): return {'sites': [copy.deepcopy(snapshot_site)]}
            def state(self, observation, catalog): return copy.deepcopy(snapshot_document)
            def native_impact(self, observation, catalog, **kwargs): return copy.deepcopy(owner.impact)
        validator.catalog, validator.observer = Snapshot(), Observer()
        return validator

    def rehash(self, bundle):
        bundle['plan']['dependency_lock_digest'] = data_digest(bundle['operation_lock'])
        bundle['plan']['target_release_digest'] = data_digest(bundle['operation_lock']['release'])
        bundle['plan_hash'] = plan_hash(bundle['plan'])
        bundle['display'] = _display(bundle['plan'], bundle['operation_lock'])
        return bundle

    def assert_post_observation_lock(self, bundle):
        identities = {r['installation_id']: r['plugin_id'] for r in self.site['installations']}
        choices = {(identities[b['consumer_installation_id']], b['alias'], b['site_id'], b['workspace_id']): b['provider_plugin_id']
                   for b in bundle['operation_lock']['bindings']}
        selected = resolve_release(self.catalog, [], self.document['environment'],
            {r['manifest']['plugin']['id']: '==' + r['manifest']['plugin']['version'] for r in self.catalog},
            scoped_provider_choices=choices)
        observed = release_lock(selected, self.document['provenance'], generation=3, created_at=STAMP)
        self.assertEqual(observed, bundle['operation_lock']['release'])

    def test_epoch_preserves_executables_and_exact_surviving_binding_identities(self):
        previous = copy.deepcopy(self.document)
        bundle = self.prepare()
        old = self.document['state']['release_lock']
        new = bundle['operation_lock']['release']
        self.assertEqual(new['generation'], 3)
        self.assertNotEqual(bundle['plan']['target_release_digest'], self.document['state']['release_digest'])
        for key in set(old) - {'generation', 'created_at', 'service_selection'}: self.assertEqual(new[key], old[key], key)
        removed = self.impact['plugins'][0]['installation_id']
        expected = [b for b in self.document['state']['bindings'] if removed not in (b['consumer_installation_id'], b['provider_installation_id'])]
        self.assertEqual(bundle['operation_lock']['bindings'], expected)
        self.assertEqual(self.validator()(bundle), self.document['state'])
        self.assert_post_observation_lock(bundle)
        self.assertEqual(self.document, previous)
        self.assertTrue(bundle['plan']['destructive'] and bundle['plan']['backup']['required'] and bundle['display']['restart_required'])

    def test_complete_closure_can_remove_all_native_features_without_source_removal(self):
        self.impact = self.make_impact({r['plugin_id'] for r in self.site['installations']})
        bundle = self.prepare()
        self.assertEqual(bundle['operation_lock']['bindings'], [])
        self.assertEqual(len(bundle['operation_lock']['release']['plugins']), 3)
        self.assert_post_observation_lock(bundle)
        self.assertEqual(self.validator()(bundle), self.document['state'])

    def test_omitted_workspace_or_native_dependent_is_rejected_including_suspension(self):
        for row in self.site['features']:
            if row['plugin_id'] == 'org.example.notes_labels' and row['workspace_id'] == ident(31):
                row['feature_state'] = 'suspended'
        for row in self.document['state']['installations']:
            if row['plugin_id'] == 'org.example.notes_labels' and row['workspace_id'] == ident(31):
                row['feature_state'] = 'suspended'
        with self.assertRaisesRegex(PlanningError, 'complete approved impact'): self.prepare(targets=self.targets()[:1])
        incomplete = copy.deepcopy(self.impact); incomplete['plugins'][0]['workspace_ids'] = [ident(30)]
        with self.assertRaisesRegex(PlanningError, 'affected workspace'): self.prepare(impact=incomplete)
        self.impact = self.make_impact({'org.example.notes'})
        with self.assertRaisesRegex(PlanningError, 'Required provider|dependent cascade'): self.prepare()

    def test_impact_drift_cannot_be_fixed_by_rehashing_proposal(self):
        for mutation in ('counts', 'epoch', 'code', 'missing_impact'):
            bundle = self.prepare()
            if mutation == 'counts': bundle['operation_lock']['native_uninstall_impact']['metadata_records'] = [dict(native_addon='mp_example_notes_labels', model='ir.model.fields', records=999)]
            elif mutation == 'epoch': bundle['operation_lock']['release']['generation'] = 2
            elif mutation == 'code': bundle['operation_lock']['release']['core_inventory_digest'] = 'sha256:'+'f'*64
            else: bundle['operation_lock'].pop('native_uninstall_impact')
            self.rehash(bundle)
            self.assertTrue(check_bundle(bundle, self.document['state']))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.validator()(bundle)

    def test_complete_impact_and_installation_identity_and_dispatch_are_bound(self):
        for mutation in ('digest', 'identity', 'version', 'dispatch', 'duplicate', 'closure'):
            impact = copy.deepcopy(self.impact)
            if mutation == 'digest': impact['plugins'][0]['artifact_digest'] = 'sha256:'+'e'*64
            elif mutation == 'identity': impact['plugins'][0]['installation_id'] = ident(999)
            elif mutation == 'version': impact['plugins'][0]['version'] = '9.0.0'
            elif mutation == 'dispatch': impact['dispatch'] = dict(state='unsupported', tables=['mp_job'])
            elif mutation == 'duplicate': impact['plugins'].append(copy.deepcopy(impact['plugins'][0]))
            else: impact['native_closure'].append('mp_example_canvas')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.prepare(impact=impact)

    def test_independent_boundary_rejects_unknown_impact_fields_before_database_inspection(self):
        bundle = self.prepare()
        bundle['operation_lock']['native_uninstall_impact']['untrusted_command'] = 'not allowed'
        self.rehash(bundle)
        validator = self.validator()
        def forbidden_call(*args, **kwargs):
            self.fail('Malformed impact reached the database inspector')
        validator.observer.native_impact = forbidden_call
        with self.assertRaises(ValueError): validator(bundle)

    def test_revocations_are_explicit_and_independently_bound_to_affected_scopes(self):
        bundle = self.prepare()
        expected = [dict(plugin_id='org.example.notes_labels', workspace_id=g['workspace_id'],
                         capability=g['capability'], action='revoke') for g in self.site['grants']
                    if g['installation_id'] == self.impact['plugins'][0]['installation_id']]
        self.assertTrue(expected)
        self.assertEqual(bundle['plan']['permission_changes'], sorted(expected, key=lambda r: (
            r['plugin_id'], r['workspace_id'], r['capability'], r['action'])))
        bundle['plan']['permission_changes'] = []
        self.rehash(bundle)
        with self.assertRaises(ValueError): self.validator()(bundle)
        self.site['grants'].append({**self.site['grants'][-1], 'installation_id':self.impact['plugins'][0]['installation_id'],
                                   'workspace_id':ident(999)})
        with self.assertRaisesRegex(PlanningError, 'grant scope'): self.prepare()

    def test_uninstall_does_not_accept_provider_switch_or_unrelated_permission_change(self):
        base = dict(operation_type='uninstall', requested={}, targets=self.targets(), operation_id=ident(600), created_at=STAMP)
        for change in ({'permission_changes': [dict(anything=True)]}, {'requested': {'org.example.notes': '>=0.1'}},
                       {'provider_choices': [dict(consumer='org.example.canvas', alias='notes', provider='org.example.notes')]},
                       {'bindings': []}):
            with self.subTest(change=change), self.assertRaises(PlanningError):
                prepare_document({**self.document, 'request': base | change}, self.catalog)

    def catalog_generation2(self):
        validator = ArtifactValidator(TrustPolicy(
            approved_digests=frozenset(self.fixture.configuration['approved_digests']), generation=2))
        return Catalog(self.fixture.store, validator, readonly=True).snapshot()

    def prepare_with_catalog(self, catalog, document=None, impact=None, targets=None):
        document = copy.deepcopy(self.document if document is None else document)
        impact = self.impact if impact is None else impact
        targets = self.targets(impact) if targets is None else targets
        return prepare_current_image_uninstall(document, [self.site], catalog, impact=impact,
            targets=targets, operation_id=ident(610), created_at=STAMP)

    def fresh_document(self, catalog):
        document = copy.deepcopy(self.document)
        document['state']['catalog_validation_digest'] = catalog_validation_digest(catalog)
        return document

    def test_trust_generation_advance_retains_all_exact_published_trust_including_target(self):
        catalog2 = self.catalog_generation2()
        self.assertNotEqual({r['digest']: r['trust']['policy_generation'] for r in catalog2},
                            {r['digest']: r['trust']['policy_generation'] for r in self.catalog})
        document = self.fresh_document(catalog2)
        before = copy.deepcopy(document)
        bundle = self.prepare_with_catalog(catalog2, document)
        old = {r['plugin_id']: r for r in document['state']['release_lock']['plugins']}
        new = {r['plugin_id']: r for r in bundle['operation_lock']['release']['plugins']}
        self.assertEqual(set(new), set(old))
        self.assertEqual(new, old)
        target = self.impact['plugins'][0]
        self.assertIn(target['plugin_id'], new)
        self.assertEqual(new[target['plugin_id']]['trust'], old[target['plugin_id']]['trust'])
        removed = target['installation_id']
        expected = [b for b in document['state']['bindings'] if removed not in (b['consumer_installation_id'], b['provider_installation_id'])]
        self.assertEqual(bundle['operation_lock']['bindings'], expected)
        expected_revocations = [dict(plugin_id=target['plugin_id'], workspace_id=g['workspace_id'],
                                     capability=g['capability'], action='revoke')
                                for g in self.site['grants'] if g['installation_id'] == removed]
        self.assertEqual(bundle['plan']['permission_changes'], sorted(expected_revocations, key=lambda r: (
            r['plugin_id'], r['workspace_id'], r['capability'], r['action'])))
        self.assertEqual(document, before)
        self.assertEqual(self.validator(catalog2, document)(bundle), document['state'])

    def test_stale_catalog_validation_and_missing_unapproved_or_quarantined_archive_still_refuse(self):
        catalog2 = self.catalog_generation2()
        stale = self.fresh_document(catalog2)
        stale['state']['catalog_validation_digest'] = catalog_validation_digest(self.catalog)
        with self.assertRaisesRegex(PlanningError, 'catalog validation'):
            self.prepare_with_catalog(catalog2, stale)
        target_digest = self.impact['plugins'][0]['artifact_digest']
        restricted = [row for row in catalog2 if row['digest'] != target_digest]
        with self.assertRaises(PlanningError):
            self.prepare_with_catalog(restricted, self.fresh_document(restricted))
        unapproved_validator = ArtifactValidator(TrustPolicy(
            approved_digests=frozenset(d for d in self.fixture.configuration['approved_digests'] if d != target_digest),
            generation=2))
        unapproved = Catalog(self.fixture.store, unapproved_validator, readonly=True)
        with self.assertRaises(ArtifactError):
            unapproved.snapshot()
        with tempfile.TemporaryDirectory(prefix='mp-uninstall-catalog-') as temporary:
            copied = Path(temporary) / 'catalog'
            shutil.copytree(self.fixture.store, copied)
            quarantine_validator = ArtifactValidator(TrustPolicy(
                approved_digests=frozenset(self.fixture.configuration['approved_digests']), generation=2))
            writable = Catalog(copied, quarantine_validator)
            writable.quarantine(target_digest)
            with self.assertRaises(PlanningError):
                self.prepare_with_catalog(writable.snapshot(), self.document)

    def test_rehashed_forged_old_trust_for_any_exact_archive_is_rejected(self):
        catalog2 = self.catalog_generation2()
        document = self.fresh_document(catalog2)
        bundle = self.prepare_with_catalog(catalog2, document)
        target_pid = self.impact['plugins'][0]['plugin_id']
        survivor_pid = next(r['plugin_id'] for r in bundle['operation_lock']['release']['plugins']
                            if r['plugin_id'] != target_pid)
        for plugin_id in (target_pid, survivor_pid):
            forged = copy.deepcopy(bundle)
            entry = next(r for r in forged['operation_lock']['release']['plugins'] if r['plugin_id'] == plugin_id)
            entry['trust']['policy_generation'] = 2
            self.rehash(forged)
            with self.subTest(plugin_id=plugin_id), self.assertRaises(ValueError):
                self.validator(catalog2, document)(forged)

    def test_changed_published_manifest_identity_cannot_retain_old_trust(self):
        catalog2 = self.catalog_generation2()
        document = self.fresh_document(catalog2)
        document['state']['release_lock']['plugins'][0]['manifest_digest'] = 'sha256:' + 'f' * 64
        with self.assertRaisesRegex(PlanningError, 'Historical trust'):
            self.prepare_with_catalog(catalog2, document)


if __name__ == '__main__': unittest.main()
