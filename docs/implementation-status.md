# Implementation status

Goal: implement specification v1.1 through R1/G7. User authorized implementation and local Git on 28 October 2026 (Asia/Riyadh). R2/R3 are excluded.

- Updated UTC: 2026-10-28T12:56:28.261660+00:00
- Specification SHA-256: `c9c355996b52c622c6432f22d1cf00bea03ec3be202cafa466371fcc2adeb201`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **E / G5 in_progress**. Latest passed gate: **G4**, see `evidence/G4/20261028t033154z/gate-G4.json`.
- Active item: **E-01d**. Actual populated native0.2.2->0.2.3 upgrade, post-native-commit failure/recovery, old-code startup refusal, current-revocation overlay and successful new-operation promotion now pass. NEXT prerequisite: G5-TRUST-RELEASE-01, preserve the independently published release lock while fencing pending plans separately on current trust/catalog metadata, before another catalog enrollment. Then default startup/client fencing, skipped/fresh migration qualification and uninstall/removal.
- Working changes: none after the populated native lifecycle checkpoint (read current Git HEAD/status). SDK production implementation unchanged sinceac8e3327;125host/98Linux proof remains for that SDK,18host/18Linux current package checks and actual native tests qualify Notes0.2.3. Corrected isolated grant test passed separately. All processes/builds/probes terminal; G5 now76dab825/gen9. The open trust/release gap is the next active prerequisite.

## Progress estimate

**Overall roughly 67%; release acceptance 49/99 passed; 5 R2 checks excluded.** Gate weights below sum to 100 and represent a rough effort estimate, not equal task counts or a completion guarantee. Estimate uses completed gate weight plus a conservatively assessed fraction of the active gate. Setup/checklists alone do not count as product acceptance. Update the estimate when meaningful deliverables pass; do not increase it based on time spent or number of files.

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
| E-01d | Recoverable native execution, backup/restore and release fencing | in_progress | MIG; LIFE; BOOT-06; OPS-02 | E-01c | populated native upgrade/fault/restore passed; release-trust identity/default-startup/client/uninstall next |
| F-01 | Deliver jobs/outbox and separately operated worker | not_started | EVT; JOB; SVC | G5 | lease/failure/scopes/duplicate tests |
| G-01 | Qualify full R1 and reproduce release/runbooks | not_started | all R0/R1 | G6 | full mapped acceptance; fresh install and recovery |

## Blockers and limitations

No external hard blocker. Docker remains healthy with the user's8GB allocation; use project Python/containers, not the Windows Store alias. There is one concrete engineering gap to resolve before the next catalog/policy enrollment:

| ID | Affected scope | Failure / evidence | Attempts / next change | Unblock condition |
| --- | --- | --- | --- | --- |
| G5-TRUST-RELEASE-01 | Spec8.3/10.2, DEP07/08, UI07; E-01d prerequisite | Current projection embeds current trust policy_generation into the current release lock, so a next trust-generation projection changes its digest at fixed image/artifact versions/generation. Read-only actual-state reproduction `evidence/G5/20261028T125100Z-trust-release-gap/trust-release-gap.json`; current actual runtime/DB digest still agrees. | One discriminating read-only reproduction; no policy/runtime mutation. Add ADR and pin exact published lock independently, revalidate current trust/quarantine separately and bind that current snapshot to base-state/approval. Preserve legacy observations and require explicit safe adoption, not relabeling/reset. | Same selected release keeps exact identity under trust revalidation; changed trust/catalog still invalidates pending plans and quarantine still denies execution. Current tools allow fixing this without user input. |

Other G5 limits remain in the resume capsule; this internal gap is not a reason to mark the goal blocked or skip its owning work.

## Last material outcomes

1. Four Notes records seeded through scoped APIs (two per workspace, revisions1/2); legacy workspace attachment creation denied as the R1 profile requires. Notes0.2.3 adds positive revision SQL constraint plus digest-bound pre/post migrations; separate candidate76dab825 and curated artifact8783acff,18host/18Linux/74freeze passed123200Z. Existing artifacts/images retained.
2. Actual native upgrade committed0.2.3/validated constraint and rejected revisionzero. Host fault before metadata/replacement entered recovery_required; old worker refused incompatible native version before Odoo import. Fresh DB restored0.2.2, all4Notes and40filestorefiles, suspendedB and a post-backup Bob revocation; separate reviewed resume. [Native fault/restore](evidence/G5/20261028T124000Z-native023-fault-recovery/native-upgrade-recovery.json). MIG06 now passed.
3. NEW exact approved op86952188 upgraded successfully to0.2.3/gen9 with same-ID completed replay. [Promotion](evidence/G5/20261028T124500Z-native023-promotion/native-upgrade.json), [real gateway/native/scope and restored asset HTTP checksum](evidence/G5/20261028T125000Z-native023-api-assets/business-api-assets.json). G5 bootstrap/Compose mutation now rejects managed state before invoking Docker. Trust-generation release-identity gap reproduced read-only and is the next finite prerequisite. Approx67%,49/99; G5 remains active.

