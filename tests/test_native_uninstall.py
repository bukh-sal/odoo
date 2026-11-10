"""Fixed native-uninstall routing, runtime compatibility and ready-state guards.

These do not simulate a successful native uninstall. Actual schema effects and
recovery remain mandatory disposable-fixture integration checks.
"""
import copy
import hashlib
import inspect
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.native_executor import (NativeExecutor, native_maintenance_flags, require_native_uninstall_runtime,
                                              verify_native_state)
from modular_platform.native_feature_executor import NativeFeatureExecutor
from modular_platform.native_uninstall import require_exact_native_closure
from modular_platform.native_uninstall import require_dispatch_snapshot
from modular_platform.plans import data_digest
from unittest.mock import MagicMock, patch
from modular_platform.operator_os import OperatorError
from test_plans import ident


class NativeUninstallGuards(unittest.TestCase):
    def test_closed_checkpoint_required_and_exact_across_native_commit(self):
        scope = dict(site_id=ident(20), release_digest='sha256:'+'a'*64, reference=None)
        base = dict(profile='r1-native-dispatch-v1', control=dict(state='paused', generation=3),
                    tables={'mp_job': dict(rows=1, sha256='1'*64)}, external_installations=0,
                    active_credentials=0, api_keys=0, uncertain_jobs=0)
        expected = base | dict(state_digest=data_digest(base))
        connection = MagicMock()
        with patch('modular_platform.dispatch_lifecycle.observe', return_value=expected):
            self.assertEqual(require_dispatch_snapshot(connection, expected, scope), expected)
        for field, value in [('control', dict(state='enabled', generation=3)), ('active_credentials', 1),
                             ('api_keys', 1), ('uncertain_jobs', 1), ('external_installations', 1)]:
            bad = base | {field: value}
            bad['state_digest'] = data_digest(bad)
            with patch('modular_platform.dispatch_lifecycle.observe', return_value=bad):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    require_dispatch_snapshot(connection, bad, scope)
        changed = copy.deepcopy(expected)
        changed['tables']['mp_job']['sha256'] = '2'*64
        with patch('modular_platform.dispatch_lifecycle.observe', return_value=changed):
            with self.assertRaises(ValueError): require_dispatch_snapshot(connection, expected, scope)
        self.assertIsNone(require_dispatch_snapshot(connection, None, None))
        with self.assertRaises(ValueError): require_dispatch_snapshot(connection, expected, None)

    def test_reference_checkpoint_needs_exact_known_registration_and_no_unknown_effects(self):
        scope = dict(site_id=ident(20), release_digest='sha256:'+'a'*64,
                     reference=dict(registrations=[dict(installation_id=ident(100))]))
        body = dict(profile='r1-reference-stateless-dispatch-v1', control=dict(state='paused', generation=3),
                    external_installations=1, active_credentials=0, api_keys=0, uncertain_jobs=0)
        expected = body | dict(state_digest=data_digest(body))
        with patch('modular_platform.dispatch_lifecycle.observe', return_value=expected):
            self.assertEqual(require_dispatch_snapshot(MagicMock(), expected, scope), expected)
            with self.assertRaises(ValueError):
                require_dispatch_snapshot(MagicMock(), expected, scope | dict(reference=None))

    def setUp(self):
        self.prior = dict(installation_id=ident(100), site_id=ident(20), workspace_id=ident(30), plugin_id='org.example.notes_labels',
                          state='installed', feature_state='enabled', metadata_state='installed')
        self.target = {k: v for k, v in self.prior.items() if k in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')} | {'action': 'uninstall'}
        self.bundle = dict(plan=dict(operation_type='uninstall', destructive=True, backup={'required': True},
            target_release_digest='sha256:'+'a'*64, permission_changes=[dict(plugin_id=self.prior['plugin_id'],
                workspace_id=ident(30), capability='org.example.notes:notes.read', action='revoke')], policy_version=1),
            operation_lock=dict(targets=[self.target], native_uninstall_impact={'known': 'only'}, bindings=[]))

    def test_checkpoint_dispatch_scope_is_exact_and_rejects_malformed_private_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'control'
            checkpoint = root / 'checkpoints' / 'op'
            checkpoint.mkdir(parents=True)
            snapshot = {'profile': 'r1-reference-stateless-dispatch-v1', 'release_digest': 'sha256:' + 'a' * 64,
                        'state_digest': 'sha256:' + 'b' * 64}
            reference = {'registrations': []}
            (checkpoint / 'manifest.json').write_text(json.dumps(dict(
                previous_release={}, dispatch_profile=snapshot, reference_policy=reference)))
            executor = object.__new__(NativeExecutor)
            executor.store = SimpleNamespace(root=root)
            executor.config = {'sites': [{'site_id': ident(20)}]}
            actual_snapshot, actual_scope = executor._checkpoint_dispatch_scope('op')
            self.assertEqual(actual_snapshot, snapshot)
            self.assertEqual(actual_scope, {'site_id': ident(20),
                                            'release_digest': snapshot['release_digest'],
                                            'reference': reference})
            (checkpoint / 'manifest.json').write_text(json.dumps(dict(
                previous_release={}, reference_policy=reference)))
            with self.assertRaisesRegex(OperatorError, 'reference policy'):
                executor._checkpoint_dispatch_scope('op')
            (checkpoint / 'manifest.json').write_text(json.dumps(dict(
                previous_release={}, dispatch_profile={'profile': 'malformed'})))
            with self.assertRaisesRegex(OperatorError, 'malformed'):
                executor._checkpoint_dispatch_scope('op')

    def test_old_or_different_metadata_reader_refuses_before_reserve_or_drain(self):
        executor = object.__new__(NativeExecutor)
        executor.staged_execution = False
        bundle = copy.deepcopy(self.bundle)
        bundle['plan']['artifacts'] = [{'runtime': 'native', 'action': 'uninstall'}]
        bundle['plan']['deployment_id'] = ident(10)
        bundle['plan']['site_ids'] = [ident(20)]
        executor.store = MagicMock()
        executor.store.bundle.return_value = bundle
        executor.store.status.return_value = {'state': 'awaiting_operator_approval', 'mutation_started': False}
        executor.observer = MagicMock()
        executor.observer.read.return_value = {'runtime': {'published_release_protocol': 1,
                                                           'inventory': {'files': {}}}}
        executor._require_jobs_drained = MagicMock()
        with patch('modular_platform.native_executor.OperationLocks', return_value=nullcontext('locks')):
            with self.assertRaisesRegex(OperatorError, 'compatible maintenance image'):
                executor.apply('op')
        executor.store.reserve.assert_not_called()
        executor._require_jobs_drained.assert_not_called()

    def test_metadata_publisher_enriches_only_uninstall_from_actual_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'control'
            checkpoint = root / 'checkpoints' / 'op'
            checkpoint.mkdir(parents=True)
            snapshot = {'profile': 'r1-reference-stateless-dispatch-v1',
                        'release_digest': 'sha256:' + 'a' * 64,
                        'state_digest': 'sha256:' + 'b' * 64}
            reference = {'registrations': []}
            (checkpoint / 'manifest.json').write_text(json.dumps(dict(
                previous_release={}, dispatch_profile=snapshot, reference_policy=reference)))
            executor = object.__new__(NativeExecutor)
            executor.store = SimpleNamespace(root=root)
            executor.config = {'sites': [{'site_id': ident(20)}]}
            executor._child = MagicMock(return_value=(['python', '-B', 'child'], 'cid'))
            executor._private_command = MagicMock()
            directory = Path(folder) / 'stage'
            directory.mkdir()
            payload = {'site_id': ident(20), 'operation_id': 'op'}
            uninstall = {'plan': {'operation_type': 'uninstall', 'operation_id': 'op'}}
            executor._publish_metadata(uninstall, payload, directory, 'image')
            sent = json.loads(executor._private_command.call_args.kwargs['input'])
            self.assertEqual(sent['dispatch_snapshot'], snapshot)
            self.assertEqual(sent['dispatch_scope'], {'site_id': ident(20),
                                                       'release_digest': snapshot['release_digest'],
                                                       'reference': reference})
            executor._private_command.reset_mock()
            install = {'plan': {'operation_type': 'install', 'operation_id': 'missing-op'}}
            executor._publish_metadata(install, payload, directory, 'image')
            self.assertEqual(json.loads(executor._private_command.call_args.kwargs['input']), payload)
            executor._private_command.reset_mock()
            missing = {'plan': {'operation_type': 'uninstall', 'operation_id': 'missing-op'}}
            with self.assertRaises(OperatorError):
                executor._publish_metadata(missing, payload, directory, 'image')
            executor._private_command.assert_not_called()

    def test_metadata_publisher_hook_keeps_four_argument_virtual_protocol(self):
        for cls in (NativeExecutor, ReferenceMetadataExecutor, NativeFeatureExecutor):
            with self.subTest(cls=cls.__name__):
                signature = inspect.signature(cls._publish_metadata)
                signature.bind(object(), {}, {}, Path('.'), 'image')
                self.assertNotIn('checkpoint', signature.parameters)

    def test_actual_upstream_closure_must_equal_the_approved_native_set(self):
        require_exact_native_closure(['notes', 'labels'], {'labels', 'notes'})
        for approved, actual in (([], set()), (['notes', 'notes'], {'notes'}), (['notes'], {'notes', 'labels'}),
                                 (['notes', 'labels'], {'notes'})):
            with self.subTest(approved=approved, actual=actual), self.assertRaises(ValueError):
                require_exact_native_closure(approved, actual)

    def test_uninstall_uses_only_fixed_child_and_never_i_u_or_core_maintenance(self):
        self.assertIsNone(native_maintenance_flags(self.bundle, {}))
        for field in ('destructive', 'backup', 'impact', 'core', 'stage'):
            bundle = copy.deepcopy(self.bundle)
            if field == 'destructive': bundle['plan']['destructive'] = False
            elif field == 'backup': bundle['plan']['backup']['required'] = False
            elif field == 'impact': bundle['operation_lock'].pop('native_uninstall_impact')
            elif field == 'core': bundle['operation_lock']['native_core_changes'] = []
            else: bundle['operation_lock']['staged_image'] = {}
            with self.subTest(field=field), self.assertRaises(OperatorError): native_maintenance_flags(bundle, {})

    def test_maintenance_source_and_schema_must_match_the_approved_image(self):
        names = ['packages/platform_sdk/modular_platform/' + name for name in ('lifecycle_impact.py', 'native_uninstall.py', 'uninstall_metadata.py')]
        names += ['packages/contracts/v1/lifecycle-impact.schema.json']
        files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
        require_native_uninstall_runtime({'inventory': {'files': files}})
        with self.assertRaises(OperatorError): require_native_uninstall_runtime({'inventory': {'files': {}}})
        for name in names:
            changed = dict(files); changed[name] = 'f'*64
            with self.subTest(name=name), self.assertRaises(OperatorError):
                require_native_uninstall_runtime({'inventory': {'files': changed}})

    def test_ready_uninstall_requires_stable_suspended_tombstone_and_revoked_grants(self):
        state = dict(release_digest=self.bundle['plan']['target_release_digest'], bindings=[], installations=[
            self.prior | dict(state='not_installed', feature_state='suspended', metadata_state='removed')])
        grant = dict(workspace_id=ident(30), installation_id=ident(100), capability='org.example.notes:notes.read', state='revoked', policy_version=1)
        observation = {'sites': [dict(site_id=ident(20), grants=[grant])]}
        verify_native_state(self.bundle, state, {'installations': [self.prior]}, observation)
        for field, value in (('metadata_state', 'installed'), ('feature_state', 'enabled'), ('state', 'installed'), ('installation_id', ident(999))):
            altered = copy.deepcopy(state); altered['installations'][0][field] = value
            with self.subTest(field=field), self.assertRaises(OperatorError):
                verify_native_state(self.bundle, altered, {'installations': [self.prior]}, observation)
        grant['state'] = 'approved'
        with self.assertRaises(OperatorError): verify_native_state(self.bundle, state, {'installations': [self.prior]}, observation)


if __name__ == '__main__': unittest.main()
