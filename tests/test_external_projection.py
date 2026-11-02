"""Metadata selection is pinned outside the image; DB/cache is not approval."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'tests')]
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.projection import project_deployment,runtime_inputs,public_profile
from modular_platform.plans import release_lock,data_digest
from modular_platform.resolution import resolve_release,PlanningError
from reference_package import assemble
from test_release_staging import staged_runtime
from test_resolution import plugin
from test_plans import ident,STAMP


class ExternalProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,raw,_=assemble(ROOT,'plugins/document_stats/plugin.toml')
        with tempfile.TemporaryDirectory(prefix='mp-external-profile-') as temporary:
            path=Path(temporary)/'metadata.mplug';path.write_bytes(raw)
            verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(path)
            cls.external=dict(manifest=verified.manifest,digest=verified.digest,inventory=verified.inventory,trust=verified.trust)

    def setUp(self):
        self.native=plugin('a');self.catalog=[self.native,copy.deepcopy(self.external)];self.runtime=staged_runtime([self.native])
        self.runtime.update(platform_version='0.1.17',native_manifests={'mp_core':{'version':'19.0.0.1.17'}})
        self.config=dict(schema_version=1,image_id='sha256:'+'a'*64,deployment_id=ident(10),generation=2,release_created_at=STAMP,policy_version=1,operator_authorization_generation=1,sites=[dict(site_id=ident(20),database='mp_disposable_r0_r1_projection')])
        self.site=dict(site_id=ident(20),release_generation='2',active_inventory_digest=self.runtime['inventory_digest'],
            installations=[dict(installation_id=ident(100),plugin_id='org.test.a',version='1.0.0',digest=self.native['digest'],runtime='native',metadata_state='installed',manifest=self.native['manifest']),
                dict(installation_id=ident(101),plugin_id='org.example.document_stats',version=self.external['manifest']['plugin']['version'],digest=self.external['digest'],runtime='external_service',metadata_state='installed',manifest=self.external['manifest'])],
            features=[dict(installation_id=ident(100),plugin_id='org.test.a',workspace_id=ident(30),feature_state='enabled'),dict(installation_id=ident(101),plugin_id='org.example.document_stats',workspace_id=ident(30),feature_state='enabled')],
            native_modules=[dict(addon='test_a',state='installed',version='19.0.1.0.0')],bindings=[],grants=[],workspaces=[],memberships=[])
        pin=dict(plugin_id='org.example.document_stats',version=self.external['manifest']['plugin']['version'],digest=self.external['digest'],runtime='external_service')
        selected,environment,provenance=runtime_inputs(self.runtime,self.catalog,external_plugins=[pin])
        solution=resolve_release(selected,[],environment,{item['manifest']['plugin']['id']:'=='+item['manifest']['plugin']['version'] for item in selected})
        lock=release_lock(solution,provenance,generation=2,created_at=STAMP);self.config['published_release']=lock;self.site['release_digest']=data_digest(lock)
        endpoint=json.loads((ROOT/'packages/contracts/examples/v1/endpoint.json').read_text())
        endpoint.update(site_id=ident(20),installation_id=ident(101),workspace_id=ident(30),expected_image_digest=self.external['manifest']['external_service']['expected_image'].split('@')[1])
        self.endpoint=endpoint;self.external_state=dict(endpoints=[endpoint],service_health={ident(101)+':'+ident(30):dict(state='healthy',expected_image_digest=endpoint['expected_image_digest'])})

    def project(self):
        return project_deployment(self.config,dict(runtime=self.runtime,image_id='sha256:'+'a'*64,sites=[self.site],external_state=self.external_state),self.catalog)

    def test_external_package_has_no_native_image_root_or_module(self):
        state=self.project()['state'];row=next(r for r in state['installations'] if r['plugin_id']=='org.example.document_stats')
        self.assertEqual(row['state'],'installed');self.assertEqual(self.site['native_modules'],[dict(addon='test_a',state='installed',version='19.0.1.0.0')])
        self.assertNotIn('org.example.document_stats',self.runtime['inventory']['artifacts'])
        self.assertIsNone(next(r for r in state['release_lock']['plugins'] if r['runtime']=='external_service')['native_addon'])
        self.assertEqual(state['endpoints'],[self.endpoint]);self.assertEqual(state['service_health'],self.external_state['service_health'])

    def test_metadata_successor_refuses_unqualified_platform_minimum(self):
        self.runtime.update(platform_version='0.1.16',native_manifests={'mp_core':{'version':'19.0.0.1.16'}})
        with self.assertRaises(PlanningError):self.project()

    def test_database_declaration_cannot_select_metadata_package(self):
        self.config.pop('published_release')
        with self.assertRaises(PlanningError):self.project()

    def test_pinned_package_still_requires_live_catalog_validation(self):
        self.catalog=[self.native]
        with self.assertRaises(PlanningError):self.project()
        self.catalog=[self.native,copy.deepcopy(self.external)];self.catalog[1]['manifest']['plugin']['description']='Forged DB-compatible declaration'
        with self.assertRaises(PlanningError):self.project()

    def test_wrong_scope_image_or_health_identity_refused(self):
        original=copy.deepcopy(self.external_state)
        for mutation in ['site','image','health']:
            self.external_state=copy.deepcopy(original)
            if mutation=='site':self.external_state['endpoints'][0]['site_id']=ident(21)
            elif mutation=='image':self.external_state['endpoints'][0]['expected_image_digest']='sha256:'+'a'*64
            else:next(iter(self.external_state['service_health'].values()))['expected_image_digest']='sha256:'+'a'*64
            with self.subTest(mutation=mutation),self.assertRaises(PlanningError):self.project()

    def test_unregistered_approval_does_not_create_installation(self):
        self.site['features']=self.site['features'][:1];self.site['installations']=self.site['installations'][:1]
        state=self.project()['state'];self.assertEqual(len(state['installations']),1);self.assertEqual(state['endpoints'],[])

    def test_removed_external_metadata_is_inert_history(self):
        self.site['installations'][1]['metadata_state']='removed';self.site['features'][1]['feature_state']='suspended'
        state=self.project()['state'];row=next(r for r in state['installations'] if r['plugin_id']=='org.example.document_stats')
        self.assertEqual((row['state'],row['metadata_state']),('not_installed','removed'));self.assertEqual(state['endpoints'],[])
        self.site['grants']=[dict(installation_id=ident(101),workspace_id=ident(30),capability='org.example.document_stats:analysis.run',state='approved')]
        with self.assertRaises(PlanningError):self.project()

    def test_missing_external_reader_or_code_in_metadata_refused(self):
        with self.assertRaises(PlanningError):project_deployment(self.config,dict(runtime=self.runtime,image_id='sha256:'+'a'*64,sites=[self.site]),self.catalog)
        self.catalog[1]['inventory']['backend/odoo_addons/fake/__init__.py']='a'*64
        with self.assertRaises(PlanningError):self.project()

    def test_profile_snapshot_is_sanitized_and_not_a_key_channel(self):
        observation=dict(runtime=self.runtime,image_id='sha256:'+'a'*64,sites=[self.site],external_state=self.external_state)
        result=public_profile(self.config,observation,self.catalog,STAMP);self.assertEqual(result['external_state'],self.external_state)
        self.external_state['service_health'][ident(101)+':'+ident(30)]['private_key']='not-allowed'
        with self.assertRaises(PlanningError):self.project()
        with self.assertRaises(PlanningError):public_profile(self.config,observation,self.catalog,STAMP)


if __name__=='__main__':unittest.main()
