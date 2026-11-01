# ADR0034: approved host-to-worker dispatch

Date: 2026-11-01. Status: transport/operator publication implemented and tested; native integration unqualified.
Parent F-01c/d/e2; spec13/14.3/14.5/14.6/22.4, SVC-02..05 and JOB-03.

The existing service gateway registers native model handlers only. The independent
document-statistics worker and frozen request/response/RS256/endpoint contracts
already exist. Reuse those contracts and PyJWT verifier; add a host transport,
then connect it to live approved endpoint/actor/resource/binding authorization.
No new wire contract, cryptographic format, orchestrator or Canvas feature is needed.

The private WorkerClient receives a host-owned current-authorization reader and
issuer lookup. Its reader must check the current actor, resource, workspace,
installation, feature, grant, binding and independently approved endpoint generation.
The transport cannot make an arbitrary endpoint DTO authoritative. Native code is
fully trusted; passing a callback is not a sandbox or evidence of native enforcement.
Actual native readers must use a fresh authority decision after detached computation,
not assume a repeatable-read snapshot observes a concurrently committed revocation.
No result can mutate host data until the existing original-actor finalization gate
has reauthorized it. Network computation belongs outside native database retries;
do not put external I/O into a handler that a database retry can replay silently.

An independently operator-owned egress map pins exact destination, installation,
site/workspace, image digest, endpoint generation and observed internal IPv4 addresses.
Connect to a pinned numeric IP and preserve the configured Host header. Runtime DNS,
redirects, proxy environment settings and package/browser URLs do not select egress.
This local Compose profile refuses global, loopback, link-local and other special
addresses. The operator must verify actual image/network identity when creating or
changing this generation; health JSON is not image attestation. Address changes
require a new approved generation. The application receives no Docker authority.

Issue fresh 120-second worker-audience RS256 credentials after current authorization,
then recheck before sending. Bind the request entirely from the authorized scope;
caller input cannot supply a different site, workspace, installation or generation.
Bound request/response bytes, apply an absolute network deadline, reject redirects,
validate the frozen response and both correlation IDs, then reauthorize before return.
Failures retain whether a request might have reached the worker; timeout never proves
remote rollback. Reference statistics are deterministic and have no remote external
effect. Non-idempotent work still needs F-01e2's durable uncertainty reconciliation.

Seven source tests include actual RS256 verification and a real local HTTP worker
exchange; network selection is explicitly mapped by that test fixture only.
They do not qualify Odoo readers, host issuer provisioning, metadata-only registration,
Notes alias/command/job, runtime image attestation, slow/degraded UI or recovery.
Implement those next. Before deploying added SDK/native integration, increment the
owned runtime versions and use the established reviewed immutable lifecycle path.

Native authority prerequisite: external_authority.py reuses the actual _locked_scope, frozen binding validator and technical-origin intersection. Existing installation/feature/binding/grant tables suffice; no fabricated native addon or extra endpoint business model is needed for an external provider. The independently published OS authority projection remains the approval source. Eight real native/PG source-module cases pass pending policy revocations, scoped positive path and forged/mismatched contexts, all rolled back with original queue/business/metadata rows exact. The module is not yet wired or deployed; tests deliberately do not claim independent publication/issuer or full service lifecycle. Its single test container was retired after diagnostics capture.

The application read-side projection uses a host-owned absolute directory with authority.json and fixed keys/<validated-reference>.pem files. Its private version1 envelope binds deployment/site/publication generation and bounded endpoint entries; each entry embeds the unchanged frozen endpoint DTO, observed numeric addresses and key ID. Reads are fresh and snapshots also bind the public-key fingerprint. Issuer access reselects current scope/publication before and after key parsing, verifies a matching RSA private/public pair, and never accepts arbitrary paths or public keys as signing keys. The existing operator path-link guard and strict JSON loader are reused. The privileged publisher must establish current approval, actual image/address verification, immutable key references/atomic generation changes and a read-only runtime mount; validation is not attestation. Host recovery must retain current independent authority rather than restore older key/endpoint approval from a database checkpoint. Seven real filesystem/key tests pass; no publisher or native bridge is yet installed.

Detached bridge implementation: native Invocation now carries a server-selected database field. compute stamps private database/claim/handler/version/fingerprint provenance from the actual Invocation, overriding any preexisting context key. external_job opens a fresh cursor for each current claim/fingerprint/original-actor/resource/binding/OS-snapshot check and rolls it back before remote I/O. It re-prepares the original resource and refuses changed input/revision, cancelled/expired/reclaimed claims and changed publication/key snapshots. Only the fixed worker schema crosses the remote boundary. Existing finish_one still reauthorizes and commits any job effect. The guarded runner preserves safe specific compute error codes rather than hiding worker outages as INTERNAL_ERROR. Core source version1.11 requires immutable rollout; JOB01/02 source evidence is invalidated pending targeted installed requalification. Four real native provenance/finalization/role/error-code tests pass; they do not exercise the entire remote bridge or runner error path yet.

