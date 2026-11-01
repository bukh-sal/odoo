"""Host transport authority, correlation, egress and failure-boundary checks."""
import copy,http.client,json,threading,time,unittest
from pathlib import Path
from uuid import uuid4
from modular_platform.worker_dispatch import WorkerClient,WorkerDispatchError
from modular_platform.tokens import verify_worker_token
import tests.test_document_stats_engine as fixtures


class Response:
    status=200
    def __init__(self,body):self.body=body
    def getheader(self,name):return 'application/json'
    def read1(self,size):chunk,self.body=self.body[:size],self.body[size:];return chunk
    def isclosed(self):return not self.body

class Connection:
    def __init__(self,address,port,timeout):
        self.address,self.port,self.timeout=address,port,timeout;self.sock=self;self.closed=False
    def connect(self):pass
    def settimeout(self,value):self.remaining=value
    def request(self,method,path,body,headers):self.method,self.path,self.request_value,self.headers=method,path,json.loads(body),headers
    def getresponse(self):
        request=self.request_value
        return Response(json.dumps(dict(api_version='1.0',request_id=request['request_id'],operation_id=request['operation_id'],data=dict(characters=11,words=2,lines=1))).encode())
    def close(self):self.closed=True

class WorkerDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.WorkerEngineTests.setUpClass()
    def setUp(self):
        root=Path(__file__).resolve().parents[1];self.endpoint=json.loads((root/'packages/contracts/examples/v1/endpoint.json').read_text());self.connections=[];self.reads=0
        self.scope={key:self.endpoint[key] for key in ['site_id','workspace_id','installation_id']}
        self.egress={self.endpoint['endpoint_config']:{key:self.endpoint[key] for key in ['destination','expected_image_digest','generation',*self.scope]}}
        self.egress[self.endpoint['endpoint_config']]['addresses']=['10.23.0.8']
    def read(self):self.reads+=1;return copy.deepcopy(self.endpoint)
    def connect(self,*args,**kwargs):
        conn=Connection(*args,**kwargs);self.connections.append(conn);return conn
    def client(self,**kwargs):return WorkerClient(self.read,lambda ref:('ephemeral-test',fixtures.WorkerEngineTests.private),self.egress,**self.scope,connection=kwargs.pop('connection',self.connect),**kwargs)
    def call(self,client=None):return (client or self.client()).analyze(dict(text='Hello world',note_id=str(uuid4()),expected_revision=1),request_id=str(uuid4()),operation_id=str(uuid4()))
    def test_numeric_pinned_connection_host_and_actual_signed_scope(self):
        value=self.call();conn=self.connections[0];self.assertEqual((conn.address,conn.port),('10.23.0.8',8080));self.assertEqual(conn.path,'/analyze')
        self.assertEqual(conn.headers['Host'],self.endpoint['destination'].removeprefix('http://'));self.assertTrue(conn.closed)
        claims=verify_worker_token(conn.headers['Authorization'][7:],fixtures.WorkerEngineTests.public,key_id='ephemeral-test',request=conn.request_value)
        self.assertEqual(claims['exp']-claims['iat'],120);self.assertEqual(self.reads,3);self.assertEqual(value['data']['words'],2)
    def test_revocation_during_key_lookup_prevents_connection(self):
        def issuer(ref):self.endpoint['state']='revoked';return 'ephemeral-test',fixtures.WorkerEngineTests.private
        client=self.client();client.issuer=issuer
        with self.assertRaises(WorkerDispatchError) as error:self.call(client)
        self.assertEqual(error.exception.code,'FORBIDDEN');self.assertFalse(error.exception.sent);self.assertEqual(self.connections,[])
    def test_revocation_after_response_refuses_return_and_marks_sent(self):
        def connect(*args,**kwargs):
            conn=self.connect(*args,**kwargs);get=conn.getresponse
            def response():value=get();self.endpoint['state']='suspended';return value
            conn.getresponse=response;return conn
        with self.assertRaises(WorkerDispatchError) as error:self.call(self.client(connection=connect))
        self.assertEqual(error.exception.code,'FORBIDDEN');self.assertTrue(error.exception.sent);self.assertTrue(self.connections[0].closed)
    def test_unapproved_destination_generation_and_loopback_never_connect(self):
        for key,value in [('destination','http://evil:8080'),('generation',99),('workspace_id',str(uuid4()))]:
            old=self.endpoint[key];self.endpoint[key]=value
            with self.assertRaises(WorkerDispatchError):self.call()
            self.endpoint[key]=old
        self.egress[self.endpoint['endpoint_config']]['addresses']=['127.0.0.1']
        with self.assertRaises(WorkerDispatchError):self.call()
        self.assertEqual(self.connections,[])
    def test_redirect_mismatched_response_and_oversize_never_return(self):
        for kind in ['redirect','wrong_id','oversize']:
            def connect(*args,**kwargs):
                conn=self.connect(*args,**kwargs)
                def response():
                    if kind=='redirect':v=Response(b'{}');v.status=302;return v
                    if kind=='oversize':return Response(b'x'*65537)
                    return Response(json.dumps(dict(api_version='1.0',request_id=str(uuid4()),operation_id=conn.request_value['operation_id'],data=dict(characters=1,words=1,lines=1))).encode())
                conn.getresponse=response;return conn
            with self.assertRaises(WorkerDispatchError) as error:self.call(self.client(connection=connect))
            self.assertTrue(error.exception.sent);self.assertEqual(error.exception.code,'DEPENDENCY_UNAVAILABLE')
    def test_connection_timeout_reports_not_sent(self):
        def connect(*args,**kwargs):
            conn=self.connect(*args,**kwargs)
            def timeout():raise TimeoutError()
            conn.connect=timeout;return conn
        with self.assertRaises(WorkerDispatchError) as error:self.call(self.client(connection=connect))
        self.assertEqual(error.exception.code,'DEADLINE_EXCEEDED');self.assertFalse(error.exception.sent)

    def test_actual_worker_HTTP_connection_close_response(self):
        from services.document_stats.engine import Engine
        from services.document_stats.server import Server
        engine=Engine(fixtures.WorkerEngineTests.public,'ephemeral-test',**self.scope,endpoint_generation=self.endpoint['generation'])
        server=Server(('127.0.0.1',0),engine)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def mapped_test_connection(address,port,timeout):
            # Only the test harness maps the approved internal address to its
            # loopback server. Production uses HTTPConnection on the pinned IP.
            self.assertEqual((address,port),('10.23.0.8',8080))
            return http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=timeout)
        try:
            value=self.call(self.client(connection=mapped_test_connection))
            self.assertEqual(value['data'],dict(characters=11,words=2,lines=1))
            self.assertEqual(engine.computations,1)
        finally:server.shutdown();server.server_close();thread.join(timeout=2)
