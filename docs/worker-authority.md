# R1 operator worker authority

The private operator API is implemented in
`packages/platform_sdk/modular_platform/worker_publication.py`, with the dedicated
Linux-volume projector in `worker_projection.py`. Normal application HTTP requests
and artifact installation do not import these modules or obtain Docker authority.
Thin CLI exposure and normal deployment/job-runner mount integration remain required
before this is a supported installed profile.

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
still required. A replacement empty volume cannot silently bootstrap an existing
generation: approved bootstrap from current independent authority must be added to
normal deployment integration. Never restore older authority from an app DB backup.

`evidence/G6/20261101-worker-publication-01/qualification.json` records real Compose,
reviewed generation1 publication, mounted signed HTTP, read-only enforcement, stopped
worker/generation2 revocation and mounted denial. Both test volumes and the worker
were retired. Six Linux OS/file/key negative/positive source checks also pass. This
is an unregistered synthetic provider scope; it does not qualify the installed Notes
bridge, metadata lifecycle, guarded runner, normal configuration rollout or recovery.
