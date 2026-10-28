# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-28T06:33:11.433749+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **E / G5 in_progress**. Latest passed gate: **G4**, see `evidence/G4/20261028t033154z/gate-G4.json`.
- Active item: **E-01c**. OS approval/journal and live feature CLI qualified; G2 revision7 operator UI DTOs/validation correction now qualified. Next: app operator queue, pure preparation using sanitized profile/current metadata, and read-only journal-status mirror; then E-01d staged release/native apply/recovery. E-01b UI integration remains pending. No G5 app mutation/apply yet.
- Working changes: G2 revision7 checkpoint (74files/26contract +50affected tests/TypeScript). E-01c primitives1698ef96, scope/readc555b771, planning4b7c7101, artifactsb6432951. G4 9b315174 unchanged.

## Progress estimate

**Overall roughly 63%; release acceptance 45/99 passed; 5 R2 checks excluded.** Gate weights below sum to 100 and represent a rough effort estimate, not equal task counts or a completion guarantee. Estimate uses completed gate weight plus a conservatively assessed fraction of the active gate. Setup/checklists alone do not count as product acceptance. Update the estimate when meaningful deliverables pass; do not increase it based on time spent or number of files.

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
| E-01c | Independent local approval and privileged journal | in_progress | SEC-06..08; LIFE; OPS-01 | E-01b core | OS/store/live CLI passed; public UI DTO freeze + queue/status integration next |
| E-01d | Recoverable native execution, backup/restore and release fencing | not_started | MIG; LIFE; BOOT-06; OPS-02 | E-01c | real faults/restore/concurrency |
| F-01 | Deliver jobs/outbox and separately operated worker | not_started | EVT; JOB; SVC | G5 | lease/failure/scopes/duplicate tests |
| G-01 | Qualify full R1 and reproduce release/runbooks | not_started | all R0/R1 | G6 | full mapped acceptance; fresh install and recovery |

## Blockers and limitations

No hard blocker currently. Docker is healthy (Linux/amd64); user increased allocation to 8 GB (8,290,807,808 bytes reported). Limits and exact setup are recorded; no global Docker settings were changed by the agent. Windows `python` is a Store alias; use the installed managed Python 3.12 interpreter or containers explicitly.

## Last material outcomes

1. G0 passed at `3069e03f`; pinned curated runtime and recovery evidence retained.
2. G1 passed: 26 backend checks, real two-tab/native/custom browser proof, 40 denied post-revocation requests across two workers, and open-page revoked data cleared in <=5.27 seconds.
3. Default builder policy regression preserved frozen R0 inventory. No ORM/registry/loader/frontend source patch was needed for G1.

## Resume capsule

