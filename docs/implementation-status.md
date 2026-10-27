# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-27T23:32:26.886278+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; HEAD at start of work: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; platform checkpoint commit pending. Use `git rev-parse HEAD` for current commit.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime locks not yet established.
- Current phase/gate: **A / G0 in_progress**. Latest passed gate: none.
- Active item: **A-02**. Next action: rebuild the curated image with the lifecycle harness, then bootstrap a fresh harness-owned database and verify HTTP login/assets.
- Working changes: initialization of this status/evidence/work-log; original planning specification preserved.

## Progress estimate

**Overall roughly 0%; release acceptance 0/99 passed; 5 R2 checks excluded.** Gate weights below sum to 100 and represent a rough effort estimate, not equal task counts or a completion guarantee. Estimate uses completed gate weight plus a conservatively assessed fraction of the active gate. Setup/checklists alone do not count as product acceptance. Update the estimate when meaningful deliverables pass; do not increase it based on time spent or number of files.

## Gate checklist

| Gate | Deliverable | State | Weight % | Prerequisite / evidence |
| --- | --- | --- | --- | --- |
| G0 | A: baseline | in_progress | 10 | none; docs/evidence/G0/20261027T2312Z/ |
| G1 | A1: feasibility | not_started | 10 | G0; not_run |
| G2 | B: contract freeze | not_started | 10 | G1; not_run |
| G3 | C: Notes and shell | not_started | 15 | G2; not_run |
| G4 | D: composition and Canvas | not_started | 10 | G3; not_run |
| G5 | E: lifecycle and packaging | not_started | 25 | G4; not_run |
| G6 | F: jobs/events/services | not_started | 10 | G5; not_run |
| G7 | G: qualification | not_started | 10 | G6; not_run |

## Work checklist

All items owned by the primary implementation agent. Later umbrella items are decomposed into bounded work at their gate, without changing gate weights silently. Changed paths and verification records are linked in the work log.

| ID | Deliverable | State | Acceptance | Dependencies | Next check |
| --- | --- | --- | --- | --- | --- |
| A-01 | Inspect tools, initialize Git and pin official upstream | passed | BOOT-02; OPS-03 | none | git checkout pinned commit; inspect source and Docker resources |
| A-02 | Build pinned Python/PostgreSQL baseline and lock dependencies | in_progress | BOOT-01..04 | A-01 | docker compose build and fresh database initialization |
| A-03 | Boot/login/assets and inventory automatic modules | not_started | BOOT-01..04 | A-02 | real HTTP/session and installed module report |
| A-04 | Run native model/extension install and schema migrations | not_started | ORM-01; VER-02 | A-03 | disposable native lifecycle harness |
| A-05 | Prove failed migration, uninstall and DB/filestore restore | not_started | MIG-02/06/07 | A-04 | fault/restore harness and attachment checks |
| A-06 | Exercise multiworker sync, repeat fresh boot and measure baseline | not_started | BOOT-02; TEN-01 | A-05 | second fresh build; benchmark; G0 evidence review |
| A1-01 | Workspace enforcement proof with asymmetric roles | not_started | FEAS-01/02 | G0 | gateway/RPC/browser/cross-worker tests |
| A1-02 | Neutral host/custom page and identity-chain proof | not_started | FEAS-03/04 | A1-01 | browser lifecycle and identity checks |
| B-01 | Freeze seven contract rows and compatibility fixtures | not_started | FREEZE-01..04 | G1 | contract tests and digest inventory |
| C-01 | Deliver Notes, identity and neutral shell vertical slice | not_started | ID; API; UI-01/09 | G2 | owning acceptance tests |
| D-01 | Deliver Notes Labels and custom Canvas | not_started | ORM; API-06; UI | G3 | packaged extension/browser contracts |
| E-01 | Deliver distribution, planner and recoverable executor | not_started | PKG; DEP; VER; LIFE; MIG; SEC; OPS | G4 | owning fault/security/restore acceptance |
| F-01 | Deliver jobs/outbox and separately operated worker | not_started | EVT; JOB; SVC | G5 | lease/failure/scopes/duplicate tests |
| G-01 | Qualify full R1 and reproduce release/runbooks | not_started | all R0/R1 | G6 | full mapped acceptance; fresh install and recovery |

## Blockers and limitations

