# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-28T03:45:29.350697+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **D / G4 in_progress**. Latest passed gate: **G3**, see `evidence/G3/20261028t011619z/gate-G3.json`.
- Active item: **D-01**. G4 native install/provision and0.1.1 patch/register complete;6 API groups and real Canvas/Labels browser subset passed. Next custom dirty/conflict/failure/theme/locale/history checks, Labels0.2 migration/import/export, package/model conflict proof. No process pending; never repeat initialization/G4 provisioning.
- Working changes: G2 revision5 (de893113),64 files/19tests/typecheck passed. G4 runtime unverified; actual package-byte installation through bounded repository assembler. G5 owns general hostile-archive/trust/executor validation.

## Progress estimate

**Overall roughly 49%; release acceptance 28/99 passed; 5 R2 checks excluded.** Gate weights below sum to 100 and represent a rough effort estimate, not equal task counts or a completion guarantee. Estimate uses completed gate weight plus a conservatively assessed fraction of the active gate. Setup/checklists alone do not count as product acceptance. Update the estimate when meaningful deliverables pass; do not increase it based on time spent or number of files.

## Gate checklist

| Gate | Deliverable | State | Weight % | Prerequisite / evidence |
| --- | --- | --- | --- | --- |
| G0 | A: baseline | passed | 10 | `evidence/G0/20261027t234238z/gate-G0.json` |
| G1 | A1: feasibility | passed | 10 | `evidence/G1/20261028t003753z/gate-G1.json` |
| G2 | B: contract freeze | passed | 10 | `evidence/G2/20261028T032804708309Z/gate-G2.json` |
| G3 | C: Notes and shell | passed | 15 | `evidence/G3/20261028t011619z/gate-G3.json` |
| G4 | D: composition and Canvas | in_progress | 10 | G3; not_run |
| G5 | E: lifecycle and packaging | not_started | 25 | G4; not_run |
| G6 | F: jobs/events/services | not_started | 10 | G5; not_run |
| G7 | G: qualification | not_started | 10 | G6; not_run |

## Work checklist

All items owned by the primary implementation agent. Later umbrella items are decomposed into bounded work at their gate, without changing gate weights silently. Changed paths and verification records are linked in the work log.

| ID | Deliverable | State | Acceptance | Dependencies | Next check |
| --- | --- | --- | --- | --- | --- |
| A-01 | Inspect tools, initialize Git and pin official upstream | passed | BOOT-02; OPS-03 | none | git checkout pinned commit; inspect source and Docker resources |
| A-02 | Build pinned Python/PostgreSQL baseline and lock dependencies | passed | BOOT-01..04 | A-01 | docker compose build and fresh database initialization |
| A-03 | Boot/login/assets and inventory automatic modules | passed | BOOT-01..04 | A-02 | real HTTP/session and installed module report |
| A-04 | Run native model/extension install and schema migrations | passed | ORM-01; VER-02 | A-03 | disposable native lifecycle harness |
| A-05 | Prove failed migration, uninstall and DB/filestore restore | passed | MIG-02/06/07 | A-04 | fault/restore harness and attachment checks |
| A-06 | Exercise multiworker sync, repeat fresh boot and measure baseline | passed | BOOT-02; TEN-01 | A-05 | second fresh build; benchmark; G0 evidence review |
| A1-01 | Workspace enforcement proof with asymmetric roles | passed | FEAS-01/02 | G0 | gateway/RPC/browser/cross-worker tests |
| A1-02 | Neutral host/custom page and identity-chain proof | passed | FEAS-03/04 | A1-01 | browser lifecycle and identity checks |
| B-01 | Freeze seven contract rows and compatibility fixtures | passed | FREEZE-01..04 | G1 | contract tests and digest inventory |
| C-01 | Site/session/installation metadata and shared identity adapter | passed | ID; FREEZE-03 | G2 | real site bootstrap, metadata and role probes |
| C-02 | Notes/revisions and schema-validated registered gateway/idempotency | passed | ID; API | C-01 | real concurrent gateway/native RPC and scope tests |
| C-03 | Neutral shell with native list/form and frozen host facade | passed | UI-01/09; ID-08 | C-02 | browser CRUD/deep links/theme/session/disposal |
| C-04 | Qualify G3 integration, authority and API outcomes | passed | ID; API; UI | C-03 | evidence and source review before G3 pass |
| D-01 | Deliver Notes Labels and custom Canvas | in_progress | ORM; API-06; UI | G3 | packaged extension/browser contracts |
| E-01 | Deliver distribution, planner and recoverable executor | not_started | PKG; DEP; VER; LIFE; MIG; SEC; OPS | G4 | owning fault/security/restore acceptance |
| F-01 | Deliver jobs/outbox and separately operated worker | not_started | EVT; JOB; SVC | G5 | lease/failure/scopes/duplicate tests |
| G-01 | Qualify full R1 and reproduce release/runbooks | not_started | all R0/R1 | G6 | full mapped acceptance; fresh install and recovery |