- Current G2 revision7 PASSED: evidence/G2/20261028T0630513883922Z/gate-G2.json,74files/26contract+50affectedtests/TypeScript; ADR0009. Two new schemas operations-request/view +four examples andtest_operation_contracts. BeforeUI, fixed confirmed terminal-newline acceptance by replacing172anchored schema patterns across22files with portable absolute-end negative assertion; property-name patterns included. Existing valid fixtures/golden hash unchanged. New validate_operations_view checksplanid/hash/exacttransitive targets/trust/restart; apprequest cannot assertOSapproval; unsignedcatalog requireswarning. CurrentG4image untouched; tighten runtime onnewG5/G7. No new release acceptance/progress credit, still63%,45/99.
- Next exact implementation: app operator human role (no role-grantHTTP), operationscontext/catalog/prepare/request/status, puremetadata preparation and untrustedappqueue, sanitized profile/publicjournalmirror fromoperator CLI (never mountprivatecontrol store). New DTOcontracts frozen; followADR0009 routes/scopes/authority. Needcontrolled newcoremodel/bootstrap in separate disposableG5site ifnecessary to preserveG4, thenE-01d independently staged code-changing validator/apply/nativebackup/crash/restore/release fencing. No freshG1/G0 restart.
- Current E-01c checkpoint: operator_os.py +operator_store.py implement authenticated system SID/effectiveUID, protected private control store/allowlist, actual process-held deployment-then-site locks, durable immutable plans/approval/revocation/reservation/journal and mutation-before-child fencing.84host/63Linux tests pass evidence/G5/20261028T0606301178838Z/planning-core.json (host173s, Linux7s). Actual CLI independent reconstruction/incorrect hash denial/approval/revoke +actualapp UID10001/no control mount/socket/CLI/read-write namespace proof evidence/G5/20261028T0604233716373Z/operator-live.json. No apply/DB mutation; final approval REVOKED. Docsoperations.md describes actual limits. Rough63%,45/99 unchanged.
- Real control store now INITIALIZED at .local/operator/control (policy.json/control.sqlite3/locks). DO NOT init-store or observer --bootstrap again. OS owner allowlist names current disposable deployment/sites; explicit noninteractive qualification policyTrue;15minstarts. All real test approvals revoked. Store is outside app/DB restore domain, app only mounts filestore+config. Init and policy root DACL are ownerSID/System/Admins; Linux0700/0600. Windows fixes: system PowerShell module path must override inherited PowerShell7 PSModulePath; create empty directory before exactDACL because Python mkdir0700 adds OWNER RIGHTS ACE. Existing broad dirs failclosed. Lock-loss cleanup handles an alreadyclosed FD. All fixed and qualified. No control secrets/SID policy is tracked.
- IndependentValidator/CLI currently accept only unchanged-release native feature enable/suspend after fresh actual observation +full plan reconstruction. Code-changing plans failclosed pendingE-01d staged release adapter. Exact targets/bindings/grants cannot come solely fromapp claims; final apply remains unimplemented. New operations init-store/register/approve/show/revoke-approval available; CLI --noninteractive requires policy +exacthash/acks. Schema fields incheck_bundle now exactfourkeys.
- Next finite step: operator UI preparation/request/status schemas/examples under compatible G2 revision/ADR before UI runtime code. App operator role only requests/views; no approval or Docker/host control credentials. App queue untrusted; OS CLI pulls/recomputes exact bundle. Publish only sanitized metadata/status mirror toapp; app never mounts private store. New core UI model/init can use a separately named disposableG5 site (preserveG4), then E-01d native staged package install/upgrade/maintenance/backup/crash/recovery/release fencing through one independently approved path. Need staged-target verification beyond current unchanged-release validator. G6/G7 remain later.
- Current E-01c active; E-01b pending UI/journal/executor integration.71host/50Linux tests pass evidence/G5/20261028T0538162201159Z/planning-core.json; current live draft evidence/G5/20261028T0538112431256Z/live-planning.json. Actual pinned G4 image source/metadata read via PostgreSQL REPEATABLE READ READ ONLY:3 site installation UUIDs shared across6 workspace features,10 bindings,75 Python distributions. No ORM/plugin imports or DB mutations. Newplans.py uses (installation_id,workspace_id) scopes; one stable installation per site/plugin; binding IDs per workspace; explicit differing workspace providers and enable/dependent guards tested. Prior initial core mistakenly modeled each workspace as a different installation; corrected before any apply.
- Operator adoption already ran once: .local/operator/targets/r1.json, trust.json, catalog +incoming hold reviewed exact G4 digests/image and stable deploymentUUID/generation. DO NOT run observe_r1.py --bootstrap again. No approval/allowlist/journal store exists yet and no OS separation claim. observe_r1.py andqualify_live_planning.py may READ in fresh evidence directories. First read0529595491769Z failed on wrong f.state column, recorded; corrected to existing availability and0530257042931Z passed. Current live draft refresh includes scoped providers. Failed and superseded records retained. Native app/image/site data unchanged, operational .local/r1/state.evidence staysG4 until actualG5 mutation.
- Next finite E-01c: current-OS operator identity/allowlist outside app DB, protected approval/journal store, exact-hash expiry/revoke/reserve/replay, exclusive process locks/no lease stealing; app identity denial and Windows/Linux fault tests. Then operator UI/queue integration with untrusted requests and redacted status, E-01d actual approved lifecycle/recovery/release fencing. Core code/bootstrap for new UI can be qualified in a separately named disposable G5 site if needed; preserve currentG4 site. Priorrough61%,45/99 unchanged.
- Passed G0 3069e03f, G1 73d8ebd2, G3 e49d3a6b; G2 revision6 e06645a5 (66files/20tests). G4 passed9b315174 evidence/G4/20261028t033154z/gate-G4.json. E-01a passed evidence/G5/20261028T0508474407833Z/archive-catalog.json (18 groups Windows + Linux, real CLI, all6 boundary limits, exact package bytes). Overall63%,45/99 release acceptance,5R2 exclusions. Goal stays active through G7.
- Prior E-01b checkpoint (superseded by current capsule above): pure complete solver, lock and exact frozen plans. Core+real CLI qualified evidence/G5/20261028T0523322202821Z/planning-core.json:67host tests incl20G2,46focused Linux; source +resolvelib1.2.1 RECORD/license checked and streamed to private tmpfs. Newresolution.py/plans.py/planning_cli.py and modular plugin plan; operator dependency lock separate fromG2. ADR0008 binds exact installation/site/workspace targets through operation-lock preimage, existing frozen dependency_lock_digest, and release digest; no frozen changes. Compatible locked versions/no downgrade, full backtracking/native mappings/parallel APImajors, scoped aliases/stale/tamper/transitive/destructive guards tested. E-01b is NOT complete: next actual independent state +Python metadata adapter, workspace-specific different provider selections, enable/provider-health preconditions and operator request UI; then E-01c/d independent approval/journal/executor/recovery. No new release observations yet; rough60%,45/99 unchanged. No site/schema mutation.
- Prior E-01a/G5: archive/catalog committedb6432951. New artifacts.py/catalog.py +tools/modular.py inspect bytes without imports, strict portable ZIP/inventory/provenance/native/external layout, explicit unsigned warning or independently approved exact digest, immutable SQLite/version index and quarantine. docs/packaging.md has format/CLI. E-01a qualified at20261028T0508474407833Z; prior0506342702143Z superseded after narrower external notices and native descriptor. BOOT05/OPS03 remain later. Next solver/plans, E-01c independent OS approval/journal, E-01d lifecycle/recovery. G6 jobs/outbox/worker and G7 release remain later. Narrow reference assembler is not the G5 validator/executor.
- Existing R1: mp-r0-r1396163208bf1 / DB mp_disposable_r0_r1_396163208bf1 / image modular-platform:r1 / localhost:18071. Operational evidence still G4/20261028t033154z, priorG3 history retained. State .local/r1/state.json: seeded/shell installed/view_refresh_1 passed; g4_install_status provisioned; patch/upgrade/notes_revision statuses registered. NEVER repeat init/seed/install/resume/provision/patch/upgrade/notes-revision actions. No process pending. Before G5 mutations, move operational evidence to its own directory while retaining history.
- Current exact packages: Notes0.2.1, Labels0.2.0, Canvas0.1.2; digest/image/source in G4 source-identity. Services documents1.0/2.0 coexist; Labels command/base chain retains actor and grants; Canvas plain DOM consumes2.0 and its own boards1.0. Builder assembles repository-owned ZIPs, verifies inventory/full manifest/migration digest and declarative model/field/slot conflicts before import. Creator metadata explicitly Unix; local/Docker bytes now reproduce. No hostile upload/runtime containment claim.
- Native Labels upgrade ran once035834796750Z, normalized2 records and fenced revisions; raw verification035909761271Z retained base IDs/content/author/boards. Initial NULL-as-empty assertion corrected by read-only verification, not rerunning migration. Metadata path corrected to addon-relative; first invalid candidate never registered. Corrected package registered040158610595Z. Notes0.2.1 patch043607959346Z closes native delete CAS (missing/stale/bool denied), disables default native delete XML and retains host revision-aware action; metadata043610706137Z. New versions/digests, no registered artifact overwritten.
- Private checkpoints: .local/r1/backups/20261028T035812866223Z-backup + old exact image modular-platform:g4-before-labels02 (20c23312...); later .local/r1/backups/20261028T043546334894Z-backup before Notes CAS. Do not delete or claim image-only rollback. Shared backup helper now records state.image; R0 default behavior preserved.
- Policies/data restored: Alice editorA/viewerB, Bob editorB, Outsider revoked, Worker no browser business authority. Personal/en-US/UTC. Journal d8243a62-f8ff-46d6-9998-9a2c35f592a0 remains2; Welcome3 r1/verified; migration fixture8c27bf82-5ab1-45c8-a665-2717121c5902 now2 important/next. BoardA4dce025f-8218-41a2-9f81-6ac1e5733d8e revision15/two cards; B46c3c488-9456-4b65-94ce-d037ae6f162e revision1. Export group/broad rule removed; grants approved, CanvasA enabled.
- G4 final API/probe records: Notes10groups043616009311Z, admin8groups041725376350Z, retained6groups044019989612Z with48 denials/two workers and native import/suspension/body limits, native extension import/export3groups043621645189Z, exact package/conflict5groups043626642916Z, composition6groups040204057727Z, current real postcommit crash042700519056Z. Gate links full paths and limits.
- Browser qualifies Canvas card/link/move/save/refresh,3 dispose cycles + one Ctrl+S8->9, two-tab viewer, labels slot, custom dirty/conflict/download, optional bounded RAM-only snapshotDraft recovery after session expiry, cancellation after observed commit reports unknown and same-key retry one effect. Live theme preserves dirty state; ArabicRTL/history; failed mount stable277s/one request and route-update failure recover; CanvasA suspension clears subtree/denies known service/native URLs while B usable, then resumed. See individual browser records. Full zoom/a11y/production/release mismatch/reproduction remain G7.
- Faults off: .local/r1/g4-cancel-state.json off; g4-feature-check.json resumed; normal app has no test --load/env/mount. mp_r1_fault is test-only/never installed. Keep recognizable disposable volumes/evidence. Latest image build043549751582Z; no pending schema operation.
- Browser handles tab6/r1ConfirmTab Welcome Notes A, tab5/r1BTab Canvas B viewer; both handoff. Restore cua documentation after compaction. Background only; localhost cookies separate R0/G1. Credentials only ignored .local/r1/bootstrap-password; never print/save. No native Codex/password-manager automation. HTML dialogs throughout.
- Frozen contract commands: .venv/Scripts/python.exe tools/check_contract_freeze.py; -m unittest discover -s tests -p test_contracts.py; npm --prefix packages/host_sdk run check with Node in PATH. Changes need ADR/revision or major + fixtures/consumers/affected qualification. R0/G1 remain separate on127.0.0.1:18069/18070; prior source inventories3942/3963. Preserve licenses/data/volumes. Python shell is Store alias; use isolated venv. Docker8GB healthy. Continue G5->G6->G7, never R2 or completion at G4.

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
