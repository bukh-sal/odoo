# ADR0038: reviewed reference-worker image transition

Date: 2026-11-02. Status: implementation/qualification in progress.
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
`../evidence/G6/20261102-core17-upgrade-01/`. This establishes the installed
default-profile regression only. Actual distinct-worker upgrade/recovery remains
required before SVC05 or this ADR's qualification can be complete.

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
remains revoked; a new successful metadata upgrade/enable/remote job is still
required. No automatic remote rollback or arbitrary-effect reconciliation is
claimed. Revocation was injected after the closed SQL restore, not before it.
