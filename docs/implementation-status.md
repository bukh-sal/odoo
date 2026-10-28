# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-28T10:24:31.494530+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **E / G5 in_progress**. Latest passed gate: **G4**, see `evidence/G4/20261028t033154z/gate-G4.json`.
- Active item: **E-01d**. Continue G5 lifecycle: finish feature/OS-store source regression checkpoint, then staged new-image lifecycle, release/startup fencing and remaining recovery/fault checks. UI-ALIGN-01 assessment complete in ADR0010: maximum practical Odoo UI reuse with our appearance; retain working shell/native views/Canvas, propose service adapters first, no whole-WebClient rewrite now. Backend/lifecycle work continues.
- Working changes: app-channel/feature executor, immutable app-request attribution and automatic bounded status mirror; live suspend/re-enable passed0959438545340Z, source qualification20138 running in1019594154741Z (see capsule). Native/recovery checkpoint d9b54d53 (96host/69Linux). Architecture clarification ADR0010 added; no frontend runtime/source changed by assessment.

## Progress estimate

**Overall roughly 65%; release acceptance 45/99 passed; 5 R2 checks excluded.** Gate weights below sum to 100 and represent a rough effort estimate, not equal task counts or a completion guarantee. Estimate uses completed gate weight plus a conservatively assessed fraction of the active gate. Setup/checklists alone do not count as product acceptance. Update the estimate when meaningful deliverables pass; do not increase it based on time spent or number of files.

## Gate checklist

| Gate | Deliverable | State | Weight % | Prerequisite / evidence |
| --- | --- | --- | --- | --- |
| G0 | A: baseline | passed | 10 | `evidence/G0/20261027t234238z/gate-G0.json` |
| G1 | A1: feasibility | passed | 10 | `evidence/G1/20261028t003753z/gate-G1.json` |
| G2 | B: contract freeze | passed | 10 | `evidence/G2/20261028T0630513883922Z/gate-G2.json` |
| G3 | C: Notes and shell | passed | 15 | `evidence/G3/20261028t011619z/gate-G3.json` |
| G4 | D: composition and Canvas | passed | 10 | `evidence/G4/20261028t033154z/gate-G4.json` |
| G5 | E: lifecycle and packaging | in_progress | 25 | G4; not_run |
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
| D-01 | Deliver Notes Labels and custom Canvas | passed | ORM; API-06; UI | G3 | packaged extension/browser contracts |
| UI-ALIGN-01 | Assess maximum practical Odoo UI reuse with custom presentation | completed_assessment | none; no acceptance credit | existing G3/G4 source | ADR0010; retain current root, reuse services first; no wholesale rewrite |
| UI-REUSE-01 | Adapt generic interactions to native services before frontend expansion | planned | UI; affected ID/API | UI-ALIGN-01 | dialogs/notifications/command adapters, then bounded action/view pilot |
| E-01a | Validate immutable archives and curated catalog before import | passed | PKG; BOOT-05; OPS-03 | G4 | hostile archives, digest/version/trust |
| E-01b | Resolve dependencies/versions/bindings into exact plans | pending_integration | DEP; VER; TEN | E-01a | pure/live CLI and feature UI/queue passed; new-image native lifecycle integration remains |
| E-01c | Independent local approval and privileged journal | pending_integration | SEC-06..08; LIFE; OPS-01 | E-01b core | OS/store and real feature request/approval/apply/mirror passed; broader native lifecycle/source qualification pending |
| E-01d | Recoverable native execution, backup/restore and release fencing | in_progress | MIG; LIFE; BOOT-06; OPS-02 | E-01c | real faults/restore/concurrency |
| F-01 | Deliver jobs/outbox and separately operated worker | not_started | EVT; JOB; SVC | G5 | lease/failure/scopes/duplicate tests |
| G-01 | Qualify full R1 and reproduce release/runbooks | not_started | all R0/R1 | G6 | full mapped acceptance; fresh install and recovery |

## Blockers and limitations

No hard blocker currently. Docker is healthy (Linux/amd64); user increased allocation to 8 GB (8,290,807,808 bytes reported). Limits and exact setup are recorded; no global Docker settings were changed by the agent. Windows `python` is a Store alias; use the installed managed Python 3.12 interpreter or containers explicitly.

## Last material outcomes

1. G0 passed at `3069e03f`; pinned curated runtime and recovery evidence retained.
2. G1 passed: 26 backend checks, real two-tab/native/custom browser proof, 40 denied post-revocation requests across two workers, and open-page revoked data cleared in <=5.27 seconds.
3. Default builder policy regression preserved frozen R0 inventory. No ORM/registry/loader/frontend source patch was needed for G1.

