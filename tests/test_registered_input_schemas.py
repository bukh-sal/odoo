"""Owned service schemas use the real registration and bound-dispatch seams."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactError
from modular_platform.contracts import CONTRACTS, ContractError


class Denied(Exception):
    pass


class PublicError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def registered_core():
    package = types.ModuleType('_owned_input_test')
    package.__path__ = [str(ROOT / 'framework_addons/mp_core')]
    odoo = types.ModuleType('odoo'); odoo.__path__ = []
    addons = types.ModuleType('odoo.addons'); addons.__path__ = []
    identity = types.ModuleType('odoo.addons.mp_identity'); identity.__path__ = []
    scopes = types.ModuleType('odoo.addons.mp_identity.scopes'); scopes.current_scope = lambda env: None
    exceptions = types.ModuleType('odoo.exceptions'); exceptions.AccessError = Denied
    controllers = types.ModuleType('_owned_input_test.controllers'); controllers.PublicError = PublicError
    modules = {'_owned_input_test': package, 'odoo': odoo, 'odoo.addons': addons,
        'odoo.addons.mp_identity': identity, 'odoo.addons.mp_identity.scopes': scopes,
        'odoo.exceptions': exceptions, '_owned_input_test.controllers': controllers}
    with patch.dict(sys.modules, modules):
        loaded = []
        try:
            for name in ('registry', 'dispatch'):
                key = '_owned_input_test.' + name
                spec = importlib.util.spec_from_file_location(key, ROOT / 'framework_addons/mp_core' / (name + '.py'))
                module = importlib.util.module_from_spec(spec)
                sys.modules[key] = module
                loaded.append(key)
                spec.loader.exec_module(module)
            yield sys.modules[loaded[0]], sys.modules[loaded[1]]
        finally:
            for key in loaded:
                sys.modules.pop(key, None)


OWNED = {'$defs': {'input': {'type': 'object', 'properties': {'name': {'type': 'string', 'minLength': 1}},
    'required': ['name'], 'additionalProperties': False}}, '$ref': '#/$defs/input'}


class RegisteredInputSchemas(unittest.TestCase):
    def method(self, registry, schema=OWNED, schema_file=None):
        return registry.Method('test.owned', '_mp_service_create', schema, schema_file,
            'dev.local:record.write', True, 'create', {'type': 'object', 'properties': {'saved': {'type': 'string'}},
                'required': ['saved'], 'additionalProperties': False})

    def test_registration_accepts_complete_local_defs_without_editing_core_contracts(self):
        with registered_core() as (registry, _):
            method = self.method(registry)
            registry.register('dev.local.records', '1.0', 'dev.local', {'create': method})
            schema = registry.input_schema_for(method)
            self.assertEqual(schema, OWNED)
            schema['$defs'].clear()
            self.assertTrue(method.input_schema['$defs'])

    def test_legacy_definition_is_byte_semantically_unchanged(self):
        with registered_core() as (registry, _):
            method = self.method(registry, 'create_input', 'documents.schema.json')
            self.assertEqual(registry.input_schema_for(method),
                json.loads((CONTRACTS / 'documents.schema.json').read_bytes())['$defs']['create_input'])

    def test_remote_refs_and_ambiguous_source_refuse_before_registration(self):
        with registered_core() as (registry, _):
            for method in (self.method(registry, {'$ref': 'https://remote.invalid/schema'}),
                    self.method(registry, {'$dynamicRef': 'https://remote.invalid/schema'}),
                    self.method(registry, OWNED, 'documents.schema.json')):
                with self.subTest(method=method), self.assertRaises((ValueError, ArtifactError)):
                    registry.register('dev.local.records', '1.0', 'dev.local', {'create': method})
                self.assertEqual(registry.SERVICES, {})

    def test_real_bound_dispatch_validates_input_guard_and_output(self):
        with registered_core() as (registry, dispatch):
            calls = []
            class Model:
                def _mp_guard(self, action): calls.append(('guard', action))
                def _mp_service_create(self, value): calls.append(('handler', value)); return {'saved': value['name']}
            bound = dispatch.BoundCall(Model(), self.method(registry), {}, 'dev.local')
            self.assertEqual(bound.invoke({'name': 'Example'}), {'saved': 'Example'})
            self.assertEqual(calls, [('guard', 'create'), ('handler', {'name': 'Example'})])
            calls.clear()
            with self.assertRaises(ContractError): bound.invoke({'name': ''})
            self.assertEqual(calls, [])

    def test_real_bound_guard_denial_precedes_handler_and_invalid_output_refuses(self):
        with registered_core() as (registry, dispatch):
            class Model:
                def _mp_guard(self, action): raise Denied()
                def _mp_service_create(self, value): raise AssertionError('Must not invoke denied handler')
            with self.assertRaises(Denied):
                dispatch.BoundCall(Model(), self.method(registry), {}, 'dev.local').invoke({'name': 'Example'})
            class BadOutput:
                def _mp_guard(self, action): pass
                def _mp_service_create(self, value): return {'unexpected': True}
            with self.assertRaises(PublicError) as failure:
                dispatch.BoundCall(BadOutput(), self.method(registry), {}, 'dev.local').invoke({'name': 'Example'})
            self.assertEqual(failure.exception.code, 'INTERNAL_ERROR')


if __name__ == '__main__':
    unittest.main()
