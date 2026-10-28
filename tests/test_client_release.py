"""Release identity and actual HTTP adapter functions, without an Odoo registry."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.client_release import read_release,matches_release,protected_gateway
from modular_platform.contracts import validate
from modular_platform.plans import data_digest


class Cursor:
    dbname='disposable'
    def __init__(self):
        self.values={'mp.site_id':'00000000-0000-4000-8000-000000000002','mp.release_generation':'16',
            'mp.release_digest':'sha256:'+'a'*64,'mp.active_inventory_digest':'sha256:'+'b'*64};self.calls=[]
    def execute(self,*args):self.calls.append(args)
    def fetchall(self):return list(self.values.items())


class ClientReleaseTests(unittest.TestCase):
    def setUp(self):self.cursor=Cursor();self.inventory=self.cursor.values['mp.active_inventory_digest']

    def test_published_tuple_single_query_and_canonical_token(self):
        doc=read_release(self.cursor,self.inventory);validate('client-release',doc)
        self.assertEqual(len(self.cursor.calls),1)
        self.assertEqual(doc['token'],data_digest({key:value for key,value in doc.items() if key!='token'}))
        self.assertTrue(matches_release(doc,doc['token']))
        for token in [None,'',doc['token']+'\n','sha256:'+'c'*64,42]:self.assertFalse(matches_release(doc,token))

    def test_epoch_restore_and_site_inventory_each_change_identity(self):
        before=read_release(self.cursor,self.inventory)
        for key,value in [('mp.release_generation','17'),('mp.site_id','00000000-0000-4000-8000-000000000003'),('mp.release_digest','sha256:'+'c'*64)]:
            old=self.cursor.values[key];self.cursor.values[key]=value
            self.assertNotEqual(read_release(self.cursor,self.inventory)['token'],before['token']);self.cursor.values[key]=old
        self.cursor.values['mp.active_inventory_digest']='sha256:'+'d'*64
        self.assertNotEqual(read_release(self.cursor,'sha256:'+'d'*64)['token'],before['token'])

    def test_missing_malformed_publication_and_wrong_image_fail_closed(self):
        original=copy.deepcopy(self.cursor.values)
        for key in original:
            self.cursor.values=original.copy();self.cursor.values.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):read_release(self.cursor,self.inventory)
        for generation in ['0','01','1\n','9007199254740992','-1','true']:
            self.cursor.values=original|{'mp.release_generation':generation}
            with self.subTest(generation=generation),self.assertRaises(ValueError):read_release(self.cursor,self.inventory)
        self.cursor.values=original
        with self.assertRaises(ValueError):read_release(self.cursor,'sha256:'+'e'*64)

    def test_only_explicit_recovery_endpoints_are_exempt(self):
        for path in ['/api/v1/session','/api/v1/workspaces','/api/v1/client-release']:self.assertFalse(protected_gateway(path))
        for path in ['/api/v1/context','/api/v1/services/notes/update','/api/v1/operations/prepare','/api/v1/session/unsafe']:
            self.assertTrue(protected_gateway(path))

    def adapter(self,path='/web/dataset/call_kw',token=None):
        exceptions=ModuleType('odoo.exceptions');exceptions.AccessError=type('AccessError',(Exception,),{})
        http=ModuleType('odoo.http');http.request=SimpleNamespace(db='disposable',httprequest=SimpleNamespace(path=path,headers={}))
        if token is not None:http.request.httprequest.headers['X-MP-Client-Release']=token
        spec=importlib.util.spec_from_file_location('isolated_release',ROOT/'platform_addons/mp_identity/release.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'odoo':ModuleType('odoo'),'odoo.exceptions':exceptions,'odoo.http':http}):spec.loader.exec_module(module)
        module.image_inventory_digest=lambda:self.inventory
        return module,SimpleNamespace(cr=self.cursor)

    def test_actual_adapter_rejects_missing_stale_and_wrong_inventory_before_dispatch(self):
        for token in [None,'sha256:'+'c'*64]:
            module,env=self.adapter(token=token)
            with self.assertRaises(module.ClientReleaseMismatch):module.require_client_release(env)
            self.assertFalse(getattr(module.request,'_mp_client_release_checked',False))
        module,env=self.adapter(token=read_release(self.cursor,self.inventory)['token'])
        self.cursor.values['mp.active_inventory_digest']='sha256:'+'d'*64
        with self.assertRaises(module.ClientReleaseUnavailable):module.require_client_release(env)

    def test_actual_adapter_current_token_recovery_and_non_http_paths(self):
        token=read_release(self.cursor,self.inventory)['token'];module,env=self.adapter(token=token)
        self.cursor.calls=[];module.require_client_release(env);module.require_client_release(env)
        self.assertEqual(len(self.cursor.calls),1)
        module,env=self.adapter(path='/api/v1/session');module.require_client_release(env)
        module.request=None;module.require_client_release(env)

    def test_contract_example_has_exact_canonical_identity(self):
        doc=json.loads((ROOT/'packages/contracts/examples/v1/client-release.json').read_text(encoding='utf-8'))
        validate('client-release',doc)
        self.assertEqual(doc['token'],data_digest({key:value for key,value in doc.items() if key!='token'}))


if __name__=='__main__':unittest.main()
