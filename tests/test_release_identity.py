"""Immutable publication versus current validation, with private adoption writes."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
sys.path.insert(0,str(ROOT/'tests'))
sys.path.insert(0,str(ROOT/'tools'))
from modular_platform.operator_os import OperatorError,protect_directory
from modular_platform.operator_store import OperatorStore,_write_new
from modular_platform.plans import prepare_plan,check_bundle,data_digest
from modular_platform.planning_cli import prepare_document
from modular_platform.projection import project_deployment,public_profile
from modular_platform.release_adoption import adopt_release
from modular_platform.profile_channel import publish_profile
from modular_platform.catalog import Catalog
from modular_platform.artifacts import ArtifactError
from test_plans import ident,target,STAMP,solution
from test_resolution import plugin
from test_release_staging import staged_runtime


def fixture():
    catalog=[plugin('a')];runtime=staged_runtime(catalog)
    config={'schema_version':1,'deployment_id':ident(10),'project':'mp-r0-r1identity',
        'sites':[{'site_id':ident(20),'database':'mp_disposable_r0_r1_identity'}],'image_id':'sha256:'+'a'*64,
        'generation':2,'release_created_at':STAMP,'policy_version':1,'operator_authorization_generation':1}
    site={'site_id':ident(20),'installations':[{'installation_id':ident(100),'plugin_id':'org.test.a',
        'version':'1.0.0','digest':catalog[0]['digest'],'runtime':'native','metadata_state':'installed','manifest':catalog[0]['manifest']}],
        'features':[{'installation_id':ident(100),'plugin_id':'org.test.a','workspace_id':ident(30),'feature_state':'enabled'}],
        'workspaces':[{'workspace_id':ident(30),'state':'active','policy_generation':1}],
        'memberships':[],'grants':[],'bindings':[],'native_modules':[{'addon':'test_a','state':'installed','version':'19.0.1.0.0'}]}
    observation={'image_id':config['image_id'],'runtime':runtime,'sites':[site]}
    doc=project_deployment(config,observation,catalog)
    config['published_release']=copy.deepcopy(doc['state']['release_lock'])
    site.update(release_digest=doc['state']['release_digest'],release_generation='2',active_inventory_digest=runtime['inventory_digest'])
    return config,observation,catalog


class PublicationIdentity(unittest.TestCase):
    def setUp(self):self.config,self.observed,self.catalog=fixture()

    def document(self,catalog=None,configuration=None):
        return project_deployment(configuration or self.config,self.observed,self.catalog if catalog is None else catalog)

    def test_trust_generation_and_unrelated_catalog_acquisition_do_not_relabel_release(self):
        before=self.document()['state'];changed=copy.deepcopy(self.catalog);changed[0]['trust']['policy_generation']=2
        for catalog in (changed,self.catalog+[plugin('b')]):
            after=self.document(catalog)['state']
            self.assertEqual(after['release_lock'],before['release_lock'])
            self.assertEqual(after['release_digest'],before['release_digest'])
            self.assertNotEqual(after['catalog_validation_digest'],before['catalog_validation_digest'])

    def test_stable_release_still_invalidates_pending_plan_on_current_validation_change(self):
        document=self.document();document['request']={'operation_type':'suspend','requested':{},'targets':[target(action='suspend')],
            'bindings':[],'operation_id':ident(500),'created_at':STAMP}
        bundle=prepare_document(document,self.catalog);check_bundle(bundle,document['state'])
        changed=copy.deepcopy(self.catalog);changed[0]['trust']['policy_generation']=2
        actual=self.document(changed)['state']
        self.assertEqual(actual['release_digest'],bundle['plan']['base_release_digest'])
        with self.assertRaisesRegex(ValueError,'Stale plan'):check_bundle(bundle,actual)
        with self.assertRaisesRegex(ValueError,'validation changed'):prepare_document(document,changed)
        self.assertEqual(bundle['display']['current_catalog_validation_digest'],document['state']['catalog_validation_digest'])

    def test_selected_quarantine_revocation_and_pin_tampering_are_never_blessed(self):
        with self.assertRaisesRegex(ValueError,'absent/untrusted'):self.document([])
        for field,value in [('core_inventory_digest','sha256:'+'f'*64),('generation',3),('created_at','2026-10-29T05:00:00Z')]:
            config=copy.deepcopy(self.config);config['published_release'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'differ from published'):self.document(configuration=config)
        config=copy.deepcopy(self.config);config['published_release']['plugins'][0]['version']='2.0.0'
        with self.assertRaisesRegex(ValueError,'differ from published'):self.document(configuration=config)
        config=copy.deepcopy(self.config);config['published_release']['plugins'][0]['trust']['signature_verified']=True
        with self.assertRaisesRegex(ValueError,'historical release trust'):self.document(configuration=config)

    def test_database_publication_mismatch_and_inventory_mismatch_fail_closed(self):
        for field,value in [('release_digest','sha256:'+'f'*64),('release_generation','1'),('active_inventory_digest','sha256:'+'e'*64)]:
            observation=copy.deepcopy(self.observed);observation['sites'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Database publication'):
                project_deployment(self.config,observation,self.catalog)

    def test_app_profile_projection_matches_os_and_contains_no_worker_db_selector(self):
        config=self.config|{'worker_id':'1'*64}
        profile=public_profile(config,self.observed,self.catalog,STAMP)
        self.assertNotIn('worker_id',profile['configuration']);self.assertNotIn('sites',profile['configuration'])
        self.assertEqual(project_deployment(profile['configuration'],self.observed,profile['catalog']),self.document(configuration=config))
        profile['configuration']['published_release']['generation']=99
        self.assertEqual(config['published_release']['generation'],2)

    def test_old_reader_cache_publication_is_refused_without_writing(self):
        observed=copy.deepcopy(self.observed);observed['runtime']['published_release_protocol']=0
        observer=SimpleNamespace(config=self.config,read=lambda:observed,state=lambda obs,cat:self.document())
        with patch('modular_platform.profile_channel._run') as run:
            with self.assertRaisesRegex(OperatorError,'preserve the old cache'):
                publish_profile(observer,SimpleNamespace(snapshot=lambda:self.catalog))
            run.assert_not_called()

    def test_legacy_unpinned_projection_keeps_its_old_shape(self):
        config=copy.deepcopy(self.config);config.pop('published_release')
        self.assertNotIn('catalog_validation_digest',self.document(configuration=config)['state'])

    def test_running_cli_validator_cannot_reuse_a_changed_or_revoked_private_policy(self):
        from modular import configuration
        from reference_package import assemble
        _,raw,_=assemble(ROOT,'plugins/notes/plugin.toml');digest='sha256:'+__import__('hashlib').sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);artifact=root/'notes.mplug';artifact.write_bytes(raw);path=root/'trust.json'
            policy={'schema_version':1,'mode':'curated','approved_digests':[digest],'allow_unsigned_development':False,'generation':1}
            path.write_text(json.dumps(policy));validator=configuration(path);validator.verify(artifact,expected_digest=digest)
            path.write_text(json.dumps(policy|{'generation':2,'approved_digests':[]}))
            with self.assertRaisesRegex(ArtifactError,'configuration changed'):validator.verify(artifact,expected_digest=digest)
            with self.assertRaisesRegex(ArtifactError,'not approved'):configuration(path).verify(artifact,expected_digest=digest)


class PrivateAdoption(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=protect_directory(Path(temporary.name)/'operator')
        protect_directory(self.directory/'locks')
        Catalog(self.directory/'catalog',None)
        self.config,self.observed,self.catalog=fixture();lock=self.config.pop('published_release')
        initial=project_deployment(self.config,self.observed,self.catalog)['state'];initial['installations']=[]
        initial['generation']=1;initial['release_lock']['generation']=1;initial['release_digest']=data_digest(initial['release_lock'])
        self.bundle=prepare_plan(initial,lock,solution(self.catalog),[target()],operation_id=ident(500),created_at=STAMP)
        self.status={'state':'completed'}
        self.store=SimpleNamespace(root=self.directory,_regular=OperatorStore._regular,
            _authorize_plan=lambda plan:None,status=lambda operation:self.status,bundle=lambda operation:self.bundle)
        self.path=self.directory/'target.json';_write_new(self.path,self.config)
        self.patches=[patch('modular_platform.release_adoption.DockerObserver.read',return_value=self.observed),
            patch('modular_platform.release_adoption.Catalog.snapshot',return_value=self.catalog)]
        for item in self.patches:item.start();self.addCleanup(item.stop)
        # The completed fixture is an exact staged image publication.
        self.bundle['operation_lock']['staged_image']={'target_image_id':self.config['image_id']}
        from modular_platform.plans import plan_hash,_display
        self.bundle['plan']['dependency_lock_digest']=data_digest(self.bundle['operation_lock'])
        self.bundle['plan_hash']=plan_hash(self.bundle['plan']);self.bundle['display']=_display(self.bundle['plan'],self.bundle['operation_lock'])

    def test_private_adoption_writes_once_preserves_identity_and_replays_without_new_record(self):
        result=adopt_release(self.store,self.path,self.directory/'catalog',None,ident(500))
        self.assertEqual(result['state'],'adopted');self.assertFalse(result['database_or_runtime_changed'])
        config=json.loads(self.path.read_text());self.assertEqual(config['published_release'],self.bundle['operation_lock']['release'])
        self.assertEqual({key:value for key,value in config.items() if key!='published_release'},self.config)
        records=list((self.directory/'release-adoptions').rglob('*.json'));self.assertEqual(len(records),1)
        before=records[0].read_bytes()
        self.assertEqual(adopt_release(self.store,self.path,self.directory/'catalog',None,ident(500))['state'],'already_pinned')
        self.assertEqual(records[0].read_bytes(),before)

    def test_incomplete_different_image_and_db_mismatch_never_write_a_pin(self):
        before=self.path.read_bytes();self.status['state']='approved'
        with self.assertRaisesRegex(OperatorError,'completed publication'):adopt_release(self.store,self.path,self.directory/'catalog',None,ident(500))
        self.status['state']='completed';self.observed['sites'][0]['release_digest']='sha256:'+'f'*64
        with self.assertRaisesRegex(ValueError,'Database publication'):adopt_release(self.store,self.path,self.directory/'catalog',None,ident(500))
        self.assertEqual(self.path.read_bytes(),before)

    def test_a_rehashed_completed_record_for_another_image_cannot_pin_current_runtime(self):
        from modular_platform.plans import plan_hash,_display
        self.bundle['operation_lock']['staged_image']['target_image_id']='sha256:'+'f'*64
        self.bundle['plan']['dependency_lock_digest']=data_digest(self.bundle['operation_lock'])
        self.bundle['plan_hash']=plan_hash(self.bundle['plan']);self.bundle['display']=_display(self.bundle['plan'],self.bundle['operation_lock'])
        before=self.path.read_bytes()
        with self.assertRaisesRegex(OperatorError,'Current image differs'):adopt_release(self.store,self.path,self.directory/'catalog',None,ident(500))
        self.assertEqual(self.path.read_bytes(),before)


if __name__=='__main__':unittest.main()
