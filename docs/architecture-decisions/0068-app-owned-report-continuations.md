# ADR0068. App-owned bounded report continuations

Status: BX-05 contract selected before implementation. No public SDK change.

Use the existing native background reference app. Its one-off report accepts
at most500 task IDs; retain that handler/version unchanged. Add a separate
version1 bulk-report handler and private application run record. This is a
reference of durable continuation, not a new reporting product. No provider,
fan-out, workflow engine, broker or custom frontend is required. Standard record
screens continue using native Odoo views.

## Input and consistency

A scoped native app adapter requests a report by an explicit task-ID range and
caller key. Capture at most5,000 authorized task ID/point pairs in the same
transaction as the run and first job. Refuse an oversized or empty selection.
This bounded immutable snapshot gives the report consistent values across
chunks; later task edits do not silently change its sum. Each stage still
checks current actor, plugin, workspace and access to its source records. Deleted
or inaccessible records stop further progress. This is a reference limit,
not an assertion that arbitrary-size snapshots belong in request transactions.

The application owns snapshot data, contract version1, an index cursor,
processed count/sum, digest, absolute expiry and current job ID. Private storage
has no ordinary CRUD ACL. Its native adapters check the current originating
principal/workspace before any metadata access; no secret or authority comes
from serialized input. An identical scoped caller key returns the original
run. Changed range conflicts. Unique identity plus a write on conflict forces
a stale concurrent transaction to retry, rather than create another chain.
Keep compact run identity/outcome after dropping terminal snapshot data.

## Transaction and cancellation

Each job contains only the run UUID and expected cursor. Prepare at most100
snapshot points, compute outside the transaction using bounded JSON, then apply
behind the existing job fence. Lock the app run, require contract1, current
cursor and active state, advance count/sum/digest and enqueue at most one
successor in the same transaction. The successor key includes run UUID/cursor;
its eligibility is when that chunk becomes ready, while the run's original
absolute expiry never extends. The enqueue adapter immediately validates
preparation. Flush the advanced cursor
inside the still-uncommitted apply before enqueue, then store the successor ID.
All three changes remain behind the same job savepoint and commit boundary.
The final chunk marks complete and clears the
snapshot. Initial request uses an Odoo savepoint so a caught enqueue failure
cannot commit an orphan run. Native apply already provides rollback/fencing.
Snapshot storage is nullable for terminal runs. A database phase check requires
an array while running and SQL NULL after completion/cancellation; an empty
Odoo JSON value must not violate an unconditional NOT NULL constraint.

Cancellation applies only to the current originating actor. Lock/cancel the
current job before locking its app run, matching worker job-then-run order.
If the chain advanced, retry from a fresh transaction; never cancel an
unobserved successor or reverse earlier committed chunks. Mark the run cancelled
and discard its remaining snapshot atomically with current-job cancellation.
An in-flight obsolete compute cannot apply after that fence. Completed wins a
race with cancellation. Progress means committed work, not a speculative
estimate of completion.

Private native adapters demonstrate the application contract. They are not a
new general RPC surface. Normal plugin code can expose the same flow through a
native Odoo action when its actual product requires one. Trusted native code
remains trusted; private storage/guards are not a hostile-code sandbox.

## Compatibility and required proof

Package0.3.0 adds the model and handler; keep handler1/cursor semantics stable
through a compatible patch upgrade. Unknown run contracts cannot advance.
Do not rewrite a cursor or resubmit the entire operation during release repair.
Checkpoint the application run, jobs and snapshot together. Fresh restore must
resume from the saved cursor under current rights, preserve earlier committed
progress, and invalidate old claims/profiles. Scope and absolute expiry remain
the original job guarantees.

Qualify1,201 rows (13 chunks), exact snapshot sum, source changes, duplicate
requests, foreign/revoked authority, direct metadata denial, initial rollback,
apply rollback after successor enqueue, process loss/stale apply, cancellation
after partial progress, compatible package upgrade and populated fresh restore.
Verify cursor/successor pairs in actual native transactions, not only mocks.
Retire owned fixtures and obsolete candidates. Provider delivery and bounded
fan-out remain unselected because this app needs neither.
