"""Actual binary gateway/result/legacy hooks, isolated only at native boundaries.

These are source proofs, not installed authentication/storage qualification.
"""
import ast
from contextlib import contextmanager
import importlib.util
import json
import traceback
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactError
from modular_platform.contracts import ContractError, validate, ERROR_STATUS


class Denied(Exception): pass
class Missing(Exception): pass
class Invalid(Exception): pass
class ReleaseMismatch(ContractError): pass
class ReleaseUnavailable(ContractError): pass
class SerializationFailure(Exception): pass
class DeadlockDetected(Exception): pass
class RequestEntityTooLarge(Exception): pass


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def gateway():
    calls = []
    cr = types.SimpleNamespace(rollback=lambda: calls.append('rollback'))
    model = types.SimpleNamespace(_mp_scoped=True, _mp_plugin_id='dev.test.files')
    model._mp_guard = lambda action: calls.append(('guard', action))
    env = {'test.file': model}
    class Env(dict): pass
    env = Env(env); env.cr = cr
    raw = types.SimpleNamespace(path='/api/v1/binary/dev.test.files/content', headers={},
        query_string=b'', mimetype='application/octet-stream', content_length=3)
    raw.get_data = lambda: calls.append('body') or b'abc'
    request = types.SimpleNamespace(httprequest=raw, env=env, session=types.SimpleNamespace(uid=7),
        validate_csrf=lambda token: token == 'valid',
        make_json_response=lambda body, status=200, headers=None: dict(body=body, status=status, headers=dict(headers or [])),
        make_response=lambda body, headers=None: dict(body=body, status=200, headers=dict(headers or [])))
    package = types.ModuleType('_binary_test'); package.__path__ = []
    http = types.ModuleType('odoo.http'); http.request = request; http.Controller = object
    http.route = lambda *a, **kw: lambda method: method
    native = types.ModuleType('odoo'); native.http = http
    exceptions = types.ModuleType('odoo.exceptions'); exceptions.AccessError = Denied
    web = types.ModuleType('werkzeug'); web.__path__ = []
    web_errors = types.ModuleType('werkzeug.exceptions'); web_errors.RequestEntityTooLarge = RequestEntityTooLarge
    # Load the ACTUAL result/PublicError definitions. Remaining unrelated
    # controller models/routes need no native registry for this boundary proof.
    tree = ast.parse((ROOT / 'framework_addons/mp_core/controllers.py').read_text())
    selected = ast.Module(body=[node for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in {'PublicError', 'result'}], type_ignores=[])
    controller = types.ModuleType('_binary_test.controllers')
    import uuid
    controller.__dict__.update(request=request, uuid4=uuid.uuid4, protected_gateway=lambda path: True,
        require_client_release=lambda env: calls.append('release'), validate=validate,
        audit=lambda decision, ident: calls.append(('audit', decision)),
        AccessError=Denied, MissingError=Missing, ValidationError=Invalid, ContractError=ContractError,
        ClientReleaseMismatch=ReleaseMismatch, ClientReleaseUnavailable=ReleaseUnavailable,
        ERROR_STATUS=ERROR_STATUS, psycopg2=types.SimpleNamespace(errors=types.SimpleNamespace(
            SerializationFailure=SerializationFailure, DeadlockDetected=DeadlockDetected)),
        traceback=traceback, Path=Path, json=json,
        _logger=types.SimpleNamespace(error=lambda *args: calls.append('private_error')))
    exec(compile(selected, 'actual-core-result', 'exec'), controller.__dict__)
    modules = {'_binary_test': package, '_binary_test.controllers': controller,
        'odoo': native, 'odoo.http': http, 'odoo.exceptions': exceptions,
        'werkzeug': web, 'werkzeug.exceptions': web_errors}
    with patch.dict(sys.modules, modules):
        try:
            binary = load('_binary_test.binary', ROOT / 'framework_addons/mp_core/binary.py')
            meta = {'type': 'object', 'properties': {'filename': {'type': 'string', 'maxLength': 180}},
                'required': ['filename'], 'additionalProperties': False}
            output = {'type': 'object', 'properties': {'saved': {'type': 'boolean'}},
                'required': ['saved'], 'additionalProperties': False}
            endpoint = binary.BinaryEndpoint('test.file', '_mp_binary_upload', '_mp_binary_download', meta, output, 8)
            binary.register_binary('dev.test.files', 'content', endpoint)
            raw.headers.update({'X-CSRFToken': 'valid', 'X-MP-Binary-Metadata': '{"filename":"brief.txt"}'})
            model._mp_binary_upload = lambda metadata, data: calls.append(('upload', metadata, data)) or {'saved': True}
            model._mp_binary_download = lambda ident: calls.append(('download', ident)) or binary.BinaryContent(b'abc', 'brief.txt')
            yield binary, controller, request, model, calls
        finally:
            sys.modules.pop('_binary_test.binary', None)


