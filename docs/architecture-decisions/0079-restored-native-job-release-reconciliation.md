# ADR0079. Bind checkpoint job identity during independent restore

Accepted9November2026 for AP-02-P2, prerequisite to AP-G/H. The fresh native-app
recovery preserved records/files/current user revocation and separately resumed,
but both original native reminder jobs remained held/FORBIDDEN with no effects.
[Counterexample](../evidence/post-r1/application-adoption/ap02-native-restore-counterexample.json).
A rollback-only diagnosis proves the original actor, installation and current
resource authorization are valid. Restored publication/control have a new release
digest while restored jobs carry the checkpoint digest. Native authorization
correctly refuses that mismatch. Earlier workspace-only recovery did not exercise
this native branch; its historical evidence retains that narrower scope.

## Frozen correction and bounds

Change the independent host recovery adapter only. Preserve sealed49/47/46,
runtime job definitions/authorization, application artifacts and platform version.
Do not loosen `native_jobs.authorized`, rewrite queued actors/payloads/digests by
hand, patch running images or force held jobs through an operator retry.

The existing host-owned job reconciliation child accepts one optional private
`source_release` hash, selected exclusively from the reviewed checkpoint's dispatch
control. The existing `previous_release` continues binding the actual closed
restored control; `release_digest` binds the actual restored publication. Reject
malformed/unknown input and wrong site/control/state before classification.
This is private host-child protocol revision2, not a public application contract.

Within one caller-owned transaction, after verifying the exact restored metadata
and locking its paused/restoring control, temporarily bind that closed control to
the exact checkpoint source release. Invoke the existing unchanged reconciliation
function with that source release and actual restored target release. It checks
original jobs, current actor/installation/resource permissions, payload/schedule
identity and effect state, fences old claims and publishes the target control
still paused. Commit only after the exact result/control postcondition passes.
Any failure rolls back the temporary tag and all decisions. Dispatch never opens
in this transaction. Ordinary forward publication omits the new field and keeps
its existing behavior. Preview may exercise the same transaction but rolls back.

The restore review already binds the immutable checkpoint manifest and actual
current authority. Record both source and target pins plus helper hashes in the
private request/receipt. Keep independent restore approval and separate resume.
No plugin chooses this source tag or receives executor authority.

## Qualification and return condition

Before fresh qualification, prove rollback-only classification with actual sealed49
native jobs: valid original actor resumes; revoked actor stays held; wrong control,
site/state/source shape and exception leave the transaction closed/unchanged.
Run affected host recovery/dispatch/reference/recurrence consumers and unchanged
public contract freeze. Then retire the failed disposable sibling by exact owned
inventory, retain its evidence, and qualify a fresh populated0.2.2→0.2.3 fault,
old-app restore/separate resume/effects plus a new successful forward operation.
The retained pilot stays useful. AP-G/H remain unpassed until actual effects work.

App-owned business ACL data such as list membership still restores to checkpoint;
this correction does not introduce a generic current-application-ACL overlay.
Current platform/native authentication revocations retain their existing explicit
reconciliation. Record this limit rather than claiming all business ACL changes
survive a point-in-time restore.
