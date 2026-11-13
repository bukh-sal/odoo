"""Actual Home authentication flow plus the stock neutral entry extension.

Native request/session/ORM/QWeb boundaries are simulated; installed browser
qualification remains separate. The original Home method is compiled from the
current source, not reimplemented in this test.
"""
import ast
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from uuid import UUID
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
A='218464f2-b2e0-466a-8310-0a78fc0bcb73'
B='f89466f6-19cd-46d2-9685-60f8fa89790e'


class AccessError(Exception):pass
class SessionExpired(Exception):pass


@contextmanager
def fixture(*,selected=None,stock=True,uid=2,session_valid=True,internal=True,redirect=None,denied=(),list_denied=False):
    calls=[];responses=[];rows=[types.SimpleNamespace(public_id=A,name='Workspace A'),types.SimpleNamespace(public_id=B,name='<script>Other</script>')]
    def route(*args,**kwargs):return lambda fn:fn
    http=types.SimpleNamespace(route=route,SessionExpiredException=SessionExpired,Controller=object)
    class Workspaces:
        def search(self,domain,**kwargs):
            calls.append(('search',domain,kwargs))
            if list_denied:raise AccessError('Workspace metadata unavailable')
            return rows
    class Environment:
        uid=None
        user=types.SimpleNamespace(_on_webclient_bootstrap=lambda:calls.append(('bootstrap_user',)),_session_token_get_values=lambda:[])
        def __call__(self,**kwargs):calls.append(('original_hmac_env',kwargs));return self
        def __getitem__(self,key):
            if key=='mp.workspace':return Workspaces()
            if key=='ir.http':return types.SimpleNamespace(webclient_rendering_context=lambda:{'session_info':{}})
            raise AssertionError('Unexpected model '+key)
    env=Environment()
    def response(template=None,values=None,status=200,location=None):
        value=types.SimpleNamespace(status_code=status,headers={},template=template,values=values,location=location);responses.append(value);return value
    request=types.SimpleNamespace(db='owned',session=types.SimpleNamespace(uid=uid,touch=lambda:calls.append(('touch',))),env=env,
        httprequest=types.SimpleNamespace(args={} if selected is None else {'workspace':selected},full_path='/odoo'),params={})
    request.update_env=lambda **kwargs:(calls.append(('restore_user',kwargs)),setattr(env,'uid',kwargs['user']))
    request.render=lambda template,qcontext=None:response(template,qcontext)
    request.redirect_query=lambda path,query=None,code=303:response(status=code,location=(path,query))
    request.redirect=lambda path,code=303:response(status=code,location=path)
    security=types.SimpleNamespace(check_session=lambda *args:session_valid)
    globals=dict(http=http,request=request,security=security,is_user_internal=lambda value:internal,ensure_db=lambda:calls.append(('ensure_db',)),hmac=lambda *args:'fixture',AccessError=AccessError)
    tree=ast.parse((ROOT/'framework_addons/web/controllers/home.py').read_text())
    home=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Home')
    home.body=[node for node in home.body if isinstance(node,ast.FunctionDef) and node.name in {'_web_client_readonly','web_client'}]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[home],type_ignores=[])),'actual-native-Home','exec'),globals)
    def scope(actual_env,public):
        calls.append(('scope',public));assert actual_env is env and env.uid==uid
        if str(UUID(public))!=public or public in denied:raise AccessError('Current membership unavailable')
        return object()
    def module(name,**values):m=types.ModuleType(name);m.__dict__.update(values);return m
    modules={
        'odoo':module('odoo',http=http),
        'odoo.exceptions':module('odoo.exceptions',AccessError=AccessError),
        'odoo.http':module('odoo.http',request=request),
        'odoo.addons.web.controllers.home':module('odoo.addons.web.controllers.home',Home=globals['Home']),
        'odoo.addons.mp_identity.release':module('odoo.addons.mp_identity.release',stock_webclient_default=lambda:stock),
        'odoo.addons.mp_identity.scopes':module('odoo.addons.mp_identity.scopes',resolve_scope=scope)}
    with patch.dict(sys.modules,modules):
        spec=importlib.util.spec_from_file_location('owned_workspace_landing',ROOT/'framework_addons/mp_core/workspace_landing.py')
        extension=importlib.util.module_from_spec(spec);spec.loader.exec_module(extension)
        def invoke():return extension.WorkspaceLanding().web_client(**({'redirect':redirect} if redirect else {}))
        yield types.SimpleNamespace(invoke=invoke,calls=calls,responses=responses,rows=rows,request=request)