No hard blocker currently. Docker is healthy (Linux/amd64); user increased allocation to 8 GB (8,290,807,808 bytes reported). Limits and exact setup are recorded; no global Docker settings were changed by the agent. Windows `python` is a Store alias; use the installed managed Python 3.12 interpreter or containers explicitly.

## Last material outcomes

1. Implementation goal created; Git initialized with official upstream remote.
2. Docker/Compose verified operational with no existing containers/images; installed Python 3.12 and 3.14 found.
3. Official pinned upstream commit fetched; checkout in progress.

## Resume capsule

- Working: specification, goal, local Git metadata, Docker engine. Product runtime has not yet booted.
- Source checkout and image pulls completed. Initial dependency/container build succeeded; rebuild with the current harness is next. No application container is running yet.
- Data: no application database or filestore created yet; no uncertain schema mutation.
- Next: run `tools/r0.py setup`, `build`, `bootstrap`, then `up` and `http` using installed Python 3.12. Inspect evidence on failure before retrying.
- Advance G0 only with section 5.3 lifecycle/restore/multiworker evidence. G1 and G2 precede substantial R1 implementation.
- Evidence identity: code/contracts/config/locks, excluding status/work-log/generated logs.

## Acceptance ledger

Every spec ID is assigned an owning phase. `not_run` is not a pass. Exact commands/procedures and source/environment evidence are bound as the owning phase is implemented; G2 freezes contract fixtures.

