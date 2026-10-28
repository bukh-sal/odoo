# Work log

## 2026-10-27T23:32:26.886278+00:00 / A-01 / environment and source initialization

Hypothesis: the available Docker Linux engine and managed Python are sufficient for isolated R0.
Actions: inspect tools and daemon; initialize Git branch `platform/r1`, add official upstream and fetch exact baseline.
Observed: Git 2.56.0, Docker Engine 29.9.2/Compose 5.6.1, Linux amd64, 16 logical CPUs, ~1.91 GiB Docker memory; Python 3.12.15/3.14.9 available via uv-managed paths. No existing Docker containers/images. Fetch succeeded; checkout pending.
New information: default Windows Python command is an alias, so use explicit interpreter; actual memory below benchmark profile is a measurement limitation, not yet a blocker.
Next: complete checkout, pin source/runtime, build baseline. No product acceptance has run.

## 2026-10-27T23:42:11.336118+00:00 / A-01 passed; A-02 in progress

Official checkout complete; exact baseline preserved as Git ancestry. Reviewed the one later 19.0 stock fix; baseline unchanged. Resolved 65 runtime dependencies with hashes; pinned build tools, base-image digests and dated Debian snapshot. Initial Docker build succeeded with pip check and a 4,486-file/10-addon curated distribution. Docker now exposes 8 GB after user allocation.

Changed: source/runtime locks, distribution builder/policy, Dockerfile/Compose and disposable lifecycle fixtures/harness. Source context was unnecessarily broad on the first build; restricted .dockerignore to curated inputs for subsequent builds. No app DB/filestore yet.

Next verification: rebuild current harness, initialize a fresh explicitly disposable database, then prove login/assets and installed closure. G0 is not yet passed.

## 2026-10-27T23:46:11.697650+00:00 / A-02 / Windows bind mount stall

Initial compose startup stalled before a database container existed. A no-mount PostgreSQL version probe succeeded; a separate read-only Windows file-bind probe stalled. Stopped only the two identified task-owned Docker clients; no database data was created or deleted.

Changed approach: replace all host runtime bind mounts with separate named config/bootstrap/evidence volumes seeded over stdin; use Docker cp for backup artifacts. App receives neither PostgreSQL admin credentials nor the bootstrap login password. Use a new project `mp-r0-20261027234238n` to avoid uncertain old container-creation reservations; old empty project resources are retained as evidence and not reused.

Next: rebuild changed harness and retry startup with this materially different mount strategy. This is a targeted environment fix, not a passed boot test.

## 2026-10-27T23:48:12.256239+00:00 / A-02 / base category bootstrap finding

Named-volume transfer and PostgreSQL startup passed. Native base initialization failed because `base.module_category_services_timesheets` is absent when excluded addons no longer contribute their category manifests. This is a concrete minimal-distribution coupling, not an ORM failure.

Fix: retain missing category records in the generated base data file, preserving catalog records and all upstream source in Git. Patch inventory records original hash and seeded IDs; regression checks static reference closure and idempotence, followed by a new real boot. Failed database `mp_disposable_r0_20261027t234238z` is retained; new harness target `mp_disposable_r0_20261027t234238z_p1` avoids blind replay.

Next: rebuild once with metadata patch and bootstrap the new target.

## 2026-10-27T23:49:56.466530+00:00 / A-02 / hidden optional editor import

The category patch passed its static regression and real base initialization progressed beyond the original failure. A distinct failure occurred while loading HTML editor: it imports `odoo.addons.iap.tools` although its manifest only lists base/bus/web.

Selected minimal-runtime adjustment: omit optional HTML editor for plain-text R0/Notes; keep all selected security modules. Do not add an unused paid-service integration just to load an optional editor. This changes the curated inventory to nine addons without patching Python or loader behavior. Preserve failed DB `mp_disposable_r0_20261027t234238z_p1` and use fresh `mp_disposable_r0_20261027t234238z_p1_p2`.

Next: one rebuild and fresh boot with this concrete dependency adjustment.

## 2026-10-27T23:53:45.248496+00:00 / A-02 passed bootstrap; A-03 HTTP routing

Fresh nine-addon native bootstrap passed; generated admin credentials applied before starting HTTP. Two HTTP workers and gevent worker started. In-container /web/health passes. Host HTTP failed because this Docker engine suppresses published ports on an internal-only network (desired HostConfig binding exists; NetworkSettings ports empty).

Fix: add a digest-pinned, non-root Nginx edge on a separate bridge plus the internal runtime network. Only edge publishes loopback; app and DB retain no external network/default route. Proxy config is transferred through its own named volume. This is a required routing adapter, not a weakened app egress policy.

