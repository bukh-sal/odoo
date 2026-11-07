# ADR 0062. Background history retention and replay identity

Status proposed for BX-01. The live scheduler and lifecycle receipts currently
depend on the complete job rows. The lifecycle refuses a dispatch table above
its row limit before taking a snapshot. The guarded history diagnostic can
show that pressure without producing an oversized receipt.

Use one private database identity registry for both enqueue and archive. Its
unique key is the current enqueue identity: site, workspace, actor, installation,
handler, handler version and idempotency key. It needs a stable row to lock
before either operation accesses the live job. The live unique constraint remains
in force. Enqueue and archival must take locks in the same order, starting with
the dispatch control row, then the identity row, then the live job. Archive
selection may nominate candidates without locks, but must reread eligibility
under these locks. Do not acquire an entire batch's live row locks first.

An unlocked read of an archive table followed by a live insert would be unsafe.
Odoo transactions use repeatable read. A transaction can start before archival,
wait for the live row to disappear, and still have a snapshot that cannot see
the new archive record. Use a unique insert/update at the shared identity row
so a stale transaction must retry or fail. The transaction owns the reservation,
archive status and deletion together. Old rows can acquire their reservation
on first use as long as both paths recognize the old live unique row and archival
starts only after the release fence has retired all writers on the old protocol.
Exercise fresh and stale snapshots, both commit orders, rollback and transaction
retry in PostgreSQL before enabling archival.

Initially archive only reviewed terminal jobs with no unresolved external
effect or remaining retry window. Enqueue still authorizes current scope and
resource access before resolving a duplicate. Preserve the original ID, semantic
input digest, release and effect policy. For an equivalent request on the same
release, return the original ID. An archived entry can appear in the new scoped
history view with minimized metadata. Existing result APIs may report that the
full result is gone. Retained keys keep rejecting changed payloads, timing or
releases. Expiry of the deduplication record is a separate policy decision with
an explicit replay horizon and recorded behavior after it expires.

The compact registry must have an independently validated lifecycle footprint
with bounded receipts. The active dispatch row limit must not simply move to a
new table containing one row per historical job. Qualify the registry and
archived status with an upgrade and restore above the old aggregate job count.
Keep remote-effect settlement evidence independent of the restored database.
The evidence window must cover any backup from which a previously sent effect
could reappear. Preserve held, running and uncertain jobs.

Qualify event and outbox retention separately within BX-01. Deliveries and
consumer receipts can refer to an outbox event. Establish the replay and
subscription rules before moving an event, and retain consumed-effect evidence
needed for a restored checkpoint. Keep cleanup disabled until the operator can
review the exact policy, cutoff, bounded batch and current site pins.

Sources: [active enqueue](../../packages/platform_sdk/modular_platform/durable.py:154),
[lifecycle control and snapshot](../../packages/platform_sdk/modular_platform/dispatch_lifecycle.py:181),
[Odoo cursor isolation](../../odoo/sql_db.py:329), and the
[follow-up gate](../../planning/background_execution.md#implementation-gates-and-acceptance).
