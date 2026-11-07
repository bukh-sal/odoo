# Native application continuations

The background reference app demonstrates an application-owned report run over
the existing scheduled-job API. It keeps its snapshot, cursor and aggregate in
private native storage; the queue supplies scoped claims, retry, cancellation,
fencing and atomic database finalization. No workflow engine or custom frontend
is required. [Contract](architecture-decisions/0068-app-owned-report-continuations.md)
and [current qualification](implementation-status.md) record the boundaries.

Inside trusted native application code with an already authorized scoped
environment:

```python
tasks = scoped_env['mp.background.task']
run_id = tasks._start_report(first_task_id, last_task_id, 'monthly-report-2026-11')
# The caller commits its normal transaction; run and first job commit together.

status = tasks._report_status(run_id)  # committed cursor, total, sum and job state
tasks._cancel_report(run_id)          # only the current originating actor
```

These are private reference adapters, not new general RPC endpoints. A real app
can expose its flow through a native Odoo action and retain native list/form
screens. It must obtain the scoped environment from the server's current actor
context, rather than accept actor/workspace authority in a job payload.

The reference captures one immutable snapshot of up to5,000 authorized task
ID/point pairs. Each job processes at most100 rows, carries only the run UUID
and expected cursor, and retains the run's original one-hour expiry with a
20-second attempt budget. Later point edits do not change the snapshot sum;
current source access is still checked, and missing or inaccessible records
block progress. Larger applications should choose their own bounded source
representation instead of expanding queue payloads without limits.

Apply locks the run after the job fence, validates its cursor/contract, writes
and flushes committed progress, then enqueues one successor and stores its ID.
Enqueue performs preparation immediately, so it must see the advanced cursor
within that same uncommitted transaction. The enclosing savepoint rolls back
the progress, successor and identity together on failure. The final chunk
discards snapshot data and retains the compact request identity/outcome.

Cancellation locks the current job before the run. If a concurrent chunk won,
retry from a fresh transaction; do not guess its successor or reset the cursor.
Previously committed chunks remain. In-flight obsolete compute may finish, but
cannot apply after cancellation. The status adapter reports blocked work when
its current job is held/dead-lettered; resolution remains an explicit app or
operator decision. An identical scoped request key returns the original run,
while a changed range conflicts.

Keep handler1 and run-contract1 semantics stable across compatible releases.
Checkpoint application state and jobs together, restore with traffic closed,
then use independent resume and freshly reviewed worker profiles. Never restart
an entire report to hide a failed release. Unknown run contracts cannot advance.
Provider delivery, fan-out and common orchestration remain conditional on an
actual app requirement. Deployment sizing remains
[reviewed profiles plus read-only advice](background-capacity.md).
