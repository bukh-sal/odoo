"""Actual gateway replay ordering; fake only HTTP/native storage boundaries."""
import ast
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import time
from types import SimpleNamespace
import unittest

import rfc8785
import test_registered_input_schemas as existing
from test_registered_input_schemas import registered_core, Denied, PublicError
from modular_platform.contracts import ContractError, FORMAT_CHECKER

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def request_path(*, duplicate=True, authorizer='_mp_authorize_record'):
    with registered_core() as (registry, dispatch):
        calls = []
        spec = replace(existing.RegisteredInputSchemas().method(registry), authorize_resource=authorizer)
        body = {'api_version': '1.0', 'input': {'name': 'Example'}, 'idempotency_key': 'one-command'}
        binding = dict(consumer_installation_id='installation', provider_installation_id='installation',
            alias='records', site_id='site', service_id='dev.local.records', api_version='1.0',
            contract_major=1, generation=2)
        manifest = {'plugin': {'id': 'dev.local'}, 'services': {'requires': [{'alias': 'records'}],
            'provides': [{'id': 'dev.local.records', 'api_version': '1.0', 'methods': ['create']}]}}
        class Cursor:
            def execute(self, sql, args):
                if 'SELECT b.descriptor' in sql: self.row = (binding, manifest, 'installed', manifest, 'installed')
                elif 'SELECT availability' in sql: self.row = ('enabled',)
                elif 'INSERT INTO mp_service_outcome' in sql:
                    calls.append('outcome_insert'); self.row = None if duplicate else (42,)
                elif 'SELECT input_digest' in sql:
                    calls.append('outcome_read')
                    self.row = (hashlib.sha256(rfc8785.dumps(body['input'])).hexdigest(), 'binding', 2,
                        '1.0', 'completed', {'saved': 'Example'}, datetime.utcnow()+timedelta(hours=1))
                elif 'UPDATE mp_service_outcome' in sql: calls.append('outcome_complete')
                else: raise AssertionError(sql)
            def fetchone(self): return self.row
        class Model:
            allowed = True
            def _mp_guard(self, action): calls.append('model_guard')
            def with_context(self, **kw):
                self.frame = kw['_mp_call_frame']; return self
            def _mp_authorize_record(self, values):
                self.asserted_frame = isinstance(self.frame, dispatch.CallFrame)
                calls.append('resource_guard')
                if not self.allowed: raise Denied('Resource revoked')
            def _mp_service_create(self, values):
                calls.append('handler'); return {'saved': values['name']}
        model = Model()
        class Env(dict): pass
        env = Env({'test.owned': model}); env.cr = Cursor()
        req = SimpleNamespace(env=env, httprequest=SimpleNamespace(headers={'X-MP-Binding': 'binding'}))
        scope = SimpleNamespace(workspace_id=1, principal_public_id='actor', workspace_public_id='workspace')
        tree = ast.parse((ROOT/'framework_addons/mp_core/controllers.py').read_bytes())
        function = next(n for cls in tree.body if isinstance(cls, ast.ClassDef)
            for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'call')
        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        ns = dict(__package__='_owned_input_test', request=req, time=time,
            bounded_body=lambda name: body, current_scope=lambda env: scope, site_id=lambda: 'site',
            validate_binding=lambda *args: None, SERVICES={('dev.local.records', '1.0', 'dev.local'): {'create': spec}},
            input_schema_for=registry.input_schema_for, FORMAT_CHECKER=FORMAT_CHECKER,
            result=lambda run: run(), ContractError=ContractError, PublicError=PublicError,
            AccessError=Denied, hashlib=hashlib, rfc8785=rfc8785, datetime=datetime, timedelta=timedelta,
            json=__import__('json'))
        exec(compile(module, 'actual-gateway-call', 'exec'), ns)
        yield lambda: ns['call'](None, 'dev.local.records', 'create'), model, body, calls, registry, dispatch, spec


class ServiceResourceAuthorization(unittest.TestCase):
    def test_completed_replay_checks_current_resource_before_outcome_without_handler(self):
        with request_path() as (call, model, _, calls, *_):
            self.assertEqual(call(), {'saved': 'Example'})
            self.assertTrue(model.asserted_frame)
            self.assertEqual(calls, ['model_guard', 'resource_guard', 'outcome_insert', 'outcome_read'])
            calls.clear(); model.allowed = False
            with self.assertRaises(Denied): call()
            self.assertEqual(calls, ['model_guard', 'resource_guard'])

    def test_new_command_checks_before_insert_handler_and_completion(self):
        with request_path(duplicate=False) as (call, _, _, calls, *_):
            self.assertEqual(call(), {'saved': 'Example'})
            self.assertEqual(calls, ['model_guard', 'resource_guard', 'outcome_insert', 'handler', 'outcome_complete'])

    def test_bad_input_does_not_reach_resource_or_outcome(self):
        with request_path() as (call, _, body, calls, *_):
            body['input'] = {'name': ''}
            with self.assertRaises(ContractError): call()
            self.assertEqual(calls, ['model_guard'])

    def test_missing_or_false_guard_fails_closed_before_outcome(self):
        for name in ('_mp_authorize_missing', '_mp_authorize_record'):
            with self.subTest(name=name), request_path(authorizer=name) as (call, model, _, calls, *_):
                if name.endswith('record'): model._mp_authorize_record = lambda values: False
                with self.assertRaises(Denied): call()
                self.assertEqual(calls, ['model_guard'])

    def test_default_none_preserves_legacy_replay(self):
        with request_path(authorizer=None) as (call, _, _, calls, *_):
            self.assertEqual(call(), {'saved': 'Example'})
            self.assertEqual(calls, ['model_guard', 'outcome_insert', 'outcome_read'])

    def test_bound_call_uses_same_guard_and_denial_before_handler(self):
        with request_path() as (_, model, body, calls, _, dispatch, spec):
            model.frame = dispatch.CallFrame('actor', 'workspace', 'site', 'installation', 'dev.local', ())
            bound = dispatch.BoundCall(model, spec, {}, 'dev.local')
            self.assertEqual(bound.invoke(body['input']), {'saved': 'Example'})
            self.assertEqual(calls, ['model_guard', 'resource_guard', 'handler'])
            calls.clear(); model.allowed = False
            with self.assertRaises(Denied): bound.invoke(body['input'])
            self.assertEqual(calls, ['model_guard', 'resource_guard'])

    def test_registration_rejects_browser_selected_or_nonprivate_hooks(self):
        with registered_core() as (registry, _):
            for name in ('write', '_mp_service_write', 42, False):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    registry.register('dev.local.records', '1.0', 'dev.local', {
                        'create': replace(existing.RegisteredInputSchemas().method(registry), authorize_resource=name)})
            self.assertEqual(registry.SERVICES, {})


if __name__ == '__main__': unittest.main()
