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
