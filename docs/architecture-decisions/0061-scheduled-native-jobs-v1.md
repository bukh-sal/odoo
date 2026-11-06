# ADR 0061: Scheduled native jobs v1

BG-02 adds an opt-in Python contract for trusted native plugins. Register an
immutable namespaced `JobDefinition` with a version and an `urgent` or `bulk`
pool. Call `enqueue_scheduled(env, alias, handler, input, key, schedule=...,
version=...)` through an authorized bound method. Use `status` and
`cancel_scheduled` with the same actor and active workspace. These are private
server adapters; there is no direct RPC or authority in serialized input.

- `JobSchedule` takes absolute, aware `run_at` and `expires_at` times and an
  integer 1–3,600 second attempt budget. Its wire form uses canonical UTC. A
  new job must not be expired or more than 30 days ahead. Its validity window
  is no longer than 24 hours. The lease may renew only within the attempt
  and expiry bounds. A pending job cannot claim before eligibility.
- Enqueue shares the source transaction. The original scope and binding
  come from the server. A repeated semantic request with the same key
  returns the original job. Changed input or timing conflicts. Preflight
  must have no effects; the worker rechecks authority and resource state.
- The database apply and outcome commit together behind the current claim.
  Detached compute receives bounded JSON and no native ORM environment.
  Only an explicit `RetryJob` requests a transient retry; attempts and
  exponential backoff are bounded. Effect-started reconcile-mode work
  remains unknown after failure or cancellation, and is never auto-replayed.
  For a remote write, call `mark_external_effect(context)` immediately
  before the authorized call. It checks the original scope and commits the
  marker separately. A timeout after this marker is an uncertain outcome.
- The existing technical-origin binding is available when required. It
  uses a scoped, revocable credential and a non-administrator mapped user.
  The reference reminder uses its originating human actor; no role is
  elevated if that actor loses access before execution.
- The job envelope advances to v2 only for scheduled jobs. Legacy v1
  jobs retain their API and semantics. No columns are removed or added.
  Handler version and effect policy remain compatibility boundaries.
  An independently approved lifecycle transition revalidates the original
  binding and scope before carrying work forward; missing versions hold.
  Never change a registered handler version's semantics or pool in place.

BG-02 requires PostgreSQL and native dispatch observations before acceptance.
BG-03 qualifies supervised operation and populated release recovery.
