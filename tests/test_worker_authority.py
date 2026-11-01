"""Actual files/key parsing; publisher/mount ownership still needs integration proof."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from uuid import uuid4
import tests.test_document_stats_engine as fixtures
from modular_platform.worker_authority import PublishedWorkerAuthority,AuthorityUnavailable


class PublishedAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.WorkerEngineTests.setUpClass()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='mp-disposable-authority-');self.root=Path(self.temp.name);(self.root/'keys').mkdir()
        endpoint=json.loads((Path(__file__).resolve().parents[1]/'packages/contracts/examples/v1/endpoint.json').read_text());self.endpoint=endpoint
        self.deployment=str(uuid4());self.document=dict(schema_version=1,deployment_id=self.deployment,site_id=endpoint['site_id'],generation=1,endpoints=[dict(descriptor=endpoint,addresses=['10.23.0.8'],key_id='fixture-issuer')])
        self.publish()
        (self.root/'keys'/(endpoint['issuer_key_ref']+'.pem')).write_bytes(fixtures.WorkerEngineTests.private)
        (self.root/'keys'/(endpoint['public_key_ref']+'.pem')).write_bytes(fixtures.WorkerEngineTests.public)
        self.reader=PublishedWorkerAuthority(self.root,deployment_id=self.deployment,site_id=endpoint['site_id'])
        self.scope={k:endpoint[k] for k in ['installation_id','workspace_id','endpoint_config']}
    def tearDown(self):self.temp.cleanup()
    def publish(self):
        staging=self.root/'next.json';staging.write_text(json.dumps(self.document));os.replace(staging,self.root/'authority.json')
    def test_scope_snapshot_and_matching_public_private_issuer(self):
        snapshot=self.reader.select(**self.scope);kid,key=self.reader.issuer(snapshot,self.endpoint['issuer_key_ref'])
        self.assertEqual(kid,'fixture-issuer');self.assertEqual(key,fixtures.WorkerEngineTests.private)
        self.assertEqual(snapshot.egress[self.endpoint['endpoint_config']]['addresses'],['10.23.0.8'])
    def test_atomic_revocation_removal_and_generation_change_reject_old_snapshot(self):
        for change in ['revoke','remove','generation']:
            self.document['endpoints']=[dict(descriptor=copy.deepcopy(self.endpoint),addresses=['10.23.0.8'],key_id='fixture-issuer')];self.document['generation']=1;self.publish();snapshot=self.reader.select(**self.scope)
            if change=='revoke':self.document['endpoints'][0]['descriptor']['state']='revoked'
            elif change=='remove':self.document['endpoints']=[]
            else:self.document['generation']=2
            self.publish()
            with self.assertRaises(AuthorityUnavailable):self.reader.issuer(snapshot,self.endpoint['issuer_key_ref'])
    def test_wrong_target_duplicate_scope_and_unapproved_address_fail_closed(self):
        baseline=copy.deepcopy(self.document)
        for change in ['target','duplicate','address']:
            self.document=copy.deepcopy(baseline)
            if change=='target':self.document['deployment_id']=str(uuid4())
            elif change=='duplicate':self.document['endpoints']*=2
            else:self.document['endpoints'][0]['addresses']=['169.254.169.254']
            self.publish()
            with self.assertRaises(AuthorityUnavailable):self.reader.select(**self.scope)
    def test_foreign_scope_and_key_reference_cannot_select_issuer(self):
        with self.assertRaises(AuthorityUnavailable):self.reader.select(**{**self.scope,'workspace_id':str(uuid4())})
        snapshot=self.reader.select(**self.scope)
        with self.assertRaises(AuthorityUnavailable):self.reader.issuer(snapshot,'../foreign')
    def test_duplicate_json_properties_and_nonfinite_json_refused(self):
        for raw in ['{"schema_version":1,"schema_version":1}','{"generation":NaN}']:
            (self.root/'authority.json').write_text(raw)
            with self.assertRaises(AuthorityUnavailable):self.reader.select(**self.scope)
    def test_public_verification_key_cannot_be_used_as_private_issuer(self):
        snapshot=self.reader.select(**self.scope)
        (self.root/'keys'/(self.endpoint['issuer_key_ref']+'.pem')).write_bytes(fixtures.WorkerEngineTests.public)
        with self.assertRaises(AuthorityUnavailable):self.reader.issuer(snapshot,self.endpoint['issuer_key_ref'])
    def test_key_replacement_cannot_reuse_old_publication_snapshot(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        snapshot=self.reader.select(**self.scope)
        replacement=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        (self.root/'keys'/(self.endpoint['issuer_key_ref']+'.pem')).write_bytes(replacement.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (self.root/'keys'/(self.endpoint['public_key_ref']+'.pem')).write_bytes(replacement.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
        with self.assertRaises(AuthorityUnavailable):self.reader.issuer(snapshot,self.endpoint['issuer_key_ref'])
