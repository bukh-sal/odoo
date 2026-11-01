"""Exact removal guards; pure source tests, not native execution evidence."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'packages/platform_sdk'), str(ROOT / 'tests')]
from modular_platform.artifact_removal import validate_removal_image, validate_removal_sites, validate_sharing_database_inventory, removal_targets
from modular_platform.approval_validation import IndependentValidator
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest, release_lock, _display
from modular_platform.contracts import plan_hash
from modular_platform.app_channel import journal_view
from modular_platform.manager_planning import prepare_manager_removal
from modular_platform.native_executor import native_maintenance_flags, verify_native_state, require_native_removal_runtime
from modular_platform.operation_views import prepared_view
from modular_platform.projection import runtime_inputs
from modular_platform.release_staging import prepare_staged_plan
from modular_platform.resolution import resolve_release
from test_plans import ident, STAMP
from test_release_staging import staged_runtime
import test_reinstall_planning


class ArtifactRemoval(unittest.TestCase):
    def setUp(self):
        fixture = test_reinstall_planning.ReinstallPlanning()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.document = copy.deepcopy(fixture.document); self.site = copy.deepcopy(fixture.site)
        self.document['state']['image_id'] = 'sha256:' + 'a'*64
        self.catalog = fixture.catalog; self.plugin = 'org.example.notes_labels'; self.addon = 'mp_example_notes_labels'
        self.site['bindings'] = [dict(descriptor=row, state='active') for row in self.document['state']['bindings']]
        self.base = staged_runtime(self.catalog)
        self.base['platform_version']=self.document['environment']['platform_version']
        manifests = {row['manifest']['runtime']['addon_name']: row['native_manifest'] for row in self.catalog}
        manifests.update(mp_core=dict(depends=[], version='19.0.'+self.base['platform_version']), mp_shell=dict(depends=['mp_core'], version='19.0.0.1.6'))
        self.base['native_manifests'] = manifests
        self.base['inventory']['native_addons'] = {name: dict(depends=manifest['depends'], license='LGPL-3') for name,manifest in manifests.items()}
        policy = self.base['inventory']['policy']
        policy.update(addons=list(manifests), explicit_install=list(manifests), server_wide_modules=['mp_core'], platform_sdk=True,
                      profile='unchanged', reference_packages=['plugins/' + row['plugin_id'] + '/plugin.toml' for row in self.catalog])
        self.base['inventory']['files'].update({'packages/platform_sdk/modular_platform/projection.py':'f'*64, 'addons/mp_core/__manifest__.py':'e'*64})
        self.base['inventory']['reference_composition'] = dict(models={'mp.example.note':'org.example.notes'},
            fields={'mp.example.note.title':'org.example.notes','mp.example.note.x_notes_labels':self.plugin},
            ui_contributions=[self.plugin + ':action:set_labels'])
        self.after = copy.deepcopy(self.base)
        inventory = self.after['inventory']; entry = inventory['artifacts'].pop(self.plugin)
        inventory['native_addons'].pop(self.addon); self.after['native_manifests'].pop(self.addon)
        for key in ('addons','explicit_install'): inventory['policy'][key].remove(self.addon)
        inventory['policy']['reference_packages'].remove('plugins/' + self.plugin + '/plugin.toml')
        inventory['files'] = {name: value for name,value in inventory['files'].items()
            if not name.startswith('addons/' + self.addon + '/') and name != 'artifacts/' + entry['file']}
        inventory['reference_composition']['fields'].pop('mp.example.note.x_notes_labels')
        inventory['reference_composition']['ui_contributions'] = []
        self.descriptor = dict(stage_digest='sha256:'+'c'*64,base_image_id='sha256:'+'a'*64,target_image_id='sha256:'+'b'*64,
            inventory_digest=self.after['inventory_digest'],runtime_digest=data_digest(self.after))

    def image(self, plugins=None):
        # Bind a deliberately modified candidate as if independently observed;
        # failures must come from the constrained delta, not a stale digest.
        self.descriptor['runtime_digest'] = data_digest(self.after)
        return validate_removal_image(self.base,self.after,self.descriptor,plugins or [self.plugin])

    def sites(self):
        return validate_removal_sites(self.document,[self.site],[self.plugin],self.base)

    def prepare(self, targets=None):
        self.descriptor['runtime_digest'] = data_digest(self.after)
        return prepare_staged_plan(self.document,[self.site],self.catalog,self.after,self.descriptor,
            targets=targets if targets is not None else removal_targets(self.document,[self.site],[self.plugin]),
            operation_type='remove',operation_id=ident(800),created_at=STAMP,base_runtime=self.base)

    def test_exact_subtraction_preserves_inputs_and_only_lists_deleted_bytes(self):
        before = copy.deepcopy((self.base,self.after,self.document,self.site))
        diff = self.image(); self.assertTrue(self.sites())
        self.assertTrue(diff)
        self.assertTrue(all(row['target_sha256'] is None for row in diff))
        self.assertTrue(all(row['path'].startswith(('addons/'+self.addon+'/', 'artifacts/'+self.plugin)) for row in diff))
        self.assertEqual(before,(self.base,self.after,self.document,self.site))

    def test_live_and_pending_native_state_always_block_source_removal(self):
        for state in ['installed','to install','to upgrade','to remove','uninstalled']:
            with self.subTest(state=state):
                self.site['native_modules'].append(dict(addon=self.addon,state=state))
                with self.assertRaisesRegex(OperatorError,'native module'): self.sites()
                self.site['native_modules'].pop()

    def test_active_metadata_availability_grants_and_bindings_are_not_tombstones(self):
        target = next(row for row in self.site['installations'] if row['plugin_id']==self.plugin)
        target['metadata_state'] = 'installed'
        with self.assertRaisesRegex(OperatorError,'installation metadata'): self.sites()
        target['metadata_state'] = 'removed'
        feature = next(row for row in self.site['features'] if row['installation_id']==target['installation_id'])
        for state in ['enabled','degraded']:
            feature['feature_state'] = state
            with self.assertRaisesRegex(OperatorError,'scope'): self.sites()
        feature['feature_state'] = 'suspended'
        grant = next(row for row in self.site['grants'] if row['installation_id']==target['installation_id'])
        grant['state'] = 'approved'
        with self.assertRaisesRegex(OperatorError,'approved scoped grant'): self.sites()
        grant['state'] = 'revoked'
        binding = copy.deepcopy(self.site['bindings'][0]); binding['descriptor']['provider_plugin_id'] = self.plugin
        self.site['bindings'].append(binding)
        with self.assertRaisesRegex(OperatorError,'live service binding'): self.sites()

    def test_an_omitted_unknown_duplicate_or_still_using_second_site_blocks(self):
        self.document['state']['site_ids'].append(ident(21))
        with self.assertRaisesRegex(OperatorError,'every sharing site'): self.sites()
        other = copy.deepcopy(self.site); other['site_id'] = ident(21)
        other['native_modules'].append(dict(addon=self.addon,state='installed'))
        with self.assertRaisesRegex(OperatorError,'native module'):
            validate_removal_sites(self.document,[self.site,other],[self.plugin],self.base)
        with self.assertRaisesRegex(OperatorError,'every sharing site'):
            validate_removal_sites(self.document,[self.site,self.site],[self.plugin],self.base)
        other['site_id'] = ident(999)
        with self.assertRaisesRegex(OperatorError,'every sharing site'):
            validate_removal_sites(self.document,[self.site,other],[self.plugin],self.base)

    def test_never_installed_package_needs_no_fabricated_installation_metadata(self):
        ids = {r['installation_id'] for r in self.site['installations'] if r['plugin_id']==self.plugin}
        self.site['installations'] = [r for r in self.site['installations'] if r['installation_id'] not in ids]
        self.site['features'] = [r for r in self.site['features'] if r['installation_id'] not in ids]
        self.site['grants'] = [r for r in self.site['grants'] if r['installation_id'] not in ids]
        self.document['state']['installations'] = [r for r in self.document['state']['installations'] if r['installation_id'] not in ids]
        self.assertTrue(self.sites()); self.assertTrue(self.image())

    def test_unrelated_source_or_package_identity_change_is_not_a_removal(self):
        good = copy.deepcopy(self.after)
        for path in ['packages/platform_sdk/modular_platform/projection.py','addons/mp_example_notes/models.py','addons/mp_example_notes_labels_evil/payload.py']:
            with self.subTest(path=path):
                self.after = copy.deepcopy(good); self.after['inventory']['files'][path] = '0'*64
                with self.assertRaisesRegex(OperatorError,'unrelated source'): self.image()
        self.after = copy.deepcopy(good)
        self.after['inventory']['artifacts']['org.example.notes']['version'] = '9.0.0'
        with self.assertRaisesRegex(OperatorError,'surviving package identity'): self.image()

    def test_python_or_upstream_patch_or_surviving_manifest_change_blocks(self):
        good = copy.deepcopy(self.after)
        for key,value in [('python','3.13.0'),('python_lock_digest','sha256:'+'0'*64),('python_metadata',[dict(name='new')]),('architecture','arm64')]:
            with self.subTest(key=key):
                self.after = copy.deepcopy(good); self.after[key] = value
                with self.assertRaisesRegex(OperatorError,'Python/runtime'): self.image()
        self.after = copy.deepcopy(good); self.after['inventory']['generated_patches'].append(dict(path='unexpected'))
        with self.assertRaisesRegex(OperatorError,'patch provenance'): self.image()
        self.after = copy.deepcopy(good); self.after['native_manifests']['mp_core']['version'] = '19.0.9.9.9'
        with self.assertRaisesRegex(OperatorError,'surviving native manifests'): self.image()

    def test_required_surviving_addon_and_server_wide_source_are_not_removable(self):
        self.base['inventory']['native_addons']['mp_core']['depends'] = [self.addon]
        self.after['inventory']['native_addons']['mp_core']['depends'] = [self.addon]
        with self.assertRaisesRegex(OperatorError,'still requires'): self.image()
        self.base['inventory']['native_addons']['mp_core']['depends'] = []
        self.after['inventory']['native_addons']['mp_core']['depends'] = []
        self.base['inventory']['policy']['server_wide_modules'].append(self.addon)
        self.after['inventory']['policy']['server_wide_modules'].append(self.addon)
        with self.assertRaisesRegex(OperatorError,'Server-wide'): self.image()

    def test_unrelated_build_policy_or_ownership_changes_are_not_removal(self):
        self.after['inventory']['policy']['profile'] = 'different policy'
        with self.assertRaisesRegex(OperatorError,'unrelated distribution policy'): self.image()
        self.after['inventory']['policy']['profile'] = self.base['inventory']['policy']['profile']
        self.after['inventory']['reference_composition']['fields']['mp.example.note.title'] = self.plugin
        with self.assertRaisesRegex(OperatorError,'reference composition'): self.image()

    def test_duplicate_unknown_package_same_image_and_unverified_source_fail(self):
        with self.assertRaisesRegex(OperatorError,'unique explicit'): self.image([self.plugin,self.plugin])
        with self.assertRaisesRegex(OperatorError,'absent'): self.image(['org.unknown.plugin'])
        self.descriptor['target_image_id'] = self.descriptor['base_image_id']
        with self.assertRaisesRegex(OperatorError,'distinct'): self.image()
        self.descriptor['target_image_id'] = 'sha256:'+'b'*64
        self.after['unexpected_addon_files'] = ['arbitrary.py']
        with self.assertRaisesRegex(OperatorError,'verified source'): self.image()

    def test_independent_database_inventory_cannot_omit_an_unknown_database(self):
        configuration = dict(sites=[dict(site_id=ident(20),database='mp_disposable_r0_r1_a')])
        observation = dict(sites=[self.site])
        inventory = dict(databases=['postgres','mp_disposable_r0_r1_a'],maintenance_relations=[])
        self.assertEqual(validate_sharing_database_inventory(configuration,observation,inventory),dict(site_ids=[ident(20)],complete=True))
        for databases in [['postgres'],['postgres','mp_disposable_r0_r1_a','mp_disposable_r0_r1_unknown'],['postgres','mp_disposable_r0_r1_a','mp_disposable_r0_r1_a']]:
            with self.subTest(databases=databases), self.assertRaisesRegex(OperatorError,'Unknown sharing'):
                validate_sharing_database_inventory(configuration,observation,inventory|dict(databases=databases))
        with self.assertRaisesRegex(OperatorError,'nonempty maintenance'):
            validate_sharing_database_inventory(configuration,observation,inventory|dict(maintenance_relations=['ir_module_module']))

    def test_duplicate_configuration_or_partial_observation_is_not_complete(self):
        configuration = dict(sites=[dict(site_id=ident(20),database='mp_disposable_r0_r1_a'),dict(site_id=ident(21),database='mp_disposable_r0_r1_b')])
        inventory = dict(databases=['postgres','mp_disposable_r0_r1_a','mp_disposable_r0_r1_b'],maintenance_relations=[])
        with self.assertRaisesRegex(OperatorError,'incomplete or ambiguous'):
            validate_sharing_database_inventory(configuration,dict(sites=[self.site]),inventory)
        other = self.site|dict(site_id=ident(21))
        self.assertTrue(validate_sharing_database_inventory(configuration,dict(sites=[self.site,other]),inventory)['complete'])
        configuration['sites'][1]['database'] = configuration['sites'][0]['database']
        with self.assertRaisesRegex(OperatorError,'incomplete or ambiguous'):
            validate_sharing_database_inventory(configuration,dict(sites=[self.site,other]),inventory)

    def test_operator_inventory_query_uses_fixed_read_only_maintenance_target(self):
        from unittest.mock import patch
        observer = object.__new__(DockerObserver)
        observer.config = dict(sites=[dict(site_id=ident(20),database='mp_disposable_r0_r1_a')])
        import json
        with patch.object(observer,'_container',return_value='owned-db'), patch('modular_platform.deployment._run',return_value=json.dumps(dict(databases=['postgres','mp_disposable_r0_r1_a'],maintenance_relations=[])).encode()) as run:
            self.assertTrue(observer.removal_site_inventory(dict(sites=[self.site]))['complete'])
            args = run.call_args.args[0]; query = run.call_args.kwargs['input'].decode()
            self.assertEqual(args[-2:],['-d','postgres']); self.assertIn('REPEATABLE READ READ ONLY',query)
            self.assertIn("statement_timeout='5s'",query); self.assertIn('ROLLBACK',query)
            self.assertNotIn('mp_disposable_r0_r1_a',query)

    def test_staged_plan_has_new_epoch_exact_survivors_and_no_metadata_or_grant_change(self):
        bundle = self.prepare()
        self.assertEqual(len(bundle['operation_lock']['targets']),2)
        self.assertEqual(bundle['plan']['artifacts'][0]['action'],'remove')
        self.assertTrue(bundle['plan']['backup']['required'])
        self.assertFalse(bundle['plan']['destructive'])
        self.assertEqual(bundle['plan']['permission_changes'],[])
        self.assertEqual(bundle['operation_lock']['bindings'],self.document['state']['bindings'])
        self.assertNotIn('native_core_changes',bundle['operation_lock'])
        self.assertTrue(all(r['target_sha256'] is None for r in bundle['operation_lock']['platform_source_diff']))
        selected,environment,provenance=runtime_inputs(self.after,self.catalog)
        ids={r['installation_id']:r['plugin_id'] for r in self.site['installations']}
        choices={(ids[b['consumer_installation_id']],b['alias'],b['site_id'],b['workspace_id']):b['provider_plugin_id'] for b in self.document['state']['bindings']}
        resolved=resolve_release(selected,self.after['python_metadata'],environment,
            {p['plugin_id']:'=='+p['version'] for p in selected},scoped_provider_choices=choices,core_python=[])
        expected=release_lock(resolved,provenance,generation=self.document['state']['generation']+1,created_at=STAMP)
        self.assertEqual(bundle['operation_lock']['release'],expected)
        self.assertNotIn(self.plugin,{r['plugin_id'] for r in expected['plugins']})

    def test_partial_scope_and_wrong_never_installed_identity_are_rejected(self):
        targets=removal_targets(self.document,[self.site],[self.plugin])
        with self.assertRaisesRegex(OperatorError,'every sharing site and retained scope'):self.prepare(targets=targets[:1])
        targets[0]['installation_id']=ident(999)
        with self.assertRaisesRegex(OperatorError,'every sharing site and retained scope'):self.prepare(targets=targets)

    def test_never_installed_staged_remove_is_only_a_nomination_not_an_install(self):
        ids={r['installation_id'] for r in self.site['installations'] if r['plugin_id']==self.plugin}
        for key in ('installations','features','grants'):
            self.site[key]=[r for r in self.site[key] if r['installation_id'] not in ids]
        self.document['state']['installations']=[r for r in self.document['state']['installations'] if r['installation_id'] not in ids]
        before=copy.deepcopy(self.document)
        bundle=self.prepare()
        self.assertEqual(len(bundle['operation_lock']['targets']),2)
        self.assertTrue(all(t['action']=='remove' for t in bundle['operation_lock']['targets']))
        self.assertEqual(self.document,before)

    def test_independent_reconstruction_checks_complete_inventory_and_rehashed_diff(self):
        owner=self;seen=[]
        class Catalog:
            def snapshot(self):return copy.deepcopy(owner.catalog)
        class Observer:
            def read(self):return dict(sites=[copy.deepcopy(owner.site)],runtime=copy.deepcopy(owner.base))
            def state(self,observation,catalog):return copy.deepcopy(owner.document)
            def removal_site_inventory(self,observation):seen.append('complete');return dict(complete=True)
        class Stage:
            def load(self,descriptor):
                if descriptor!=owner.descriptor:raise OperatorError('Changed independent stage')
                return copy.deepcopy(descriptor),dict(runtime=copy.deepcopy(owner.after))
        validator=object.__new__(IndependentValidator);validator.observer=Observer();validator.catalog=Catalog();validator.stage_store=Stage();validator.quiesced=False
        bundle=self.prepare();self.assertEqual(validator(bundle),self.document['state']);self.assertEqual(seen,['complete'])
        forged=copy.deepcopy(bundle);forged['operation_lock']['platform_source_diff'].append(dict(path='addons/mp_core/__manifest__.py',previous_sha256='e'*64,target_sha256=None))
        forged['plan']['dependency_lock_digest']=data_digest(forged['operation_lock']);forged['plan_hash']=plan_hash(forged['plan']);forged['display']=_display(forged['plan'],forged['operation_lock'])
        with self.assertRaisesRegex(OperatorError,'reconstruction differs'):validator(forged)

    def test_manager_requires_exact_digest_and_operator_staged_image(self):
        nomination=dict(schema_version=1,operation='prepare',operation_type='remove',plugin_id=self.plugin,
            artifact_digest=self.base['inventory']['artifacts'][self.plugin]['digest'],site_id=ident(20),workspace_ids=[],cascade=False)
        def manager(body=nomination,staged=True):
            self.descriptor['base_image_id']=self.document['state']['image_id'];self.descriptor['runtime_digest']=data_digest(self.after)
            return prepare_manager_removal(self.document,[self.site],self.catalog,self.base,
                dict(descriptor=self.descriptor,runtime=self.after) if staged else None,body,operation_id=ident(800),created_at=STAMP)
        bundle=manager();self.assertEqual(prepared_view(bundle,observed_at=STAMP)['plan']['operation_type'],'remove')
        with self.assertRaisesRegex(ValueError,'stage and publish'):manager(staged=False)
        with self.assertRaisesRegex(ValueError,'exact package'):manager(nomination|dict(artifact_digest='sha256:'+'0'*64))
        self.after['inventory']['artifacts'].pop('org.example.canvas')
        with self.assertRaisesRegex(ValueError,'cascade consent'):manager()
        with self.assertRaisesRegex(ValueError,'outside the nominated dependent closure'):manager(nomination|dict(cascade=True))

    def test_no_native_maintenance_and_readiness_keeps_history_exact(self):
        bundle=self.prepare();self.assertIsNone(native_maintenance_flags(bundle,{}))
        previous=copy.deepcopy(self.document['state']);state=copy.deepcopy(previous)
        state['release_digest']=bundle['plan']['target_release_digest'];state['release_lock']=bundle['operation_lock']['release']
        verify_native_state(bundle,state,previous,dict(sites=[self.site]))
        forged=copy.deepcopy(state);next(i for i in forged['installations'] if i['plugin_id']==self.plugin)['feature_state']='enabled'
        with self.assertRaises(OperatorError):verify_native_state(bundle,forged,previous,dict(sites=[self.site]))
        altered=copy.deepcopy(bundle);altered['operation_lock']['native_core_changes']=[dict(addon='mp_core')]
        with self.assertRaisesRegex(OperatorError,'without native maintenance'):native_maintenance_flags(altered,{})
        altered=copy.deepcopy(bundle);altered['operation_lock']['platform_source_diff'][0]['target_sha256']='0'*64
        with self.assertRaisesRegex(OperatorError,'without native maintenance'):native_maintenance_flags(altered,{})

    def test_current_image_cannot_run_new_source_removal_publisher(self):
        runtime=dict(inventory=dict(files={}))
        with self.assertRaisesRegex(OperatorError,'compatible publication image'):require_native_removal_runtime(runtime)
        names=('artifact_removal.py','remove_metadata.py','projection.py','planning_cli.py','plans.py')
        import hashlib
        runtime['inventory']['files']={'packages/platform_sdk/modular_platform/'+name:hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform'/name).read_bytes()).hexdigest() for name in names}
        require_native_removal_runtime(runtime)
        runtime['inventory']['files']['packages/platform_sdk/modular_platform/remove_metadata.py']='0'*64
        with self.assertRaisesRegex(OperatorError,'compatible publication image'):require_native_removal_runtime(runtime)

    def test_journal_distinguishes_removed_runtime_from_catalog_archive_retention(self):
        bundle=self.prepare();state=copy.deepcopy(self.document['state'])
        status=dict(operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],state='completed',phase='completed',
            history=[dict(sequence=1,utc=STAMP,code='completed',details={})],approval_expires_at=None)
        request=dict(requested_by=ident(50))
        # Before source publication it is still present, even if the proposal
        # says remove. The proposal alone cannot claim an observed outcome.
        self.assertTrue(all(d['artifact_state']=='verified' for d in journal_view(bundle,status,request,state)['dimensions']))
        state.update(release_digest=bundle['plan']['target_release_digest'],release_lock=bundle['operation_lock']['release'])
        view=journal_view(bundle,status,request,state)
        self.assertTrue(all(d['artifact_state']=='removed' and d['database_state']=='not_installed' and d['feature_state']=='suspended' for d in view['dimensions']))
        self.assertEqual({r['plugin_id'] for r in self.catalog},{'org.example.notes','org.example.notes_labels','org.example.canvas'})


if __name__ == '__main__': unittest.main()
