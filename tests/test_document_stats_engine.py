"""Actual signed credentials, concurrent duplicates and bounded restart state."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import unittest
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from modular_platform.contracts import validate
from services.document_stats.engine import Engine, WorkerError


class WorkerEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.request = json.loads((Path(__file__).resolve().parents[1]/'packages/contracts/examples/v1/worker-request.json').read_text())
        self.scope = {key:self.request[key] for key in ['site_id','workspace_id','installation_id','endpoint_generation']}
        self.engine = Engine(self.public, 'ephemeral-test', **self.scope)

    def token(self, **changes):
        now = int(time.time())
        claims = dict(iss='modular-platform-host-v1', aud='mp-document-stats-v1',
                      sub=self.scope['installation_id'],jti=str(uuid4()),iat=now,
                      nbf=now,exp=now+120,methods=['analyze'],**self.scope)
        claims.update(changes)
        return jwt.encode(claims,self.private,algorithm='RS256',headers={'kid':'ephemeral-test'})

    def test_frozen_request_response_and_unicode(self):
        self.request['input']['text']='Hello 世界\nمرحبا'
        value=self.engine.analyze(self.token(),self.request)
        validate('worker-response',value)
        self.assertEqual(value['data'],dict(characters=14,words=3,lines=2))

    def test_concurrent_duplicate_with_new_transport_ids_computes_once(self):
        token=self.token()
        requests=[dict(self.request,request_id=str(uuid4())) for _ in range(16)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            values=list(pool.map(lambda request:self.engine.analyze(token,request),requests))
        self.assertEqual(self.engine.computations,1)
        self.assertEqual([v['request_id'] for v in values],[r['request_id'] for r in requests])
        self.assertTrue(all(v['data']==dict(characters=11,words=2,lines=1) for v in values))

    def test_changed_input_conflicts_without_retaining_text(self):
        token=self.token();self.engine.analyze(token,self.request)
        changed={**self.request,'input':{**self.request['input'],'text':'Private fixture body changed'}}
        with self.assertRaises(WorkerError) as error:self.engine.analyze(token,changed)
        self.assertEqual(error.exception.code,'CONFLICT')
        self.assertNotIn('Hello world',repr(self.engine.cache))

    def test_retry_still_rejects_expired_wrong_audience_and_forged_scope(self):
        self.engine.analyze(self.token(),self.request)
        now=int(time.time())
        for token in [self.token(iat=now-301,nbf=now-301,exp=now-1),self.token(aud='wrong'),self.token(workspace_id=str(uuid4()))]:
            with self.assertRaises(WorkerError) as error:self.engine.analyze(token,self.request)
            self.assertEqual(error.exception.status,401)
        other={**self.request,'workspace_id':str(uuid4())}
        with self.assertRaises(WorkerError) as error:self.engine.analyze(self.token(workspace_id=other['workspace_id']),other)
        self.assertEqual(error.exception.status,403)

    def test_capacity_expiry_and_restart_recompute_same_pure_result(self):
        clock=[0];engine=Engine(self.public,'ephemeral-test',**self.scope,capacity=1,retention=1,clock=lambda:clock[0])
        token=self.token();first=engine.analyze(token,self.request)
        engine.analyze(token,{**self.request,'operation_id':str(uuid4())});self.assertEqual(len(engine.cache),1)
        clock[0]=2;self.assertEqual(engine.analyze(token,self.request),first)
        self.assertEqual(Engine(self.public,'ephemeral-test',**self.scope).analyze(token,self.request),first)