The optional `org.example.notes_stats` connector now has a dedicated abstract
Odoo service model (`mp.example.notes.stats`) and no stored fields/table. This
keeps its own current feature/installation and base Notes guards ahead of gateway
idempotency replay. Attaching only private handlers to Notes would leave the
generic pre-replay model guard checking the wrong plugin. Its read-only job is
authorized through its self-bound `status` method, avoiding re-entry into the
active `analyze` provider-chain target. The resource handler reads Note body via
the declared/granted Notes service and requires the expected revision in prepare
and final apply. Compute uses the existing detached bridge; the only saved result
is revision-tagged statistics. The payload does not persist Note text. Status
first authorizes the Note and selects only the current actor/workspace/connector's
latest job, then delegates to the existing original-actor job status guard.

Connector source qualification loads its actual abstract model into one isolated
native registry and uses the existing database/identity/binding/queue/finalization
primitives. Seven cases pass; every metadata/business/queue mutation rolls back.
Four actual reference archives validate and reproduce; the previous three remain
byte-identical to the retained assembler's output. No shared frozen contract or
default distribution policy changed. The shipped connector schema reuses frozen
document and worker shapes. There is no new frontend yet: a small existing native
detail-slot action is deferred until it can demonstrate the real remote path.
Independent publisher, metadata-only lifecycle, committed bridge and installed
runner/error/recovery tests remain required. These source results grant no new
SVC/JOB acceptance and do not replace the immutable lifecycle rollout.

Operator publication is now implemented, superseding the earlier publisher gap.
It reuses OperatorStore's actual OS owner/target/policy checks and process locks,
requires the exact prepared plan hash, expires reviews, re-observes current runtime
identity/addresses/public-key configuration and refuses replay or stale generations.
Immutable key references and durable intent/result files stay outside app restore.
An explicit projector updates an independently labeled dedicated Linux volume using
the exact existing native image, no network, no worker control, atomic replacement
and fsync. The nonroot application mounts it read-only; the worker mounts public
configuration only. Revocation does not require a running worker. Real Compose
publication/signed dispatch/read-only denial/outage revocation pass, then all test
containers/volumes are retired. Six current-source Linux OS/file/key checks pass.
See `../worker-authority.md` and worker-publication-01/qualification.json. This
unregistered scope is a boundary prerequisite, not installed SVC/JOB qualification.
Thin operator CLI, reviewed normal deployment/runner mounts, replacement-volume
bootstrap/reconciliation, metadata lifecycle and the committed Notes bridge remain.

Normal operator integration is now implemented. The new worker CLI delegates to
the independent publisher, including explicit exact-hash bootstrap of an empty,
unattached replacement volume from CURRENT OS authority. Bootstrap preserves
generation/revocation, refuses changed authority or volume identity, nonempty
volumes and replay. Disabled entries remain publishable when retired key files
are absent. Eight actual Linux store/file/key cases and five CLI regressions pass.
The actual CLI bootstrapped retained generation2 and refused wrong hashes/replay/
nonempty volume and the old runner before any claim.

Only the guarded native job process needs the authority volume; enqueue/status
HTTP handlers do not read signing material. Keep the normal HTTP app topology
unchanged and attach the current approved volume read-only through the operator's
fixed `run-job-once` path. Independent image/database/inventory and native bridge
source checks precede process creation; the inventoried startup/claim/finalization
guards still apply. No artifact or app request selects mounts or Docker commands.
This reduces unnecessary key exposure without claiming native-code containment.

The first core1.11 candidate was rejected before stage enrollment because SDK
projection still advertised0.1.10. Correcting its explicit version constant and
rebuilding produced a strictly admitted core1.11/SDK0.1.11 image; native plugin
artifacts/manifests, Python and distribution policy stayed exact. The reviewed
same-DB checkpointed core-only upgrade completed config9/dispatch40, preserving
27Notes/44event envelopes/five old jobs/all46old files and scoped installations/
bindings. Native Odoo list/form reads in all three workspaces and scoped/foreign
HTTP checks pass. One real normal CLI job completed once as its original actor
using the installed runner, with no source substitution or business edit. This
does not yet restore JOB01/02: installed lease/kill/stale-claim, actor revocation
and compute-error paths still require targeted qualification. External metadata,
connector installation, real remote jobs and complete recovery remain required.
