# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-28T09:54:11.543470+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **E / G5 in_progress**. Latest passed gate: **G4**, see `evidence/G4/20261028t033154z/gate-G4.json`.
- Active item: **E-01d**. Corrected managed current-image Notes install and same-ID replay passed, after a real failed-safe native commit/readiness mismatch and fresh-target DB/filestore restore. Next finite step: successful app request -> independent import/approval -> metadata-only feature apply -> typed status mirror/browser, then new-image staging/upgrade/uninstall, release fencing and fault matrix. E-01b/c remain pending integration; G5 not passed.
- Working changes: native install/recovery checkpoint with real G5 evidence; source qualification passed0950064513077Z. UI/site checkpoint01832c10. No G4 mutation. New app_channel.py is unverified follow-on work, not part of native qualification.

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
| E-01a | Validate immutable archives and curated catalog before import | passed | PKG; BOOT-05; OPS-03 | G4 | hostile archives, digest/version/trust |
| E-01b | Resolve dependencies/versions/bindings into exact plans | pending_integration | DEP; VER; TEN | E-01a | pure/live CLI and actual metadata passed; UI/queue waits on E-01c/d |
| E-01c | Independent local approval and privileged journal | pending_integration | SEC-06..08; LIFE; OPS-01 | E-01b core | OS/store/live CLI and UI authority subset passed; successful queue/status/apply integration pending |
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

- CURRENT G5: managed Notes0.2.2 installed in A ONLY on restored DB `mp_disposable_r0_r1_g5_fd0445d406d6_restore_94b8f9db`; `.local/g5/state.json` and independent target/appconfig/current local odoo.conf updated. Release generation3, image3cf02495 unchanged. Successful operation `ec2e6dfa-382a-412b-8183-64d873557db1`, hash a8d88666..., evidence `evidence/G5/20261028T0950064552054Z-native-install-corrected/native-install.json`. Unapproved apply no mutation, exact approval, actual locks/stage/drain/checkpoint/native install+metadata+bindings/readiness/publish/traffic/complete, repeated sameID no new child all passed. Private new checkpoint under control/checkpoints/<newoperation>. NEVER rerun init/seed or managed install harness on this now-installed site.
- Prior failed operation94b8f9db-d38e-4924-8ad1-2058d28bb675 remains retired/revoked (not completed). Original DB `mp_disposable_r0_r1_g5_fd0445d406d6` and filestore retained. Failure readiness caught missing concrete provider scope in approved release; planning now materializes scope BEFORE hashing, with regression test. Evidence `evidence/G5/20261028T0936230141742Z-native-install`: failed status/readiness-observed, restore-review/decision/result, separate resume-review/decision/result and recovery-summary. Fresh-target restore verified DB/filestore/code/lock, current human authority, secret rotation/technical revocation; public traffic reopened only via separate exact reviewed resume. Original marker archived `.local/g5/managed-install-<oldoperation>-failed-restored.json`; current marker records successful NEW operation. No native installer rerun under old ID, no approved bytes rewritten.
- New executor/restore files are uncommitted at this capsule. Target source qualification session22434 in `evidence/G5/20261028T0950064513077Z-executor-core`, completed with host/Linux/freeze passed; no running qualification process. Focused43data-only tests and explicit restore-retirement/traffic-fence test passed (39.35s Windows). Full source suite passed; see evidence host/Linux records. New app_channel.py staged in working tree but NOT yet integrated/qualified. Next bridge must independently import only active-human own app requests, no queue approval; read-only catalog/status and exact full recomputation; mirror bounded statuses without private diagnostics. Metadata-only feature sequence must not claim migration/worker replacement. Recovery review expiry, archive selection with retained old DB directories, and startup/release fencing remain finite G5 improvements.