IDENT = '6c380fd2-a250-4e01-b902-83c907c82620'


class WorkspaceBinaryTests(unittest.TestCase):
    def upload(self, binary, **kw):
        return binary.BinaryGateway().upload('dev.test.files', 'content', **kw)

    def download(self, binary, ident=IDENT, **kw):
        return binary.BinaryGateway().download('dev.test.files', 'content', ident, **kw)

    def test_real_upload_orders_fences_guard_metadata_body_private_handler_and_audit(self):
        with gateway() as (binary, _, req, _, calls):
            response = self.upload(binary)
            self.assertEqual(response['body']['data'], {'saved': True})
            self.assertEqual(response['headers']['Cache-Control'], 'no-store')
            self.assertEqual(calls, ['release', ('guard', 'create'), 'body',
                ('upload', {'filename': 'brief.txt'}, b'abc'), ('guard', 'create'), ('audit', 'allowed')])

    def test_session_release_and_guard_denials_never_read_body_or_call_handler(self):
        for failure in ('session', 'release', 'model_guard', 'owner'):
            with self.subTest(failure=failure), gateway() as (binary, ctrl, req, model, calls):
                if failure == 'session': req.session.uid = None
                if failure == 'release': ctrl.require_client_release = lambda env: (_ for _ in ()).throw(ReleaseMismatch())
                if failure == 'model_guard': model._mp_guard = lambda action: (_ for _ in ()).throw(Denied())
                if failure == 'owner': model._mp_plugin_id = 'dev.foreign'
                response = self.upload(binary)
                self.assertIn(response['status'], (401, 403, 409))
                self.assertNotIn('body', calls)
                self.assertFalse(any(isinstance(c, tuple) and c[0] == 'upload' for c in calls))
                self.assertIn('rollback', calls)

    def test_csrf_and_transport_headers_query_refuse_before_body(self):
        for change in ('csrf', 'mimetype', 'encoding', 'query', 'kwargs'):
            with self.subTest(change=change), gateway() as (binary, _, req, _, calls):
                if change == 'csrf': req.httprequest.headers['X-CSRFToken'] = 'wrong'
                if change == 'mimetype': req.httprequest.mimetype = 'multipart/form-data'
                if change == 'encoding': req.httprequest.headers['Content-Encoding'] = 'gzip'
                if change == 'query': req.httprequest.query_string = b'model=foreign'
                response = self.upload(binary, **({'handler': '_other'} if change == 'kwargs' else {}))
                self.assertIn(response['status'], (400, 403))
                self.assertNotIn('body', calls)

    def test_metadata_bound_schema_duplicates_and_remote_schema_refused(self):
        for value in ('', '{}', '{"filename":"a","filename":"b"}', '{"filename":"a","model":"foreign"}',
                      '{"filename":"' + 'a' * 4096 + '"}'):
            with self.subTest(value=value[:40]), gateway() as (binary, _, req, _, calls):
                req.httprequest.headers['X-MP-Binary-Metadata'] = value
                self.assertEqual(self.upload(binary)['status'], 400)
                self.assertNotIn('body', calls)
        with gateway() as (binary, _, _, _, _):
            endpoint = binary.ENDPOINTS['dev.test.files', 'content']
            from dataclasses import replace
            for schema in ({'$ref': 'https://example.invalid/schema'}, {'$dynamicRef': 'https://invalid'}):
                with self.assertRaises(ArtifactError):
                    binary.register_binary('dev.test.other', 'content', replace(endpoint, metadata_schema=schema))

    def test_declared_and_actual_body_bounds_include_unknown_length(self):
        for length, data, body_read in ((9, b'abc', False), (None, b'123456789', True), (3, b'', True)):
            with self.subTest(length=length, data=data), gateway() as (binary, _, req, _, calls):
                req.httprequest.content_length = length
                req.httprequest.get_data = lambda: calls.append('body') or data
                self.assertEqual(self.upload(binary)['status'], 400)
                self.assertEqual('body' in calls, body_read)
                self.assertFalse(any(isinstance(c, tuple) and c[0] == 'upload' for c in calls))

    def test_native_body_limit_exception_is_validation_failure_not_internal_error(self):
        with gateway() as (binary, _, req, _, calls):
            req.httprequest.content_length = None
            req.httprequest.get_data = lambda: (_ for _ in ()).throw(RequestEntityTooLarge())
            response = self.upload(binary)
            self.assertEqual(response['status'], 400)
            self.assertNotIn(('audit', 'allowed'), calls)

    def test_download_rechecks_guard_and_never_returns_inline_or_cacheable_content(self):
        with gateway() as (binary, _, req, model, calls):
            model._mp_binary_download = lambda ident: binary.BinaryContent(b'<script>not rendered</script>', 'résumé.txt')
            from dataclasses import replace
            binary.ENDPOINTS['dev.test.files', 'content'] = replace(binary.ENDPOINTS['dev.test.files', 'content'], max_bytes=100)
            response = self.download(binary)
            self.assertEqual(response['body'], b'<script>not rendered</script>')
            headers = response['headers']
            self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
            self.assertIn('r%C3%A9sum%C3%A9.txt', headers['Content-Disposition'])
            self.assertEqual(headers['Content-Type'], 'application/octet-stream')
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertIn('sandbox', headers['Content-Security-Policy'])
            self.assertEqual(calls.count(('guard', 'read')), 2)
            self.assertEqual(calls[-1], ('audit', 'allowed'))

    def test_download_uuid_query_range_unknown_resource_no_byte_handler(self):
        for change in ('uuid', 'query', 'range', 'unknown'):
            with self.subTest(change=change), gateway() as (binary, _, req, _, calls):
                if change == 'query': req.httprequest.query_string = b'access_token=forged'
                if change == 'range': req.httprequest.headers['Range'] = 'bytes=0-1'
                if change == 'unknown': binary.ENDPOINTS.clear()
                response = self.download(binary, '1' if change == 'uuid' else IDENT)
                self.assertIn(response['status'], (400, 404))
                self.assertFalse(any(isinstance(c, tuple) and c[0] == 'download' for c in calls))

    def test_download_bad_type_oversize_and_header_injection_rollback(self):
        for data, name in (('not bytes', 'a.txt'), (b'123456789', 'a.txt'), (b'a', 'a\r\nInjected: yes'),
                           (b'a', '../secret'), (b'a', 'bad\u202efdp')):
            with self.subTest(data=data, name=name), gateway() as (binary, _, _, model, calls):
                model._mp_binary_download = lambda ident: binary.BinaryContent(data, name)
                self.assertIn(self.download(binary)['status'], (400, 500))
                self.assertIn('rollback', calls)
                self.assertNotIn(('audit', 'allowed'), calls)

    def test_invalid_upload_output_rollback_and_serialization_failure_not_hidden(self):
        with gateway() as (binary, _, _, model, calls):
            model._mp_binary_upload = lambda *args: {'not_saved': True}
            self.assertEqual(self.upload(binary)['status'], 500)
            self.assertIn('rollback', calls)
        for error in (SerializationFailure, DeadlockDetected):
            with gateway() as (binary, _, _, model, calls):
                model._mp_binary_upload = lambda *args: (_ for _ in ()).throw(error())
                with self.assertRaises(error): self.upload(binary)
                self.assertNotIn(('audit', 'allowed'), calls)

    def test_registration_is_explicit_bounded_nonmutable_and_duplicates_refuse(self):
        with gateway() as (binary, _, _, _, _):
            from dataclasses import replace
            endpoint = binary.ENDPOINTS['dev.test.files', 'content']
            with self.assertRaises(ValueError): binary.register_binary('dev.test.files', 'content', endpoint)
            for spec in (replace(endpoint, max_bytes=True), replace(endpoint, max_bytes=binary.MAX_BYTES + 1),
                         replace(endpoint, upload='create'), replace(endpoint, download='_other'), replace(endpoint, model='../../file')):
                with self.assertRaises(ValueError): binary.register_binary('dev.test.other', 'content', spec)
            schema = {'type': 'object'}
            binary.register_binary('dev.test.other', 'content', replace(endpoint, metadata_schema=schema))
            schema['type'] = 'string'
            self.assertEqual(binary.ENDPOINTS['dev.test.other', 'content'].metadata_schema, {'type': 'object'})

    def test_default_json_result_still_validates_original_service_envelope(self):
        with gateway() as (_, ctrl, _, _, _):
            response = ctrl.result(lambda: {'normal': 'json'})
            self.assertEqual(response['status'], 200)
            validate('service-response', response['body'])

    def test_actual_scope_and_two_model_guards_reconstruct_current_authority_before_upload(self):
        # Exercise real resolve_scope + WorkspaceScoped._mp_guard + the core
        # installation override. Only SQL/native model storage is fake here.
        for failure in (None, 'membership', 'inactive_actor', 'viewer', 'feature', 'installation', 'action'):
            with self.subTest(failure=failure), gateway() as (binary, _, req, _, calls):
                try:
                    scopes = load('_binary_scope_test', ROOT / 'framework_addons/mp_identity/scopes.py')
                    workspace = 'b4f50e80-1b1b-43a5-a6b8-565a48828a2f'
                    state = {'failure': failure, 'row': None}
                    def execute(sql, params):
                        calls.append('policy_sql')
                        if 'FROM mp_principal' in sql:
                            state['row'] = None if failure in ('membership', 'inactive_actor') else (
                                2, IDENT, 'human', 3, workspace, 'viewer' if failure == 'viewer' else 'editor', 4)
                        elif 'SELECT availability' in sql:
                            state['row'] = ('suspended' if failure == 'feature' else 'enabled',)
                        elif 'SELECT state' in sql:
                            state['row'] = ('removed' if failure == 'installation' else 'installed',)
                        else: raise AssertionError(sql)
                    req.env.uid = 7
                    req.env.cr.dbname = 'owned_test'
                    req.env.cr.execute = execute
                    req.env.cr.fetchone = lambda: state['row']
                    req.env['mp.plugin.installation'] = types.SimpleNamespace(flush_model=lambda fields: None)
                    scopes._flush_identity_policy = lambda env: None
                    previous = scopes.Scope('owned_test', 7, 2, IDENT, 'human', 3, workspace, 'editor', 4,
                        allowed_actions=frozenset({'read'}) if failure == 'action' else None)
                    namespace = {'AccessError': Denied, 'current_scope': lambda env: scopes.resolve_scope(env, workspace, previous)}
                    for path, name, parent in (
                        ('framework_addons/mp_identity/models/scoped.py', 'WorkspaceScoped', object),
                        ('framework_addons/mp_core/models.py', 'SupportedInstallationGuard', None)):
                        tree = ast.parse((ROOT / path).read_text())
                        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
                        guard = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_mp_guard')
                        namespace['Parent'] = parent or namespace['WorkspaceScoped']
                        selected = ast.Module(body=[ast.ClassDef(name=name, bases=[ast.Name(id='Parent', ctx=ast.Load())],
                            keywords=[], body=[guard], decorator_list=[])], type_ignores=[])
                        exec(compile(ast.fix_missing_locations(selected), 'actual-scoped-guard', 'exec'), namespace)
                    model = namespace['SupportedInstallationGuard']()
                    model.env = req.env; model._origin = types.SimpleNamespace(ids=[])
                    model._mp_scoped = True; model._mp_plugin_id = 'dev.test.files'
                    model._mp_binary_upload = lambda *args: calls.append('authorized_upload') or {'saved': True}
                    req.env['test.file'] = model
                    response = self.upload(binary)
                    self.assertEqual(response['status'], 200 if failure is None else 403)
                    self.assertEqual('body' in calls, failure is None)
                    self.assertEqual('authorized_upload' in calls, failure is None)
                finally:
                    sys.modules.pop('_binary_scope_test', None)


