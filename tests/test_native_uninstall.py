"""Fixed native-uninstall routing, runtime compatibility and ready-state guards.

These do not simulate a successful native uninstall. Actual schema effects and
recovery remain mandatory disposable-fixture integration checks.
"""
import copy
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
sys.path.insert(0, str(ROOT / 'tests'))
from modular_platform.native_executor import (native_maintenance_flags, require_native_uninstall_runtime,
                                              verify_native_state)
from modular_platform.native_uninstall import require_exact_native_closure
from modular_platform.operator_os import OperatorError
from test_plans import ident


class NativeUninstallGuards(unittest.TestCase):
    def setUp(self):
        self.prior = dict(installation_id=ident(100), site_id=ident(20), workspace_id=ident(30), plugin_id='org.example.notes_labels',
                          state='installed', feature_state='enabled', metadata_state='installed')
        self.target = {k: v for k, v in self.prior.items() if k in ('installation_id', 'site_id', 'workspace_id', 'plugin_id')} | {'action': 'uninstall'}
        self.bundle = dict(plan=dict(operation_type='uninstall', destructive=True, backup={'required': True},
            target_release_digest='sha256:'+'a'*64, permission_changes=[dict(plugin_id=self.prior['plugin_id'],
                workspace_id=ident(30), capability='org.example.notes:notes.read', action='revoke')], policy_version=1),
            operation_lock=dict(targets=[self.target], native_uninstall_impact={'known': 'only'}, bindings=[]))

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