Next: seed proxy config, start edge, rerun real login/assets and native fixture lifecycle.

## 2026-10-27T23:54:46.529785+00:00 / A-03 / public endpoint verification

Edge routing fixed host access. Login and compiled assets succeeded; logout initially exposed a probe assumption (native JSON-RPC omits null result), corrected to accept void and verify subsequent authenticated access fails. The next security assertion found `/web/database/manager` still renders despite list_db=False; inspected its controller to confirm that flag does not remove the route.

Kept the denial assertion and added an explicit edge block for the entire database manager route family. App remains reachable only on its private runtime network. Native model/operator transport restrictions still require platform work in later gates; do not infer full production security from R0.

Next: reload fixed proxy, rerun HTTP proof and proceed to native lifecycle fixtures.

## 2026-10-27T23:56:54.682162+00:00 / A-03 and A-04 passed

HTTP login/logout, compiled assets, anonymous route denial and omitted RPC checks passed. Installed closure is inspected; v1 fixture+extension installed from native files; v2 added schema and uppercased extension data while preserving original base name and attachment bytes. Evidence: timestamped http-probe, inspect, install, upgrade and check-v2 logs under docs\evidence\G0\20261027t234238z. This is native foundation proof, not yet packaged R1 acceptance.

Next: bounded multiworker signal proof, private coordinated backup, deliberate post-commit fixture failure, restoration and real uninstall. Rough overall progress 4%; G0 remains in progress; early R1 gates not started.

## 2026-10-27T23:59:37.214438+00:00 / A-05 passed native foundation recovery

Both HTTP workers served the newly added manual field after registry signaling (50 checked responses). Coordinated DB/filestore checkpoint captured with traffic stopped and cron disabled. The injected pre-migration committed a fixture name change and then failed; a separate process verified the committed change, demonstrating why rollback must not be claimed. Restored DB plus attachment bytes and exact image identity verified offline. Native base uninstall cascaded through extension and removed its table. Raw checkpoint stays under ignored .local; only hashes/proof logs are versioned.

Next: rotate restored authority, verify dependent uninstall states, reopen baseline for browser inspection; build a second uncached image and fresh database to compare inventories. R0 proof is not the R1 executor/journal implementation. Rough overall estimate 7%.

## 2026-10-28T00:06:26.180376+00:00 / A-06 / browser catches frontend style coupling

Actual login-page rendering showed error/fallback CSS despite HTTP 200; therefore G0 cannot pass on the earlier HTTP probe. Server logs identify undefined `increase-contrast`, supplied by excluded html_editor. Root cause source: two generic functions in html_editor.variables.scss call web's existing luma utility, while web frontend styles call them unconditionally.

Fix through supported addon composition: platform-owned `mp_compat` contributes the two unchanged upstream LGPL helpers to web._assets_helpers. No extra ORM/loader/frontend-root patch or IAP/mail code. Inventory now contains nine upstream addons plus this adapter. HTTP probe now fetches login and backend bundles and rejects native compiler-error CSS; actual browser verification remains required.

An independent uncached image build completed, but its result parser also matched its echoed command; corrected to match output lines only. It did not create a repro database. The source inventory has now changed for the style fix, so rerun reproduction only after successful styled boot. Start fresh target `mp_disposable_r0_20261027t234238z_final`, preserving all older targets.

## 2026-10-28T00:09:32.369397+00:00 / A-06 / corrected styles verified in browser

Ten-addon baseline (nine upstream plus mp_compat) boots from a fresh DB. Strengthened HTTP probe fetched six login/backend assets and rejected fallback error CSS; passed. Browser reload shows styled login, actual admin login reaches the native Apps client, and console has no errors/warnings. Screenshots saved as login-styled.jpg and authenticated-webclient.jpg. Baseline Apps screen still contains inherited catalog advertisements; these are metadata, not installed ERP/Enterprise code, and neutral shell/plugin manager remains later R1 work.

Because the runtime inventory changed for the compatibility addon, repeat the native lifecycle and restore fixture once against this final baseline, then rerun the second uncached build. Earlier evidence remains historical; do not claim it qualifies changed assets. New restore target derives from checkpoint DB, preserving the previous restore target.

## 2026-10-28T00:12:39.428962+00:00 / A-06 / deterministic worker coverage

Final-baseline install/upgrade passed. Registry signal changed the field correctly in all responses, but sequential requests happened to use only worker 10, so the coverage assertion correctly refused a multiworker pass. This does not show a registry failure.

