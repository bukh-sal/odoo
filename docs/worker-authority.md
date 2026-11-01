# R1 operator worker authority

The private operator API is implemented in
`packages/platform_sdk/modular_platform/worker_publication.py`, with the dedicated
Linux-volume projector in `worker_projection.py`. Normal application HTTP requests
and artifact installation do not import these modules or obtain Docker authority.
The normal `tools/modular.py worker` commands now expose this boundary. The
inventoried guarded job process mounts authority read-only; the HTTP application
does not need the issuer mount. Actual remote Notes integration and the full
external recovery profile still require qualification.

The publisher reuses the existing independent `OperatorStore` OS owner/allowlist,
deployment/site authorization, approval lifetime and noninteractive policy. It keeps
its plans, durable publication intents/results, immutable key references and current
authority under that private store, outside application database recovery. A caller
prepares a plan, reviews its complete hash, then explicitly supplies that exact hash
to publish. Current policy, base generation, keys and runtime observation are checked
again; a consumed intent cannot be replayed. There is no web approval route.

The operator supplies the fixed local Compose policy. Enabling an endpoint verifies
the actual container image/RepoDigest, hardened reference command, user and public-only
mount, exact internal network/address/alias, healthy process, and actual public key,
scope and endpoint generation. Health JSON is not used as image attestation. Only
the fixed reference destination is supported. Application transport continues to pin
the observed numeric address and reauthorize around signing, I/O and final apply.

For a dedicated, already-created and independently owned Linux volume, the projector
uses one explicit, named, network-isolated helper with the exact existing native
image. It does not pull/build images or launch/stop the worker. It compares the actual
volume's prior document with the reviewed base, writes immutable keys, then atomically
replaces and fsyncs `authority.json`. The application mounts this volume read-only at
`/run/worker-authority` as UID10001. Private key files are owner-readable by that UID
and group-readable by root for later operator reconciliation; the worker receives a
separate public-key/configuration-only volume. The projector helper auto-removes;
its stdout/stderr remain in private operator records.

Suspension/revocation advances endpoint/publication generations and publishes a
disabled endpoint without inspecting or restarting the worker. Old snapshots fail
fresh selection/issuer checks. Already-sent pure computations can finish; they do
not become permission to apply a host result. Metadata lifecycle, original-actor
finalization and non-idempotent uncertainty remain separate required checks.

Crash handling is deliberately fail-closed: intent precedes runtime projection,
which precedes the host mirror and result receipt. If these disagree, neither a new
plan nor a retry silently overwrites the actual volume. Inspect the intent, volume,
mirror and worker, then reconcile explicitly. The full external recovery adapter is
still required. `prepare-bootstrap`, review and exact-hash `publish` initialize an
empty, unattached replacement volume from CURRENT independently owned authority,
preserving its generation, revocations and immutable key references. Changed
authority, changed volume identity, nonempty volumes and replay are refused.
Never restore older authority from an app DB backup. Full enabled-worker and
failure/crash reconciliation remain part of the external recovery qualification.

The CLI group takes `--store`, `--deployment-config` and `--worker-config` before
its action. The worker configuration is an OS-owned JSON file with exactly
`schema_version`, `deployment_id`, `site_id`, `runtime`, `authority_volume` and
`helper_image`; the helper must be the current native deployment image. Runtime
policy has the fixed project/service/network/public-config-volume/image/destination
fields documented by `DockerWorkerObservation`. No HTTP input supplies these paths.

Actions are `provision-keys`, `prepare`, `prepare-bootstrap`, `review`, `publish`
and `run-job-once`. Key provisioning reads bounded files from private OS directories;
it never prints private material or overwrites a different immutable key reference.
Publication requires the exact reviewed hash, interactive confirmation or explicit
`--noninteractive` with existing OS policy permission. A bootstrap plan copies
current authority, without enabling endpoints or resetting their generations.

`run-job-once` independently observes the current native image/DB/inventory, refuses
outdated runner/native bridge code before any claim, compares the mounted authority
with the current operator mirror, then starts the actual inventoried runner. The
runner still reconstructs and freshly authorizes the saved original actor. Only this
job process receives the authority mount. Its one-shot container auto-removes and
private stdout/stderr remain in the control store. This mount selection does not
claim to sandbox trusted Python plugins.

`evidence/G6/20261101-worker-publication-01/qualification.json` records real Compose,
reviewed generation1 publication, mounted signed HTTP, read-only enforcement, stopped
worker/generation2 revocation and mounted denial. Both test volumes and the worker
were retired. Six Linux OS/file/key negative/positive source checks also pass. This
is an unregistered synthetic provider scope; it does not qualify the installed Notes
bridge, metadata lifecycle, guarded runner, normal configuration rollout or recovery.

Later evidence in `20261101-worker-operator-01` proves actual CLI bootstrap at
generation2, current revocation preservation, wrong-hash/replay/nonempty refusal and
old-runner refusal. `20261101-core11-upgrade-01` proves the normal immutable core1.11/
SDK0.1.11 rollout, exact original data/history/file preservation, native Odoo views
and one normal original-actor read-only job without source substitution. The
authority volume is retained for integration; lease/error/revocation requalification
and the committed external Notes path remain required.

Current native runner qualification is now in `20261101-core12-runner-01`:
core1.12/SDK0.1.12 fixes bridge CANCELLED handling, preserves safe suspension/missing
codes, passes12 installed authority cases and seven actual process error/cancel
cases plus normal CLI execution. Cancellation means claim loss, with ordinary
bounded reaping; it never proves a remote computation stopped or rolled back.
Recorded death/reclaim/committed-demotion cases retain exact unchanged code paths.
The reference provider/connector require this corrected minimum. Metadata artifact
validation is ready in `20261101-external-artifact-01`; live metadata registration,
real scoped remote Notes jobs, degraded UI and full external recovery still remain.
