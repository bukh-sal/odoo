"""Actual OS store/locks/files/keys; runtime observations are explicit test data."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from uuid import uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError
from modular_platform.worker_publication import WorkerAuthorityPublisher,DockerWorkerObservation
from modular_platform.worker_authority import PublishedWorkerAuthority,AuthorityUnavailable
from modular_platform.worker_operator import WorkerOperator,operator_observer


class WorkerPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        cls.public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='mp-worker-publisher-');self.addCleanup(self.temp.cleanup)
        self.deployment=str(uuid4());self.site=str(uuid4())
        self.store=OperatorStore.initialize(Path(self.temp.name)/'control',{self.deployment:[self.site]},allow_noninteractive=True)
        self.publisher=WorkerAuthorityPublisher(self.store,self.deployment,self.site)
        self.endpoint=json.loads((ROOT/'packages/contracts/examples/v1/endpoint.json').read_text());self.endpoint['site_id']=self.site
        self.publisher.provision_keypair(self.endpoint['issuer_key_ref'],self.endpoint['public_key_ref'],self.private,self.public)
        self.observed=dict(addresses=['172.28.0.19'],image_digest=self.endpoint['expected_image_digest'],container_id='a'*64)
        self.observer=lambda endpoint,digest,key_id:copy.deepcopy(self.observed)
        self.reader=PublishedWorkerAuthority(self.publisher.projection,deployment_id=self.deployment,site_id=self.site)
        self.scope={k:self.endpoint[k] for k in ['installation_id','workspace_id','endpoint_config']}

    def review(self):return self.publisher.prepare(self.endpoint,'worker01',self.observer)
    def publish(self,review=None):
        review=review or self.review()
        return self.publisher.publish(review,exact_hash=review['plan_hash'],observer=self.observer,noninteractive=True)

    def test_exact_hash_publication_reader_issuer_and_no_replay(self):
        review=self.review()
        with self.assertRaises(OperatorError):self.publisher.publish(review,exact_hash='sha256:'+'0'*64,observer=self.observer)
        self.assertEqual(self.publish(review)['generation'],1)
        snapshot=self.reader.select(**self.scope);self.assertEqual(self.reader.issuer(snapshot,self.endpoint['issuer_key_ref']),('worker01',self.private))
        with self.assertRaises(OperatorError):self.publish(review)

    def test_current_observation_change_refuses_before_publication(self):
        review=self.review();self.observed['addresses']=['172.28.0.20']
        with self.assertRaises(OperatorError):self.publish(review)
        self.assertFalse((self.publisher.projection/'authority.json').exists())

    def test_revoke_with_runtime_down_invalidates_old_reader_snapshot(self):
        self.publish();snapshot=self.reader.select(**self.scope)
        self.endpoint.update(generation=2,state='revoked')
        def down(*args):raise AssertionError('Revocation must not inspect a failed runtime')
        review=self.publisher.prepare(self.endpoint,'worker01',down)
        self.publisher.publish(review,exact_hash=review['plan_hash'],observer=down)
        with self.assertRaises(AuthorityUnavailable):self.reader.select(**self.scope)
        with self.assertRaises(AuthorityUnavailable):self.reader.issuer(snapshot,self.endpoint['issuer_key_ref'])

    def test_generation_and_intervening_publication_fence_old_review(self):
        first=self.review();second=self.review();self.publish(first)
        with self.assertRaises(OperatorError):self.publish(second)
        with self.assertRaises(OperatorError):self.review()

    def test_changed_operator_generation_and_immutable_key_reference_refused(self):
        review=self.review();path=self.store.root/'policy.json';policy=json.loads(path.read_text());policy['authorization_generation']+=1;path.write_text(json.dumps(policy))
        with self.assertRaises(OperatorError):self.publish(review)
        replacement=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=replacement.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=replacement.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        with self.assertRaises(OperatorError):self.publisher.provision_keypair(self.endpoint['issuer_key_ref'],self.endpoint['public_key_ref'],private,public)

    def test_unsafe_destination_and_unlisted_target_refused(self):
        with self.assertRaises(OperatorError):WorkerAuthorityPublisher(self.store,self.deployment,str(uuid4()))
        policy=dict(project='owned-worker',service='document-stats',network='internal',public_config_volume='public-config',image='modular-document-stats@'+self.endpoint['expected_image_digest'],destination='http://169.254.169.254:8080')
        with self.assertRaises(OperatorError):DockerWorkerObservation(policy)
        self.observed['addresses']=['169.254.169.254']
        with self.assertRaises(OperatorError):self.review()

    def test_bootstrap_preserves_current_revocation_and_never_resets_generation(self):
        self.publish();self.endpoint.update(generation=2,state='revoked');self.publish()
        before=self.publisher._document()
        # Revocation stays publishable even after issuer material is retired.
        for path in self.publisher.keys.glob('*.pem'):path.unlink()
        class Sink:
            descriptor={'kind':'test-replacement'}
            def observe_empty(self):return dict(identity='same-empty-volume')
            def bootstrap(self,document,keys,operation):self.document=document;self.keys=keys
        sink=Sink();self.publisher.sink=sink;review=self.publisher.prepare_bootstrap()
        self.assertEqual(review['plan']['document']['generation'],2)
        self.publisher.publish_bootstrap(review,exact_hash=review['plan_hash'])
        self.assertEqual(sink.document,before);self.assertEqual(sink.keys,{})
        self.assertEqual(self.publisher._document(),before)
        with self.assertRaises(AuthorityUnavailable):self.reader.select(**self.scope)
        with self.assertRaises(OperatorError):self.publisher.publish_bootstrap(review,exact_hash=review['plan_hash'])

    def test_bootstrap_wrong_hash_or_replaced_empty_volume_refused(self):
        self.publish()
        class Sink:
            descriptor={'kind':'test-replacement'}
            generation=1
            def observe_empty(self):return dict(identity=self.generation)
            def bootstrap(self,*args):raise AssertionError('Stale bootstrap must not mutate')
        sink=Sink();self.publisher.sink=sink;review=self.publisher.prepare_bootstrap()
        with self.assertRaises(OperatorError):self.publisher.publish_bootstrap(review,exact_hash='sha256:'+'0'*64)
        sink.generation=2
        with self.assertRaises(OperatorError):self.publisher.publish_bootstrap(review,exact_hash=review['plan_hash'])

    def planning_operator(self, observer=None):
        # Keep the real independent store/publication/key reader. Only Docker
        # observation is substituted; these tests never launch a worker.
        operator=WorkerOperator.__new__(WorkerOperator)
        operator.publisher=self.publisher
        operator.config=dict(deployment_id=self.deployment,site_id=self.site)
        operator.observer=observer or self.observer
        return operator

    def test_planning_health_retains_approved_descriptor_during_outage(self):
        self.publish();operator=self.planning_operator();before=self.publisher._document()
        state=operator.planning_state();key=self.endpoint['installation_id']+':'+self.endpoint['workspace_id']
        self.assertEqual(state['endpoints'],[self.endpoint]);self.assertEqual(state['service_health'][key]['state'],'healthy')
        def down(*args):raise OperatorError('Worker unavailable')
        operator.observer=down
        state=operator.planning_state();self.assertEqual(state['endpoints'],[self.endpoint])
        self.assertEqual(state['service_health'][key]['state'],'unavailable')
        self.assertEqual(self.publisher._document(),before)
        self.assertNotIn(self.private.decode(),json.dumps(state));self.assertNotIn('addresses',json.dumps(state))

    def test_planning_new_address_requires_separate_publication(self):
        self.publish();self.observed['addresses']=['172.28.0.20']
        state=self.planning_operator().planning_state()
        self.assertEqual(next(iter(state['service_health'].values()))['state'],'unavailable')

    def test_planning_revoked_endpoint_needs_no_runtime_or_keys(self):
        self.publish();self.endpoint.update(generation=2,state='revoked');self.publish()
        for path in self.publisher.keys.glob('*.pem'):path.unlink()
        def forbidden(*args):raise AssertionError('Revoked endpoint must not inspect a runtime')
        state=self.planning_operator(forbidden).planning_state()
        self.assertEqual(state['endpoints'],[self.endpoint])
        self.assertEqual(next(iter(state['service_health'].values()))['state'],'disabled')

    def test_planning_publication_race_is_refused(self):
        self.publish()
        def replaced(*args):
            self.endpoint.update(generation=2,state='revoked');self.publish()
            return copy.deepcopy(self.observed)
        with self.assertRaises(OperatorError):self.planning_operator(replaced).planning_state()

    def test_planning_missing_verification_key_is_unavailable(self):
        self.publish();(self.publisher.keys/(self.endpoint['public_key_ref']+'.pem')).unlink()
        def forbidden(*args):raise AssertionError('Missing publication key must not inspect a runtime')
        state=self.planning_operator(forbidden).planning_state()
        self.assertEqual(next(iter(state['service_health'].values()))['state'],'unavailable')

    def test_planning_missing_issuer_cannot_claim_healthy_credentials(self):
        self.publish();(self.publisher.keys/(self.endpoint['issuer_key_ref']+'.pem')).unlink()
        def forbidden(*args):raise AssertionError('Missing issuer must not report healthy worker authority')
        state=self.planning_operator(forbidden).planning_state()
        self.assertEqual(next(iter(state['service_health'].values()))['state'],'unavailable')

    def configured_reader(self):
        target=dict(schema_version=1,deployment_id=self.deployment,project='mp-r0-r1readerunit',
            sites=[dict(site_id=self.site,database='mp_disposable_r0_r1_reader')],image_id='sha256:'+'a'*64,
            generation=1,policy_version=1,operator_authorization_generation=1,release_created_at='2026-11-01T00:00:00Z')
        runtime=dict(project='mp-disposable-document-stats-reader',service='document-stats',network='mp-r0-r1readerunit_runtime',
            public_config_volume='mp-disposable-reader-public',image='modular-document-stats@'+self.endpoint['expected_image_digest'],destination=self.endpoint['destination'])
        config=dict(schema_version=1,deployment_id=self.deployment,site_id=self.site,runtime=runtime,
            authority_volume='mp-r0-r1readerunit_authority',helper_image='sha256:'+'b'*64)
        path=self.store.root/'deployment.json';path.write_text(json.dumps(target))
        worker=path.with_name('worker-target.json');worker.write_text(json.dumps(config))
        return path,worker,config

    def test_operator_composition_reloads_protected_sibling_and_does_not_execute_helper(self):
        self.publish();self.endpoint.update(generation=2,state='revoked');self.publish()
        path,worker,config=self.configured_reader();observer=operator_observer(self.store,path)
        self.assertEqual(observer.external_reader()['endpoints'],[self.endpoint])
        # Read-only observation tolerates a retained helper pin; actual worker
        # writes still require the exact current native image.
        with self.assertRaises(OperatorError):WorkerOperator(self.store,path,worker)
        config['site_id']=str(uuid4());worker.write_text(json.dumps(config))
        with self.assertRaises(OperatorError):observer.external_reader()

    def test_legacy_reader_optional_but_changed_deployment_refused(self):
        path,worker,config=self.configured_reader();worker.unlink()
        self.assertIsNone(operator_observer(self.store,path).external_reader)
        worker.write_text(json.dumps(config));observer=operator_observer(self.store,path)
        target=json.loads(path.read_text());target['generation']+=1;path.write_text(json.dumps(target))
        with self.assertRaises(OperatorError):observer.external_reader()


if __name__=='__main__':unittest.main()
