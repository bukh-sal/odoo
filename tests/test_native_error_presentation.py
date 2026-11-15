"""Actual native error boundary; fake request/parent response, no database."""
import ast
import copy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'framework_addons/mp_core/models.py'

def load_handler(request,payload):
    controllers=ModuleType('native_error_fixture.controllers')
    source=ast.parse((ROOT/'framework_addons/mp_core/controllers.py').read_text(encoding='utf-8'))
    cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='PublicError')
    exec(compile(ast.Module(body=[cls],type_ignores=[]),'actual_PublicError','exec'),controllers.__dict__)
    class Response:
        def __init__(self):self.body=copy.deepcopy(payload);self.writes=0
        def get_json(self):return self.body
        def set_data(self,text):self.body=json.loads(text);self.writes+=1
    response=Response();calls=[]
    class Parent:
        @classmethod
        def _handle_error(cls,error):calls.append(error);return response
    node=next(n for n in ast.parse(SOURCE.read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name=='ApiHttpErrors')
    namespace=dict(models=SimpleNamespace(AbstractModel=Parent),uuid4=lambda:'bounded-request-id',__package__='native_error_fixture')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(SOURCE),'exec'),namespace)
    modules={'odoo.http':ModuleType('odoo.http'),'native_error_fixture.controllers':controllers,
             'werkzeug.exceptions':ModuleType('werkzeug.exceptions')}
    modules['werkzeug.exceptions'].RequestEntityTooLarge=type('RequestEntityTooLarge',(Exception,),{})
    modules['odoo.http'].request=request
    return namespace['ApiHttpErrors'],controllers.PublicError,response,calls,modules

class NativeErrorPresentation(unittest.TestCase):
    def fixture(self,routing='jsonrpc',payload=None):
        if payload is None:payload={'jsonrpc':'2.0','id':37,'error':{'code':200,'message':'private dynamic text','data':{'name':'private.Exception','debug':'secret SQL','arguments':['password'],'context':{'token':'secret'},'message':'hostile message'}}}
        return load_handler(SimpleNamespace(dispatcher=SimpleNamespace(routing_type=routing),httprequest=SimpleNamespace(path='/web/dataset/call_kw')),payload)

    def test_actual_public_conflict_selects_fixed_native_warning_without_details(self):
        handler,PublicError,response,calls,modules=self.fixture()
        error=PublicError('CONFLICT',{'revision':999,'sql':'secret SQL','message':'injected'})
        with patch.dict(sys.modules,modules):result=handler._handle_error(error)
        self.assertIs(result,response);self.assertEqual(calls,[error])
        self.assertEqual(result.body['id'],37);self.assertEqual(result.body['error']['code'],200)
        data=result.body['error']['data'];self.assertEqual(data['name'],'odoo.exceptions.UserError')
        self.assertIn('review the latest state',data['message']);self.assertIn('keep a copy',data['message'])
        self.assertEqual(set(data),{'name','message','request_id'})
        text=json.dumps(result.body)
        for secret in ('secret SQL','password','hostile','injected','999','private.Exception','arguments','context','debug'):
            self.assertNotIn(secret,text)

    def test_unknown_public_and_authority_codes_keep_generic_redaction(self):
        for code in ('FORBIDDEN','NOT_FOUND','VALIDATION_FAILED','CONFLICT<script>','UNKNOWN'):
            with self.subTest(code=code):
                handler,PublicError,response,_,modules=self.fixture()
                with patch.dict(sys.modules,modules):handler._handle_error(PublicError(code,{'private':'secret'}))
                self.assertEqual(response.body['error']['message'],'Operation denied or invalid')
                self.assertEqual(response.body['error']['data']['name'],'private.Exception')
                self.assertNotIn('secret',json.dumps(response.body))

    def test_lookalike_exception_code_does_not_select_public_warning(self):
        handler,_,response,_,modules=self.fixture()
        error=RuntimeError('CONFLICT secret');error.code='CONFLICT'
        with patch.dict(sys.modules,modules):handler._handle_error(error)
        self.assertEqual(response.body['error']['message'],'Operation denied or invalid')

    def test_non_rpc_parent_response_is_unchanged(self):
        handler,PublicError,response,calls,modules=self.fixture('http');before=copy.deepcopy(response.body)
        error=PublicError('CONFLICT')
        with patch.dict(sys.modules,modules):handler._handle_error(error)
        self.assertEqual(response.body,before);self.assertEqual(response.writes,0);self.assertEqual(calls,[error])

    def test_non_error_response_shapes_are_not_rewritten(self):
        for payload in ([],None,{'result':True},{'error':None},{'error':'invalid'}):
            handler,PublicError,response,_,modules=self.fixture(payload=payload if payload is not None else [])
            before=copy.deepcopy(response.body)
            with patch.dict(sys.modules,modules):handler._handle_error(PublicError('CONFLICT'))
            self.assertEqual(response.body,before);self.assertEqual(response.writes,0)

    def test_unreadable_parent_response_passes_through(self):
        handler,PublicError,response,_,modules=self.fixture()
        response.get_json=lambda:(_ for _ in ()).throw(ValueError('not JSON'))
        with patch.dict(sys.modules,modules):self.assertIs(handler._handle_error(PublicError('CONFLICT')),response)
        self.assertEqual(response.writes,0)

if __name__=='__main__':unittest.main()
