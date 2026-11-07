# ADR 0064. Native recurring schedules

Status: selected private contract; BX-03 implementation in progress. No recurring
producer is enabled yet. The deterministic time-selection primitive is the
first implementation boundary. Existing one-off job contracts remain unchanged.
Ten deterministic cases and fifteen PostgreSQL credential-footprint checks
passed. The credential guard is not yet selected by the lifecycle executor;
its database fixture was retired. This is prerequisite evidence, not a BX-03 exit.

BX-03 needs a separate pinned producer because guarded Odoo startup deliberately
uses zero cron threads. Reuse the reviewed worker fleet for one optional producer
role, on the same image and private network, with the same release, readiness,
pause, drain and independent operator controls. It creates existing one-off
jobs; it never executes handlers or opens dispatch. Start with at most one
producer per site. The database protocol must still tolerate duplicate ticks.

Persist a versioned private schedule, a cursor and compact occurrence receipts.
The producer takes the shared dispatch fence before the schedule row lock. The
occurrence reservation, authorized one-off enqueue, outstanding-job pointer and
cursor advance commit together. No cursor may advance after a failed enqueue.
Serialize all occurrence writers on that schedule row. Enqueue and final receipt
insertion run inside one savepoint, so a caller catching an exception cannot
commit an orphan job. A stale repeatable-read tick must retry the entire
transaction. Keep the immutable creation digest separately from the current
configuration digest so a create retry still resolves after an authorized edit.
Use bounded batches and fresh transactions. A schedule has at most one
outstanding job; pending, running, retry, held and unknown outcomes block another
occurrence. A completed, cancelled or terminal failed job permits future work.
Use compact job history after archival to resolve terminal status.

The occurrence identity is `(site, schedule public ID, nominal UTC instant)`.
It excludes credential ID, schedule revision, handler version and release.
The receipt is authoritative if a cursor is replayed: edits or credential
rotation cannot create a second job for that occurrence. One-off enqueue keeps
its existing scoped deduplication too. An outstanding job and its saved
authority are immutable; rotating a schedule credential affects future jobs
and does not elevate or rewrite work already submitted.

Use second-aligned UTC anchors and integer intervals from one second to 366
days. Each emitted job has a validity window of at most 24 hours and an attempt
budget of at most one hour, no greater than that validity through the existing lease
contract. Emit due occurrences only, so a distant schedule is stored without
creating one-off jobs outside the 30-day horizon. No local-calendar, cron or
daylight-saving interpretation is introduced.

For `skip`, emit the cursor's nominal occurrence only if no later occurrence
is already due, the lateness is within the explicit grace and validity remains.
Otherwise advance to the first future occurrence without emitting. For
`coalesce_latest`, emit only the latest nominal occurrence at or before the
tick, provided its original validity remains. Both policies consider any
number of missed intervals in constant time and record skipped counts. Neither
extends an occurrence's expiry. Full catch-up remains excluded until its replay
window and batch policy are separately specified and qualified.

Pause retains the cursor; resume applies the selected missed-occurrence policy.
An authorized edit increments the configuration revision, leaves any outstanding
job intact and selects future nominal instants strictly after the durable
considered high-water mark on the new interval grid. It cannot rewind the
occurrence identity. Changing the service principal or installation requires a
new schedule; credential rotation within that same scope can preserve the ID.

Create and edit through trusted native adapters with a non-administrator
service principal, active workspace membership and an explicit, unexpired
credential for the selected native installation. Reuse bound-service and
resource authorization at creation and every tick. No caller-provided actor,
site or backing user is accepted. Store the credential reference and bounded
scope, never its secret. Revocation, missing handler, suspended installation or
lost binding holds the schedule with a safe reason. An application must
explicitly repair and resume it under current authority.

The existing lifecycle profile refuses all active technical credentials. Its
replacement for this requirement must recognize only independently reviewed
native schedule credentials, validate exact actor/workspace/installation and
action scope, and retain all existing external-effect and unknown-result
refusals. Do not relax the generic credential-count guard. Maintenance requires
producer and lanes paused/stopped, and its snapshot includes schedule, cursor
and occurrence receipts. Restores preserve occurrence identity and current
revocations, keep traffic and dispatch closed, and require separate resume.
The coordinated checkpoint follows producer drain and the dispatch fence. No
supported occurrence writer can commit after it. Verify the immutable receipt
digest against the failed source during both restore review and execution.
Unexpected post-checkpoint receipts or rewritten history refuse automatic
restore and require independent reconciliation; do not merge migrated source
jobs, credentials or configuration into retained code. A restored cursor and
its receipts come from the same committed checkpoint. Uncertain remote effects
remain an independent hold.
Credential replacement must not silently reactivate restored schedules.

Qualification order: deterministic time/identity cases; PostgreSQL duplicate
ticks and rollback; native service authorization and credential rotation;
one-outstanding overlap and edit/pause/revocation; managed producer readiness
and drain; populated maintenance and fresh restore of a previously emitted
occurrence. Native recurrence is unavailable until the physical schema,
lifecycle recognition and authority checks have passed together. Record exact
semantics, fixtures and compatibility effects before exposing an app adapter.

The private SQL store passed fifteen PostgreSQL checks, including a caught
post-enqueue failure, caller rollback, stale duplicate tick, handler edit with a
rewound cursor, compact terminal history and missing/foreign job pointers.
This proof uses disposable SQL tables. Native model installation, lifecycle
recognition and recovery are separate BX-03 requirements. Native model
installation and schema recognition subsequently passed on core 0.1.37. Both
host and native generic guards refused a populated schedule with dispatch
unchanged. Recovery and the reviewed credential profile remain pending. The
host-injected schema helper stays self-contained so retained images do not
need the new recurrence module just to inspect or restore their old schema.

The service adapter and optional producer role passed current native checks.
Nine adapter checks and the managed 203-occurrence run covered service scope,
rotation, holds, edit, automatic child restart, pause and full drain. Native
tests exposed a pending ORM revocation rollback: use Odoo's flush-aware
savepoint with cache clearing, retaining a raw SQL fallback for psycopg callers.
Review can request zero or one producer, sharing the eight-role
single-host bound. The supervised producer uses database UTC time, current
dispatch and release pins, bounded candidate batches and fresh transactions.
It reconstructs saved service authority before calling the existing scheduled
enqueue path. An expired or revoked credential holds future production; editing
under a new current credential affects future jobs only. The generic lifecycle
guard remains strict. Reviewed current-schema maintenance passed; full
fresh-restore qualification remains pending.

The role's reviewed credential footprint coordinates maintenance; it is not a
sandbox or a replacement for per-job scope and resource authorization. Native
plugins remain trusted. A new or broader credential must be reflected in a
fresh independent role review before maintenance can rely on it. Preserve
current revocations and stable occurrence high-water marks during recovery.
