# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-28T14:36:46.884199+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **E / G5 in_progress**. Latest passed gate: **G4**, see `evidence/G4/20261028t033154z/gate-G4.json`.
- Active item: **E-01d**. Default R1 startup qualified on a separate candidate (ADR0014):25 actual denial probes and compatible unchanged-DB/source boot. NEXT finite prerequisite for client fencing: UI-REUSE-01 native dialog/notification/command adapters under ADR0010, preserving public host contracts and workspace/Canvas disposal. Then client release epoch/UI07, native UI preparation, skipped/fresh migrations and uninstall/removal.
- Working changes: none after this default-startup checkpoint (read Git HEAD/status). Default-entrypoint/strict source observer/SDK guard, focused tests, isolated qualifier and architecture/runbook records committed together.36host (one Windows symlink skip)/36Linux/74freeze passed. Actual isolated startup marker qualified; all sessions terminal. Live G5 remains SDK1/image95820dc4/gen12; candidate60c03d32 is built/qualified, NOT deployed. No frontend source changed.

## Progress estimate

**Overall roughly 69%; release acceptance 53/99 passed; 5 R2 checks excluded.** Gate weights below sum to 100 and represent a rough effort estimate, not equal task counts or a completion guarantee. Estimate uses completed gate weight plus a conservatively assessed fraction of the active gate. Setup/checklists alone do not count as product acceptance. Update the estimate when meaningful deliverables pass; do not increase it based on time spent or number of files.

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
| E-01d | Recoverable native execution, backup/restore and release fencing | in_progress | MIG; LIFE; BOOT-06; OPS-02 | E-01c | populated native upgrade/fault/restore and default startup passed; client/native UI/skipped/fresh/uninstall next |
| F-01 | Deliver jobs/outbox and separately operated worker | not_started | EVT; JOB; SVC | G5 | lease/failure/scopes/duplicate tests |
| G-01 | Qualify full R1 and reproduce release/runbooks | not_started | all R0/R1 | G6 | full mapped acceptance; fresh install and recovery |

## Blockers and limitations

No external hard blocker. Startup harness row-order failure resolved by resuming the existing clone; no repeated mutations or open recovery.  Docker remains healthy with the user's8GB allocation; use project Python/containers, not the Windows Store alias. G5 remains incomplete; the remaining client/native UI/skipped/fresh/uninstall checks are explicit in the resume capsule.

| ID | Scope / state | Evidence / resolution |
| --- | --- | --- |
| G5-TRUST-RELEASE-01 | resolved; current published identity no longer changes under current trust revalidation | ADR0013;136host/109Linux full source131800Z plus current47host/47Linux/freeze132700Z; actual non-mutating gen9 adoption133000Z, SDK1 rollout/app/OS agreement/stale actual CLI denial133700Z, current pinned restore135000Z. Historical release trust retained; current catalog validation separately fences plans. A configured validator also refuses a changed private policy file within a running command. Quarantine/revocation still deny selected bytes. |

Retained legacy images without SDK reader protocol1 preserve their old cache during restore and require the independent CLI until a compatible release; new native publication requires reader1. Current G5 uses reader1. No legacy image is silently relabeled or removed.

## Last material outcomes

1. Default startup source boundary passes36host (one Windows symlink skip)/36Linux/74freeze. ADR0014 guards the default image entrypoint with independent DB/inventory pins; strict source/observer checks include bytecode, symlinks and upstream writable data-dir addon discovery. [Source](evidence/G5/20261028T143000Z-default-startup-source/planning-core.json), [candidate](evidence/G5/20261028T143500Z-default-startup-candidate/candidate-build.json).
2. Actual candidate default entrypoint denies25 unsafe cases with unchanged clone during each attempt; compatible boot reaches health and preserves complete canonical schema/data/sequences/source. [Actual probes](evidence/G5/20261028T144000Z-default-startup/default-startup.json). Harness failed on dump heap-row ordering after fixture updates BEFORE positive boot, retained failure, canonicalized COPY rows and resumed SAME clone; negative probes/database creation NOT repeated. Live G5 remains unchanged; candidate not deployed. BOOT05/06 passed; conservative69%,53/99; G5 remains active.
3. Previous release identity/native rollout/restore remains working: SDK1/gen12 current, immutable published lock with current catalog fence, automatic verified cache; current pinned restore removed committed Canvas table and retained4Notes/40files/3feature scopes/Bob revocation. [Pinned restore](evidence/G5/20261028T135000Z-pinned-cache-restore/pinned-restore.json), [current gateway/native/assets](evidence/G5/20261028T135500Z-pinned-restored-api-assets/business-api-assets.json). DEP07/OPS01 and MIG06 prior evidence retained; changed guard/observer consumers covered by current focused regression. No G5 exit.

