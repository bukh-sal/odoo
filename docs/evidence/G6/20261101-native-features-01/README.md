# Checkpointed native feature changes with durable work

F-01d prerequisite G6-QUEUED-NATIVE-FEATURE-01, spec §§9.1, 10.5, 13, 14.6;
ADR0034. This is source qualification, not an installed lifecycle operation.

`qualification.json` / attempt04: ten real PostgreSQL rollback cases pass against
the owned populated database, using current candidate plans/projection/planning/
feature writer modules in an isolated existing-container process. All19 original
table row hashes and protected deployment configuration hashes remain exact.
No new Docker assets are created; PostgreSQL sequences may advance.

New `prepare_current_feature` plans request coordinated backup. OperatorStore
recognizes the existing full journal for those plans while retaining the historical
short journal for old no-backup native plans. The legacy executor refuses queue
tables before reservation. The new NativeFeatureExecutor reuses the existing
NativeExecutor loop, including independent approval, ingress/dispatch fencing,
drain, checkpoint, reconciliation, worker readiness, publication and conservative
traffic fence. It skips native install/upgrade/unload. Its image/source preflight
refuses an incompatible image before reservation. Plan display reflects the host
worker restart. Unchanged-release recovery admits these new checkpointed features
under its existing pre-mutation/no-replacement guards.

The common availability/grant/audit SQL is shared with the unchanged conservative
legacy gate. The coordinated entry point independently checks the exact plan/base
state, database/site/deployment/inventory, raw metadata preimage, unchanged release/
bindings/endpoints, paused dispatch and absence of running/uncertain work or leased
events before applying feature changes. Only declared exact enable grant reapproval
is accepted. Caller transaction ownership preserves atomicity; no native schema,
business record, remote request or external runtime is controlled by the writer.

Ten SQL cases cover suspend/enable preservation, enable grant reapproval, legacy
queue refusal, enabled dispatch, running/uncertain jobs, leased events, wrong
database/deployment/inventory, stale/replayed input, missing checkpoint flag and a
fault after feature/audit SQL. Additional host checks pass: six new feature adapter/
planning/journal checks, six lifecycle-planning, two legacy feature journals, eight
metadata adapter, thirteen plan and eighteen external planning checks:53host plus
10SQL =63. Temporary OS journals/locks/reviews are real where their fixtures specify
them; checkpoint/replacement effects in the journal test are fixtures. No actual
coordinated backup/restore/runner/readiness/traffic operation is claimed. Frozen
94files/eight contract rows remain unchanged and passing.

Attempt01 stopped before tests because a reused snapshot helper imported an
uninstalled external-planning module. Its process is terminal; no test mutation
ran. Attempt02 exposed fixture defects: timestamp formatting violated the existing
frozen UTC pattern, and Labels was nominated in C where it is not installed. A
read-only current-state observation confirmed installed Labels scopes A/B; the
grant fixture now uses A and the canonical UTC timestamp. Attempt03 passes all10
SQL cases. Attempt04 includes the current candidate plans module too, extending
source coverage from the earlier deployed-plan dependency, and passes all10 again.
Failed report restoration flags were derived conservatively from test success;
every actual transaction rolls back and the passing report verifies row hashes.
Initial host fixtures omitted a real path/display shape and one required journal
publication step; fixtures were corrected, production guards preserved.

Next: bump core/SDK coherently to.13, build and independently admit the immutable
core-only candidate while retaining all current native artifacts/Python/policy,
then perform actual reviewed rollout and native feature qualification. Follow with
metadata registration/connector/remote/degraded/lifecycle/recovery and explicit
changed-worker-image compatibility. No SVC acceptance is added by these tests.