## Blockers and limitations

No hard blocker currently. Docker is healthy (Linux/amd64); user increased allocation to 8 GB (8,290,807,808 bytes reported). Limits and exact setup are recorded; no global Docker settings were changed by the agent. Windows `python` is a Store alias; use the installed managed Python 3.12 interpreter or containers explicitly.

## Last material outcomes

1. G0 passed at `3069e03f`; pinned curated runtime and recovery evidence retained.
2. G1 passed: 26 backend checks, real two-tab/native/custom browser proof, 40 denied post-revocation requests across two workers, and open-page revoked data cleared in <=5.27 seconds.
3. Default builder policy regression preserved frozen R0 inventory. No ORM/registry/loader/frontend source patch was needed for G1.

## Resume capsule

- Passed G0 `3069e03f`, G1 `73d8ebd2`, G3 `e49d3a6b`; current G2 major1 revision5 `de893113`,19 tests/64 frozen files/typecheck, evidence G2/20261028T032804708309Z. G4 D-01 active; no later gate passed. Rough49%,28/99 release acceptance,5 R2 exclusions. G4 working checkpoint pending commit.
- R1 same site: project mp-r0-r1396163208bf1, database mp_disposable_r0_r1_396163208bf1, image modular-platform:r1, localhost:18071. Operational evidence **docs/evidence/G4/20261028t033154z**, G3 history retained. State .local/r1/state.json: install_status seeded, shell_install_status installed, view_refresh_1 passed, g4_install_status provisioned, g4_patch_status registered. DO NOT repeat init/seed/install-shell/install/resume-install/provision/update-patches/register-patches. No pending process/schema mutation. Latest image build034051890770Z/up034118497837Z.
- Active next: custom Canvas dirty/conflict/failed-mount recovery/theme/locale/history/cancellation; Labels0.2 migration/native import-export preserves base/extension fields; artifact/model contribution conflict checks and composition gate review. Stay in G4; G5 owns general hostile archive/trust/planner/independent approval/executor/recovery, G6 jobs/outbox/worker, G7 full release/runbooks. Do not inflate acceptance from WIP.
- G4 implemented: strict typed actor-preserving nested provider frames; Notes publishes documents1.0/2.0 concurrently; Labels owns x_notes_labels and compiled provider detail action/command; plain DOM Canvas consumes documents2.0 and boards1.0 via frozen host. One reference board per explicit workspace, optional board_id selects it. Native/plugin0.2.0 Notes,0.1.1 Labels/Canvas; .mplug bytes assembled from repository-only inputs, inventory verified and addon source extracted into image. Metadata uses actual outer digests (G4 fixture packages), not development-source. This narrow assembler is not the G5 hostile-archive validator or executor.
- Native initial install failure: access.csv inferred model access. SQL033408957067Z proved new addons uninstalled/no new fields/table and three original notes intact. Fixed CSV filename, guarded resume only new addons passed033506344277Z; one-time provision033508752008Z. Later field-prefetch guard wrongly blocked base Notes during Labels suspension; fixed via native _has_field_access. Native browser initially accumulated error dialogs; added Owl child-page boundary. Rebuilt with new numeric versions0.1.1 to avoid same-version/different bytes. Guarded patch update034113533345Z and registration034116120746Z passed. Never repeat those mutations.
- Current API proof034121516830Z-composition-api.json:6 groups pass concurrent exact majors, strict DTO/binding failure, Labels base-call chain/current actor/revocation/idempotency, nested grant revocation no effect, board ownership/CAS/foreign references/duplicate IDs,8 same-key saves one revision, suspended extension denies explicit field/action but base Notes stays usable and field/data retained. Normal policies restored; test note deleted. G3 Notes/admin/boundary/crash regression still available under G3; recheck changed paths before G4 pass.
- Browser tab6/r1ConfirmTab currently Welcome note in A with labels R1/Verified, revision2/body retained. Journal UUID d8243a62-f8ff-46d6-9998-9a2c35f592a0 remains revision2. Tab5/r1BTab Canvas B viewer. localhost cookie hostname isolates R0/G1. Restore browser docs after compaction; mark handoff each turn. Only browser automation, never Codex/password-manager native windows. Generated password only ignored .local/r1/bootstrap-password; never print/save.
- Browser G4 subset browser-composition-progress.json/screenshots: added card Qualify the Canvas contract linked to Welcome, moved doing/saved8, refresh retained;3 native/custom cycles then ArrowDown+one Ctrl+S moved done and revision8->9 (independent keyboard-board-readback.json). A board now two cards/revision9, B board one card/revision1. Viewer has no add/move/delete and Save disabled. Link navigated public note ID; Labels dialog command persisted R1/Verified. No console errors. Remaining dirty/conflict/mount-failure/theme/locale/history checks not yet claimed.
- Migration fixture from .local/r1/g4-fixtures.json is a separate note Labels migration fixture with body Base content must survive the extension upgrade., labels Important/Next and revision1. Preserve it for planned0.2 extension migration; do not normalize it early. G4 fixture records hold current/previous package digests and binding IDs. Never use g4_seed again. Current user roles Alice editorA/viewerB, Bob editorB, Outsider revoked, Worker no browser business authority; Personal/en-US/UTC.
- Contract inventory current revision5; changing frozen boundaries requires ADR/revision/fixtures/consumers and affected qualification. Commands .venv/Scripts/python.exe tools/check_contract_freeze.py; -m unittest discover -s tests -p test_contracts.py; npm --prefix packages/host_sdk run check (Node in PATH). New board/slot/command/v2 schemas already frozen; no reason to expand public API without an owning requirement.
- R0/G1 sites/images remain separate on127.0.0.1:18069/18070; prior default inventory3942/G13963 file regression passed. Avoid repeating completed lifecycle for unrelated product changes. Docker8GB healthy, no global settings changed. Python shell is Store alias; use isolated .venv/Scripts/python.exe explicitly. Raw credentials/backups/downloads remain local/ignored.