Changed probe to eight concurrent clients and 80 checked responses, with a unique fixture field and durable pending/signal-committed/passed record so retry cannot blindly repeat schema creation. Both worker PIDs remain mandatory in logs. A fresh signal after the candidate restart will test real invalidation rather than only initial registry load.

Next: cached rebuild, focused concurrent proof, remaining lifecycle/restore chain and fresh-build comparison. No unrelated feature expansion.

## 2026-10-28T00:20:59.566919+00:00 / G0 passed; advance to G1

Corrected ten-addon source/runtime inventories match in an independent uncached image; a second fresh DB reproduces exact installed versions; native registries/parameters remain distinct. Final source also passes concurrent cross-worker signaling, post-commit failure, DB+filestore/image restore, attachment/value checks and cascading uninstall. Browser verifies styled login/authenticated client and rejects old restored session. Regression, generated-credential exclusion and private raw-backup checks pass. Gate record: docs/evidence/G0/20261027t234238z/gate-G0.json.

R0 is complete; this is not R1 completion. Rough weighted effort 10%; 5/99 release observations passed. Next ready item A1-01 is the small workspace authorization feasibility proof. No blocked gate, no permission decision needed, continue within the authorized goal.

## 2026-10-28T00:51:42.540159+00:00 / A1-01 / backend authorization proof

Separate G1 project mp-r0-g18a21ede14068 / DB mp_disposable_r0_g1_8a21ede14068 / loopback 18070 installed and provisioned successfully. First 22 backend cases passed: asymmetric roles, CRUD/search/aggregates, foreign ownership/relation rejection, native context spoof denial, gateway/provider-chain restrictions, scoped technical identity, role revocation and suspension.

Expanded proof also passed positive gateway CRUD, forbidden/not-found consistency, forged user/sudo/company context, and a deliberately broad native group rule with a required global scope rule. Concurrent revocation denial was observed on both HTTP workers. A later assertion caught a representation defect: revoked membership was denied, but the HTTP context route inherited an HTML 403 from pre-dispatch instead of a typed public error. Fixed by preserving a failed authoritative scope for HTTP boundary normalization; scoped model access still fails closed, and native dataset errors retain their JSON-RPC path.

Next: rebuild/restart only the G1 candidate and rerun expanded backend cases. G0 baseline/image/site remain separate and unchanged. Broader schemas stay unfrozen until G1 browser/custom-host proof.

- A1-01: expanded backend proof passed 26 checks (20261028T005204356478Z), including two-worker revocation, typed revoked-context denial and feature suspension. Default policy regression passed: 3942 native files unchanged from frozen R0. G1 remains open for browser proof.
- A1-02: implemented a G1-only root using the replaceable entrypoint, plain JS mount/dispose and concentrated native action-to-View adapter; no upstream frontend edits. Native RPC cache disabled in this proof; scope all native transport per tab. Next build, explicit fixture addon upgrade and browser checks.

- A1-02/G1 passed: real tabs preserve asymmetric roles and workspace data; native action/View adapter works in both, custom/native deep links and history work, three remount cycles and stale-completed-response discard observed. Membership revocation committed externally cleared private A in <=5.27s while B remained usable. No core source patches. Evidence gate-G1.json. Next B-01 contract freeze, progress20% / 9 of99 acceptance.

- B-01/G2 passed: seven concrete contract rows,50 frozen schemas/types/examples/validator/lock files, strict JSON2020-12, numeric/native version fixtures, exact-provider aliases, independent approval canonical bytes/hash and expiry/revocation contract checks, RS256 worker identity vectors.15 Python tests + TypeScript + digest check pass; G1source unchanged. ADR0003/protocol-v1 documents all critical authority/version/lifecycle choices. Next C-01 Notes/shell vertical slice; progress30%,13/99acceptance.

- C-01/C-02 implementation: minimal core install/binding/grant/audit/idempotency metadata, bounded typed gateway and live scope checks; Notes native model, revision CAS, list/filter/paging and registered CRUD implemented but unverified. Build uses separate R1 requirements/policy/SDK; no general planner/executor. R1 source metadata labelled development-source until G5 packaging. Image build pending session25669; no init attempted. Next real bootstrap/HTTP checks before shell integration.

- C-01/C-02: R1 native initialization and one-time synthetic provisioning passed; eight gateway/native check groups passed, including strict dispatch, asymmetric permissions, foreign-ID not-found, revisions and eight concurrent identical idempotency keys with one committed record. Core code remains unqualified for remaining G3 fault/admin/browser cases. Default/G1 runtime inventories unchanged after optional builder flags. Next C-03 shell install/browser.

