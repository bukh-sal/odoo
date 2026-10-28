"""Execute actual new controller methods against the existing request boundary."""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.client_release import protected_gateway
from modular_platform.contracts import ContractError
from modular_platform.manager_views import UPLOAD_LIMIT

class Denied(Exception):pass

class ManagerRoutes(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((ROOT/'platform_addons/mp_core/operations.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Operations')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ['upload','installed','details']]
        for method in methods:method.decorator_list=[]
        self.request=SimpleNamespace(validate_csrf=Mock(return_value=True),httprequest=SimpleNamespace(mimetype='application/octet-stream',content_length=7,headers={'X-CSRFToken':'token','X-MP-Artifact-Digest':'digest'},get_data=Mock(return_value=b'fixture')))
        self.ns={'request':self.request,'operator':Mock(),'profile_metadata':Mock(return_value=({'catalog':[]},{})),
            'result':lambda run:run(),'stamp':lambda:'now','AccessError':Denied,'ContractError':ContractError,'UPLOAD_LIMIT':UPLOAD_LIMIT,
            'validate_upload':Mock(return_value={'result':'fixture'}),'installed_view':Mock(return_value={'items':[]}),
            'details_view':Mock(return_value={'kind':'plugin_details'}),'PublicError':Denied}
        exec(compile(ast.Module(body=methods,type_ignores=[]),'actual-new-manager-routes','exec'),self.ns)

    def test_role_and_csrf_denied_before_reading_archive(self):
        for boundary in ['role','csrf']:
            self.setUp()
            if boundary=='role':self.ns['operator'].side_effect=Denied()
            else:self.request.validate_csrf.return_value=False
            with self.assertRaises(Denied):self.ns['upload'](None)
            self.request.httprequest.get_data.assert_not_called();self.ns['validate_upload'].assert_not_called()

    def test_wrong_content_type_or_oversize_denied_before_body(self):
        for mimetype,length in [('application/json',7),('application/octet-stream',UPLOAD_LIMIT+1)]:
            self.request.httprequest.mimetype=mimetype;self.request.httprequest.content_length=length
            with self.assertRaises(ContractError):self.ns['upload'](None)
            self.request.httprequest.get_data.assert_not_called()

    def test_current_profile_raw_bytes_and_digest_reach_shared_validator(self):
        self.assertEqual(self.ns['upload'](None),{'result':'fixture'})
        self.ns['validate_upload'].assert_called_once_with(b'fixture','digest',{'catalog':[]},now='now')
        self.request.validate_csrf.assert_called_once_with('token')

    def test_details_and_installed_are_operator_only_and_release_protected(self):
        for method,path,args in [('details','details',{'digest':'digest'}),('installed','installed',{'offset':'20'})]:
            self.assertTrue(protected_gateway('/api/v1/operations/'+path));self.ns[method](None,**args)
        self.assertTrue(protected_gateway('/api/v1/operations/validate-upload'))
        self.assertEqual(self.ns['operator'].call_count,2)

if __name__=='__main__':unittest.main()
