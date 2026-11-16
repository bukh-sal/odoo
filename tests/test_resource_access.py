"""Actual private helper/mixin and scope guards with only native/SQL boundaries fake.

No installed registry, concurrency or recovery qualification is claimed here.
"""
import ast
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class Denied(Exception): pass
class Invalid(Exception): pass


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def native_sql():
    tree = ast.parse((ROOT / 'engine/odoo/tools/sql.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SQL')
    code = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
    ns = dict(IDENT_RE=re.compile(r'^[a-z0-9_][a-z0-9_$\-]*$', re.I))
    exec(compile(ast.fix_missing_locations(code), 'actual-native-sql', 'exec'), ns)
    return ns['SQL']


class DomainBoundary:
    def __init__(self, *values):
        value = values[0] if len(values)==1 else values
        self.value = value.value if isinstance(value,DomainBoundary) else value
    def __and__(self, other): return DomainBoundary((self, other))
    @staticmethod
    def custom(*, to_sql):
        result = DomainBoundary(None); result.to_sql = to_sql
        return result


@contextmanager
def harness():
    SQL = native_sql(); state = dict(denial=None, allowed=True, policy_revision=1)
    calls = []; returned = []
    manifest = dict(data=dict(models=['test.record']), permissions=dict(defines={
        'record.read':'Read', 'record.write':'Write', 'record.manage':'Manage'}))
    class Cursor:
        dbname = 'owned_test'
        def execute(self, sql, params=None):
            nonlocal returned
            text = sql.code if isinstance(sql, SQL) else sql
            params = sql.params if isinstance(sql, SQL) else params
            calls.append((text, params)); returned = []
            if 'SELECT p.id, p.public_id, p.kind' in text:
                if state['denial'] not in {'actor', 'membership'}:
                    returned = [(2, ACTOR, state.get('kind','human'), 3, WORKSPACE, state.get('role','editor'), 4)]
            elif 'FROM mp_service_credential' in text:
                returned = [] if state['denial']=='credential' else [(RESOURCE,'read')]
            elif 'SELECT availability FROM mp_workspace_plugin' in text:
                returned = [('suspended' if state['denial']=='feature' else 'enabled',)]
            elif 'SELECT state FROM mp_plugin_installation' in text:
                returned = [('removed' if state['denial']=='installation' else 'installed',)]
            elif 'SELECT id FROM "test_record"' in text:
                returned = [] if state['denial']=='foreign' else [(10,)]
            elif 'SELECT i.id,i.manifest' in text:
                returned = [(7, manifest)]
            elif 'SELECT rp.id FROM mp_resource_policy' in text:
                returned = [(20,)] if state.get('lock_present',True) else []
            elif 'SELECT resource.id' in text:
                returned = [(10,)] if state['allowed'] else []
            elif 'SELECT p.id FROM mp_principal' in text:
                returned = [(9,)] if state['denial']!='subject' else []
            elif 'UPDATE mp_resource_policy rp SET revision' in text:
                if params[-1] == state['policy_revision']:
                    state['policy_revision'] += 1; returned = [(20,)]
            elif 'SELECT rp.public_id,rp.revision' in text:
                returned = [(POLICY, state['policy_revision'], 'active', ['record.read'], ACTOR)]
            elif 'SELECT p.public_id,g.capability' in text:
                returned = [(SUBJECT, 'record.read', 'approved')]
            elif 'SELECT id FROM mp_resource_policy' in text:
                returned = [(20,)] if state.get('registered',False) else []
            elif not (text.startswith(('INSERT ', 'UPDATE ')) or 'FROM mp_workspace WHERE' in text):
                raise AssertionError(text)
        def fetchone(self): return returned[0] if returned else None
        def fetchall(self): return list(returned)
    class Env(dict): pass
    env = Env(); env.uid=7; env.su=False; env.cr=Cursor(); env.context={}; env._field_dirty={}
    for model in ('res.users','mp.principal','mp.membership','mp.workspace','mp.workspace.plugin','mp.service.credential','mp.plugin.installation'):
        env[model] = types.SimpleNamespace(flush_model=lambda fields: None)
    identity = lambda method: method
    class NativeBase:
        def _has_field_access(self, field, operation): return True
        def _search(self, domain, **kwargs): return domain, kwargs
        def create(self, values_list): return values_list
        def ensure_one(self):
            if len(self.ids)!=1: raise ValueError('one required')
    native=types.ModuleType('odoo'); native.__path__=[]
    native.api=types.SimpleNamespace(private=identity, model=identity, model_create_multi=identity, readonly=identity)
    native.models=types.SimpleNamespace(AbstractModel=NativeBase)
    native.fields=types.SimpleNamespace(Many2one=lambda *a,**k:None)
    errors=types.ModuleType('odoo.exceptions'); errors.AccessError=Denied; errors.ValidationError=Invalid
    http=types.ModuleType('odoo.http'); http.request=None
    fields=types.ModuleType('odoo.fields'); fields.Domain=DomainBoundary
    tools=types.ModuleType('odoo.tools'); tools.SQL=SQL
    release=types.ModuleType('odoo.addons.mp_identity.release'); release.require_client_release=lambda env:None
    read_window=types.ModuleType('odoo.addons.mp_identity.read_window')
    read_window.KEY='_mp_read_window'; read_window.ReadWindow=object; read_window.active_window=lambda records:None
    package=types.ModuleType('_resource_test'); package.__path__=[]
    controller=types.ModuleType('_resource_test.controllers')
    # Use the actual app capability ceiling producer, not a test allow-all.
    node=next(n for n in ast.parse((ROOT/'framework_addons/mp_core/controllers.py').read_text()).body
              if isinstance(n,ast.FunctionDef) and n.name=='advertised_capabilities')
    controller.__dict__.update(json=json, CONTRACTS=ROOT/'packages/contracts/v1')
    exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-capability-ceiling','exec'),controller.__dict__)
    controller.PublicError=Invalid
    modules={'odoo':native,'odoo.exceptions':errors,'odoo.http':http,'odoo.fields':fields,'odoo.tools':tools,
             'odoo.addons.mp_identity.release':release,'odoo.addons.mp_identity.read_window':read_window,
             '_resource_test':package,'_resource_test.controllers':controller}
    with patch.dict(sys.modules,modules):
        names=[]
        try:
            scopes=load('odoo.addons.mp_identity.scopes','framework_addons/mp_identity/scopes.py'); names.append(scopes.__name__)
            env.context['_mp_scope']=scopes.Scope('owned_test',7,2,ACTOR,'human',3,WORKSPACE,'editor',4)
            ns=dict(api=native.api,fields=native.fields,models=native.models,AccessError=Denied,
                    current_scope=scopes.current_scope,SQL=SQL,Domain=DomainBoundary,active_window=lambda r:None,
                    contextmanager=contextmanager)
            for path,name,parent in [('framework_addons/mp_identity/models/scoped.py','WorkspaceScoped',NativeBase),
                    ('framework_addons/mp_core/models.py','SupportedInstallationGuard',None)]:
                cls=next(n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.ClassDef) and n.name==name)
                cls.bases=[ast.Name(id='Parent',ctx=ast.Load())]; ns['Parent']=parent or ns['WorkspaceScoped']
                exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),path,'exec'),ns)
            native.models.AbstractModel=ns['SupportedInstallationGuard']
            module=load('_resource_test.resource_access','framework_addons/mp_core/resource_access.py'); names.append(module.__name__)
            record=module.ResourceScoped(); record.env=env; record._name='test.record'; record._table='test_record'
            record._mp_plugin_id='dev.test.records'; record._mp_scoped=True
            record._mp_resource_actions=dict(read='record.read',create='record.write',write='record.write',unlink='record.write',manage='record.manage')
            record._fields={'public_id':types.SimpleNamespace(type='char')}; record._origin=types.SimpleNamespace(ids=[10]); record.ids=[10]; record._ids=(10,); record.id=10
            yield module,record,state,calls,manifest,SQL
        finally:
            for name in names:sys.modules.pop(name,None)


