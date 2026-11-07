# ADR0067. Enforce the managed workspace limit after session loss

Status:selected after BX-04's isolated slot-backend termination. The worker's
compute and heartbeat stayed alive; another lane acquired the lost advisory
slot and admitted a second valid claim in the same workspace/pool. Both jobs
finished with no external effect, but the configured concurrency bound failed.

Keep the long-lived workspace session slot for efficient candidate exclusion.
Add a separate claim/preparation guard on that operation's own connection. It
survives loss of the compute-slot connection. Acquire it on a fresh cursor,
discard the acquisition's repeatable-read snapshot, then observe and prepare
the job. Hold it through the preparation commit, release before detached
compute, and retain normal per-job heartbeat/finalization fences.

After the existing expired-attempt cleanup, refuse a different pooled claim if
any running row remains for the workspace's registered pool routes. Include
expired rows skipped because another heartbeat/finalization holds their row
lock. That transaction must settle before a new claim can be admitted. A
fresh-snapshot guard prevents missing an uncommitted prior claim. A guard on
only the selector connection or a repeatable-read advisory transaction alone
does not cover that race. Do not lock the business workspace row for the whole
preparation phase or block ordinary Odoo readers.

The managed runner owns the fresh cursor and rollback boundaries. The private
SQL claim primitive accepts an optional pool and verifies the same backend
holds its preparation guard. Legacy private callers keep their existing
behavior; the managed pool guarantee requires this guarded path. No schema,
public job envelope, actor, credential, expiry or effect policy changes.

The bound is one valid managed claim per workspace/pool. Lease loss can still
leave obsolete detached compute running until its watchdog/cancellation check;
its apply/effect fence remains decisive. Native plugins are trusted, and these
locks are not a sandbox for arbitrary native SQL or manual worker code.

Qualification: invisible uncommitted claim, rollback, renewed/locked expired
attempt, expiry reclaim and another pool in PostgreSQL; repeat the exact
isolated backend termination natively; recheck fairness/restart and admitted
web/job load. Keep failed baselines and zero-effect observations separate.