| ID | Primary phase | Result | Required observation | Procedure / evidence |
| --- | --- | --- | --- | --- |
| FEAS-01 | A1/G1 | not_run | Asymmetric workspace roles and record ownership are enforced through gateway and legacy model paths | not_run; procedure to be bound in owning phase |
| FEAS-02 | A1/G1 | not_run | Two tabs, warmed caches and cross-worker revocation preserve workspace/role boundaries | not_run; procedure to be bound in owning phase |
| FEAS-03 | A1/G1 | not_run | Minimal custom non-Owl page and native action coexist through the host adapter with correct routing/disposal | not_run; procedure to be bound in owning phase |
| FEAS-04 | A1/G1 | not_run | Browser attribution and supported call chains cannot expand authenticated authority | not_run; procedure to be bound in owning phase |
| FREEZE-01 | B/G2 | not_run | All seven section 5.5 contract rows have versioned schema/type/example paths and digests, with no critical authority/lifecycle TODO | not_run; procedure to be bound in owning phase |
| FREEZE-02 | B/G2 | not_run | Manifest, restricted version mapping, alias bindings and approval canonicalization fixtures pass | not_run; procedure to be bound in owning phase |
| FREEZE-03 | B/G2 | not_run | Frozen workspace/identity/UI contracts agree with passing G1 behavior and documented patch surface | not_run; procedure to be bound in owning phase |
| FREEZE-04 | B/G2 | not_run | Contract inventory maps owning phases, acceptance IDs, compatibility fixtures and change/invalidation rules | not_run; procedure to be bound in owning phase |
| BOOT-01 | A/G0 | not_run | Empty volumes initialize and an administrator can log in | not_run; procedure to be bound in owning phase |
| BOOT-02 | A/G0 | not_run | A second fresh build reproduces the declared inventory | not_run; procedure to be bound in owning phase |
| BOOT-03 | A/G0 | not_run | Explicit server-wide module choice works, including RPC omission if selected | not_run; procedure to be bound in owning phase |
| BOOT-04 | A/G0 | not_run | No excluded ERP application is unexpectedly installed | not_run; procedure to be bound in owning phase |
| BOOT-05 | E/G5 | not_run | Unexpected addon search-path content cannot bypass release inventory policy | not_run; procedure to be bound in owning phase |
| BOOT-06 | E/G5 | not_run | Worker startup does not silently migrate production state | not_run; procedure to be bound in owning phase |
| PKG-01 | E/G5 | not_run | Manifest validation does not import plugin code | not_run; procedure to be bound in owning phase |
| PKG-02 | E/G5 | not_run | Traversal, symlinks, duplicate normalized paths and ZIP bombs are rejected | not_run; procedure to be bound in owning phase |
| PKG-03 | E/G5 | not_run | Digest mismatch and same-version/different-artifact conflict are rejected | not_run; procedure to be bound in owning phase |
| PKG-04 | E/G5 | not_run | Unsigned artifacts follow the actual configured trust policy | not_run; procedure to be bound in owning phase |
| PKG-05 | E/G5 | not_run | Unknown sensitive schema fields and contract majors fail safely | not_run; procedure to be bound in owning phase |
| DEP-01 | E/G5 | not_run | Missing transitive dependency fails before any runtime mutation | not_run; procedure to be bound in owning phase |
| DEP-02 | E/G5 | not_run | Version conflict explains the incompatible constraints | not_run; procedure to be bound in owning phase |
| DEP-03 | E/G5 | not_run | Hard dependency cycle reports the cycle | not_run; procedure to be bound in owning phase |
| DEP-04 | E/G5 | not_run | Python dependency conflict fails the native release plan | not_run; procedure to be bound in owning phase |
| DEP-05 | E/G5 | not_run | Multiple service providers require an explicit binding | not_run; procedure to be bound in owning phase |
| DEP-06 | E/G5 | not_run | Optional absent/incompatible integration does not break the base plugin | not_run; procedure to be bound in owning phase |
| DEP-07 | E/G5 | not_run | Stale plan is rejected | not_run; procedure to be bound in owning phase |
| DEP-08 | E/G5 | not_run | Existing compatible locked versions are preserved unless update requested | not_run; procedure to be bound in owning phase |
| VER-01 | E/G5 | not_run | Invalid package version forms are rejected and numeric package/native order agrees | not_run; procedure to be bound in owning phase |
| VER-02 | E/G5 | not_run | Adjacent and skipped-release migrations run applicable scripts; fresh install does not simulate an upgrade | not_run; procedure to be bound in owning phase |
| ORM-01 | D/G4 | not_run | One packaged addon creates a model and another extends it | not_run; procedure to be bound in owning phase |
| ORM-02 | D/G4 | not_run | Extension upgrade preserves original and extension-owned values as specified | not_run; procedure to be bound in owning phase |
| ORM-03 | D/G4 | not_run | Duplicate field/contribution conflict is caught or deterministically rejected | not_run; procedure to be bound in owning phase |
| ORM-04 | D/G4 | not_run | Export/import preserves supported data and rejects unsafe scope reassignment | not_run; procedure to be bound in owning phase |
| ID-01 | C/G3 | not_run | Two workspaces cannot read/write/create/delete each other's private records | not_run; procedure to be bound in owning phase |
| ID-02 | C/G3 | not_run | Forged actor, database, company and workspace inputs do not grant access | not_run; procedure to be bound in owning phase |
| ID-03 | C/G3 | not_run | Export/search/attachments/autocomplete/batch/job paths enforce scope | not_run; procedure to be bound in owning phase |
| ID-04 | C/G3 | not_run | Service principal has no implicit administrator authority | not_run; procedure to be bound in owning phase |
| ID-05 | C/G3 | not_run | Revocation affects new and cached requests within the declared bound | not_run; procedure to be bound in owning phase |
| ID-06 | C/G3 | not_run | Workspace admin cannot install native code or run deployment operations | not_run; procedure to be bound in owning phase |
| ID-07 | C/G3 | not_run | Direct legacy RPC/model calls cannot bypass scope, authorization or supported suspension gates | not_run; procedure to be bound in owning phase |
| ID-08 | C/G3 | not_run | Two tabs on different workspaces and their caches/replies remain isolated | not_run; procedure to be bound in owning phase |
| ID-09 | C/G3 | not_run | One user is editor in A and viewer in B without global-group privilege leakage, including direct RPC | not_run; procedure to be bound in owning phase |
| ID-10 | C/G3 | not_run | Cross-worker membership/policy changes invalidate scoped rules and cached authorization within the declared bounds | not_run; procedure to be bound in owning phase |
| TEN-01 | E/G5 | not_run | Two test databases do not leak data or registry context | not_run; procedure to be bound in owning phase |
| TEN-02 | E/G5 | not_run | Incompatible native versions sharing one runtime are rejected | not_run; procedure to be bound in owning phase |
| LIFE-01 | E/G5 | not_run | Feature suspension retains native schema/data and blocks documented entry points | not_run; procedure to be bound in owning phase |
| LIFE-02 | E/G5 | not_run | UI/docs do not claim native overrides/imports are unloaded | not_run; procedure to be bound in owning phase |
| LIFE-03 | E/G5 | not_run | Required-provider suspension/removal shows the dependent closure | not_run; procedure to be bound in owning phase |
| LIFE-04 | E/G5 | not_run | Native uninstall requires explicit destructive approval and backup | not_run; procedure to be bound in owning phase |
| LIFE-05 | E/G5 | not_run | Upgrade permission expansion requires reapproval | not_run; procedure to be bound in owning phase |
| LIFE-06 | E/G5 | not_run | Artifact removal is blocked while a site still needs it | not_run; procedure to be bound in owning phase |
| MIG-01 | E/G5 | not_run | Failure before mutation preserves the previous working release | not_run; procedure to be bound in owning phase |
| MIG-02 | E/G5 | not_run | Failure after an internal commit enters recovery_required, not false rollback success | not_run; procedure to be bound in owning phase |
| MIG-03 | E/G5 | not_run | Executor crash is reconciled before a retry | not_run; procedure to be bound in owning phase |
| MIG-04 | E/G5 | not_run | Concurrent operations serialize or reject safely | not_run; procedure to be bound in owning phase |
| MIG-05 | E/G5 | not_run | Reusing operation ID does not repeat migrations | not_run; procedure to be bound in owning phase |
| MIG-06 | E/G5 | not_run | Restore recreates DB, filestore and previous release consistently | not_run; procedure to be bound in owning phase |
| MIG-07 | E/G5 | not_run | Destructive fixture uninstall proves the real deletion semantics | not_run; procedure to be bound in owning phase |
| MIG-08 | E/G5 | not_run | Old workers/jobs do not serve incompatible new schema | not_run; procedure to be bound in owning phase |
| MIG-09 | E/G5 | not_run | Restored queues remain fenced until externally completed effects are reconciled | not_run; procedure to be bound in owning phase |
| API-01 | C/G3 | not_run | Gateway exposes only declared methods and validates schemas | not_run; procedure to be bound in owning phase |
| API-02 | C/G3 | not_run | Idempotency repeats return the same outcome; changed input conflicts | not_run; procedure to be bound in owning phase |
| API-03 | C/G3 | not_run | Deadline/cancellation errors do not falsely imply rollback | not_run; procedure to be bound in owning phase |
| API-04 | C/G3 | not_run | Private ORM objects and stack traces do not cross public boundary | not_run; procedure to be bound in owning phase |
| API-05 | C/G3 | not_run | Concurrent same-key mutations and a crash before response do not duplicate the reference database effect | not_run; procedure to be bound in owning phase |
| API-06 | C/G3 | not_run | Consumers use named bindings to call v1 and v2 concurrently; missing/mismatched bindings never select latest | not_run; procedure to be bound in owning phase |
| API-07 | C/G3 | not_run | Forged browser plugin attribution and supported provider call chains cannot acquire broader actor/token/grant authority | not_run; procedure to be bound in owning phase |
| EVT-01 | F/G6 | not_run | Rolled-back writes produce no externally delivered success event | not_run; procedure to be bound in owning phase |
| EVT-02 | F/G6 | not_run | Duplicate delivery does not duplicate a deduplicated consumer effect | not_run; procedure to be bound in owning phase |
| EVT-03 | F/G6 | not_run | Unauthorized subscription or cross-workspace payload access fails | not_run; procedure to be bound in owning phase |
| JOB-01 | F/G6 | not_run | Reference idempotent DB job survives lease reclaim without duplicate effect; obsolete claims cannot commit | not_run; procedure to be bound in owning phase |
| JOB-02 | F/G6 | not_run | Revoked/suspended actor/plugin is checked before dispatch | not_run; procedure to be bound in owning phase |
| JOB-03 | F/G6 | not_run | Non-idempotent uncertain outcomes are reported for reconciliation | not_run; procedure to be bound in owning phase |
| UI-01 | C/G3 | not_run | Standard CRUD plugin uses the shared shell and components | not_run; procedure to be bound in owning phase |
| UI-02 | D/G4 | not_run | Custom non-Owl page works without a new core patch | not_run; procedure to be bound in owning phase |
| UI-03 | D/G4 | not_run | Direct links, refresh and back/forward work | not_run; procedure to be bound in owning phase |
| UI-04 | D/G4 | not_run | Unauthorized/disabled pages and service calls fail even if URL is known | not_run; procedure to be bound in owning phase |
| UI-05 | D/G4 | not_run | Repeated mount/dispose does not accumulate listeners or stale updates | not_run; procedure to be bound in owning phase |
| UI-06 | D/G4 | not_run | Failed plugin page offers recovery and does not trap the user | not_run; procedure to be bound in owning phase |
| UI-07 | D/G4 | not_run | Native release mismatch triggers controlled reload | not_run; procedure to be bound in owning phase |
| UI-08 | D/G4 | not_run | Generic SDK does not require company/partner/session internals | not_run; procedure to be bound in owning phase |
| UI-09 | C/G3 | not_run | Standard shell passes keyboard, contrast, zoom and RTL checks | not_run; procedure to be bound in owning phase |
| UI-10 | D/G4 | not_run | Unsaved-work and expired-session flows preserve a safe recovery path | not_run; procedure to be bound in owning phase |
| SVC-01 | F/G6 | not_run | Reference worker runs without Odoo import or database credentials | not_run; procedure to be bound in owning phase |
| SVC-02 | F/G6 | not_run | Worker timeout/crash leaves host healthy and feature degraded | not_run; procedure to be bound in owning phase |
| SVC-03 | F/G6 | not_run | Scoped token cannot change workspace/site by altering payload | not_run; procedure to be bound in owning phase |
| SVC-04 | F/G6 | not_run | Metadata register/suspend/unregister does not create a native addon, launch/stop a runtime or erase remote data | not_run; procedure to be bound in owning phase |
| SVC-05 | F/G6 | not_run | Operator-approved endpoint/image generation and audience/scoped credentials are verified; artifact metadata cannot override them | not_run; procedure to be bound in owning phase |
| SEC-01 | E/G5 | not_run | Plugin metadata cannot execute script in manager UI | not_run; procedure to be bound in owning phase |
| SEC-02 | E/G5 | not_run | CSRF/CORS/session/proxy/host defaults match the threat model | not_run; procedure to be bound in owning phase |
| SEC-03 | E/G5 | not_run | No secrets in artifacts, logs, lockfiles or browser bundles | not_run; procedure to be bound in owning phase |
| SEC-04 | E/G5 | not_run | Production profile disables database manager/listing and dev endpoints | not_run; procedure to be bound in owning phase |
| SEC-05 | E/G5 | not_run | Native trust warning accurately describes full process authority | not_run; procedure to be bound in owning phase |
| SEC-06 | E/G5 | not_run | A fabricated app-queue approval cannot authorize privileged executor actions | not_run; procedure to be bound in owning phase |
| SEC-07 | E/G5 | not_run | Exact-hash approvals expire/revoke correctly; stale targets/policy/authority and cross-operation replay are rejected | not_run; procedure to be bound in owning phase |
| SEC-08 | E/G5 | not_run | Application OS/container identity cannot write/read privileged approval/operator/secret stores beyond the redacted status channel | not_run; procedure to be bound in owning phase |
| OPS-01 | E/G5 | not_run | Operator can inspect journal when main app cannot boot | not_run; procedure to be bound in owning phase |
| OPS-02 | E/G5 | not_run | Documented restore works in a clean disposable environment | not_run; procedure to be bound in owning phase |
| OPS-03 | E/G5 | not_run | Build/source/license provenance is preserved | not_run; procedure to be bound in owning phase |
| ISO-01 | H/R2 | excluded_R2 | Hostile service cannot access host mounts, DB credentials or privileged sockets | not_run; procedure to be bound in owning phase |
| ISO-02 | H/R2 | excluded_R2 | Resource and network controls behave under abuse | not_run; procedure to be bound in owning phase |
| ISO-03 | H/R2 | excluded_R2 | Frontend origin/source/nonce/replay/stale-frame tests pass | not_run; procedure to be bound in owning phase |
| ISO-04 | H/R2 | excluded_R2 | Host cookies and DOM are unavailable to sandboxed frontend | not_run; procedure to be bound in owning phase |
| ISO-05 | H/R2 | excluded_R2 | Revocation and teardown invalidate runtime/bridge authority | not_run; procedure to be bound in owning phase |
