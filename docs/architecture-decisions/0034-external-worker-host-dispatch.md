# ADR0034: approved host-to-worker dispatch

Date: 2026-11-01. Status: bounded transport implemented; native integration unqualified.
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