class LegacyBinaryTests(unittest.TestCase):
    def test_actual_managed_hooks_reject_before_token_or_stream_and_unmanaged_still_works(self):
        calls = []
        class Parent:
            def _find_record(self, *args): calls.append(('token_find', args)); return 'unmanaged'
            def _record_to_stream(self, *args): calls.append(('stream', args)); return 'asset'
        models = types.SimpleNamespace(Model=Parent, AbstractModel=Parent)
        native = types.ModuleType('odoo'); native.models = models
        native.api = types.SimpleNamespace(model_create_multi=lambda fn: fn)
        exceptions = types.ModuleType('odoo.exceptions'); exceptions.AccessError = Denied
        with patch.dict(sys.modules, {'odoo': native, 'odoo.exceptions': exceptions}):
            try:
                module = load('_legacy_binary_test', ROOT / 'framework_addons/mp_core/attachments.py')
                scoped = types.SimpleNamespace(_mp_scoped=True)
                class EmptyRecord:
                    _mp_scoped = True
                    def __bool__(self): return False
                class Env(dict):
                    def ref(self, name, unused): return self[name]
                helper = module.WorkspaceBinary(); helper.env = Env({'managed': EmptyRecord(), 'xml.managed': scoped, 'asset': object()})
                for invoke in (lambda: helper._find_record(res_model='managed', res_id=7, access_token='valid'),
                               lambda: helper._find_record(xmlid='xml.managed', access_token='valid'),
                               lambda: helper._record_to_stream(scoped, 'data')):
                    with self.assertRaises(Denied): invoke()
                    self.assertEqual(calls, [])
                self.assertEqual(helper._find_record(res_model='asset', res_id=1), 'unmanaged')
                self.assertEqual(helper._record_to_stream(object(), 'raw'), 'asset')
                self.assertEqual([c[0] for c in calls], ['token_find', 'stream'])
            finally:
                sys.modules.pop('_legacy_binary_test', None)


if __name__ == '__main__': unittest.main()