- C-03 browser: actual native create/edit saved journal revision2 and refreshed public-ID deep link; screenshot/AX retained. Fixed stale native-form New save target by using host list/New flow and disabled extra form New; added explicit revision-aware delete. Dark/RTL smoke found heading contrast and unnamed breadcrumb; bounded fixes pending rebuild.
- C-02 regression: first attempt hit startup proxy before readiness; next assumed seed first despite newly created journal. Added readiness and owner-based assertions; nine backend groups now pass including legacy public-attachment creation denial. No authorization expectation relaxed.
- G2 revision2: ADR0004 documents optional-format validation gap and ambiguous core capability name correction. Explicit UTC calendar checker + negative cases,51file freeze and16contract tests/typecheck pass. PriorG2 evidence preserved, current gate requalified; R1 must rebuild to load corrected validator. Next C-03 browser/export/viewer/session and C-04 remaining authority/admin/fault work.

- C-03 native window.confirm blocked IAB CDP; browser close/state APIs also timed out. Used Windows recovery to cancel the native test dialog; no further native app automation permitted by skill guidance. Replacement uses accessible HTML dialog for delete/unsaved/SDK confirms. Reconcile the synthetic temporary note via API before any new browser claim; no repeated unchanged retries. Browser credential save was not approved/saved. Next build/up, fresh browser tab if previous close took effect, explicit in-page dialog tests.

- C-03: native HTML confirmations qualified; Cancel preserved saved synthetic note and draft, explicit Delete removed only disposable note, browser Back cancellation restored URL/draft. Export froze two A notes/noB data. Dark/RTL shell contrast/title corrected; native Note body now accessible label via one explicit view update, preserving journalrevision2. Session invalidation cleared editor<=5.515s and offered exact explicit memory-draft download; reauthentication preserved deep link. Default / enters neutral shell with explicit workspace selection. Membership revokeA cleared data<=6.932s while B worked; fixture restored. Evidence files linked in resume capsule.
- C-03 code review: pending unique-main landmark and overlapping async dispose/navigation fencing fixes preserve contract but require next image/browser check. C-04 remains active for workspace-admin/audit/retained-route/fault qualification; no G3 acceptance/gate inflated. Rough38%,13/99.

- C04 contract preparation: additive workspace administrator endpoints get strict principal-UUID/role/config schemas and response definitions before runtime implementation. ADR0005 preserves existing human-admin/workspace-only authority, reviewed elevation/audit and last-admin rule; no installer powers. G2 revision3 requalified17tests +56file freeze +TypeScript. Runtime feature still unimplemented/unqualified; no new acceptance marked passed.

- C04 / 2026-10-28T03:04Z: workspace administration backend eight real HTTP groups passed (023121221301Z-administrator-authority.json), with redacted audit readback. Unsupported native stream property fixed using route limits/get_data. Workspace admins cannot even read module metadata; operator fixture resolves the known ID to test direct installation denial. Browser renamed/restored workspace, added/changed/revoked synthetic Outsider, preserved last administrator and displayed timezone validation. Readback confirms revoked state and Personal/en-US/UTC.
- C04 authority failure: rapid initial navigation left administrator controls visible although fresh requests denied access. Logs proved polling never started. Native abort(false) left activation unsettled while onMounted awaited it before starting the timer. Fix starts polling before activation and settles wrapper cancellation independently. New build025801179366Z; rapid reload -> Settings then role restoration030159028239Z: polling continued, context reactivated03:02:05Z, controls removed, no console errors. Evidence browser-admin-revocation.json and screenshot. Alice editorA/viewerB; no schema/process pending. Next retained-route/bounded-body/error/crash outcomes. Rough41%; no additional release acceptance claimed.

