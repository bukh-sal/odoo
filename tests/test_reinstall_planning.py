"""Data-only retained-scope planning; not proof of actual native deletion/init."""
import copy
from pathlib import Path
import sys
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.approval_validation import IndependentValidator
from modular_platform.contracts import plan_hash
from modular_platform.lifecycle_planning import prepare_current_image_install, prepare_current_feature
from modular_platform.manager_planning import prepare_manager_native
from modular_platform.native_executor import native_maintenance_flags, verify_native_state
from modular_platform.plans import _display, data_digest, release_lock
from modular_platform.resolution import resolve_release
from modular_platform.operator_store import OperatorStore
import test_uninstall_planning
from test_plans import ident, STAMP, base_state, PROVENANCE
from test_release_staging import staged_runtime
from test_resolution import plugin, ENVIRONMENT


class ReinstallPlanning(unittest.TestCase):
    def setUp(self):
        self.fixture = test_uninstall_planning.UninstallPlanning()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.catalog = self.fixture.catalog
        self.document = copy.deepcopy(self.fixture.document)
        self.site = copy.deepcopy(self.fixture.site)
        self.site['workspaces'] = [dict(workspace_id=ident(30), state='active'), dict(workspace_id=ident(31), state='active')]
        self.remove({'org.example.notes_labels'})

    def remove(self, plugins):
        # Construct a hypothetical checkpoint for pure planning only. Actual
        # uninstall/SQL effects must be qualified on the disposable deployment.
        self.fixture.document = self.document; self.fixture.site = self.site
        self.fixture.impact = self.fixture.make_impact(plugins)
        bundle = self.fixture.prepare()
        state = self.document['state']; removed = {p['installation_id'] for p in self.fixture.impact['plugins']}
        state.update(release_lock=bundle['operation_lock']['release'], release_digest=bundle['plan']['target_release_digest'],
                     generation=bundle['operation_lock']['release']['generation'], bindings=bundle['operation_lock']['bindings'])
        for row in state['installations']:
            if row['installation_id'] in removed: row.update(state='not_installed', metadata_state='removed', feature_state='suspended')
        for row in self.site['installations']:
            if row['installation_id'] in removed: row['metadata_state'] = 'removed'
        for row in self.site['features']:
            if row['installation_id'] in removed: row['feature_state'] = 'suspended'
        for row in self.site['grants']:
            if row['installation_id'] in removed: row['state'] = 'revoked'
        addons = {r['native_addon'] for r in self.fixture.impact['plugins']}
        self.site['native_modules'] = [r for r in self.site['native_modules'] if r['addon'] not in addons]

    def prepare(self, plugin='org.example.notes_labels', workspaces=None):
        entry = next(p for p in self.document['state']['release_lock']['plugins'] if p['plugin_id'] == plugin)
        return prepare_current_image_install(self.document, [self.site], self.catalog, site_id=ident(20),
            workspace_ids=workspaces or [ident(30)], plugin_id=plugin, version=entry['version'], artifact_digest=entry['digest'],
            operation_id=ident(700), created_at=STAMP)

    def validator(self):
        owner = self; validator = object.__new__(IndependentValidator)
        class Catalog:
            def snapshot(self): return copy.deepcopy(owner.catalog)
        class Observer:
            def read(self): return {'sites': [copy.deepcopy(owner.site)]}
            def state(self, observation, catalog): return copy.deepcopy(owner.document)
        validator.catalog, validator.observer = Catalog(), Observer()
        return validator

    def rehash(self, bundle):
        bundle['plan']['dependency_lock_digest'] = data_digest(bundle['operation_lock'])
        bundle['plan_hash'] = plan_hash(bundle['plan'])
        bundle['display'] = _display(bundle['plan'], bundle['operation_lock'])

    def test_partial_reinstall_restores_all_retained_ids_but_only_requested_availability_and_grants(self):
        previous = copy.deepcopy(self.document)
        bundle = self.prepare()
        targets = bundle['operation_lock']['targets']
        self.assertEqual(len(targets), 2)
        self.assertEqual({t['installation_id'] for t in targets}, {self.fixture.impact['plugins'][0]['installation_id']})
        self.assertEqual({r['workspace_id']: r['availability'] for r in bundle['operation_lock']['feature_states']},
                         {ident(30): 'enabled', ident(31): 'suspended'})
        self.assertTrue(bundle['plan']['permission_changes'])
        self.assertTrue(all(r['action'] == 'grant' and r['workspace_id'] == ident(30) for r in bundle['plan']['permission_changes']))
        self.assertEqual(len(bundle['operation_lock']['bindings']), 10)
        self.assertEqual(bundle['plan']['artifacts'][0]['migration_digests'], [])
        self.assertEqual(native_maintenance_flags(bundle, {p['plugin_id']: p for p in self.catalog}), ['-i', 'mp_example_notes_labels'])
        self.assertEqual(self.validator()(bundle), self.document['state'])
        self.assertEqual(self.document, previous)
        ids = {r['installation_id']: r['plugin_id'] for r in self.site['installations']}
        choices = {(ids[b['consumer_installation_id']], b['alias'], b['site_id'], b['workspace_id']): b['provider_plugin_id'] for b in bundle['operation_lock']['bindings']}
        resolved = resolve_release(self.catalog, [], self.document['environment'],
            {p['manifest']['plugin']['id']: '==' + p['manifest']['plugin']['version'] for p in self.catalog}, scoped_provider_choices=choices)
        self.assertEqual(release_lock(resolved, self.document['provenance'], generation=4, created_at=STAMP), bundle['operation_lock']['release'])

    def test_complete_site_reinstall_still_binds_explicit_states_and_reapproves_both_scopes(self):
        bundle = self.prepare(workspaces=[ident(30), ident(31)])
        self.assertTrue(all(r['availability'] == 'enabled' for r in bundle['operation_lock']['feature_states']))
        self.assertEqual({g['workspace_id'] for g in bundle['plan']['permission_changes']}, {ident(30), ident(31)})
        self.assertEqual(self.validator()(bundle), self.document['state'])

    def test_feature_operations_cannot_enable_or_suspend_an_uninstalled_native_schema(self):
        minimal=plugin('plain')
        target=dict(installation_id=ident(199),site_id=ident(20),workspace_id=ident(30),plugin_id='org.test.plain')
        state=base_state([minimal])|dict(bindings=[],endpoints=[],installations=[target|dict(state='not_installed',metadata_state='removed',feature_state='suspended')])
        document=dict(state=state,environment=ENVIRONMENT,provenance=PROVENANCE,python_metadata=[])
        site=dict(site_id=ident(20),workspaces=[dict(workspace_id=ident(30),state='active')],grants=[])
        for action in ('enable','suspend'):
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'not installed'):
                prepare_current_feature(document,[site],[minimal],targets=[target|{'action':action}],operation_type=action,
                                        operation_id=ident(701),created_at=STAMP)

    def test_dependent_reinstall_restores_inactive_dependencies_without_reinstalling_unrelated_package(self):
        self.remove({'org.example.notes', 'org.example.canvas'})
        bundle = self.prepare(plugin='org.example.canvas')
        self.assertEqual({t['plugin_id'] for t in bundle['operation_lock']['targets']}, {'org.example.notes', 'org.example.canvas'})
        self.assertEqual(len(bundle['operation_lock']['targets']), 4)
        self.assertTrue(all(r['availability'] == ('enabled' if r['workspace_id'] == ident(30) else 'suspended')
                            for r in bundle['operation_lock']['feature_states']))
        self.assertTrue(all(r['workspace_id'] == ident(30) for r in bundle['plan']['permission_changes']))
        self.assertEqual(self.validator()(bundle), self.document['state'])

    def test_archived_retained_scope_can_stay_suspended_but_cannot_be_activated(self):
        self.site['workspaces'] = [dict(workspace_id=ident(30), state='active'), dict(workspace_id=ident(31), state='archived')]
        self.assertEqual(self.validator()(self.prepare()), self.document['state'])
        with self.assertRaisesRegex(ValueError, 'active workspace'): self.prepare(workspaces=[ident(31)])

    def test_forged_scope_omission_or_grant_is_rejected_even_when_rehashed(self):
        for change in ('omit_scope', 'grant_suspended', 'omit_grant', 'invalid_state'):
            bundle = self.prepare()
            if change == 'omit_scope':
                bundle['operation_lock']['targets'] = bundle['operation_lock']['targets'][:1]
                bundle['operation_lock']['feature_states'] = bundle['operation_lock']['feature_states'][:1]
            elif change == 'grant_suspended': bundle['plan']['permission_changes'].append({**bundle['plan']['permission_changes'][0], 'workspace_id':ident(31)})
            elif change == 'omit_grant': bundle['plan']['permission_changes'] = []
            else: bundle['operation_lock']['feature_states'][0]['availability'] = 'removed'
            self.rehash(bundle)
            with self.subTest(change=change), self.assertRaises(ValueError): self.validator()(bundle)

    def test_manager_reuses_current_image_reinstall_without_requiring_a_new_artifact_stage(self):
        entry = next(p for p in self.document['state']['release_lock']['plugins'] if p['plugin_id'] == 'org.example.notes_labels')
        nomination = dict(schema_version=1, operation='prepare', operation_type='install', plugin_id=entry['plugin_id'],
            site_id=ident(20), workspace_ids=[ident(30)], cascade=False, artifact_version=entry['version'], artifact_digest=entry['digest'])
        bundle = prepare_manager_native(self.document, [self.site], self.catalog, {}, None, nomination, operation_id=ident(700), created_at=STAMP)
        self.assertEqual(bundle, self.prepare())

    def test_new_version_staged_reinstall_initializes_current_schema_with_retained_inactive_scopes(self):
        base=staged_runtime(self.catalog)
        new=copy.deepcopy(next(p for p in self.catalog if p['plugin_id']=='org.example.notes_labels'))
        new['version']='0.3.0';new['manifest']['plugin']['version']='0.3.0';new['native_manifest']['version']='19.0.0.3.0'
        new['digest']='sha256:'+'e'*64
        selected=[new if p['plugin_id']==new['plugin_id'] else p for p in self.catalog]
        catalog=self.catalog+[new];runtime=staged_runtime(selected)
        self.document['state']['image_id']='sha256:'+'a'*64
        descriptor=dict(stage_digest='sha256:'+'b'*64,base_image_id=self.document['state']['image_id'],
            target_image_id='sha256:'+'f'*64,inventory_digest=runtime['inventory_digest'],runtime_digest=data_digest(runtime))
        nomination=dict(schema_version=1,operation='prepare',operation_type='install',plugin_id=new['plugin_id'],
            site_id=ident(20),workspace_ids=[ident(30)],cascade=False,artifact_version='0.3.0',artifact_digest=new['digest'])
        bundle=prepare_manager_native(self.document,[self.site],catalog,base,dict(descriptor=descriptor,runtime=runtime),nomination,
            operation_id=ident(700),created_at=STAMP)
        self.assertEqual(bundle['plan']['artifacts'][0]['version'],'0.3.0')
        self.assertEqual(bundle['plan']['artifacts'][0]['migration_digests'],[])
        self.assertEqual(len(bundle['operation_lock']['targets']),2)
        self.assertEqual({r['workspace_id']:r['availability'] for r in bundle['operation_lock']['feature_states']},
                         {ident(30):'enabled',ident(31):'suspended'})
        validator=self.validator()
        class Stages:
            def load(self,provided):
                self_check=provided==descriptor
                if not self_check:raise ValueError('Wrong independent stage')
                return descriptor,dict(runtime=runtime)
        class Snapshot:
            def snapshot(self):return copy.deepcopy(catalog)
        validator.stage_store=Stages();validator.catalog=Snapshot()
        original=validator.observer.read
        validator.observer.read=lambda:original()|{'runtime':base}
        self.assertEqual(validator(bundle),self.document['state'])

    def test_retained_scope_enable_requires_explicit_permission_acknowledgment_and_ready_grants(self):
        bundle = self.prepare(); previous = copy.deepcopy(self.document['state'])
        post = copy.deepcopy(previous)
        post.update(release_lock=bundle['operation_lock']['release'], release_digest=bundle['plan']['target_release_digest'],
                    generation=4, bindings=bundle['operation_lock']['bindings'])
        states = {(r['installation_id'],r['workspace_id']):r['availability'] for r in bundle['operation_lock']['feature_states']}
        for row in post['installations']:
            key = row['installation_id'],row['workspace_id']
            if key in states: row.update(state='installed',metadata_state='installed',feature_state=states[key])
        site = copy.deepcopy(self.site)
        for row in site['installations']:
            if row['plugin_id']=='org.example.notes_labels':row['metadata_state']='installed'
        for row in site['features']:
            key=row['installation_id'],row['workspace_id']
            if key in states:row['feature_state']=states[key]
        site['native_modules'].append(dict(addon='mp_example_notes_labels',state='installed',version='19.0.0.2.1'))
        for row in site['grants']:
            if row['installation_id']==self.fixture.impact['plugins'][0]['installation_id'] and row['workspace_id']==ident(30):row['state']='approved'
        verify_native_state(bundle,post,previous,{'sites':[site]})
        broken=copy.deepcopy(site)
        for row in broken['grants']:
            if row['installation_id']==self.fixture.impact['plugins'][0]['installation_id'] and row['workspace_id']==ident(31):row['state']='approved'
        with self.assertRaises(ValueError):verify_native_state(bundle,post,previous,{'sites':[broken]})
        self.document['state']=post;self.site=site
        target=next(r for r in bundle['operation_lock']['targets'] if r['workspace_id']==ident(31))|{'action':'enable'}
        enabled=prepare_current_feature(self.document,[site],self.catalog,targets=[target],operation_type='enable',operation_id=ident(701),created_at=STAMP)
        self.assertTrue(enabled['plan']['permission_changes'])
        self.assertTrue(all(r['workspace_id']==ident(31) and r['action']=='grant' for r in enabled['plan']['permission_changes']))
        self.assertEqual(self.validator()(enabled),post)
        self.assertFalse(enabled['plan']['backup']['required'] or enabled['display']['restart_required'])
        with tempfile.TemporaryDirectory() as directory:
            store=OperatorStore.initialize(Path(directory)/'control',{post['deployment_id']:post['site_ids']})
            check=lambda _:copy.deepcopy(post)
            operation=store.register(enabled,check)
            with self.assertRaisesRegex(ValueError,'acknowledgment'):
                store.approve(operation,exact_hash=enabled['plan_hash'],acknowledgments=dict(destructive=False,trust_expansion=False,permission_expansion=False),revalidate=check)
            store.approve(operation,exact_hash=enabled['plan_hash'],acknowledgments=dict(destructive=False,trust_expansion=False,permission_expansion=True),revalidate=check)
            self.assertEqual(store.status(operation)['state'],'approved')


if __name__ == '__main__': unittest.main()