- G0/G1/G2/G3/G4 passed. Current G2 revision7: `evidence/G2/20261028T0630513883922Z/gate-G2.json`, 74 files/26 contract +50 affected tests/TypeScript. G4 `9b315174`, gate `evidence/G4/20261028t033154z/gate-G4.json`. Current HEAD must be read from Git. Rough65%,45/99; no new full acceptance from partial slices.
- One active item **E-01d**; E-01b/c pending integration. Next: exact native install nomination/reconstruction against independently verified code already in G5 image, approval, maintenance/drain, coordinated DB/filestore checkpoint outside app restore domain, durable mutation marker, controlled native install and metadata/bindings, worker readiness, release/client epoch and traffic. Then successful queue/CLI/status UI integration and fault/recovery. No ad hoc plugin install to bypass this pipeline.
- New G5 core-only target ALREADY initialized/seeded: `.local/g5/state.json`, project `mp-r0-r1g5fd0445d406d6`, DB `mp_disposable_r0_r1_g5_fd0445d406d6`, image `modular-platform:g5-fd0445d406d6` / `sha256:3cf024957a263cba9e288977fecc212fbd760a3ef532f6183cb2ea279593f720`, URL `http://g5.localhost:18072`, site `5b35a39c-2c92-4a98-9ec0-82a2fe9fba5e`, deployment `eb7ce420-a928-4ecb-80c7-1f8ff3b3fa08`. NEVER repeat init/seed. Only mp_shell/core installed, zero reference-plugin installations. App operator is g5_operator; Alice workspace admin is not an app operator. Secrets ignored in .local.
- G5 evidence `evidence/G5/20261028T090117143542Z-site`: build/init/provision, corrected build, six HTTP authority/CSRF/schema/native RPC/catalog groups `20261028T091648594867Z-operator-http.json`, actual browser `browser-operator-frame.json` plus screenshots. OWL compilation/render, explicit workspace selection, trust warning and session actor change clearing passed. Successful prepare/request/apply not yet tested; browser role-clear latency not precisely timed. Optional ops poll independent of business authority poll.
- G2 schema tightening changed embedded package bytes. First candidate rejected absent trusted digest BEFORE any plugin install/registration; corrected through NEW patch identities Notes0.2.2, Labels0.2.1, Canvas0.1.3. Old G4 package identities preserved. Corrected G5 image/core-only site rebuilt without reinitialization; independent target release generation2. Runtime resolver1.2.1 added with all other pins unchanged; static observation/projection has no plugin import.
- Independent control store `.local/operator/control` ALREADY initialized. Do not init-store or observer --bootstrap again. Authenticated OS policy generation2 now includes G4+G5; trust generation2 contains six old/new exact artifact digests; targets in `.local/operator/targets`. No active test approval. Private store never app-mounted. Existing IndependentValidator only feature operations; extend with independent staged/current code validation, never trust app queue approval. Read-only refactor live proof `evidence/G5/20261028T0641552814067Z/live-planning.json`.
- Current E-01c primitives `1698ef96`: 84host/63Linux `evidence/G5/20261028T0606301178838Z/planning-core.json`, real CLI wronghash/approve/finally revoke and appUID isolation `evidence/G5/20261028T0604233716373Z/operator-live.json`. Ordered actual process locks, private immutable bundle/approval/journal, 15min starts, exacthash/revoke/gen, durable mutation-before-child and new-owner recovery. Feature-only journal must avoid falsely claiming native migration/restart. `authorize_deployment` authenticates OSowner and atomic policy lock. Public sanitized profile/status mirrors untrusted.
- PRESERVE existing G4 `.local/r1/state.json`, project `mp-r0-r1396163208bf1`, DB `mp_disposable_r0_r1_396163208bf1`, `http://localhost:18071`, runtime image `modular-platform:r1` sha256:65ab6a5143756af473e75023f217898db427436b59a27d153c554be5b2a025e2. Actual packages Notes0.2.1/Labels0.2.0/Canvas0.1.2, operational evidence G4. NEVER repeat seed/install/patch/upgrade/provision/revision actions. Existing backups `.local/r1/backups/20261028T035812866223Z-backup` and `20261028T043546334894Z-backup` retained; old pinned image retained. Policies restored, cancel fixture off, jobs ordinary; fixtures in ignored JSON. G0/G1 targets also retained.
- Follow section25 and bounded next checks; no subagents, no publication/production. G6 jobs/outbox/independent worker and G7 full qualification/repro/runbooks remain. Check runtime health before use; Docker now8GB. Use `.venv/Scripts/python.exe`; never global Store-alias python. Preserve CRLF in docs. No known running process. Goal active through G7.

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
