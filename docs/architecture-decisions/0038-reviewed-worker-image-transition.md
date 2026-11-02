# ADR0038: reviewed reference-worker image transition

Date: 2026-11-02. Status: qualified for the R1 stateless reference profile.
Scope: G6 F-01d, spec14.6/SVC05; no new public wire contract or runtime control.

The current planner requires a matching approved new-image endpoint before a
metadata upgrade. The maintenance adapter simultaneously requires the running
image to match old installed metadata. This prevents a real changed-image upgrade.

The operator first suspends every affected provider workspace, separately changes
the worker/runtime and independently approves its new endpoint/image. Normal host
record screens remain available; service dispatch is blocked by feature gates.
The metadata upgrade then uses the existing manager/request/review/approval path.
The installer still neither pulls images nor controls the external process.

Read-only planning must expose the real approved new image before a plan exists.
Projection may therefore retain an image mismatch for this reference installation
only while every installed workspace scope is suspended. Site/configuration and
health/image consistency checks still apply. No synthetic old endpoint is used;
the current independent endpoint is recorded in the plan. Selecting the upgrade
requires its new artifact to match that endpoint. This read-only observation does
not opt into the private maintenance profile or enable service availability.

A private maintenance context may recognize the exact old metadata while the
approved target worker runs. It is derived from the protected operation store,
not a request field. It binds operation/plan hash, base/target release pins,
installation and complete workspace map, old/new artifact/manifest/image identities.
The target keeps the same reference protocol/configuration; all provider features
must be suspended. Apply requires the exact reviewed endpoint and fresh healthy
new-image observation. Recovery may retain newer independent endpoint revocations;
it still requires the same target image and a new current-state resume review.

The private profile explicitly identifies this transition. The database child
rechecks its actual old manifest/artifact and complete suspended feature footprint.
Unknown effects/credentials remain fenced. After new metadata publishes, ordinary
same-image validation applies again. Ordinary observations without this reviewed
context never admit a mismatch; no general degraded/unknown-service bypass exists.

Qualification must cover rejected active/unapproved/stale/third-image/partial-scope
cases, retained default profiles, a real distinct worker-image upgrade and recovery
boundaries. Source tests alone do not pass SVC05. Version owned SDK/core code before
an immutable rollout; retain old working/current checkpoint assets until proved.

Source qualification: `../evidence/G6/20261102-worker-image-transition-01/`
records 98 passing targeted tests and the unchanged 97-file contract freeze.
Core17 was normally staged/reviewed/approved/applied under operation
`6348ddd4-f48f-4793-9adf-13ef14918de3`; native epoch20/control101 retains the
existing provider/connector, all 29 terminal jobs, 30 Notes, schema/files and
independent worker/publication7. Native views and old-release refusals pass in
`../evidence/G6/20261102-core17-upgrade-01/`. That rollout established the installed
default-profile regression; the following records establish the actual different
worker image transition, recovery and final success path.

Actual transition/recovery evidence now lives in
`../evidence/G6/20261102-worker-image-upgrade-01/`. A separate compatible image548202
and metadata0.1.2 were approved after all provider scopes were suspended. Actual
unapproved/old/third-image and default maintenance refusals passed, followed by
installed native acceptance of the exact stored transition. The real metadata
commit was faulted before readiness. Fresh native22 restored metadata0.1.1 and
all29job outcomes/30Notes/native/auth/history/48files while the new worker/image
and publication9 remained unchanged. Independent revocation10 then invalidated
an unexpired resume review. A fresh review resumed host records with that current
revocation retained and the provider still suspended. The original failed plan
remains revoked; the success path below uses a new metadata upgrade/enable and
ordinary remote job. No automatic remote rollback or arbitrary-effect reconciliation is
claimed. Revocation was injected after the closed SQL restore, not before it.

The final success path is qualified in
`../evidence/G6/20261102-worker-image-success-01/qualification.json`: separate
publicconfig9/approval11, NEW normal metadata0.1.2 upgrade/enable at native23/control114,
strict default profile restored, actual current-generation/audience/scope/key
checks and an ordinary original-user remote job completed once. All old outcomes,
native/auth/history and48files remained. A current installed rollback-only check
still refuses unknown effects. The obsolete worker05/container/public volume and
22terminal containers were retired after diagnostics; current and real checkpoint
image roles remain. SVC05 passes; SVC02/rendering/full G6/G7 are separate.