- C04 / 2026-10-28T03:12Z: retained-boundaries run030840352011Z passes six groups: mixed batches, native export with temporary export-only permission, autocomplete/aggregate, missing/forged scope, safe/unsafe imports, bounded malformed/duplicate/oversized/chunked errors, CSRF and native traceback redaction,48 denied cached-client writes across both worker PIDs, feature/installation suspension retains data. Export permission restored in finally. Native load initially passed a resolved id into strict write; narrow private _load_records_write consumes matching ID after ownership guard, leaving public write unchanged. Suspension expectation corrected to frozen HTTP409. No repeated unchanged hypothesis.
- C04 API05 real crash: test-only server-wide addon with read-only operator exact-match file registers native postcommit callback. Worker9 exits86 after effect+outcome commit and before response; client gets502, worker14 respawns, independent read sees one record, two same-key retries return same saved result. Evidence030918423461Z-crash-before-response.json. Finally recreated normal app without fixture load/env/mount and removed synthetic note. No production arming endpoint, manual handler commit or upstream patch. Test fixture remains excluded from default --load and never installed.
- C03 stale browser save: separate disposable note revision1 edited locally while independent API updates revision2. Save returns conflict/revision, retains title/body, explicit recovery download exactly matches draft. Try again asks unsaved confirmation; Continue loads committed revision2. Independent read confirms no overwrite; fixture deleted. browser-stale-revision.json + screenshot. Product host network/cancel normalization now preserves unknown outcome after dispatch; browser recheck on next build, fuller custom SDK cancellation at G4. Next source/evidence gate review after focused regression.

- G3 passed / 2026-10-28T03:15:48.391499+00:00: useful native Notes/shell, supported admin, cross-workspace authority, bounded transport and real crash-before-response evidence reviewed against source hashes. Final browser reload: one main landmark, no console errors, journal intact.15 owning observations now passed, total28/99; job/custom/installer/release-wide items remain explicit later checks. Rough45%. Next D-01/G4 only. Broad-rule harness first had a generated Python quote error; no rule committed, export group restored. Fixed by repr-serializing domain; six groups passed with broad rule, then both fixture permissions/rule removed.

- D-01 prerequisite / 2026-10-28T03:22:55.630388+00:00: ADR0006 concrete optional UI slots/contributions/commands, public board DTOs and concurrent documents2.0 contract.19 contract tests/64 frozen files +TypeScript pass. Required slot/dependency/order/ownership errors and safe optional omission exercised without importing plugins. Existing1.0 examples remain valid. This is contract preparation, not G4 implementation or progress credit. Next native Labels/board/compiled UI runtime work.

- D01 narrow contract clarification: initial Canvas URL needs its one board without an unadvertised native ID convention. Before exercising runtime, revision5 makes boards.get board_id optional within an already explicit workspace; explicit foreign/unknown IDs still fail. ADR0006 addendum;19tests/64files/typecheck pass. Service-binding inventory cross-links corrected. No progress credit. Return to board/extension runtime.

- D01/G4: implemented supported typed provider frames, Labels shared-table extension/compiled slot command, documents2.0 and plain-DOM Canvas + board service; unverified. Bounded repository-only assembler packages immutable .mplug bytes and verifies/extracts native source into image; this is ORM01 prerequisite, not hostile upload trust/executor implementation. Initial install033313897853Z reached Notes0.2 then failed because access.csv inferred nonexistent model access. SQL033408957067Z confirms both new addons uninstalled/no new table/field and all3 original notes intact. Fixed filename to ir.model.access.csv. Guarded resume only new addons after explicit native preflight, no reseed/repeated Notes update. Next actual metadata/board provisioning and API/browser proof.

- D01: guarded resume/install/provision passed033506344277Z/033508752008Z, packaged Notes0.2.0/Labels0.1.0/Canvas0.1.0 installed on existing site. Six API groups initially passed majors/nested grant/CAS/concurrency but caught extension suspension breaking base reads: fetch candidate preflight denied automatic native prefetch. Replaced extension fetch override with supported _has_field_access, preserving explicit suspended field denial and base operation. Initial open browser accumulated native error dialogs during the4-second failure window; added Owl child-page boundary and will verify fresh bundle/recovery. Corrected Canvas route-only changes to let the host own one dirty confirmation. Six groups passed033933325013Z with fixes, but that development candidate changed artifact bytes at0.1.0 before registry reconciliation, so it is not qualified provenance. Bumped Labels/Canvas to0.1.1 and added a core same-version/different-digest rejection. Guarded native patch update/register/new-version probe now running; preserve initial migration fixture and journal. No G4 gate/acceptance passed yet.

- D01 / 2026-10-28T03:45:29.357691+00:00: patch0.1.1 native update034113533345Z and exact-byte package registration034116120746Z passed; six composition groups034121516830Z pass. Fresh browser Canvas/Labels subset passes actual card add/link/move/save8/refresh,3 native/custom cycles, ArrowDown+single Ctrl+S8->9 independent readback, isolated Research viewer, public note deep link and provider-owned labels command persists Welcome R1/Verified revision2/body unchanged. Journalrev2 and separate uppercase migration fixture preserved. No console errors. Rough49%, acceptance28/99 unchanged; next custom fault/dirty/conflict/theme/history and migration/import/packaging qualification.
