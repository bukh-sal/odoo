# JOB-03: real non-idempotent effect with an unknown caller outcome

Qualified on unchanged nativeBB1/coreSDK0.1.16 and cached worker image1d.
Product source commit `8b0e25d5`. The live19/98 site,29 old jobs and canonical
worker/config5/publication7 stayed exact. No production code/contract was edited.

The fixture copied only the project-owned disposable site into a separately
named owned database/config volume. A trusted test definition was registered
through installed `JobDefinition`, using real original-Alice scope, service
binding, resource/feature/grant checks and startup inventory/database pins.
Existing functions/modules were not replaced. The actual installed
`job_runner.run_once` performed preparation, claim and computation.

The separate test recipient used the cached worker image, standard scoped RS256
worker-token verification and a public-only config/key volume. It received no
database credentials, filestore, host bind, signing key or Docker socket, and
published no host port. It is a private operator-owned effect fixture, not a
replacement or additional deployed public reference service.

Before HTTP I/O, the native producer freshly reauthorized the actual job/resource/
external scope and committed `effect_started`. The recipient then committed and
fsynced an incrementing counter/operation/input receipt and withheld the HTTP
response. This counter deliberately has no deduplication: another request would
increment it again. After independently observing count1, the driver killed the
exact owned native producer with SIGKILL; actual exit137, no Python cleanup or
host-result commit. The other recipient process retained its committed receipt.

After the real30-second lease expired, the installed runner classified the job
as `outcome_unknown`, one attempt, LEASE_EXPIRED, no result. This occurred with
retry budget remaining (max3) and before its original180-second deadline. Two
subsequent actual runner passes returned idle; the external counter stayed1.
Actual native original-actor job status produced a schema-valid unknown-outcome
DTO. Private operator fencing then committed a paused control state, and the
installed enable function refused unreconciled effects. The receipt/status/
trace and a reconciliation diagnostic were archived; no guessed rollback,
automatic retry or invented completed outcome was applied.

The test reports a state requiring effect-specific operator reconciliation.
It does not implement a generic effects orchestrator, claim arbitrary remote
rollback, or promise exactly-once delivery. The observed counter receipt tells
the operator what happened; the caller's lost response remains an uncertain
outcome until deliberately reconciled.

Harness corrections, without reissuing the effect:

- Direct test containers have no Compose healthcheck field. An actual HTTP200
  readiness continuation verified the same already-running recipient before
  any producer request. A diagnostic import-name collision was avoided by naming
  the driver explicitly.
- The first native observer passed its unknown-status checks, then correctly
  refused the test's repeatable-read fencing transaction. The operator check was
  moved to a fresh READ COMMITTED connection, matching the existing adapter.
- A continuation initially waited on a lease already cleared by the unknown
  transition. Inspection confirmed unknown/attempt1/NULL lease; the next bounded
  status/fencing continuation used that existing state, never another producer.
- Cleanup's strict identity guard stopped before DB deletion because PostgreSQL
  serialized OID as JSON text. A bigint cast verified the exact same OID, owner
  and zero connections before completing removal. Ownership checks were retained.

All fixture containers, the exact owned DB and one private config volume were
removed after diagnostic archive. Two duplicate setup dumps were removed with
digest/size receipts. No new image, force/global prune, or unknown asset deletion.
All17 tracked live-site tables and canonical worker observations remained exact.
See `qualification.json`, `unknown-outcome.json`, `retry-budget-proof.json`,
`reconciliation-diagnostic.json`, and `cleanup.json`. Do not replay this fixture.