## Acceptance ledger

Every spec ID is assigned an owning phase. `not_run` is not a pass. Exact commands/procedures and source/environment evidence are bound as the owning phase is implemented; G2 freezes contract fixtures.

| ID | Primary phase | Result | Required observation | Procedure / evidence |
| --- | --- | --- | --- | --- |
| FEAS-01 | A1/G1 | passed | Asymmetric workspace roles and record ownership are enforced through gateway and legacy model paths | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-02 | A1/G1 | passed | Two tabs, warmed caches and cross-worker revocation preserve workspace/role boundaries | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-03 | A1/G1 | passed | Minimal custom non-Owl page and native action coexist through the host adapter with correct routing/disposal | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-04 | A1/G1 | passed | Browser attribution and supported call chains cannot expand authenticated authority | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FREEZE-01 | B/G2 | passed | All seven section 5.5 contract rows have versioned schema/type/example paths and digests, with no critical authority/lifecycle TODO | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T032804708309Z/gate-G2.json` |
| FREEZE-02 | B/G2 | passed | Manifest, restricted version mapping, alias bindings and approval canonicalization fixtures pass | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T032804708309Z/gate-G2.json` |
| FREEZE-03 | B/G2 | passed | Frozen workspace/identity/UI contracts agree with passing G1 behavior and documented patch surface | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T032804708309Z/gate-G2.json` |
| FREEZE-04 | B/G2 | passed | Contract inventory maps owning phases, acceptance IDs, compatibility fixtures and change/invalidation rules | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T032804708309Z/gate-G2.json` |
| BOOT-01 | A/G0 | passed | Empty volumes initialize and an administrator can log in | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
| BOOT-02 | A/G0 | passed | A second fresh build reproduces the declared inventory | `tools/r0_repro.py`; `evidence/G0/20261027t234238z/20261028T001455995688Z-reproduction-summary.json` |
| BOOT-03 | A/G0 | passed | Explicit server-wide module choice works, including RPC omission if selected | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
| BOOT-04 | A/G0 | passed | No excluded ERP application is unexpectedly installed | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
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
| ID-01 | C/G3 | passed | Two workspaces cannot read/write/create/delete each other's private records | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-02 | C/G3 | passed | Forged actor, database, company and workspace inputs do not grant access | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-03 | C/G3 | not_run | Export/search/attachments/autocomplete/batch/job paths enforce scope | not_run; procedure to be bound in owning phase |
| ID-04 | C/G3 | passed | Service principal has no implicit administrator authority | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-05 | C/G3 | passed | Revocation affects new and cached requests within the declared bound | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-06 | C/G3 | not_run | Workspace admin cannot install native code or run deployment operations | not_run; procedure to be bound in owning phase |
| ID-07 | C/G3 | passed | Direct legacy RPC/model calls cannot bypass scope, authorization or supported suspension gates | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-08 | C/G3 | passed | Two tabs on different workspaces and their caches/replies remain isolated | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-09 | C/G3 | passed | One user is editor in A and viewer in B without global-group privilege leakage, including direct RPC | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| ID-10 | C/G3 | passed | Cross-worker membership/policy changes invalidate scoped rules and cached authorization within the declared bounds | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
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
| MIG-07 | E/G5 | passed | Destructive fixture uninstall proves the real deletion semantics | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
| MIG-08 | E/G5 | not_run | Old workers/jobs do not serve incompatible new schema | not_run; procedure to be bound in owning phase |
| MIG-09 | E/G5 | not_run | Restored queues remain fenced until externally completed effects are reconciled | not_run; procedure to be bound in owning phase |
| API-01 | C/G3 | passed | Gateway exposes only declared methods and validates schemas | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| API-02 | C/G3 | passed | Idempotency repeats return the same outcome; changed input conflicts | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| API-03 | C/G3 | not_run | Deadline/cancellation errors do not falsely imply rollback | not_run; procedure to be bound in owning phase |
| API-04 | C/G3 | passed | Private ORM objects and stack traces do not cross public boundary | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| API-05 | C/G3 | passed | Concurrent same-key mutations and a crash before response do not duplicate the reference database effect | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| API-06 | C/G3 | not_run | Consumers use named bindings to call v1 and v2 concurrently; missing/mismatched bindings never select latest | not_run; procedure to be bound in owning phase |
| API-07 | C/G3 | not_run | Forged browser plugin attribution and supported provider call chains cannot acquire broader actor/token/grant authority | not_run; procedure to be bound in owning phase |
| EVT-01 | F/G6 | not_run | Rolled-back writes produce no externally delivered success event | not_run; procedure to be bound in owning phase |
| EVT-02 | F/G6 | not_run | Duplicate delivery does not duplicate a deduplicated consumer effect | not_run; procedure to be bound in owning phase |
| EVT-03 | F/G6 | not_run | Unauthorized subscription or cross-workspace payload access fails | not_run; procedure to be bound in owning phase |
| JOB-01 | F/G6 | not_run | Reference idempotent DB job survives lease reclaim without duplicate effect; obsolete claims cannot commit | not_run; procedure to be bound in owning phase |
| JOB-02 | F/G6 | not_run | Revoked/suspended actor/plugin is checked before dispatch | not_run; procedure to be bound in owning phase |
| JOB-03 | F/G6 | not_run | Non-idempotent uncertain outcomes are reported for reconciliation | not_run; procedure to be bound in owning phase |
| UI-01 | C/G3 | passed | Standard CRUD plugin uses the shared shell and components | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| UI-02 | D/G4 | not_run | Custom non-Owl page works without a new core patch | not_run; procedure to be bound in owning phase |
| UI-03 | D/G4 | passed | Direct links, refresh and back/forward work | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| UI-04 | D/G4 | not_run | Unauthorized/disabled pages and service calls fail even if URL is known | not_run; procedure to be bound in owning phase |
| UI-05 | D/G4 | not_run | Repeated mount/dispose does not accumulate listeners or stale updates | not_run; procedure to be bound in owning phase |
| UI-06 | D/G4 | not_run | Failed plugin page offers recovery and does not trap the user | not_run; procedure to be bound in owning phase |
| UI-07 | D/G4 | not_run | Native release mismatch triggers controlled reload | not_run; procedure to be bound in owning phase |
| UI-08 | D/G4 | not_run | Generic SDK does not require company/partner/session internals | not_run; procedure to be bound in owning phase |
| UI-09 | C/G3 | not_run | Standard shell passes keyboard, contrast, zoom and RTL checks | not_run; procedure to be bound in owning phase |
| UI-10 | D/G4 | passed | Unsaved-work and expired-session flows preserve a safe recovery path | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
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