## Resume capsule

- **NEXT EXACT E-01d:** UI-REUSE-01 is the prerequisite for client release epoch/UI07. Read ADR0010 plus `platform_addons/mp_shell/static/src/host.js`/templates and native dialog/notification/command services. Implement the smallest adapters preserving frozen facade Promise/severity/cleanup, current authorization, dirty navigation and Canvas/workspace lifecycles; no full WebClient change or parallel generic UI. Qualify targeted source/browser behavior on a new recorded candidate/independently approved operation. Then client epoch/reload fencing. Current live worker remains95820dc4; do not mistake qualified default-start candidate for deployed release.
- **Startup completed / retain:** source36host(one Windows symlink skip)/36Linux/74freeze143000Z; candidate60c03d32/image inventory4706e1cc built143500Z; actual25negative + compatible unchanged-canonical-DB/source default boot144000Z. Marker `.local/g5/startup-probes/20261028T144000Z-default-startup.json` qualified, retained DB `mp_disposable_r0_r1_boot_1e44903a0fa34d63`, volume `mp-r1-startup-1e44903a0fa34d63`, all26probe containers stopped. No published release/deployment claimed for clone (copied publication deliberately stale except inventory). Initial harness dump-row-order failure retained; resumed same clone after canonicalizing COPY rows; NEVER rerun qualifier or resume terminal marker. Sessions79962/50396/46360/24168 terminal. Candidate includes earlier qualifier helper before harness resume fix; actual HOST helper hashes bound in final actual report; runtime SDK/entrypoint/observer bytes match both source and candidate. ADR0014/runbook record pins and historical bootstrap limitation; current G5 bootstrap refuses managed mutations. No upstream source edit.
- **Other remaining G5:** client release epoch/UI07 (first ADR0010 native dialog/notification/command adapters, then bounded action/view pilot), native install/upgrade UI preparation (currently controller supports feature operations only), actual skipped-release/fresh migration semantics, uninstall/removal/dependent closure/destructive approval/retention, before-mutation recovery/crash/concurrency and remaining security/dependency/operator qualification. G6/G7 not started. Jobs/outbox/API keys/external runtimes are deliberately rejected by current restore profile until the later effect/credential reconciliation adapter. All R1 requirements still block final G7;69%,53/99 is partial progress.
- **Current G5 live:** project `mp-r0-r1g5fd0445d406d6`, URL `http://g5.localhost:18072`, site5b35a39c-2c92-4a98-9ec0-82a2fe9fba5e/deploymenteb7ce420-a928-4ecb-80c7-1f8ff3b3fa08. DB `mp_disposable_r0_r1_restore_736f872ff76d4cd8af14ce8049452691`, image `sha256:95820dc46d22a40443b016c64a0afb9f3afc9c834df7eb0875f559ae8efeba93` / tag`modular-platform:stage-20261028t131814679124z`, SDKpublished_release_protocol1, gen12, worker `855f544087fa6a4d432ac14f74660c185d25cab1f2e816ef1d0235ac2a24d798`. Private config `.local/operator/targets/g5.json` includes exact published_release; current DBgen/digest/inventory must match it. `.local/g5/state.json`, appconfig and lifecycle-data.restored_database current. Bootstrap Compose target/tag/odoo.conf are historical; tools/g5.py refuses build/init/seed/up when worker_id exists. No bypass/reseed/reset/repeat migration.
- **Business state:** Notes0.2.3 installed globally with positive-revision SQL constraint; A enabled/B feature-suspended. Labels0.2.1 now DB-installed/enabled ONLYA; its x_notes_labels field exists globally but gated.4synthetic Notes rows from seed rune0713c96-86d0-41d5-ad98-1997c37485fc remain identical including baseline labels=[] DTO (do not pop that field). BobB membership deliberately revoked after earlier checkpoint and still revoked; AliceA administrator/B viewer, operatoradminAB, worker serviceviewerA. Canvas0.1.3 only packaged; its deliberately committed install was restored, so no Canvas table/activation claimed. Workspace attachments excluded/denied; supported internal asset HTTP SHA1read verified. A c578135b-df92-482e-9f2f-e306617cf561; B efb30aaf-6120-4fde-9410-80c2bcfa50a5.
- **Current boundary ADR0013:** published_release preserves historical trust evidence but is compared with independently reconstructed image/Python/manifests/frontend/provider contents; DB publication must match. Current catalog validation hash separately enters state and plan preimage/display. Quarantine/revocation still deny selected bytes. Configured host validators fence original private configuration bytes before/after each archive verification, so a running command cannot keep a revoked snapshot. Explicit operations adopt-release only accepts exact completed independent publication and writes config/backup outside DB; gen9 adoption133000Z changed no runtime/identity. New native target and restore configs pin exact target/reviewed lock; higher restore epoch required. Automatic SQL-checked sanitized profile publication before native ready/traffic and before reviewed restore resume; SDK0 legacy cache is preserved/deferred. New staged native plans require SDK1, old current-image native install refuses incompatible image before reservation.
- **Current source/evidence:**136host/109Linux/74freeze131800Z qualifies SDK implementation; subsequent host CLI fence changed tests/test_release_identity.py, tools/modular.py and qualification scope, current47host/47Linux/freeze132700Z covers that delta and all its source hashes match. SDK source unchanged since full report. Candidate95820dc4 SDK bytes match qualified source; its bundled tools predate final HOST CLI fence, which runs from this qualified repository and is not exposed/used as privileged app-container tooling. Actual gen9 adoption133000Z, SDK1 install/cache/app-OS matching/stale actualCLI denial133700Z, pinned current-code restore135000Z and API/assets135500Z all match relevant current source hashes. G2major1/74files/golden/specdigestc9c35599 unchanged.
- **Terminal operations / NEVER repeat:** SDKrollout4ec0ba68-04f1-4c9c-91ed-f492ea827cb7/hash4aedc7a59f85d45e51aacd94917349e32e2d55d9aa405d101dd357f2eb95ff97 COMPLETEDgen10, LabelsA and1Notes.read grant, same-ID replay no mutation. `.local/g5/release-reader-rollout.json` completed. Initial postcheck wrongly popped baseline labels, fixed using `verify_release_reader_rollout.py` without any native repeat; postcheck-failure.json retained. App follow-up request independently imported then revoked/mirrored, no second feature apply. Pinned restore736f872f-f76d-4cd8-af14-ce8049452691 intentionally failed AFTER nativeCanvascommit/BEFORE metadata; recovery_required then NEW freshDB/oldSDK1 release/gen12 plus automatic cache and separate reviewed resume; original approval revoked. `.local/g5/pinned-restore.json` restored_verified_and_resumed. Initial Canvas existence preflight expectedJSON but PGbool emitted f/t; fixed to to_jsonb BEFORE any operation/marker/output and native attempt ran once. All sessions3600/1960/51665/39817/84255/11068/15818 terminal, no running probe/build. Do not rerun these once-only qualifiers or restore over existing targets.
- **Private controls:** operator policygen2/policyversion1, live trustgen3/7curated artifacts unchanged this turn. New policy4/revocation/quarantine tests used probe configuration/catalog only; live policy never replaced. All7actual catalog bytes validated, including Notes0.2.3 digest8783acff040d97d678bc4c1b0a9a9843f12d0a787e3abf40423e9bb345cad6e6 and6historical artifacts. Control store/probes/adoption backups protected ownerDACL/UID, no app mounts/socket. Candidate active StageStore bound to older basegen10 and stale aftergen12; any new operation needs new stage+plan+approval. No init-store/observe --bootstrap, blob overwrite, paid service, publication or cleanup of retained data authorized.
- **Recovery safeguards ADR0012/0013:** deployment-then-site process locks, checkpoint+durable mutation marker, stopped public edge/drained workers, exact scope/DB/bindings/grants/version readiness, immutable image and private worker_id. Recovery accepts exact base/private approved target, observes raw DB offline without plugin/ORM boot, revalidates current catalog and authority, restores freshDB/selected filestore/previous code with newer epoch, rotates sessions/revokes technical credentials, preserves current human revocations and requires separate expiring exact reviewed resume. Traffic-may-have-opened fence forbids automatic destructive restore afterward. All failedDBs/images/filestores/old workers retained. Retained legacy readers may need CLI until compatible rollout; no sandbox/unload claim.
- **Retain history/sites:** prior native fault2364c27b restored, success86952188 gen9, imagefault3ec081c1/imagepromotion500230e9 and initialfailed94b8f9db/currentimageec2e6dfa terminal. Their markers/backups/DBs remain; never rerun first-install/bootstrap tools. G4mp-r0-r1396163208bf1/DBmp_disposable_r0_r1_396163208bf1:18071/image65ab6a51 withNotes0.2.1/Labels0.2.0/Canvas0.1.2 untouched. R0mp-r0-20261027234238n:18069/G1mp-r0-g18a21ede14068:18070 retained. SEC06 app-approved forgery denial and browser feature flow0959438545340Z/1019594154741Z still supported by unchanged store/authority boundary/current regressions.
- **UI ADR0010 remains:** retain useful custom appearance, native list/forms as standard, workspace/CAS/safe custom-page/Canvas lifecycle. Generic confirmations/notifications/commands reuse Odoo services before frontend expansion, then one action/view pilot. No full WebClient replacement without concrete benefit/retained-scope explanation. No frontend source changed this turn; existing Labels addon activation is qualified backend lifecycle, not a claim that client reload/UI07 is done.

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
| BOOT-05 | E/G5 | passed | Unexpected addon search-path content cannot bypass release inventory policy | `evidence/G5/20261028T144000Z-default-startup/default-startup.json`; actual default entrypoint rejects extra source/bytecode/cache/symlinks/writable data-dir addons before native import; strict observer source36host/36Linux/freeze143000Z; candidate60c03d32, live unchanged. |
| BOOT-06 | E/G5 | passed | Worker startup does not silently migrate production state | `evidence/G5/20261028T144000Z-default-startup/default-startup.json`; actual default missing/wrong independent pins, native pending install/upgrade/remove/version, CLI/config maintenance denials; compatible boot preserves full canonical DB schema/data/sequences and source. Clone disposable; candidate not deployed. |
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
| DEP-07 | E/G5 | passed | Stale plan is rejected | `evidence/G5/20261028T133700Z-release-reader-rollout/stale-app-plan-denied.json`; actual CLI re-observes deployment/catalog under alternate current policy, stable published identity but old app preimage denied before registration/mutation; current47host/47Linux fence tests132700Z. |
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
| MIG-02 | E/G5 | passed | Failure after an internal commit enters recovery_required, not false rollback success | `evidence/G5/20261028T121200Z-staged-fault-restore/failed-status.json`;125host/98Linux source122000Z; bounded post-publication/pre-traffic failure, no false completion |
| MIG-03 | E/G5 | not_run | Executor crash is reconciled before a retry | not_run; procedure to be bound in owning phase |
| MIG-04 | E/G5 | not_run | Concurrent operations serialize or reject safely | not_run; procedure to be bound in owning phase |
| MIG-05 | E/G5 | passed | Reusing operation ID does not repeat migrations | `evidence/G5/20261028T121400Z-staged-promotion/completed-replay.json`; completed journal/source122000Z; same-ID replay returns unchanged completed result without another native child |
| MIG-06 | E/G5 | passed | Restore recreates DB, filestore and previous release consistently | Current-source `evidence/G5/20261028T135000Z-pinned-cache-restore/pinned-restore.json`;4Notes/40files/3feature scopes/bindings/published pin+new epoch+automatic cache, committedCanvas table removed by fresh-target restore; current API/assets135500Z. Historical post-backup revocation/constraint restore124000Z retained. |
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
| SEC-06 | E/G5 | passed | A fabricated app-queue approval cannot authorize privileged executor actions | `evidence/G5/20261028T0959438545340Z-app-operation/forged-app-approval-denied.json`; source `evidence/G5/20261028T1019594154741Z-feature-source/feature-slice.json` |
| SEC-07 | E/G5 | not_run | Exact-hash approvals expire/revoke correctly; stale targets/policy/authority and cross-operation replay are rejected | not_run; procedure to be bound in owning phase |
| SEC-08 | E/G5 | not_run | Application OS/container identity cannot write/read privileged approval/operator/secret stores beyond the redacted status channel | not_run; procedure to be bound in owning phase |
| OPS-01 | E/G5 | passed | Operator can inspect journal when main app cannot boot | `evidence/G5/20261028T135000Z-pinned-cache-restore/independent-cli-no-app.json`; actual independent CLI shows recovery journal with no running app process, no registry/app dependency; actual incompatible old-code guard refusal124000Z also retained. |
| OPS-02 | E/G5 | not_run | Documented restore works in a clean disposable environment | not_run; procedure to be bound in owning phase |
| OPS-03 | E/G5 | not_run | Build/source/license provenance is preserved | not_run; procedure to be bound in owning phase |
| ISO-01 | H/R2 | excluded_R2 | Hostile service cannot access host mounts, DB credentials or privileged sockets | not_run; procedure to be bound in owning phase |
| ISO-02 | H/R2 | excluded_R2 | Resource and network controls behave under abuse | not_run; procedure to be bound in owning phase |
| ISO-03 | H/R2 | excluded_R2 | Frontend origin/source/nonce/replay/stale-frame tests pass | not_run; procedure to be bound in owning phase |
| ISO-04 | H/R2 | excluded_R2 | Host cookies and DOM are unavailable to sandboxed frontend | not_run; procedure to be bound in owning phase |
| ISO-05 | H/R2 | excluded_R2 | Revocation and teardown invalidate runtime/bridge authority | not_run; procedure to be bound in owning phase |
