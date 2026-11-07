# ADR 0062. Background history retention and replay identity

Status qualified for the BX-01 reference workload. Native enqueue and private terminal
archival passed on a fresh Odoo site. The populated core upgrade and fresh
restore passed. The reviewed job archive and interrupted-result reconciliation
also passed above the live-table limit. Native scoped history and aggregate
alerts passed over HTTP and in the in-app browser. Reviewed event retention,
the populated upgrade, fresh restore and cleanup latency checks passed. The lifecycle still refuses an active dispatch table above its
row limit. The guarded history diagnostic reports that pressure without
producing an oversized receipt.

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

The stock Workspace menu opens a native list scoped to the current human
actor, workspace and site. The receipt projects the public job ID, state,
submission or completion time, and archive marker. Held and unknown outcomes
remain visible to their original actor with an active workspace membership.
Payload and result access still use their separate job authorization path.
The stock list uses pages of 50 and a capped total of 10,000. The local
operator's history command reports site-wide table alerts at the existing
advisory and hard bounds.

Direct-ID ownership checks translate the view's even/odd projected IDs into
scoped source primary keys. The initial union-based check repeatedly scanned
the hot history and caused the web baseline to miss. With primary-key checks,
the two paired cleanup samples kept worst list/detail/history p95 at
34.839/17.516/59.201 ms. The fixture included 20 paced readers, an active native
producer, about 80,000 live jobs and events per table, and over 100,000 compact
job receipts. Captured plans and dispatch-lock bounds are in the
[cleanup qualification](../evidence/post-r1/background-execution/bx-01-cleanup-qualified.json).

The first job policy retains the full payload and result for at least seven
days after both the terminal timestamp and original deadline. The independent
operator chooses an explicit UTC cutoff no newer than that floor and a batch
of at most 100 rows. Review shows the exact job IDs and binds the selection,
cutoff, dispatch generation and current deployment pins. Apply rechecks the
batch and commits it together. The private intent precedes the mutation.
If the result receipt is lost, a read-only status command checks those exact
IDs against the live table and compact registry. A subsequent batch requires
its own review.

At 10,000 retained jobs per day, seven days accounts for 70,000 terminal rows
when deadlines have elapsed. This leaves 10,000 rows to the 80% advisory and
30,000 to the hard limit for scheduled, active, held and other excluded work.
For each site, budget the effective full-record age and the excluded backlog
against the advisory threshold. Include extra days from late deadlines and
archival interruptions, and verify that maintenance can clear eligible work
faster than it accumulates. The advisory measures physical table pressure.
Compact safe status and scoped deduplication records currently share one
indefinite retention window. Checkpoint expiry controls historical full
payloads still present in retained dumps. Jobs with remote effects stay in the
live table under this policy. Keep their independent settlement evidence for
at least the longest still-restorable checkpoint and until provider uncertainty
has been resolved.

The compact registry must have an independently validated lifecycle footprint
with bounded receipts. The active dispatch row limit must not simply move to a
new table containing one row per historical job. The lifecycle computes its
count and digest in ordered pages of up to 4,096 rows. PostgreSQL evidence
covers 100,007 entries and detects a change to retained identity metadata.
The initial implementation retains keys indefinitely. The populated lifecycle
drill restored 100,002 retained identities with a byte-identical digest and
the original ID of a job archived through the native path.
Keep remote-effect settlement evidence independent of the restored database.
The evidence window must cover any backup from which a previously sent effect
could reappear. Preserve held, running and uncertain jobs.

During recovery of a failed 0.1.30 to 0.1.31 native core upgrade, the paused
source can already have the new table even though the coordinated checkpoint
predates it. Recovery accepts that one schema extension only when the source
table is empty and both physical schemas match their known layouts. The fresh
restore still has to match the original checkpoint schema and complete its
separate resume review. A nonempty table during that transition requires
independent reconciliation.

The 0.1.32 to 0.1.33 transition applies the same exact empty-table rule for
the compact event history. The populated checkpoint drill restored 100,007
compact event and receipt rows with the original digest, the native projection
and its consumption receipt. [Event retention evidence](../evidence/post-r1/background-execution/bx-01-event-retention.json)

The event policy keeps the existing seven-day occurrence-time replay window
and one-hour subscription lifetime. Event cleanup requires a cutoff at least
eight days in the past. Start by archiving deliveries for expired subscriptions
and native consumption receipts for events at or before that cutoff. A delivery
can move only when both its subscription and any lease have expired within the
fixed review window. After those references move, archive eligible outbox rows
and expired subscriptions that have no remaining live deliveries. Held events
and their references remain live. The extra day gives the latest in-window
subscription time to expire before a payload or receipt can move.

The compact history records original public IDs, routing scope, safe delivery
outcomes, event payload digests and native consumption identities. Payloads,
binding descriptors, lease tokens and subscription keys are absent from the
compact records. The original scoped subscription key is preserved as a digest
and still refuses recreation. A live consumer deduplicates by the original
public event ID as well as the live receipt. Archived subscription status
returns `NOT_FOUND`. Native effects and their receipts share the checkpoint
transaction. This policy requires a native-only profile without live technical
credentials or API keys. A remote provider needs independent effect evidence
before its transport can use event cleanup.

The operator reviews a single kind and at most 25 records per batch. Apply
updates the dispatch control row without advancing its generation and then
reselects the approved records under that exclusive lock using read committed.
Concurrent producers and subscribers take the existing shared lock. An older
repeatable-read transaction must retry after the control-row version changes.
The measured exclusive and shared control-lock upper bounds stayed below
129 ms in the qualified workload. At
10,000 events per day, eight days already reaches the 80,000-row advisory for
the outbox. Size deliveries and consumptions from their own fan-out rates and
subscriptions from their own expiry rate. Include retained held work and time
to apply reviewed batches when evaluating headroom.

Sources: [active enqueue](../../packages/platform_sdk/modular_platform/durable.py:154),
[lifecycle control and snapshot](../../packages/platform_sdk/modular_platform/dispatch_lifecycle.py:181),
[Odoo cursor isolation](../../odoo/sql_db.py:329), and the
[follow-up gate](../../planning/background_execution.md#implementation-gates-and-acceptance).
[Native archival evidence](../evidence/post-r1/background-execution/bx-01-native-archive.json),
[operator archive evidence](../evidence/post-r1/background-execution/bx-01-archive-operator.json),
[scoped history evidence](../evidence/post-r1/background-execution/bx-01-scoped-history.json) and
[Populated lifecycle evidence](../evidence/post-r1/background-execution/bx-01-retention-lifecycle.json)
