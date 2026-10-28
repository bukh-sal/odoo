"""OS-owned approvals and append-oriented journal outside app database restore.

Only the local OS owner may call this store. Callers MUST independently observe
deployment/catalog/trust through the mandatory revalidation callback. No record
from an application queue, role, HTTP body or copied operation ID grants access.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat

from .contracts import check_start_approval, load_json, validate
from .operator_os import OperatorError, OperationLocks, current_identity, protect_directory, verify_private_directory, _not_link
from .plans import check_bundle, data_digest


STEPS = ['reserved', 'staged', 'maintenance', 'drained', 'checkpointed', 'mutation_started',
         'migrated', 'workers_replaced', 'ready', 'release_published', 'traffic_resumed', 'completed']
ACKS = {'destructive', 'trust_expansion', 'permission_expansion'}


def _utc(value=None):
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)


def _stamp(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def _write_new(path, value):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())


class OperatorStore:
    @classmethod
    def initialize(cls, root, deployments, *, maximum_start_lifetime=900, allow_noninteractive=False):
        root = Path(root).absolute()
        if root.exists():
            raise OperatorError('Control store already exists; inspect instead of reinitializing')
        if type(maximum_start_lifetime) is not int or not 1 <= maximum_start_lifetime <= 86400:
            raise OperatorError('Invalid operator-configured approval lifetime')
        if type(allow_noninteractive) is not bool:
            raise OperatorError('Noninteractive approval policy must be explicitly boolean')
        protect_directory(root)
        identity = current_identity()
        policy = {'schema_version': 1, 'owner_identity': identity, 'authorized_operators': [identity],
                  'authorization_generation': 1, 'policy_version': 1,
                  'maximum_start_lifetime': maximum_start_lifetime, 'deployments': deployments}
        policy['allow_noninteractive'] = allow_noninteractive
        _write_new(root / 'policy.json', policy)
        store = cls(root)
        protect_directory(root / 'locks')
        with store._connect() as database:
            database.executescript('''
                CREATE TABLE operations (
                    operation_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, bundle TEXT NOT NULL,
                    approval TEXT, phase TEXT NOT NULL, state TEXT NOT NULL,
                    owner_nonce TEXT, mutation_started INTEGER NOT NULL DEFAULT 0,
                    traffic_resumed INTEGER NOT NULL DEFAULT 0, backup_id TEXT);
                CREATE TABLE events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL,
                    utc TEXT NOT NULL, code TEXT NOT NULL, details TEXT NOT NULL,
                    FOREIGN KEY(operation_id) REFERENCES operations(operation_id));
                CREATE TABLE revocations (
                    operation_id TEXT PRIMARY KEY, utc TEXT NOT NULL, operator_id TEXT NOT NULL,
                    FOREIGN KEY(operation_id) REFERENCES operations(operation_id));
            ''')
        return store

    def __init__(self, root):
        self.root = Path(root).absolute()
        self.database = self.root / 'control.sqlite3'
        self.policy = self._policy()

    def _policy(self):
        identity = verify_private_directory(self.root)
        path = self.root / 'policy.json'
        self._regular(path)
        policy = load_json(path.read_bytes())
        required = {'schema_version', 'owner_identity', 'authorized_operators', 'authorization_generation',
                    'policy_version', 'maximum_start_lifetime', 'deployments', 'allow_noninteractive'}
        if (not isinstance(policy, dict) or set(policy) != required or type(policy['schema_version']) is not int or policy['schema_version'] != 1
                or not isinstance(policy['authorized_operators'], list)
                or identity != policy['owner_identity'] or identity not in policy['authorized_operators']
                or type(policy['authorization_generation']) is not int or policy['authorization_generation'] < 1
                or type(policy['policy_version']) is not int or policy['policy_version'] < 1
                or type(policy['maximum_start_lifetime']) is not int or not 1 <= policy['maximum_start_lifetime'] <= 86400
                or type(policy['allow_noninteractive']) is not bool
                or not isinstance(policy['deployments'], dict)):
            raise OperatorError('OS operator is not authorized by the independently owned allowlist/policy')
        return policy

    def review(self, operation_id, revalidate):
        with self._connect() as database:
            bundle = load_json(self._row(database, operation_id)['bundle'])
        self._authorize_plan(bundle['plan'])
        check_bundle(bundle, revalidate(bundle))
        return {'operation_id': operation_id, 'plan_hash': bundle['plan_hash'],
                'display': bundle['display'], 'approval_lifetime_seconds': self.policy['maximum_start_lifetime']}

    @staticmethod
    def _regular(path):
        _not_link(path)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OperatorError('Control records must be ordinary single-link files')
        if os.name == 'posix' and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise OperatorError('Control record ownership/permissions mismatch')

    @contextmanager
    def _connect(self, *, transaction=False):
        self.policy = self._policy()
        if self.database.exists():
            self._regular(self.database)
        else:
            descriptor = os.open(self.database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        database = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        database.row_factory = sqlite3.Row
        database.execute('PRAGMA foreign_keys=ON')
        database.execute('PRAGMA synchronous=FULL')
        try:
            if transaction:
                database.execute('BEGIN IMMEDIATE')
            yield database
            if transaction:
                database.execute('COMMIT')
        except BaseException:
            if database.in_transaction:
                database.execute('ROLLBACK')
            raise
        finally:
            database.close()

    def _authorize_plan(self, plan, *, generation=True):
        self.policy = self._policy()
        sites = self.policy['deployments'].get(plan['deployment_id'])
        if not isinstance(sites, list) or not set(plan['site_ids']) <= set(sites):
            raise OperatorError('Operation targets are outside the OS operator deployment allowlist')
        if generation and (plan['policy_version'] != self.policy['policy_version'] or plan['operator_authorization_generation'] != self.policy['authorization_generation']):
            raise OperatorError('Policy or independent operator authority generation changed')

    @staticmethod
    def _event(database, operation_id, code, details=None, now=None):
        details = details or {}
        if len(json.dumps(details)) > 65536:
            raise OperatorError('Journal metadata size limit')
        database.execute('INSERT INTO events (operation_id,utc,code,details) VALUES (?,?,?,?)',
                         (operation_id, _stamp(_utc(now)), code, json.dumps(details, sort_keys=True)))

    @staticmethod
    def _row(database, operation_id):
        row = database.execute('SELECT * FROM operations WHERE operation_id=?', (operation_id,)).fetchone()
        if row is None:
            raise OperatorError('Unknown independently registered operation')
        return row

    def register(self, bundle, revalidate):
        self._authorize_plan(bundle['plan'])
        check_bundle(bundle, revalidate(bundle))
        operation_id = bundle['plan']['operation_id']
        with self._connect(transaction=True) as database:
            old = database.execute('SELECT * FROM operations WHERE operation_id=?', (operation_id,)).fetchone()
            encoded = json.dumps(bundle, sort_keys=True)
            if old:
                if old['plan_hash'] != bundle['plan_hash'] or old['bundle'] != encoded:
                    raise OperatorError('Operation identity is already bound to a different immutable plan')
            else:
                database.execute('INSERT INTO operations (operation_id,plan_hash,bundle,phase,state) VALUES (?,?,?,?,?)',
                                 (operation_id, bundle['plan_hash'], encoded, 'prepared', 'awaiting_operator_approval'))
                self._event(database, operation_id, 'prepared', {'plan_hash': bundle['plan_hash']})
        return operation_id

    @staticmethod
    def _check_acks(bundle, acknowledgments):
        if not isinstance(acknowledgments, dict) or set(acknowledgments) != ACKS or any(type(value) is not bool for value in acknowledgments.values()):
            raise OperatorError('Explicit destructive/trust/permission acknowledgments required')
        declarations = bundle['operation_lock']['declaration_changes']
        permission_expansion = any(
            set((item.get('target_permissions') or {}).get('defines', {})) - set((item.get('previous_permissions') or {}).get('defines', {}))
            or any(request not in (item.get('previous_permissions') or {}).get('requests', []) for request in item['target_permissions'].get('requests', []))
            or set(item['target_activation']['scopes']) - set((item.get('previous_activation') or {}).get('scopes', []))
            for item in declarations.values())
        native_change = any(item['runtime'] == 'native' and item['action'] in ('install', 'upgrade') for item in bundle['plan']['artifacts'])
        if native_change and not acknowledgments['trust_expansion'] or permission_expansion and not acknowledgments['permission_expansion']:
            raise OperatorError('New native code or expanded declarations require explicit acknowledgment')

    def approve(self, operation_id, *, exact_hash, acknowledgments, revalidate, now=None, noninteractive=False):
        with self._connect() as database:
            bundle = load_json(self._row(database, operation_id)['bundle'])
        self._authorize_plan(bundle['plan'])
        if noninteractive and self.policy['allow_noninteractive'] is not True:
            raise OperatorError('Noninteractive approval is not enabled by independent operator policy')
        if exact_hash != bundle['plan_hash']:
            raise OperatorError('Exact reviewed plan hash is required')
        check_bundle(bundle, revalidate(bundle))
        self._check_acks(bundle, acknowledgments)
        issued = _utc(now)
        approval = {'schema_version': 1, 'operation_id': operation_id, 'plan_hash': exact_hash,
            'operator_id': current_identity(), 'deployment_id': bundle['plan']['deployment_id'],
            'site_ids': bundle['plan']['site_ids'], 'issued_at': _stamp(issued),
            'expires_at': _stamp(issued + timedelta(seconds=self.policy['maximum_start_lifetime'])),
            'policy_version': self.policy['policy_version'], 'operator_authorization_generation': self.policy['authorization_generation'],
            'acknowledgments': acknowledgments, 'state': 'approved', 'consumed_operation_id': None}
        check_start_approval(bundle['plan'], approval, operator_generation=self.policy['authorization_generation'], now=issued,
                             maximum_lifetime=self.policy['maximum_start_lifetime'])
        with self._connect(transaction=True) as database:
            row = self._row(database, operation_id)
            self._authorize_plan(bundle['plan'])
            if database.execute('SELECT 1 FROM revocations WHERE operation_id=?', (operation_id,)).fetchone():
                raise OperatorError('Independent approval revocation is final for this operation ID')
            if row['approval']:
                existing = load_json(row['approval'])
                if existing['state'] != 'approved':
                    raise OperatorError('Reserved/consumed approval cannot authorize a new start')
                if datetime.fromisoformat(existing['expires_at'].replace('Z', '+00:00')) > issued:
                    return existing  # Idempotent review never silently extends TTL.
            database.execute('UPDATE operations SET approval=?,state=? WHERE operation_id=?',
                             (json.dumps(approval, sort_keys=True), 'approved', operation_id))
            self._event(database, operation_id, 'approved', {'plan_hash': exact_hash}, now=issued)
        return approval

    def revoke(self, operation_id):
        with self._connect(transaction=True) as database:
            row = self._row(database, operation_id)
            self._authorize_plan(load_json(row['bundle'])['plan'], generation=False)
            database.execute('INSERT OR IGNORE INTO revocations (operation_id,utc,operator_id) VALUES (?,?,?)',
                             (operation_id, _stamp(_utc()), current_identity()))
            state = 'recovery_required' if row['mutation_started'] else 'revoked'
            database.execute('UPDATE operations SET state=? WHERE operation_id=?', (state, operation_id))
            self._event(database, operation_id, 'approval_revoked')

    def _lock_identity(self, plan, locks):
        nonces = locks.check()
        expected = ['deployment-' + plan['deployment_id']] + ['site-' + value for value in sorted(plan['site_ids'])]
        if ([lock.name for lock in locks.locks] != expected
                or any(lock.directory.resolve() != (self.root / 'locks').resolve() for lock in locks.locks)):
            raise OperatorError('Process locks do not cover the exact independent store/deployment/sites')
        return data_digest(nonces)

    def _reservation(self, database, operation_id, locks, *, now=None, start=False):
        row = self._row(database, operation_id)
        bundle = load_json(row['bundle'])
        self._authorize_plan(bundle['plan'])
        nonce = self._lock_identity(bundle['plan'], locks)
        if database.execute('SELECT 1 FROM revocations WHERE operation_id=?', (operation_id,)).fetchone():
            raise OperatorError('Independent approval is revoked; stop at a safe boundary and reconcile')
        if row['approval'] is None or row['state'] in ('completed', 'recovery_required', 'failed_before_mutation', 'revoked'):
            raise OperatorError('Operation cannot start or continue without reconciliation')
        approval = load_json(row['approval'])
        validate('approval', approval)
        if approval['plan_hash'] != row['plan_hash'] or approval['operation_id'] != operation_id:
            raise OperatorError('Stored approval identity/hash mismatch')
        if row['mutation_started'] and (approval['state'] != 'reserved' or approval['consumed_operation_id'] != operation_id):
            raise OperatorError('Started operation lost its one-operation approval reservation')
        if not row['mutation_started']:
            starting = {**approval, 'state': 'approved', 'consumed_operation_id': None}
            check_start_approval(bundle['plan'], starting, operator_generation=self.policy['authorization_generation'], now=_utc(now),
                                 maximum_lifetime=self.policy['maximum_start_lifetime'])
        if not start and row['owner_nonce'] != nonce:
            raise OperatorError('Operation reservation is fenced by a different executor lock owner')
        return row, bundle, approval, nonce

    def reserve(self, operation_id, locks: OperationLocks, revalidate, *, now=None):
        with self._connect() as database:
            previous = self._row(database, operation_id)
            bundle = load_json(previous['bundle'])
        if previous['mutation_started']:
            # Do this BEFORE comparing initial state: a native child may already
            # have changed the DB. A stale-state error must not leave UI/journal
            # falsely claiming that a crashed old executor is still running.
            uncertain = False
            with self._connect(transaction=True) as database:
                row = self._row(database, operation_id)
                self._authorize_plan(bundle['plan'], generation=False)
                nonce = self._lock_identity(bundle['plan'], locks)
                if row['state'] == 'completed':
                    raise OperatorError('Completed operation cannot start or continue')
                if row['state'] == 'recovery_required' or row['owner_nonce'] != nonce:
                    if row['state'] != 'recovery_required':
                        database.execute('UPDATE operations SET state=? WHERE operation_id=?', ('recovery_required', operation_id))
                        self._event(database, operation_id, 'executor_lost_after_possible_mutation')
                    uncertain = True
                else:
                    self._reservation(database, operation_id, locks, now=now, start=True)
            if uncertain:
                raise OperatorError('Previous executor may have committed or still have a native child; recovery_required')
            return self.status(operation_id)
        check_bundle(bundle, revalidate(bundle))
        uncertain = False
        with self._connect(transaction=True) as database:
            row, bundle, approval, nonce = self._reservation(database, operation_id, locks, now=now, start=True)
            if row['mutation_started'] and row['owner_nonce'] != nonce:
                database.execute('UPDATE operations SET state=? WHERE operation_id=?', ('recovery_required', operation_id))
                self._event(database, operation_id, 'executor_lost_after_possible_mutation')
                uncertain = True
            else:
                approval.update(state='reserved', consumed_operation_id=operation_id)
                phase = 'reserved' if row['phase'] == 'prepared' else row['phase']
                database.execute('UPDATE operations SET approval=?,state=?,phase=?,owner_nonce=? WHERE operation_id=?',
                    (json.dumps(approval, sort_keys=True), 'running', phase, nonce, operation_id))
                self._event(database, operation_id, 'reserved' if row['owner_nonce'] is None else 'resumed_before_mutation',
                            {'executor_pid': os.getpid(), 'lock_owner_digest': nonce}, now=now)
        if uncertain:
            raise OperatorError('Previous executor may have committed or still have a native child; recovery_required')
        return self.status(operation_id)

    def advance(self, operation_id, locks, phase, *, backup_id=None):
        if phase not in STEPS or phase in ('reserved', 'mutation_started'):
            raise OperatorError('Invalid journal step; mutation needs its dedicated authority check')
        with self._connect(transaction=True) as database:
            row, bundle, approval, nonce = self._reservation(database, operation_id, locks)
            steps = STEPS if bundle['plan']['backup']['required'] else [value for value in STEPS if value != 'checkpointed']
            if steps.index(phase) != steps.index(row['phase']) + 1:
                raise OperatorError('Journal steps cannot be skipped, repeated or rewound')
            if phase == 'checkpointed' and (not isinstance(backup_id, str) or not backup_id or len(backup_id) > 200):
                raise OperatorError('Coordinated backup identity required before native mutation')
            database.execute('UPDATE operations SET phase=?,backup_id=COALESCE(?,backup_id),traffic_resumed=? WHERE operation_id=?',
                             (phase, backup_id, int(row['traffic_resumed'] or phase == 'traffic_resumed'), operation_id))
            if phase == 'completed':
                approval['state'] = 'consumed'
                database.execute('UPDATE operations SET approval=?,state=? WHERE operation_id=?', (json.dumps(approval, sort_keys=True), 'completed', operation_id))
            self._event(database, operation_id, phase, {'backup_id': backup_id} if backup_id else {})

    def before_mutation(self, operation_id, locks, revalidate, *, now=None):
        with self._connect() as database:
            bundle = load_json(self._row(database, operation_id)['bundle'])
        check_bundle(bundle, revalidate(bundle))
        with self._connect(transaction=True) as database:
            row, bundle, approval, nonce = self._reservation(database, operation_id, locks, now=now)
            expected = 'checkpointed' if bundle['plan']['backup']['required'] else 'drained'
            if row['phase'] != expected or row['mutation_started']:
                raise OperatorError('Mutation requires a drained/checkpointed operation and one reservation')
            database.execute('UPDATE operations SET mutation_started=1,phase=? WHERE operation_id=?', ('mutation_started', operation_id))
            self._event(database, operation_id, 'mutation_started', now=now)
        # This durable record precedes launching ANY native mutating child. If the
        # parent dies, a new lock owner cannot infer that the child also stopped.

    def fail(self, operation_id, locks, *, code):
        if code not in ('STAGING_FAILED', 'DRAIN_FAILED', 'BACKUP_FAILED', 'MUTATION_FAILED', 'READINESS_FAILED', 'LOCK_LOST'):
            raise OperatorError('Bounded redacted failure code required')
        locks.check()
        with self._connect(transaction=True) as database:
            row = self._row(database, operation_id)
            if row['owner_nonce'] != data_digest(locks.check()):
                raise OperatorError('Failure report is fenced by another executor')
            state = 'recovery_required' if row['mutation_started'] else 'failed_before_mutation'
            database.execute('UPDATE operations SET state=? WHERE operation_id=?', (state, operation_id))
            self._event(database, operation_id, state, {'code': code})

    def status(self, operation_id):
        with self._connect() as database:
            row = self._row(database, operation_id)
            bundle = load_json(row['bundle'])
            self._authorize_plan(bundle['plan'], generation=False)
            events = database.execute('SELECT sequence,utc,code,details FROM events WHERE operation_id=? ORDER BY sequence', (operation_id,)).fetchall()
            approval = load_json(row['approval']) if row['approval'] else None
            effective = row['state']
            if effective in ('approved', 'running') and not row['mutation_started'] and approval:
                if approval['operator_authorization_generation'] != self.policy['authorization_generation'] or approval['policy_version'] != self.policy['policy_version']:
                    effective = 'authorization_changed'
                elif _utc() >= datetime.fromisoformat(approval['expires_at'].replace('Z', '+00:00')):
                    effective = 'expired'
            return {'operation_id': operation_id, 'plan_hash': row['plan_hash'], 'state': effective,
                    'phase': row['phase'], 'mutation_started': bool(row['mutation_started']),
                    'traffic_resumed': bool(row['traffic_resumed']), 'backup_id': row['backup_id'],
                    'approval_expires_at': approval['expires_at'] if approval else None,
                    'history': [{'sequence': event['sequence'], 'utc': event['utc'], 'code': event['code'],
                                 'details': load_json(event['details'])} for event in events]}
