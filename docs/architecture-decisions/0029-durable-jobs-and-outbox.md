# ADR0029: native scheduler records with PostgreSQL leases and transaction fences

Date: 2026-10-29. Status: F-01a primitives qualified; remaining integration in progress, no complete G6 acceptance claim. Builds on ADR0003/0016/0025/0028 and specification11.6,13.4,14,25.5F.

G5 is complete. Its recovery profile deliberately rejects job/outbox tables and external installations. G6 must implement the actual adapters and extend that profile; retaining the rejection is not completion of jobs or recovery. Current source has service authorization and frozen worker JWT/request/response/endpoint contracts, but no durable scheduler or outbox. The host event SDK currently stores local callbacks without domain delivery.

Use native Odoo models in the existing core addon to own scheduler/outbox tables. These are site-owned internal control records, with explicit workspace/actor tags; they expose no generic ORM CRUD or arbitrary handler execution. Supported projections and mutations require separate current workspace authorization. The private SDK adapter uses parameterized SQL for atomic claims and fencing, without replacing the native ORM or adding a broker dependency. Business handlers run in fresh native environments as their current mapped actor, never through an administrator fallback.

The first bounded item, F-01a, is the durable primitive: native schema, atomic claim/lease generation, bounded attempts/backoff, cancellation, deadlines/progress, explicit uncertain/dead-letter/held states, dispatch pause generation, and a transactional outbox append. Verify it on a fresh owned native installation and real PostgreSQL with concurrent workers and an actual native business write. It does not by itself qualify the complete JOB/EVT/SVC requirements.

Claims commit in short transactions. Final business mutation acquires the current job row and dispatch-control row, checks owner/generation/release/lease/deadline/cancellation, executes the native handler, and validates the same fence before completing in the same transaction. Failure rolls back the business mutation and outcome together. A competing reclaimer cannot advance a generation while that transaction holds the job row. Computation or network requests happen outside that transaction and confer no authority to apply a result. Lost non-idempotent attempts become outcome_unknown and require reconciliation; they are never automatically repeated. No exactly-once external-effect promise is made.

Dispatch has an explicit site/release generation and starts paused. Maintenance blocks new enqueue/claim/finalization and invalidates old claims. Restored queues must be held, credentials invalidated and externally completed effects reconciled through the independent control path before a separately reviewed resume. G5's existing targets remain unchanged. A new G6 candidate and disposable environment qualify new native core schema; source existence cannot qualify deployment or recovery.

Outbox envelopes contain event ID/topic/schema, owner/aggregate, site/workspace, timestamp, correlation/causation and a minimized validated payload. The outbox append shares the producer transaction. Later F-01b adds authorized delivery/subscription, consumer deduplication, retention/retry/dead-letter/replay and the existing host-event facade, reusing native bus wakeups where useful. No global ordering is promised.

Remaining bounded items, in order:

| Item | Required output | Acceptance |
| --- | --- | --- |
| F-01a (passed) | Native durable job/outbox primitive; concurrent real database and native mutation proof | prerequisites for JOB-01/03 and EVT-01; durable-01/qualification.json |
| F-01b | Live actor/plugin/grant/release authorization, commit-safe reference events, scoped subscriptions and deduplicated consumer | JOB-01..03; EVT-01..03 |
| F-01c | Deterministic standalone stats worker, pinned image/own dependency inventory, frozen RS256/JSON boundary, timeout/restart/duplicate tests | SVC-01..03 |
| F-01d | Independently configured/approved endpoint, metadata-only artifact and lifecycle, host issuer/connector, native result/status screens and visible degradation | SVC-04/05; shared API/ID/lifecycle |
| F-01e | Actual dispatch drain, incompatible old-worker refusal, checkpoint/effect/credential reconciliation and reviewed restore/resume | MIG-08/09 and affected MIG-06/OPS-02 |
| F-01f | Integrated G6 walkthrough, source/image/security/provenance and acceptance review | all G6 checks; prerequisite for G7 |

Use the existing frozen endpoint, binding and worker contracts. Add/version/freeze any genuinely new public wire DTO before consuming it. Private scheduler storage is not a new public API. The reference worker receives only minimized text and a short-lived worker-audience credential, retains no text, has no Odoo import or database credentials, and never receives the issuer private key. No callback or human delegation token is introduced.

Standard record screens continue using native Odoo views. Canvas remains unchanged and minimal. Native Python and same-origin frontend code remain trusted; queue scopes, container names and grants do not constitute a hostile-code sandbox.

F-01a evidence: [qualification](../evidence/G6/20261029-durable-01/qualification.json), eleven actual native/PostgreSQL tests plus four Linux validation tests, four Windows checks, twelve direct HTTP CRUD refusals, native Odoo views, six protected target configurations and full protected G5 state/data audits. New owned site/image/core19.0.0.1.7; dispatch paused and all synthetic rows retained. Lease reclaim and late-finalization rollback are proven; this is not an OS-worker-kill or external outage claim. The full11 G6 acceptance checks remain not_run until the supported adapters are integrated.