class WorkspaceLandingTests(unittest.TestCase):
    def test_unscoped_stock_keeps_actual_authentication_then_chooses_before_app(self):
        with fixture() as f:
            result=f.invoke()
            self.assertEqual(f.calls[:3],[('ensure_db',),('touch',),('restore_user',{'user':2})])
            self.assertEqual(result.template,'mp_core.workspace_landing')
            self.assertEqual(result.values['workspaces'],[{'id':A,'name':'Workspace A'},{'id':B,'name':'<script>Other</script>'}])
            self.assertIn(('search',[('state','=','active')],{'order':'name,id'}),f.calls)
            self.assertEqual([v for v in f.calls if v[0]=='scope'],[('scope',A),('scope',B)])
            self.assertEqual(result.headers,{'Cache-Control':'no-store','X-Frame-Options':'DENY'})
            self.assertEqual(f.responses[0].template,'web.webclient_bootstrap')
            self.assertEqual([v for v in f.calls if v[0]=='original_hmac_env'],[('original_hmac_env',{'su':True})])

    def test_original_unauthenticated_redirect_remains_and_reads_no_workspaces(self):
        with fixture(uid=None) as f:
            result=f.invoke();self.assertEqual(result.status_code,303)
            self.assertEqual(result.location,('/web/login',{'redirect':'/odoo'}));self.assertEqual(f.calls,[('ensure_db',)])

    def test_original_session_validation_cannot_be_bypassed_by_chooser(self):
        with fixture(session_valid=False) as f:
            with self.assertRaises(SessionExpired):f.invoke()
            self.assertEqual(f.calls,[('ensure_db',)])

    def test_original_internal_user_check_and_redirect_remain(self):
        with fixture(internal=False) as f:
            self.assertEqual(f.invoke().location,'/web/login_successful');self.assertEqual(f.calls,[('ensure_db',)])
        with fixture(redirect='/bounded-existing-native-redirect') as f:
            self.assertEqual(f.invoke().location,'/bounded-existing-native-redirect');self.assertEqual(f.calls,[('ensure_db',)])

    def test_current_membership_principal_denial_removes_choices(self):
        with fixture(denied=(B,)) as f:
            self.assertEqual(f.invoke().values['workspaces'],[{'id':A,'name':'Workspace A'}])
        with fixture(denied=(A,B)) as f:self.assertEqual(f.invoke().values['workspaces'],[])

    def test_empty_workspaces_and_empty_selection_are_neutral(self):
        with fixture(selected='') as f:
            f.rows.clear();result=f.invoke();self.assertEqual(result.template,'mp_core.workspace_landing');self.assertEqual(result.values['workspaces'],[])

    def test_metadata_access_denial_has_no_names_and_distinct_reload_state(self):
        with fixture(list_denied=True) as f:
            result=f.invoke();self.assertEqual(result.values,{'workspaces':[],'workspaces_unavailable':True})
            self.assertEqual(result.headers['Cache-Control'],'no-store');self.assertFalse(any(v[0]=='scope' for v in f.calls))

    def test_scoped_unknown_or_malformed_queries_keep_original_response_and_gates(self):
        for selected in (A,'unknown-workspace','https://foreign.invalid/?workspace='+A):
            with fixture(selected=selected) as f:
                result=f.invoke();self.assertIs(result,f.responses[0]);self.assertEqual(result.template,'web.webclient_bootstrap')
                self.assertFalse(any(v[0] in ('search','scope') for v in f.calls))

    def test_nonstock_reference_profile_keeps_original_bootstrap(self):
        with fixture(stock=False) as f:
            result=f.invoke();self.assertIs(result,f.responses[0]);self.assertFalse(any(v[0]=='search' for v in f.calls))

    def test_owned_template_is_escaped_neutral_and_keeps_initial_links_local(self):
        tree=ET.parse(ROOT/'framework_addons/mp_core/views/workspace_landing.xml')
        link=next(e for e in tree.iter('a') if e.get('class')=='mp-workspace-choice')
        self.assertEqual(link.get('t-esc'),"space['name']")
        self.assertEqual(link.get('t-att-href'),"'/odoo?workspace=' + space['id']")
        self.assertIsNone(link.get('target'));self.assertFalse(any('t-raw' in e.attrib for e in tree.iter()))
        self.assertTrue(any(e.get('name')=='viewport' for e in tree.iter('meta')))
        self.assertTrue(any(e.get('role')=='status' for e in tree.iter('p')))


if __name__=='__main__':unittest.main()
