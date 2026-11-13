"""Separate OS recovery history; the completed source operation is immutable.

This records reviewed command intent/completion, not proof a Docker command ran.
Executors must independently verify physical effects before completing a step.
No intent alone authorizes repetition or proves a process is alive.
"""
from datetime import datetime, timezone
import re
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
            adopted = {'pending_adoption_review','pending_adoption_digest'} & completion['details'].keys()
            if adopted:
                if adopted != {'pending_adoption_review','pending_adoption_digest'} or step != 'restore_verified':
                    raise OperatorError('Unknown checkpoint command adoption')
                adoption = self._adoption(intent, binding, completion['details']['pending_adoption_review'])
                if data_digest(adoption) != completion['details']['pending_adoption_digest']:
                    raise OperatorError('Checkpoint command adoption changed')
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
                or {'pending_adoption_review','pending_adoption_digest'} & details.keys()):
            raise OperatorError('Only the same fenced executor may complete its exact pending command')
        if pending['intent']['lock_identity'] != owner or pending['intent']['review_hash'] != exact_hash:
            if step != 'restore_verified':
                raise OperatorError('Only the same fenced executor may complete its exact pending command')
            adoption = self._adoption(pending['intent'], state['binding'], decision['review']['review_id'], active=True)
            if adoption['lock_identity'] != owner or adoption['review_hash'] != exact_hash:
                raise OperatorError('Pending checkpoint command is not adopted by this reviewed executor')
            details = dict(details, pending_adoption_review=decision['review']['review_id'],
                           pending_adoption_digest=data_digest(adoption))
        index = len(state['completed'])
        _write_new(self.root/'journal'/f'{index:02d}-{step}.complete.json',
            dict(step=step, intent_digest=data_digest(pending['intent']), details=details))

    def _adoption(self, intent, binding, review_id, *, active=False):
        canonical_id(review_id)
        value = self._read(self.root/'adoptions'/(review_id+'.json'))
        decision = self._read(self.root/'continuations'/review_id/'decision.json')
        exact_hash = data_digest(decision)
        reviews = RecoveryReviews(self.store)
        if active: reviews.check_reserved(decision, exact_hash=exact_hash)
        else: reviews._record(decision, exact_hash)
        continuation = decision.get('continuation', {})
        if (intent['step'] != 'restore_verified' or intent['review_hash'] != binding['decision_hash']
                or decision.get('action') != 'continue_completed_checkpoint'
                or decision.get('operation_id') != self.recovery_id
                or decision.get('checkpoint_operation_id') != binding['checkpoint_operation_id']
                or continuation.get('phase') != 'restored_before_first_dispatch_fence'
                or continuation.get('reason') != 'retained_source_fence_name_collision'
                or continuation.get('pending_intent_digest') != data_digest(intent)
                or continuation.get('original_decision_digest') != data_digest(self._read(self.root/'decision.json'))
                or decision['review']['review_id'] != review_id):
            raise OperatorError('Only the reviewed unstarted restored-fence verification may be adopted')
        expected = dict(schema_version=1, kind='unstarted_restored_fence', step='restore_verified',
            intent_digest=data_digest(intent), prior_review_hash=intent['review_hash'],
            prior_lock_identity=intent['lock_identity'], review_hash=exact_hash,
            review_id=review_id, lock_identity=value.get('lock_identity'),
            continuation_digest=data_digest(continuation))
        if (value != expected or not isinstance(value.get('lock_identity'),str)
                or not re.fullmatch('sha256:[0-9a-f]{64}',value['lock_identity'])):
            raise OperatorError('Exact pending-command adoption evidence required')
        return value

    def adopt_unstarted_restored_fence(self, *, decision, exact_hash, locks):
        """New fenced authority for one proven unstarted verification, no replay.

        Physical proof is independently reconstructed by the recovery executor
        before this method. The original command intent/history is not edited.
        """
        bundle, _ = self._review(decision, exact_hash)
        owner = self.store._lock_identity(bundle['plan'], locks)
        state = self.status(); pending = state['pending']
        continuation = decision.get('continuation', {})
        if (state['phase'] != 'authority_applied' or pending is None
                or pending['step'] != 'restore_verified' or len(state['completed']) != 7
                or decision.get('action') != 'continue_completed_checkpoint'
                or continuation.get('phase') != 'restored_before_first_dispatch_fence'
                or continuation.get('reason') != 'retained_source_fence_name_collision'
                or continuation.get('pending_intent_digest') != data_digest(pending['intent'])
                or pending['intent']['review_hash'] != state['binding']['decision_hash']):
            raise OperatorError('Unsupported pending checkpoint command adoption')
        review_id = canonical_id(decision['review']['review_id'])
        value = dict(schema_version=1, kind='unstarted_restored_fence', step='restore_verified',
            intent_digest=data_digest(pending['intent']), prior_review_hash=pending['intent']['review_hash'],
            prior_lock_identity=pending['intent']['lock_identity'], review_hash=exact_hash,
            review_id=review_id, lock_identity=owner, continuation_digest=data_digest(continuation))
        protect_directory(self.root/'adoptions')
        path=self.root/'adoptions'/(review_id+'.json')
        if path.exists() or path.is_symlink():
            raise OperatorError('Pending checkpoint command adoption already attempted; inspect without replacement')
        _write_new(path, value)
        self._adoption(pending['intent'], state['binding'], review_id, active=True)
        return value