ACTOR='00000000-0000-4000-8000-000000000001'
WORKSPACE='00000000-0000-4000-8000-000000000002'
SUBJECT='00000000-0000-4000-8000-000000000003'
POLICY='00000000-0000-4000-8000-000000000004'
RESOURCE='00000000-0000-4000-8000-000000000005'


class ResourceAccessTests(unittest.TestCase):
    def test_authority_models_refuse_native_crud_and_cached_field_access(self):
        tree=ast.parse((ROOT/'framework_addons/mp_core/resource_models.py').read_text())
        for cls in (node for node in tree.body if isinstance(node,ast.ClassDef)):
            methods=[node for node in cls.body if isinstance(node,ast.FunctionDef)]
            selected=ast.ClassDef(name=cls.name,bases=[],keywords=[],body=methods,decorator_list=[])
            ns=dict(AccessError=Denied,api=types.SimpleNamespace(model=lambda fn:fn,model_create_multi=lambda fn:fn))
            exec(compile(ast.fix_missing_locations(ast.Module(body=[selected],type_ignores=[])),cls.name,'exec'),ns)
            instance=ns[cls.name]()
            self.assertFalse(instance._has_field_access('public_id','read'))
            for call in (lambda:instance._check_access('read'),lambda:instance.create([{}]),
                         lambda:instance.write({}),lambda:instance.unlink()):
                with self.subTest(model=cls.name),self.assertRaises(Denied):call()

    def test_registration_binds_current_actor_workspace_model_and_declared_caps(self):
        with harness() as (module,record,state,calls,manifest,SQL):
            record._ids=(); record._origin.ids=[]
            module.register(record,RESOURCE,member_capabilities=['record.read'])
            query,params=next(c for c in calls if c[0].startswith('INSERT'))
            self.assertEqual(params[1:6],[7,3,'test.record',RESOURCE,2])
            self.assertEqual(json.loads(params[6]),['record.read'])
            self.assertLess(next(i for i,c in enumerate(calls) if 'FOR SHARE' in c[0]),len(calls)-1)

    def test_actual_scope_feature_installation_and_technical_ceiling_always_apply(self):
        for denial in ('actor','membership','feature','installation','foreign'):
            with self.subTest(denial=denial),harness() as (module,record,state,calls,*_):
                state['denial']=denial
                with self.assertRaises(Denied):module.require(record,'record.read')
                self.assertFalse(any(c[0].startswith(('UPDATE ','INSERT ')) for c in calls))
        with harness() as (module,record,state,calls,*_):
            from dataclasses import replace
            record.env.context['_mp_scope']=replace(record.env.context['_mp_scope'],allowed_actions=frozenset({'read'}))
            with self.assertRaises(Denied):module.require(record,'record.write',action='write')
        with harness() as (module,record,state,calls,*_):
            record.env.context['_mp_scope']={'role':'administrator'}
            with self.assertRaises(Denied):module.require(record,'record.read')

    def test_manifest_models_unknown_caps_and_viewer_ceiling_refuse(self):
        for mutation in ('model','cap','viewer'):
            with self.subTest(mutation=mutation),harness() as (module,record,state,calls,manifest,SQL):
                if mutation=='model':manifest['data']['models']=[]
                if mutation=='cap':del manifest['permissions']['defines']['record.manage']
                if mutation=='viewer':state['role']='viewer'
                with self.assertRaises(Denied):module.require(record,'record.write')
        for capability in ('',None,{},'unregistered'):
            with self.subTest(capability=capability),harness() as (module,record,*_):
                with self.assertRaises(Denied):module.require(record,capability)

    def test_service_principal_grant_never_substitutes_for_current_credential(self):
        from dataclasses import replace
        with harness() as (module,record,state,calls,*_):
            state['kind']='service'
            record.env.context['_mp_scope']=replace(record.env.context['_mp_scope'],credential_id=4)
            module.require(record,'record.read')
            with self.assertRaises(Denied):module.require(record,'record.write',action='write')
            state['denial']='credential'
            with self.assertRaises(Denied):module.require(record,'record.read')

    def test_resource_check_covers_direct_and_cached_native_reads(self):
        with harness() as (module,record,state,calls,*_):
            self.assertTrue(record._has_field_access('name','read'))
            state['allowed']=False
            self.assertFalse(record._has_field_access('name','read'))
            with self.assertRaises(Denied):record.fetch(['name'])
            with self.assertRaises(Denied):record.web_read({})
            self.assertFalse(any('FOR UPDATE' in q for q,p in calls))

    def test_query_predicate_stays_in_native_search_before_limit_and_count(self):
        with harness() as (module,record,state,calls,manifest,SQL):
            record._origin.ids=[];record._ids=()
            domain,options=record._search([],offset=20,limit=10,bypass_access=True)
            # Actual WorkspaceScoped adds workspace, ResourceScoped adds owned
            # SQL; even an internal bypass_access request retains both guards.
            resource_domain=domain.value[0].value[1]
            query=resource_domain.to_sql(record,'test_record',None)
            self.assertIn('rp.resource_id="test_record"."public_id"',query.code)
            self.assertIn('rg.state=\'approved\'',query.code)
            self.assertIn('record.read',query.params)
            self.assertIn(3,query.params)
            self.assertEqual(options['limit'],10)
            self.assertEqual(options['offset'],20)
            self.assertEqual(query.code.count('('),query.code.count(')'))

    def test_write_locks_workspace_then_same_policy_before_capability_read(self):
        with harness() as (module,record,state,calls,*_):
            module.require(record,'record.write',action='write')
            texts=[q for q,p in calls]
            workspace=next(i for i,q in enumerate(texts) if 'FOR SHARE' in q)
            resource=next(i for i,q in enumerate(texts) if 'FOR UPDATE OF rp' in q)
            allowed=next(i for i,q in enumerate(texts) if 'SELECT resource.id' in q)
            self.assertLess(workspace,resource);self.assertLess(resource,allowed)
            state['lock_present']=False
            with self.assertRaises(Denied):module.require(record,'record.write',action='write')

    def test_cas_policy_change_uses_exact_subject_and_retains_tombstones(self):
        with harness() as (module,record,state,calls,*_):
            value=module.change_policy(record,expected_revision=1,member_capabilities=[],
                grants=[dict(principal_id=SUBJECT,capabilities=['record.read'])])
            self.assertEqual(value['revision'],2)
            writes=[(q,p) for q,p in calls if q.startswith(('UPDATE ','INSERT '))]
            self.assertIn('rp.revision=%s RETURNING rp.id',writes[0][0])
            # Resource tables commonly have their own revision column. UPDATE
            # FROM must increment the policy's revision, never the resource's.
            self.assertIn('SET revision=rp.revision+1',writes[0][0])
            self.assertNotIn('SET revision=revision+1',writes[0][0])
            self.assertIn("SET state='revoked'",writes[1][0])
            self.assertEqual(writes[2][1][:3],[20,9,'record.read'])
            self.assertFalse(any('DELETE ' in q for q,p in calls))
            self.assertEqual(next(p for q,p in calls if 'SELECT p.id FROM mp_principal' in q),[SUBJECT,3])

    def test_stale_policy_revision_never_writes_grants(self):
        with harness() as (module,record,state,calls,*_):
            state['policy_revision']=2
            with self.assertRaises(Invalid):module.change_policy(record,expected_revision=1,member_capabilities=[],grants=[])
            self.assertFalse(any('UPDATE mp_resource_grant' in q or 'INSERT INTO mp_resource_grant' in q for q,p in calls))

    def test_ineligible_subject_and_unknown_capability_refuse_before_policy_dml(self):
        for kind in ('subject','unknown','duplicate'):
            with self.subTest(kind=kind),harness() as (module,record,state,calls,*_):
                state['denial']='subject' if kind=='subject' else None
                grants=[dict(principal_id=SUBJECT,capabilities=['unknown' if kind=='unknown' else 'record.read'])]
                if kind=='duplicate':grants*=2
                with self.assertRaises((Denied,Invalid)):
                    module.change_policy(record,expected_revision=1,member_capabilities=[],grants=grants)
                self.assertFalse(any(q.startswith(('UPDATE ','INSERT ')) for q,p in calls))

    def test_native_create_requires_private_registration_not_forged_marker(self):
        with harness() as (module,record,state,calls,*_):
            record._origin.ids=[];record._ids=()
            record.env.context['_mp_resource_registered']=True
            with self.assertRaises(Denied):record.create([dict(public_id=RESOURCE)])
            state['registered']=True
            self.assertEqual(record.create([dict(public_id=RESOURCE)]),[dict(public_id=RESOURCE,workspace_id=3)])


if __name__=='__main__':unittest.main()