## Resume capsule

- USER DIRECTION ACCEPTED / ADR0010: maximize practical reuse of existing Odoo UI infrastructure with our own appearance and platform additions. Keep backend/security/deployment, useful presentation and current native list/form integration; default standard record screens to native views; retain optional Canvas/custom pages. Visual layout is not itself duplicate behavior. Assessment maps confirmation/notifications/palette, partial routing/action handling and native view orchestration to pinned upstream counterparts. Smallest proposed change: reuse already-running dialog/notification/command services, then isolate and pilot native action/view adapter. No wholesale rewrite or WebClient swap now; explain concrete retained/change scope before any substantial root switch. No frontend code/runtime changed by this assessment. UI-ALIGN-01 completed_assessment, UI-REUSE-01 planned (not active); E-01d is active. ADR does not change frozen contracts/spec v1.1 hash or grant new acceptance/progress credit.
- IN PROGRESS source qualification: exec session20138, `evidence/G5/20261028T1019594154741Z-feature-source`; full host suite plus focused non-root/read-only/network-disabled Linux suite and74-file freeze. Poll before editing tested source, do not start duplicate run. Source now includes test_feature_executor in Linux selection. Actual feature/app-origin/native phase checks changed, so this regression is justified. Before that: native/recovery checkpoint d9b54d53 qualified96host/69Linux in `evidence/G5/20261028T0950064513077Z-executor-core`. Current G5 feature code/evidence uncommitted; checkpoint after tests and clean diff review.
- G5 feature integration live PASSED: `evidence/G5/20261028T0959438545340Z-app-operation`. Browser suspend request7800293e-1844-4c46-8281-03d77b6e6b7f, exact961391ee...; full downloaded bundle equals independently read queue. Fabricated app-side approved mirror could not authorize apply; base state unchanged. Independent exact OS approval -> atomic metadata-only feature change -> typed approved/completed mirror and actual browser completed/installed+suspended dimensions. Unchanged release/bindings/container start, same-ID completed replay, no native migration/restart claim. Browser screenshot/browser-operation.json retained; no console errors.
- Re-enable69e45545-257b-494d-81ca-8e714c966cce exact8c016edd... COMPLETED. `enable-automatic-mirror.json` proves import/approval/apply automatically mirror progress, gateway/native access restored, app container start unchanged. NotesA ENABLED again. No running live probe. Provider suspension correctly gives403/FORBIDDEN at provider model guard before consumer availability (consumer-only suspension409); initial probe expectation corrected, runtime unchanged. Never repeat these mutations merely for evidence.
- Current uncommitted backend: app_channel.py bounded active-human requested queue input and redacted five-dimension journal output; feature_executor.py/feature_metadata.py atomic availability with metadata table locks/current security digest, dispatch-table guard untilG6; private store FEATURE_STEPS and possible-live-traffic fence; immutable observed application actor/request attribution (not approval authority). CLI import-request/mirror-status; approve/apply automatically best-effort mirror app-origin operations; independent show remains usable without app. Tests cover origin mismatch/immutability, no fake native phases, traffic fence and private-detail redaction.
- Current G5 site: project `mp-r0-r1g5fd0445d406d6`, actual DB `mp_disposable_r0_r1_g5_fd0445d406d6_restore_94b8f9db`, URL `http://g5.localhost:18072`, image `modular-platform:g5-fd0445d406d6` / sha256:3cf024957a263cba9e288977fecc212fbd760a3ef532f6183cb2ea279593f720, release generation3. Site5b35a39c-2c92-4a98-9ec0-82a2fe9fba5e/deploymenteb7ce420-a928-4ecb-80c7-1f8ff3b3fa08. `.local/g5/state.json`, appconfig, local odoo.conf and independent targets/g5.json already retargeted. Notes0.2.2 installed A only; Labels/Canvas code packaged but not DB-installed. NEVER init/seed/repeat first managed install harness.
- Managed native install ec2e6dfa-382a-412b-8183-64d873557db1 exacta8d88666... passed on restored site; `evidence/G5/20261028T0950064552054Z-native-install-corrected/native-install.json`. Actual unapproved denial, exact approval, ordered locks/stage/maintenance/drain/coordinated checkpoint/durable mutation/native install+metadata/bindings/internal HTTP readiness/exact release/publish/traffic/complete and same-ID replay. Private checkpoint control/checkpoints/<operation>, retained image tag; no installer repeat.
- Prior first install94b8f9db-d38e-4924-8ad1-2058d28bb675 failed readiness AFTER native commit because proposed lock missed concrete service scopes. Corrected planning binds scopes before hashing with regression; old immutable plan unchanged, never retried. Public edge kept stopped/recovery_required. Separate exact reviewed fresh-target DB+filestore restore reconciled current human authority, rotated session secret/revoked technical credentials, retained failed DB `mp_disposable_r0_r1_g5_fd0445d406d6` and original filestore. Separate reviewed resume reopened restored old working release; original plan retired/revoked, not called completed. Evidence `evidence/G5/20261028T0936230141742Z-native-install/recovery-summary.json`; private recovery/old config retained; old marker archived. Never repeat restore over existing targets.
- Next finite E-01d checks after source checkpoint: strengthen exact recovery-decision start expiry and archive selection with retained old DB directories; independently stage new-image upgrade/uninstall/removal (current adapter only current-image install + feature enable/suspend); startup inventory/no implicit migration, release/client epoch, native fault/crash/concurrency and clean attachment restore. New-image installation UI preparation remains pending. G6 adds jobs/outbox/worker/effect reconciliation; current recovery/feature adapter rejects dispatcher/API-key/external-runtime cases until the reviewed adapter exists. No generic effect reconciliation claim yet.
- Independent OS store `.local/operator/control` ALREADY initialized (policy.json/control.sqlite3/locks/checkpoints/stages/recoveries), authgeneration2/policy1; trustgeneration2 contains six immutable old/new curated artifact digests. No active test start approval: earlier tests revoked, successful native/feature plans consumed, failed native plan retired. DO NOT init-store or observe_r1.py --bootstrap. App UID10001 has no private store mount/Docker/socket. Approvals/checkpoints survive app DB restore. `targets/g5.json` currentgen3 and `targets/r1.json` preserved. Observer never imports plugin code.
- G0/G1/G2/G3/G4 passed historically. CurrentG2 rev7 `evidence/G2/20261028T0630513883922Z/gate-G2.json`,74files/26contract+50affectedtests/TypeScript; ADR0009. Existing valid/golden hash unchanged, strict absolute-end patterns. Current source packages Notes0.2.2/Labels0.2.1/Canvas0.1.3 required new identities after embedded schema changes; immutable G4 bytes preserved. No extra contract revision for UI implementation reuse.
- PRESERVE G4 `.local/r1/state.json`, projectmp-r0-r1396163208bf1 / DBmp_disposable_r0_r1_396163208bf1 / localhost:18071 / imagemodular-platform:r1 sha256:65ab6a5143756af473e75023f217898db427436b59a27d153c554be5b2a025e2. Actual old packages Notes0.2.1/Labels0.2.0/Canvas0.1.2; operational evidenceG4/20261028t033154z, passed9b315174. NEVER repeat init/seed/provision/patch/upgrade/notes revision; ignored fixture JSON and old checkpoints035812866223Z/043546334894Z plus retained image preserved. G0/G1 sites preserved. Browser user may be viewing Settings; do not overwrite their current tab for tests.
- Overall rough65%,45/99 release acceptance,5R2excluded. Historical G3/G4 browser results stay historical if future UI adapters change behavior; requalify affected paths, retain backend evidence. No progress increase for ADR/docs. Follow section25 finite checks/no loops; no subagents/publication/production/unknown data reset. Docker8GB; explicit `.venv/Scripts/python.exe`, no global Store-alias Python. Preserve CRLF docs. Goal active throughG7; read Git HEAD/status, not stale capsule commit wording.