## Resume capsule

- **Next exact work E-01d:** fix G5-TRUST-RELEASE-01 before another catalog/trust enrollment. Read its reproduction125100Z and add an ADR for immutable independently published lock vs current trust revalidation. Preserve currentgen9/image/version/release digest during any reversible private adoption; do not rewrite a live release identity or fabricate a new DB publication. Bind current trust/catalog digest separately into pending plan base-state so changes still stale approvals; quarantine/revocation must still fail closed. Test both properties, then qualify affected consumers and exact adoption. No external blocker; same full R1 objective, no new feature scope.
- **Current live G5:** project `mp-r0-r1g5fd0445d406d6`, URL `http://g5.localhost:18072`, site5b35a39c-2c92-4a98-9ec0-82a2fe9fba5e/deploymenteb7ce420-a928-4ecb-80c7-1f8ff3b3fa08; actual DB `mp_disposable_r0_r1_restore_2364c27b48964da9a87585887d529436`; image `sha256:76dab825202dd0903af22cef381dcc3d03dbb52b3df47e98cbec60c318c6ea14` / tag`modular-platform:stage-20261028t123038959491z`; generation9; worker `00ccf0c6c91a0accdb6f7e6fb56bc4f3a2b24d484ebacc308943bc0574061aa3`. `.local/operator/targets/g5.json` and `.local/g5/state.json` current. Original local odoo.conf/Compose bootstrap target/tag are historical. `tools/g5.py` now refuses build/init/seed/up once worker_id exists; do not bypass that guard. Named appconfig contains currentDB; independent executor creates/selects workers. Public planning profile manually refreshed after promotion; current SQLpublished digest equals independent projection at trustgen3.
- **Reference state:** Notes0.2.3 installed globally, A enabled/B feature-suspended (preparationeb8dccfa completed123400Z). Four synthetic Notes rows in `.local/g5/lifecycle-data.json`, original seed rune0713c96-86d0-41d5-ad98-1997c37485fc; current restored_database recorded. Two each in A/B, revisions1/2, author/body/timestamps/IDs preserved. Bob membershipB deliberately revoked AFTER checkpoint; recovery preserved it; AliceA administrator/B viewer, operatoradministratorAB and worker serviceviewerA remain. Labels0.2.1/Canvas0.1.3 still only packaged. Workspace attachments are excluded in this R1 profile; do not add them solely for tests. Attachment denial plus supported internal asset restore/read is qualified. A c578135b-df92-482e-9f2f-e306617cf561; B efb30aaf-6120-4fde-9410-80c2bcfa50a5.
- **Terminal native operations, NEVER repeat:** fault2364c27b-4896-4da9-a875-85887d529436/hashd1a046615ebc20ca035cd136e1d8d2438e447c78c409d6cd3a07153b998afd5f native0.2.3 actually committed, exact host fault BEFORE metadata/replacement, state recovery_required. Guarded old0.2.2 refused changed native schema BEFORE import. Separate exact reviewed fresh restore to currentDB/oldac3e/gen8 verified oldschema/no new constraint,4Notes/40files, human revocation overlay, sessions rotated/technicalcredentials revoked; separately reviewed resume retired failed approval. NEW success86952188-580b-4de2-bab5-4ef536a29ce7/hash336da1ecd86109c8b72390ce1c0d8cd44cd9c96b12a3b53fb1c421e70c984529 completed0.2.3/gen9/replay. `.local/g5/native023-fault.json`, native023-promotion.json, upgrade-preparation.json and lifecycle-data.json terminal. Do not rerun once-only harnesses, reseed or replay migrations under a new arbitrary ID. Sessions28468/67840/52553/77706 all terminal, no process left running.
- **Current source proof:** SDK implementation stillac8e3327,125host/98Linux/74freeze historical source; corrected grant-ack test uses declaration_changes (prior test cleared wrong unused key); focused actual1test4.660s passed, record123200Z/grant-ack-isolation.json. Changed Notes native/package source qualified18host/18Linux/74freeze123200Z plus actual migration/SQL constraint/fault/restore124000Z and successful promotion124500Z, gateway/native/cross-scope/disabled/revoked denial and asset HTTP SHA1read125000Z. SDK hashes unchanged; whole old source report hashes are historical because reference source/test changed. No blanket claim that old package-source hashes remain current. Spec hashc9c35599 unchanged;74frozen files unchanged. New native/public API semantics remain compatible: same fields/DTO, positive revision now also SQL-enforced; malformed previous revisions stop migration instead of rewriting user data.
- **Independent trust/builds:** operator policygen2/policyversion1, trustgen3 with7curated exact artifacts. Newly enrolled Notes0.2.3 digest8783acff040d97d678bc4c1b0a9a9843f12d0a787e3abf40423e9bb345cad6e6; all6older artifacts retained. Private previous trust backup/control/catalog-enrollments and candidate build record `.local/operator/builds/20261028T123100Z-notes023-candidate.json`; source/hash build evidence123100Z. Current StageStore candidate bound against oldbasegen8 and stale aftergen9; next operation requires a NEW stage/plan. Do not init-store, observe --bootstrap, overwrite blobs/sameversion bytes, indiscriminately revoke consumed plans, or enroll next artifact until release identity gap fixed.
- **Backend profile ADR0012:** exact private worker_id distinguishes retained same-image workers. Non-root/read-only/cap-drop replacement bootstrap validates inventory/source/exactaddon paths/fixedconfig/DB inventory/native state+versions before Odoo import. Only executor-created workers use guard so far; default Docker startup still pendingBOOT05/06. Native maintenance separate from startup; new-image metadata preserves IDs/feature availability, writes exact bindings/grants/DB pin. Native trust/grant acknowledgement remains independent; no sandbox/unload claim. Restore observes retained source+raw DB offline, accepts only exact base/private-approved-target configuration, current authority review, fresh DB/filestore and higher epoch; separately reviewed resume. Traffic-may-have-opened prevents automatic destructive restore. Jobs/outbox/API keys/external runtimes still require later reconciliation profile.
- **G5 remaining after identity fix:** real skipped-release and fresh-install migration selection, default production startup/DB pin/version guard, automatic sanitized profile publication, client release epoch/UI07, uninstall/removal/dependent closure/approval/source-retention, crash/concurrency/before-mutation paths and remaining package/dependency/security/operator qualification. Current0.2.3 adjacent upgrade is real and passed, but VER02 remains pending until actual skipped/fresh cases. G6/G7 not started. Do not call G5 passed or goal complete. Conservative67%,49/99.
- **Retain other sites/history:** G4 projectmp-r0-r1396163208bf1/DBmp_disposable_r0_r1_396163208bf1:18071/image65ab6a51 and packages0.2.1/0.2.0/0.1.2 untouched; R0mp-r0-20261027234238n:18069/G1mp-r0-g18a21ede14068:18070 retained. All G5 failed/original/oldrestore DBs, filestores, images and stopped workers retained. Prior current-image ec2e6dfa, firstfailed94b8f9db, imagefault3ec081c1 and imagepromotion500230e9 all historical terminal; never rerun their first-install/once-only qualifiers. SEC06 app approval forgery denial and browser feature flow retained0959438545340Z/1019594154741Z.
- **UI ADR0010:** preserve custom presentation, standard native views, workspace/plugin scope/CAS/disposal and optional Canvas. Generic dialog/notification/command service adapters precede frontend expansion, then one action/view pilot; no whole WebClient rewrite without concrete benefit/scope explanation. UI-ALIGN assessment done, UI-REUSE planned, no frontend source changed by this native lifecycle work.

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
| MIG-02 | E/G5 | passed | Failure after an internal commit enters recovery_required, not false rollback success | `evidence/G5/20261028T121200Z-staged-fault-restore/failed-status.json`;125host/98Linux source122000Z; bounded post-publication/pre-traffic failure, no false completion |
| MIG-03 | E/G5 | not_run | Executor crash is reconciled before a retry | not_run; procedure to be bound in owning phase |
| MIG-04 | E/G5 | not_run | Concurrent operations serialize or reject safely | not_run; procedure to be bound in owning phase |
| MIG-05 | E/G5 | passed | Reusing operation ID does not repeat migrations | `evidence/G5/20261028T121400Z-staged-promotion/completed-replay.json`; completed journal/source122000Z; same-ID replay returns unchanged completed result without another native child |
| MIG-06 | E/G5 | passed | Restore recreates DB, filestore and previous release consistently | `evidence/G5/20261028T124000Z-native023-fault-recovery/native-upgrade-recovery.json`;4Notes/40filestorefiles, old native/schema/lock, current revocation and suspended scope; actual supported asset HTTPread125000Z. Workspace attachments excluded/denied. |
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
| OPS-01 | E/G5 | not_run | Operator can inspect journal when main app cannot boot | not_run; procedure to be bound in owning phase |
| OPS-02 | E/G5 | not_run | Documented restore works in a clean disposable environment | not_run; procedure to be bound in owning phase |
| OPS-03 | E/G5 | not_run | Build/source/license provenance is preserved | not_run; procedure to be bound in owning phase |
| ISO-01 | H/R2 | excluded_R2 | Hostile service cannot access host mounts, DB credentials or privileged sockets | not_run; procedure to be bound in owning phase |
| ISO-02 | H/R2 | excluded_R2 | Resource and network controls behave under abuse | not_run; procedure to be bound in owning phase |
| ISO-03 | H/R2 | excluded_R2 | Frontend origin/source/nonce/replay/stale-frame tests pass | not_run; procedure to be bound in owning phase |
| ISO-04 | H/R2 | excluded_R2 | Host cookies and DOM are unavailable to sandboxed frontend | not_run; procedure to be bound in owning phase |
| ISO-05 | H/R2 | excluded_R2 | Revocation and teardown invalidate runtime/bridge authority | not_run; procedure to be bound in owning phase |
