"""Exact metadata plans preserve native bytes and independent endpoint gates."""
import copy,sys,unittest
from types import SimpleNamespace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
import test_external_projection as fixtures
from modular_platform.external_planning import prepare_external_metadata,external_selections
from modular_platform.lifecycle_planning import installation_id
from modular_platform.projection import runtime_inputs
from modular_platform.resolution import resolve_release,PlanningError
from modular_platform.plans import release_lock,data_digest,check_bundle
from test_plans import ident,STAMP
from modular_platform.approval_validation import IndependentValidator
from modular_platform.operator_os import OperatorError
from modular_platform.native_executor import NativeExecutor


class ExternalPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ExternalProjection.setUpClass()

    def setUp(self):
        self.f=fixtures.ExternalProjection();self.f.setUp()
        self.f.site['workspaces']=[dict(workspace_id=ident(30),state='active',policy_generation=1)]
        self.target=dict(installation_id=ident(101),site_id=ident(20),workspace_id=ident(30),plugin_id='org.example.document_stats',action='suspend')
        self.document=self.f.project()

    def prepare(self, action, *, activate=False, selections=None):
        target={**self.target,'action':action};features=[]
        if action=='install':features=[{k:target[k] for k in ['installation_id','site_id','workspace_id']}|dict(availability='enabled' if activate else 'suspended')]
        if selections is None:
            selections=[{k:self.f.external['manifest']['plugin'][k.removeprefix('plugin_')] if k!='digest' else self.f.external['digest'] for k in ['plugin_id','version','digest']}] if action in ('install','upgrade') else []
        return prepare_external_metadata(self.document,[self.f.site],self.f.catalog,targets=[target],operation_type=action,
            external_state=self.f.external_state,selections=selections,feature_states=features,operation_id=ident(500),created_at=STAMP)

    def unregistered(self):
        self.f.site['installations']=self.f.site['installations'][:1];self.f.site['features']=self.f.site['features'][:1]
        canonical=installation_id(self.f.site,self.target['plugin_id']);oldkey=ident(101)+':'+ident(30)
        self.target['installation_id']=canonical;self.f.endpoint['installation_id']=canonical
        self.f.external_state['service_health'][canonical+':'+ident(30)]=self.f.external_state['service_health'].pop(oldkey)
        chosen,environment,provenance=runtime_inputs(self.f.runtime,self.f.catalog)
        lock=release_lock(resolve_release(chosen,[],environment,{'org.test.a':'==1.0.0'}),provenance,generation=2,created_at=STAMP)
        self.f.config['published_release']=lock;self.f.site['release_digest']=data_digest(lock)
        self.document=self.f.project()

    def test_register_suspended_during_outage_is_exact_metadata_only(self):
        self.unregistered();next(iter(self.f.external_state['service_health'].values()))['state']='unavailable'
        before=copy.deepcopy(self.document);bundle=self.prepare('install')
        self.assertTrue(check_bundle(bundle,self.document['state']));self.assertEqual(self.document,before)
        self.assertEqual(bundle,self.prepare('install'))
        artifact=bundle['plan']['artifacts'][0]
        self.assertEqual(artifact['runtime'],'external_service');self.assertIsNone(artifact['native_addon'])
        self.assertEqual(artifact['migration_digests'],[])
        self.assertEqual(bundle['operation_lock']['feature_states'][0]['availability'],'suspended')
        self.assertEqual(bundle['plan']['permission_changes'],[])
        self.assertEqual(external_selections(bundle),[dict(plugin_id='org.example.document_stats',version=self.f.external['manifest']['plugin']['version'],digest=self.f.external['digest'])])

    def test_activate_registration_requires_current_health(self):
        self.unregistered();next(iter(self.f.external_state['service_health'].values()))['state']='unavailable'
        with self.assertRaises(PlanningError):self.prepare('install',activate=True)
        next(iter(self.f.external_state['service_health'].values()))['state']='healthy'
        self.assertEqual(self.prepare('install',activate=True)['operation_lock']['feature_states'][0]['availability'],'enabled')

    def test_enable_and_suspend_preserve_release_and_health_is_not_approval(self):
        self.assertEqual(self.prepare('enable')['operation_lock']['release'],self.document['state']['release_lock'])
        self.f.endpoint['state']='revoked'
        with self.assertRaises(PlanningError):self.prepare('enable')
        next(iter(self.f.external_state['service_health'].values()))['state']='unavailable'
        self.assertEqual(self.prepare('suspend')['operation_lock']['release'],self.document['state']['release_lock'])

    def test_unregister_requires_revocation_and_retains_package(self):
        with self.assertRaises(PlanningError):self.prepare('unregister')
        self.f.endpoint.update(state='revoked',generation=2)
        bundle=self.prepare('unregister')
        self.assertEqual(bundle['operation_lock']['release'],self.document['state']['release_lock'])
        self.assertEqual(bundle['operation_lock']['endpoints'],[])
        self.assertEqual(bundle['plan']['artifacts'][0]['action'],'unregister')

    def test_scope_image_catalog_and_native_nomination_refused(self):
        original=copy.deepcopy(self.target)
        for key,value in [('installation_id',ident(102)),('site_id',ident(21)),('workspace_id',ident(31)),('plugin_id','org.test.a')]:
            self.target={**original,key:value}
            with self.subTest(key=key),self.assertRaises(PlanningError):self.prepare('enable')
        self.target=original;self.f.endpoint['expected_image_digest']='sha256:'+'a'*64
        with self.assertRaises(PlanningError):self.prepare('enable')

    def test_registration_cannot_change_untargeted_native_bytes(self):
        self.unregistered();self.f.catalog[0]=copy.deepcopy(self.f.catalog[0]);self.f.catalog[0]['digest']='sha256:'+'b'*64
        with self.assertRaises(PlanningError):self.prepare('install')

    def test_new_catalog_policy_keeps_published_native_trust_history(self):
        self.unregistered();prior=copy.deepcopy(self.document['state']['release_lock']['plugins'][0])
        for descriptor in self.f.catalog:descriptor['trust']['policy_generation']+=1
        self.document=self.f.project();bundle=self.prepare('install')
        native=next(r for r in bundle['operation_lock']['release']['plugins'] if r['runtime']=='native')
        self.assertEqual(native,prior)
        external=next(r for r in bundle['operation_lock']['release']['plugins'] if r['runtime']=='external_service')
        self.assertEqual(external['trust']['policy_generation'],self.f.catalog[1]['trust']['policy_generation'])
        self.assertEqual(self.independent()(bundle),self.document['state'])

    def test_untrusted_request_cannot_select_historical_trust_option(self):
        from modular_platform.planning_cli import prepare_document
        request=dict(operation_type='suspend',requested={},targets=[self.target],retained_trust_for=['org.test.a'])
        with self.assertRaisesRegex(PlanningError,'request fields'):prepare_document({**self.document,'request':request},self.f.catalog)

    def test_closed_workspace_allows_removal_but_not_activation(self):
        self.f.site['workspaces'][0]['state']='closed'
        with self.assertRaises(PlanningError):self.prepare('enable')
        self.f.endpoint['state']='revoked'
        self.assertEqual(self.prepare('unregister')['plan']['operation_type'],'unregister')

    def test_selection_must_match_metadata_target(self):
        self.unregistered()
        with self.assertRaises(PlanningError):self.prepare('install',selections=[])
        pin=dict(plugin_id='org.example.document_stats',version='0.1.0',digest='sha256:'+'a'*64)
        with self.assertRaises(PlanningError):self.prepare('install',selections=[pin])

    def independent(self):
        validator=IndependentValidator.__new__(IndependentValidator)
        validator.catalog=SimpleNamespace(snapshot=lambda:self.f.catalog)
        validator.observer=SimpleNamespace(external_reader=lambda:None,
            read=lambda:dict(sites=[self.f.site],external_state=self.f.external_state),
            state=lambda observation,catalog:self.document)
        return validator

    def test_independent_reconstruction_ignores_proposal_health_and_endpoint(self):
        bundle=self.prepare('enable');validator=self.independent()
        self.assertEqual(validator(bundle),self.document['state'])
        next(iter(self.f.external_state['service_health'].values()))['state']='unavailable'
        with self.assertRaises(PlanningError):validator(bundle)
        next(iter(self.f.external_state['service_health'].values()))['state']='healthy'
        self.f.endpoint['generation']+=1
        with self.assertRaises(OperatorError):validator(bundle)

    def test_independent_reader_is_required_and_native_executor_refuses_before_drain(self):
        bundle=self.prepare('enable');validator=self.independent();validator.observer.external_reader=None
        with self.assertRaises(OperatorError):validator(bundle)
        executor=NativeExecutor.__new__(NativeExecutor);executor.store=SimpleNamespace(bundle=lambda operation:bundle)
        with self.assertRaisesRegex(OperatorError,'before drain'):executor.apply(ident(500))

    def test_unregister_reconstructs_only_actual_scope_grant_revocations(self):
        self.f.site['grants']=[dict(installation_id=ident(101),workspace_id=ident(30),capability='org.example.document_stats:analysis.run',state='approved'),
            dict(installation_id=ident(100),workspace_id=ident(30),capability='org.example.document_stats:analysis.run',state='approved')]
        self.f.endpoint['state']='revoked';bundle=self.prepare('unregister')
        self.assertEqual(bundle['plan']['permission_changes'],[dict(plugin_id=self.target['plugin_id'],workspace_id=ident(30),capability='org.example.document_stats:analysis.run',action='revoke')])
        self.assertEqual(self.independent()(bundle),self.document['state'])

    def test_site_unregister_cannot_omit_another_workspace_or_live_grant(self):
        self.f.endpoint['state']='revoked'
        self.document['state']['installations'].append({**self.document['state']['installations'][0],
            'installation_id':ident(101),'plugin_id':self.target['plugin_id'],'workspace_id':ident(31)})
        with self.assertRaisesRegex(PlanningError,'every retained workspace'):self.prepare('unregister')
        self.document['state']['installations'].pop()
        self.f.site['grants']=[dict(installation_id=ident(101),workspace_id=ident(31),state='approved',capability='org.example.document_stats:analysis.run')]
        with self.assertRaisesRegex(PlanningError,'approved grants outside'):self.prepare('unregister')

    def test_upgrade_keeps_native_and_existing_feature_state(self):
        candidate=copy.deepcopy(self.f.external);candidate['manifest']['plugin']['version']='0.1.3';candidate['digest']='sha256:'+'c'*64
        self.f.catalog.append(candidate);self.document=self.f.project();pin=dict(plugin_id=self.target['plugin_id'],version='0.1.3',digest=candidate['digest'])
        bundle=self.prepare('upgrade',selections=[pin])
        self.assertEqual(external_selections(bundle),[pin]);self.assertNotIn('feature_states',bundle['operation_lock'])
        self.assertEqual(next(r for r in bundle['operation_lock']['release']['plugins'] if r['runtime']=='native'),next(r for r in self.document['state']['release_lock']['plugins'] if r['runtime']=='native'))

    def test_changed_image_suspended_projection_and_real_independent_reconstruction(self):
        from modular_platform.projection import project_deployment
        self.f.site=copy.deepcopy(self.f.site)
        self.f.site['features'][1]['feature_state']='suspended'
        candidate=copy.deepcopy(self.f.external);candidate['manifest']['plugin']['version']='99.0.0'
        candidate['digest']='sha256:'+'7'*64
        candidate['manifest']['external_service']['expected_image']='modular-document-stats@sha256:'+'8'*64
        self.f.catalog.append(candidate)
        self.f.endpoint['expected_image_digest']='sha256:'+'8'*64
        next(iter(self.f.external_state['service_health'].values()))['expected_image_digest']=self.f.endpoint['expected_image_digest']
        self.document=self.f.project()
        self.assertEqual(self.document['state']['endpoints'],[self.f.endpoint])
        pin=dict(plugin_id=self.target['plugin_id'],version='99.0.0',digest=candidate['digest'])
        bundle=self.prepare('upgrade',selections=[pin])
        validator=self.independent()
        observation=dict(runtime=self.f.runtime,image_id=self.f.config['image_id'],sites=[self.f.site],external_state=self.f.external_state)
        validator.observer.read=lambda:observation
        validator.observer.state=lambda actual,catalog:project_deployment(self.f.config,actual,catalog)
        self.assertEqual(validator(bundle),self.document['state'])
        # An ordinary enable still selects the old pin and refuses the new image.
        with self.assertRaisesRegex(PlanningError,'endpoint/image'):self.prepare('enable')
        # One active scope prevents treating the installation as inert.
        self.f.site['features'].append(dict(self.f.site['features'][1],workspace_id=ident(31),feature_state='enabled'))
        with self.assertRaisesRegex(PlanningError,'pinned package'):self.f.project()

    def consumer(self, optional):
        from test_resolution import plugin
        from test_release_staging import staged_runtime
        from modular_platform.planning_cli import scoped_bindings
        native=plugin('a',requires=[dict(alias='stats',id='org.example.document_stats.analysis',contract_major=1,version='>=1.0,<2.0',optional=optional)])
        self.f.native=native;self.f.catalog[0]=native;self.f.runtime=staged_runtime([native])
        self.f.runtime.update(platform_version='0.1.17',native_manifests={'mp_core':{'version':'19.0.0.1.17'}})
        self.f.site['active_inventory_digest']=self.f.runtime['inventory_digest']
        self.f.site['installations'][0].update(digest=native['digest'],manifest=native['manifest'])
        pin={k:self.document['state']['release_lock']['plugins'][0][k] for k in ['plugin_id','version','digest','runtime']}
        selected,environment,provenance=runtime_inputs(self.f.runtime,self.f.catalog,external_plugins=[pin])
        solution=resolve_release(selected,[],environment,{r['manifest']['plugin']['id']:'=='+r['manifest']['plugin']['version'] for r in selected},
            scoped_provider_choices={('org.test.a','stats',ident(20),ident(30)):self.target['plugin_id']})
        lock=release_lock(solution,provenance,generation=2,created_at=STAMP)
        self.f.config['published_release']=lock;self.f.site['release_digest']=data_digest(lock)
        self.f.site['bindings']=[dict(descriptor=b,state='active') for b in scoped_bindings(solution,self.document['state']['installations'],[])]
        self.document=self.f.project()

    def test_unregister_rejects_required_consumer_without_runtime_mutation(self):
        self.consumer(optional=False);self.f.endpoint['state']='revoked'
        with self.assertRaises(PlanningError):self.prepare('unregister')

    def test_missing_required_binding_does_not_become_published_authority(self):
        self.consumer(optional=False);self.f.site['bindings']=[]
        with self.assertRaises(PlanningError):self.f.project()

    def test_optional_binding_removed_but_published_release_remains_observable(self):
        self.consumer(optional=True);self.f.endpoint['state']='revoked';bundle=self.prepare('unregister')
        self.assertEqual(bundle['operation_lock']['bindings'],[])
        self.f.site['installations'][1]['metadata_state']='removed';self.f.site['features'][1]['feature_state']='suspended'
        self.f.site['bindings']=[]
        self.assertEqual(self.f.project()['state']['release_lock'],bundle['operation_lock']['release'])


if __name__=='__main__':unittest.main()
