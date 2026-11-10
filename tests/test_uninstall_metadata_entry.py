"""Actual uninstall_metadata entry with a source-consistent closed checkpoint."""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'packages/platform_sdk'), str(ROOT / 'tests')]
import modular_platform.dispatch_lifecycle as dispatch_lifecycle
from modular_platform.native_uninstall import require_dispatch_snapshot
from modular_platform.plans import data_digest

_spec = importlib.util.spec_from_file_location(
    'uninstall_metadata_entry_under_test', ROOT / 'packages/platform_sdk/modular_platform/uninstall_metadata.py')
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)

OLD = 'sha256:' + '1' * 64
NEW = 'sha256:' + '2' * 64


def make_snapshot(release):
    body = {'profile': 'r1-native-dispatch-v1', 'site_id': 'site', 'release_digest': release,
            'control': {'site_id': 'site', 'release_digest': release, 'state': 'paused', 'generation': 14},
            'active_credentials': 0, 'api_keys': 0, 'uncertain_jobs': 0, 'external_installations': 0}
    return body | {'state_digest': data_digest(body)}


def payload(snapshot=None, scope=None, release=NEW):
    return {
        'site_id': 'site', 'deployment_id': 'deployment', 'operation_id': 'op',
        'generation': 2, 'release_digest': release,
        'targets': [
            {'action': 'uninstall', 'site_id': 'site', 'plugin_id': 'org.example.notes_stats',
             'installation_id': 'inst-public', 'workspace_id': 'wsA'},
            {'action': 'uninstall', 'site_id': 'site', 'plugin_id': 'org.example.notes_stats',
             'installation_id': 'inst-public', 'workspace_id': 'wsB'},
        ],
        'plugins': {'org.example.notes_stats': {
            'digest': 'sha256:' + 'b' * 64,
            'manifest': {'plugin': {'version': '0.1.3'},
                         'runtime': {'kind': 'native', 'addon_name': 'mp_example_notes_stats'}},
        }},
        'bindings': [{'binding_id': 'survivor', 'provider_installation_id': 'other'}],
        'permission_changes': [
            {'plugin_id': 'org.example.notes_stats', 'workspace_id': 'wsA', 'capability': 'cap', 'action': 'revoke'},
            {'plugin_id': 'org.example.notes_stats', 'workspace_id': 'wsB', 'capability': 'cap', 'action': 'revoke'},
        ],
        'previous_plugins': {}, 'database': 'db', 'policy_version': 1,
        'dispatch_snapshot': snapshot, 'dispatch_scope': scope,
    }


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.owner.sql.append(sql.strip())
        self.owner.writes.append((sql.strip(), params))
        self.owner.events.append(('sql', sql.strip()))
        if 'INSERT INTO ir_config_parameter' in sql and params and params[0] == 'mp.release_digest':
            self.owner.release_digest = params[1]
        self.owner.last = (sql, params)
    def fetchone(self):
        sql, params = self.owner.last
        if 'ir_config_parameter' in sql:
            return (self.owner.identity[params[0]],)
        if 'ir_module_module' in sql:
            return ('uninstalled',)
        if 'mp_plugin_installation' in sql:
            return (1, 'inst-public', '0.1.3', 'sha256:' + 'b' * 64, 'installed')
        if 'to_regclass' in sql:
            return self.owner.tables
        return None
    def fetchall(self):
        sql, _ = self.owner.last
        if 'mp_workspace_plugin' in sql:
            return [('wsA', 1, 'org.example.notes_stats'), ('wsB', 2, 'org.example.notes_stats')]
        if 'mp_plugin_grant' in sql:
            return [('wsA', 'cap'), ('wsB', 'cap')]
        if 'mp_service_binding' in sql:
            return [(101, 1, {'binding_id': 'target', 'provider_installation_id': 'inst-public'}),
                    (102, 2, {'binding_id': 'survivor', 'provider_installation_id': 'other'})]
        return []


