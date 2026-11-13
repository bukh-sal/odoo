"""Separate OS recovery history; the completed source operation is immutable.

This records reviewed command intent/completion, not proof a Docker command ran.
Executors must independently verify physical effects before completing a step.
No intent alone authorizes repetition or proves a process is alive.
"""
from datetime import datetime, timezone
from uuid import UUID

from .contracts import load_json
from .operator_os import OperatorError, current_identity, protect_directory, verify_private_directory
from .operator_store import _write_new
from .plans import data_digest
from .recovery_reviews import RecoveryReviews


STEPS = ('traffic_closed', 'dispatch_fenced', 'workers_drained', 'source_verified',
         'target_created', 'checkpoint_loaded', 'authority_applied', 'restore_verified',
         'resume_started', 'resumed')
ACTIONS = frozenset({'restore_completed_checkpoint', 'continue_completed_checkpoint', 'resume_completed_checkpoint'})


def canonical_id(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise OperatorError('Canonical checkpoint recovery identity required') from None
    return value


class CheckpointRecoveryJournal:
    def __init__(self, store, recovery_id):
        self.store = store
        self.recovery_id = canonical_id(recovery_id)
        self.root = store.root/'checkpoint-restores'/self.recovery_id

    def _read(self, path):
        self.store._regular(path)
        return load_json(path.read_bytes())

    def _source(self, source_id):
        canonical_id(source_id)
        if source_id == self.recovery_id:
            raise OperatorError('Checkpoint recovery needs a new identity')
        bundle = self.store.bundle(source_id)
        self.store._authorize_plan(bundle['plan'], generation=False)
        status = self.store.status(source_id)
        if (status['state'] != 'completed' or status['phase'] != 'completed'
                or status['backup_id'] != source_id or status['traffic_resumed'] is not True
                or not bundle['plan']['backup']['required']):
            raise OperatorError('An immutable completed operation with its own checkpoint is required')
        return bundle, status

    def _review(self, decision, exact_hash, *, start=False):
        if (decision.get('action') not in ACTIONS or decision.get('operation_id') != self.recovery_id
                or data_digest(decision) != exact_hash):
            raise OperatorError('Exact independent checkpoint recovery review required')
        source = canonical_id(decision.get('checkpoint_operation_id'))
        bundle, status = self._source(source)
        if (decision.get('source_bundle_digest') != data_digest(bundle)
                or decision.get('source_operation_digest') != data_digest(status)
                or decision.get('plan_hash') != bundle['plan_hash']):
            raise OperatorError('Completed source operation or bundle changed')
        reviews = RecoveryReviews(self.store)
        if start:
            payload = dict(decision); payload.pop('review', None)
            # The executor separately supplies/rechecks the independently observed
            # current deployment payload. This additionally checks journal start TTL.
            reviews.verify(decision, exact_hash=exact_hash, current_payload=payload)
        else:
            reviews.check_reserved(decision, exact_hash=exact_hash)
        return bundle, status

    def create(self, decision, *, exact_hash, locks):
        if decision.get('action') != 'restore_completed_checkpoint':
            raise OperatorError('A fresh completed-checkpoint restore review is required')
        bundle, source = self._review(decision, exact_hash, start=True)
        owner = self.store._lock_identity(bundle['plan'], locks)
        parent = protect_directory(self.root.parent)
        if self.root.exists() or self.root.is_symlink():
            raise OperatorError('Checkpoint recovery already attempted; inspect without replay')
        # The existing helper creates/protects a fresh Windows directory before
        # writing data. Hand-created mode0700 directories have a different ACL.
        # Site/deployment locks and the exclusive binding write fence callers.
        protect_directory(self.root)
        protect_directory(self.root/'journal')
        binding = dict(schema_version=1, recovery_id=self.recovery_id,
            checkpoint_operation_id=decision['checkpoint_operation_id'],
            source_operation_digest=data_digest(source), source_bundle_digest=data_digest(bundle),
            decision=decision, decision_hash=exact_hash, operator_identity=current_identity(),
            initial_lock=owner, started_at=datetime.now(timezone.utc).isoformat())
        _write_new(parent/self.recovery_id/'binding.json', binding)
        return self.status()

    def status(self):
        verify_private_directory(self.root.parent)
        verify_private_directory(self.root)
        verify_private_directory(self.root/'journal')
        binding = self._read(self.root/'binding.json')
        required = {'schema_version','recovery_id','checkpoint_operation_id','source_operation_digest',
                    'source_bundle_digest','decision','decision_hash','operator_identity','initial_lock','started_at'}
        if (not isinstance(binding,dict) or set(binding) != required or type(binding['schema_version']) is not int or binding['schema_version'] != 1
                or binding['recovery_id'] != self.recovery_id or binding['operator_identity'] != current_identity()
                or data_digest(binding['decision']) != binding['decision_hash']):
            raise OperatorError('Checkpoint recovery binding changed')
        decision = binding['decision']
        RecoveryReviews(self.store)._record(decision, binding['decision_hash'])
        if (decision.get('operation_id') != self.recovery_id or decision.get('action') != 'restore_completed_checkpoint'
                or any(binding[key] != decision.get(key) for key in (
                    'checkpoint_operation_id','source_operation_digest','source_bundle_digest'))):
            raise OperatorError('Checkpoint recovery binding differs from its original reviewed source')
        bundle, source = self._source(binding['checkpoint_operation_id'])
        if (data_digest(source) != binding['source_operation_digest']
                or data_digest(bundle) != binding['source_bundle_digest']):
            raise OperatorError('Completed source history changed; recovery stays closed')
        files = {path.name for path in (self.root/'journal').iterdir()}
        previous = data_digest(binding)
        completed = []
        pending = None
        expected_files = set()
        for index, step in enumerate(STEPS):
            stem = f'{index:02d}-{step}'
            intent_name, complete_name = stem+'.intent.json', stem+'.complete.json'
            if intent_name not in files:
                break
            expected_files.add(intent_name)
            intent = self._read(self.root/'journal'/intent_name)
            if (set(intent) != {'step','previous','details','review_hash','lock_identity'}
                    or intent['step'] != step or intent['previous'] != previous
                    or not isinstance(intent['details'],dict)):
                raise OperatorError('Checkpoint recovery intent order or binding changed')
            if complete_name not in files:
                pending = dict(step=step, intent=intent)
                break
            expected_files.add(complete_name)
            completion = self._read(self.root/'journal'/complete_name)
            if (set(completion) != {'step','intent_digest','details'} or completion['step'] != step
                    or completion['intent_digest'] != data_digest(intent) or not isinstance(completion['details'],dict)):
                raise OperatorError('Checkpoint recovery completion differs from its exact intent')
            completed.append(dict(step=step, intent=intent, completion=completion))
            previous = data_digest(completion)
        if files != expected_files:
            raise OperatorError('Checkpoint recovery has unknown or reordered journal records')
        return dict(recovery_id=self.recovery_id, checkpoint_operation_id=binding['checkpoint_operation_id'],
            phase=completed[-1]['step'] if completed else 'started', pending=pending,
            completed=completed, chain_digest=previous, binding=binding)

    def begin(self, step, details, *, decision, exact_hash, locks):
        bundle, _ = self._review(decision, exact_hash)
        owner = self.store._lock_identity(bundle['plan'], locks)
        state = self.status()
        index = len(state['completed'])
        if (state['pending'] is not None or index >= len(STEPS) or step != STEPS[index]
                or not isinstance(details,dict)):
            raise OperatorError('Checkpoint recovery command is pending, out of order or already completed')
        if decision['checkpoint_operation_id'] != state['checkpoint_operation_id']:
            raise OperatorError('Recovery review selected a different source checkpoint')
        if ((step in {'resume_started','resumed'}) != (decision['action'] == 'resume_completed_checkpoint')
                or decision['action'] == 'continue_completed_checkpoint' and index < 4):
            raise OperatorError('A distinct reviewed continuation or resume boundary is required')
        _write_new(self.root/'journal'/f'{index:02d}-{step}.intent.json',
            dict(step=step, previous=state['chain_digest'], details=details,
                 review_hash=exact_hash, lock_identity=owner))

    def finish(self, step, details, *, decision, exact_hash, locks):
        bundle, _ = self._review(decision, exact_hash)
        owner = self.store._lock_identity(bundle['plan'], locks)
        state = self.status(); pending = state['pending']
        if (pending is None or pending['step'] != step or not isinstance(details,dict)
                or pending['intent']['lock_identity'] != owner
                or pending['intent']['review_hash'] != exact_hash):
            raise OperatorError('Only the same fenced executor may complete its exact pending command')
        index = len(state['completed'])
        _write_new(self.root/'journal'/f'{index:02d}-{step}.complete.json',
            dict(step=step, intent_digest=data_digest(pending['intent']), details=details))