## Acceptance ledger

Every spec ID is assigned an owning phase. `not_run` is not a pass. Exact commands/procedures and source/environment evidence are bound as the owning phase is implemented; G2 freezes contract fixtures.

| ID | Primary phase | Result | Required observation | Procedure / evidence |
| --- | --- | --- | --- | --- |
| FEAS-01 | A1/G1 | passed | Asymmetric workspace roles and record ownership are enforced through gateway and legacy model paths | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-02 | A1/G1 | passed | Two tabs, warmed caches and cross-worker revocation preserve workspace/role boundaries | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-03 | A1/G1 | passed | Minimal custom non-Owl page and native action coexist through the host adapter with correct routing/disposal | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-04 | A1/G1 | passed | Browser attribution and supported call chains cannot expand authenticated authority | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FREEZE-01 | B/G2 | passed | All seven section 5.5 contract rows have versioned schema/type/example paths and digests, with no critical authority/lifecycle TODO | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T0630513883922Z/gate-G2.json` |
| FREEZE-02 | B/G2 | passed | Manifest, restricted version mapping, alias bindings and approval canonicalization fixtures pass | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T0630513883922Z/gate-G2.json` |
| FREEZE-03 | B/G2 | passed | Frozen workspace/identity/UI contracts agree with passing G1 behavior and documented patch surface | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T0630513883922Z/gate-G2.json` |
| FREEZE-04 | B/G2 | passed | Contract inventory maps owning phases, acceptance IDs, compatibility fixtures and change/invalidation rules | `tests/test_contracts.py`, host SDK typecheck, freeze digest checker; `evidence/G2/20261028T0630513883922Z/gate-G2.json` |
| BOOT-01 | A/G0 | passed | Empty volumes initialize and an administrator can log in | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
| BOOT-02 | A/G0 | passed | A second fresh build reproduces the declared inventory | `tools/r0_repro.py`; `evidence/G0/20261027t234238z/20261028T001455995688Z-reproduction-summary.json` |
| BOOT-03 | A/G0 | passed | Explicit server-wide module choice works, including RPC omission if selected | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
| BOOT-04 | A/G0 | passed | No excluded ERP application is unexpectedly installed | `evidence/G0/20261027t234238z/gate-G0.json` and linked qualifying native/HTTP observations; R1 integration remains at owning phases |
| BOOT-05 | E/G5 | not_run | Unexpected addon search-path content cannot bypass release inventory policy | not_run; procedure to be bound in owning phase |
| BOOT-06 | E/G5 | not_run | Worker startup does not silently migrate production state | not_run; procedure to be bound in owning phase |
| PKG-01 | E/G5 | passed | Manifest validation does not import plugin code | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-02 | E/G5 | passed | Traversal, symlinks, duplicate normalized paths and ZIP bombs are rejected | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-03 | E/G5 | passed | Digest mismatch and same-version/different-artifact conflict are rejected | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-04 | E/G5 | passed | Unsigned artifacts follow the actual configured trust policy | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-05 | E/G5 | passed | Unknown sensitive schema fields and contract majors fail safely | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
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
| ORM-01 | D/G4 | passed | One packaged addon creates a model and another extends it | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ORM-02 | D/G4 | passed | Extension upgrade preserves original and extension-owned values as specified | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ORM-03 | D/G4 | passed | Duplicate field/contribution conflict is caught or deterministically rejected | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ORM-04 | D/G4 | passed | Export/import preserves supported data and rejects unsafe scope reassignment | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
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
| API-03 | C/G3 | passed | Deadline/cancellation errors do not falsely imply rollback | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| API-04 | C/G3 | passed | Private ORM objects and stack traces do not cross public boundary | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| API-05 | C/G3 | passed | Concurrent same-key mutations and a crash before response do not duplicate the reference database effect | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| API-06 | C/G3 | passed | Consumers use named bindings to call v1 and v2 concurrently; missing/mismatched bindings never select latest | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| API-07 | C/G3 | passed | Forged browser plugin attribution and supported provider call chains cannot acquire broader actor/token/grant authority | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| EVT-01 | F/G6 | not_run | Rolled-back writes produce no externally delivered success event | not_run; procedure to be bound in owning phase |
| EVT-02 | F/G6 | not_run | Duplicate delivery does not duplicate a deduplicated consumer effect | not_run; procedure to be bound in owning phase |
| EVT-03 | F/G6 | not_run | Unauthorized subscription or cross-workspace payload access fails | not_run; procedure to be bound in owning phase |
| JOB-01 | F/G6 | not_run | Reference idempotent DB job survives lease reclaim without duplicate effect; obsolete claims cannot commit | not_run; procedure to be bound in owning phase |
| JOB-02 | F/G6 | not_run | Revoked/suspended actor/plugin is checked before dispatch | not_run; procedure to be bound in owning phase |
| JOB-03 | F/G6 | not_run | Non-idempotent uncertain outcomes are reported for reconciliation | not_run; procedure to be bound in owning phase |
| UI-01 | C/G3 | passed | Standard CRUD plugin uses the shared shell and components | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| UI-02 | D/G4 | passed | Custom non-Owl page works without a new core patch | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| UI-03 | D/G4 | passed | Direct links, refresh and back/forward work | `evidence/G3/20261028t011619z/gate-G3.json` and linked qualifying procedures |
| UI-04 | D/G4 | passed | Unauthorized/disabled pages and service calls fail even if URL is known | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| UI-05 | D/G4 | passed | Repeated mount/dispose does not accumulate listeners or stale updates | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| UI-06 | D/G4 | passed | Failed plugin page offers recovery and does not trap the user | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| UI-07 | D/G4 | not_run | Native release mismatch triggers controlled reload | not_run; procedure to be bound in owning phase |
| UI-08 | D/G4 | passed | Generic SDK does not require company/partner/session internals | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
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