class FakeConnection:
    def __init__(self, tables=(None, None)):
        self.sql, self.writes, self.tables, self.last = [], [], tables, None
        self.events = []
        self.release_digest = OLD
        self.identity = {'mp.site_id': 'site', 'mp.deployment_id': 'deployment'}
        self.committed = self.rolled_back = self.closed = False
    def cursor(self): return FakeCursor(self)
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.committed = True
            self.events.append(('commit', None))
        else:
            self.rolled_back = True
            self.events.append(('rollback', None))
        return False
    def close(self): self.closed = True


class FakeConfigParser:
    def read(self, path): return None
    def __getitem__(self, key):
        return FakeOptions()


class FakeOptions(dict):
    def __init__(self):
        super().__init__({'db_name': 'db', 'db_host': 'db', 'db_port': '5432',
                          'db_user': 'u', 'db_password': 'p'})
    def getint(self, key):
        return int(self[key])


class UninstallMetadataEntry(unittest.TestCase):
    def run_main(self, data, *, tables=(None, None), observe_side_effect=None):
        connection = FakeConnection(tables)
        observe_calls = []
        if observe_side_effect is None:
            def observe(cursor, scope):
                observe_calls.append(scope)
                connection.events.append(('observe', scope.release_digest))
                if scope.release_digest != connection.release_digest:
                    raise ValueError('Lifecycle site or published release changed')
                return make_snapshot(scope.release_digest)
        else:
            iterator = iter(observe_side_effect)
            def observe(cursor, scope):
                observe_calls.append(scope)
                connection.events.append(('observe', scope.release_digest))
                value = next(iterator)
                if isinstance(value, Exception):
                    raise value
                return value
        psycopg2 = Mock()
        psycopg2.connect.return_value = connection
        out = io.StringIO()
        fake_path = lambda value: Mock(read_bytes=lambda: b'{"files":{}}')
        with patch.object(sys, 'stdin', io.StringIO(json.dumps(data))), \
             patch.dict(sys.modules, {'psycopg2': psycopg2}), \
             patch.object(module, 'configparser', Mock(ConfigParser=lambda: FakeConfigParser())), \
             patch.object(module, 'Path', fake_path), \
             patch.object(dispatch_lifecycle, 'observe', side_effect=observe), \
             contextlib.redirect_stdout(out):
            try:
                module.main()
                error = None
            except Exception as exc:
                error = exc
        return connection, observe_calls, out.getvalue(), error

    def test_populated_closed_profile_uses_actual_helper_and_release_mutation_before_commit(self):
        snapshot = make_snapshot(OLD)
        scope = {'site_id': 'site', 'release_digest': OLD, 'reference': None}
        connection, observe_calls, output, error = self.run_main(payload(snapshot, scope))
        self.assertIsNone(error)
        self.assertEqual(connection.release_digest, NEW)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertEqual([scope.release_digest for scope in observe_calls], [OLD, OLD])
        event_names = [event[0] for event in connection.events]
        self.assertEqual(event_names[0], 'observe')
        self.assertEqual(event_names[-1], 'commit')
        observe_indices = [i for i, event in enumerate(connection.events) if event[0] == 'observe']
        release_writes = [i for i, event in enumerate(connection.events)
                          if event[0] == 'sql' and 'INSERT INTO ir_config_parameter' in event[1]]
        mutations = [i for i, event in enumerate(connection.events)
                     if event[0] == 'sql' and event[1].startswith(('DELETE', 'UPDATE'))]
        self.assertEqual(len(observe_indices), 2)
        self.assertTrue(all(observe_indices[0] < i < observe_indices[1] for i in mutations))
        self.assertTrue(release_writes and all(i > observe_indices[1] for i in release_writes))
        self.assertGreater(event_names.index('commit'), max(release_writes))
        self.assertIn('DELETE FROM mp_service_binding', '\n'.join(connection.sql))
        self.assertIn("UPDATE mp_plugin_grant SET state='revoked'", '\n'.join(connection.sql))
        self.assertIn("UPDATE mp_workspace_plugin SET availability='suspended'", '\n'.join(connection.sql))
        self.assertIn("UPDATE mp_plugin_installation SET state='removed'", '\n'.join(connection.sql))
        self.assertEqual(json.loads(output)['metadata_published'], True)

    def test_postrelease_legacy_order_provably_refuses_actual_helper(self):
        connection = FakeConnection()
        snapshot = make_snapshot(OLD)
        scope = {'site_id': 'site', 'release_digest': OLD, 'reference': None}
        def observe(cursor, actual_scope):
            if actual_scope.release_digest != connection.release_digest:
                raise ValueError('Lifecycle site or published release changed')
            return make_snapshot(actual_scope.release_digest)
        with patch.object(dispatch_lifecycle, 'observe', side_effect=observe):
            require_dispatch_snapshot(connection, snapshot, scope)
            connection.release_digest = NEW
            with self.assertRaisesRegex(ValueError, 'published release changed'):
                require_dispatch_snapshot(connection, snapshot, scope)

    def test_no_dispatch_path_proves_absence_and_still_commits(self):
        connection, observe_calls, output, error = self.run_main(payload(None, None))
        self.assertIsNone(error)
        self.assertEqual(observe_calls, [])
        self.assertIn('to_regclass', '\n'.join(connection.sql))
        self.assertTrue(connection.committed)
        self.assertEqual(json.loads(output)['metadata_published'], True)

    def test_missing_null_partial_and_populated_no_dispatch_refuse_before_dml(self):
        for data, tables in (
            ({k: v for k, v in payload(None, None).items() if k not in ('dispatch_snapshot', 'dispatch_scope')}, (None, None)),
            (payload({'profile': 'known'}, {'site_id': 'site'}), (None, None)),
            (payload(None, None), ('mp_job', 'mp_outbox')),
        ):
            connection, observe_calls, output, error = self.run_main(data, tables=tables)
            self.assertIsNotNone(error)
            self.assertFalse(any(sql.startswith(('DELETE', 'UPDATE', 'INSERT')) for sql in connection.sql))
            self.assertFalse(connection.committed)
            self.assertEqual(output, '')

    def test_stale_foreign_open_or_uncertain_profile_refuses_before_dml(self):
        data = payload({'profile': 'known'}, {'site_id': 'site', 'release_digest': OLD, 'reference': None})
        for message in ('closed reconciled dispatch differs', 'foreign release', 'open control', 'uncertain work'):
            connection, observe_calls, output, error = self.run_main(
                data, observe_side_effect=[ValueError(message)])
            self.assertIsNotNone(error)
            self.assertIn(message, str(error))
            self.assertEqual(connection.sql, [])
            self.assertFalse(connection.committed)
            self.assertEqual(output, '')

    def test_postwrite_snapshot_failure_rolls_back_without_release_publication(self):
        snapshot = make_snapshot(OLD)
        scope = {'site_id': 'site', 'release_digest': OLD, 'reference': None}
        connection, observe_calls, output, error = self.run_main(
            payload(snapshot, scope), observe_side_effect=[snapshot, ValueError('stale queue hash')])
        self.assertIsNotNone(error)
        self.assertIn('stale queue hash', str(error))
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertIn('DELETE FROM mp_service_binding', '\n'.join(connection.sql))
        self.assertFalse(any('INSERT INTO ir_config_parameter' in sql for sql in connection.sql))
        self.assertEqual(output, '')

    def test_full_private_fields_are_bound_to_the_actual_dispatch_scope(self):
        snapshot = make_snapshot(OLD)
        scope = {'site_id': 'site', 'release_digest': OLD, 'reference': None}
        connection, observe_calls, output, error = self.run_main(payload(snapshot, scope))
        self.assertIsNone(error)
        self.assertEqual(len(observe_calls), 2)
        self.assertEqual(observe_calls[0].site_id, 'site')
        self.assertEqual(observe_calls[0].release_digest, OLD)
        self.assertIsNone(observe_calls[0].reference)
        config_params = [params for sql, params in connection.writes if 'INSERT INTO ir_config_parameter' in sql]
        self.assertTrue(any(params[0] == 'mp.last_operation_id' for params in config_params))
        self.assertEqual(json.loads(output)['operation_id'], 'op')


if __name__ == '__main__':
    unittest.main()
