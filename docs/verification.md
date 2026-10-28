# Verification evidence index

## G0 foundation: passed

Decision and source/runtime identity: [gate-G0.json](evidence/G0/20261027t234238z/gate-G0.json). Historical failed attempts are preserved in the same directory and explained in the work log. The corrected ten-addon baseline is the qualifying run.

| Observation | Evidence |
| --- | --- |
| empty database bootstrap | [20261028T000648534988Z-bootstrap.log](evidence/G0/20261027t234238z/20261028T000648534988Z-bootstrap.log) |
| login logout assets and anonymous controls | [20261028T001320256156Z-http-probe.json](evidence/G0/20261027t234238z/20261028T001320256156Z-http-probe.json) |
| native model and extension install | [20261028T001002968819Z-install.log](evidence/G0/20261027t234238z/20261028T001002968819Z-install.log) |
| schema upgrade | [20261028T001006972470Z-upgrade.log](evidence/G0/20261027t234238z/20261028T001006972470Z-upgrade.log) |
| upgrade values and attachment | [20261028T001009175718Z-check-v2.log](evidence/G0/20261027t234238z/20261028T001009175718Z-check-v2.log) |
| multiworker registry sync | [20261028T001254739829Z-http-probe.json](evidence/G0/20261027t234238z/20261028T001254739829Z-http-probe.json) |
| backup manifest | [20261028T001255951803Z-backup-manifest.json](evidence/G0/20261027t234238z/20261028T001255951803Z-backup-manifest.json) |
| committed fixture failure | [20261028T001259090266Z-fail.log](evidence/G0/20261027t234238z/20261028T001259090266Z-fail.log) |
| independent partial commit observation | [20261028T001301242499Z-check-partial.log](evidence/G0/20261027t234238z/20261028T001301242499Z-check-partial.log) |
| database restore | [20261028T001304374459Z-database-restore.log](evidence/G0/20261027t234238z/20261028T001304374459Z-database-restore.log) |
| filestore restore | [20261028T001307715558Z-filestore-restore.log](evidence/G0/20261027t234238z/20261028T001307715558Z-filestore-restore.log) |
| restored values and attachment | [20261028T001308501003Z-check-v2.log](evidence/G0/20261027t234238z/20261028T001308501003Z-check-v2.log) |
| destructive uninstall | [20261028T001310712599Z-uninstall.log](evidence/G0/20261027t234238z/20261028T001310712599Z-uninstall.log) |
| authority rotation and dependent states | [20261028T001313160348Z-reopen-authority-check.log](evidence/G0/20261027t234238z/20261028T001313160348Z-reopen-authority-check.log) |
| second build and fresh database | [20261028T001455995688Z-reproduction-summary.json](evidence/G0/20261027t234238z/20261028T001455995688Z-reproduction-summary.json) |
| two native registries | [20261028T001454086279Z-two-database-registry-proof.log](evidence/G0/20261027t234238z/20261028T001454086279Z-two-database-registry-proof.log) |
| styled login browser | [login-styled.jpg](evidence/G0/20261027t234238z/login-styled.jpg) |
| authenticated web client browser | [authenticated-webclient.jpg](evidence/G0/20261027t234238z/authenticated-webclient.jpg) |
| restored browser session denied | [restored-session-login.jpg](evidence/G0/20261027t234238z/restored-session-login.jpg) |
| source identity | [source-identity.json](evidence/G0/20261027t234238z/source-identity.json) |
| resource sample | [resource-snapshot.jsonl](evidence/G0/20261027t234238z/resource-snapshot.jsonl) |
| python inventory | [runtime-packages.txt](evidence/G0/20261027t234238z/runtime-packages.txt) |
| os inventory | [os-packages.txt](evidence/G0/20261027t234238z/os-packages.txt) |
| metadata regression | [metadata-regression.txt](evidence/G0/20261027t234238z/metadata-regression.txt) |

## Later gates

G3 integration passed; G4-G7 qualification is pending. R0 native observations do not certify those later boundaries. Five ISO checks are R2 exclusions. See the acceptance ledger for release status. Raw DB/filestore checkpoints and all generated passwords remain ignored local material, not tracked evidence.

## G1 feasibility: passed

Decision/source/environment: [gate-G1.json](evidence/G1/20261028t003753z/gate-G1.json). Backend command `python tools/g1_probe.py` passed 26 cases. Browser procedure: sign in as synthetic Alice; open A/B URLs in separate tabs; warm gateway/native views, try attributed write in B, refresh both deep links, exercise back/forward and route-only update, repeat native/custom transitions, delay an A callback then switch B, revoke Alice A from a separate maintenance process, observe cleared A and usable B, restore only that fixture, then select missing scope. Evidence [browser-proof.json](evidence/G1/20261028t003753z/browser-proof.json), linked screenshots and [source-identity.json](evidence/G1/20261028t003753z/source-identity.json). Qualified backend [report](evidence/G1/20261028t003753z/20261028T005744618594Z-backend-feasibility.json). Historical failed normalization attempts remain preserved.

## G2 contract freeze: passed

Seven-row reader inventory [freeze-v1.md](contracts/freeze-v1.md); current66file digests [freeze-v1.json](contracts/freeze-v1.json). Revision6 passes20 contract/golden tests, TypeScript compile and freeze check. [Current gate evidence](evidence/G2/20261028T035054399755Z/gate-G2.json). Historical revisions retained. G1 source unchanged. Executor/recovery, packaged migrations and worker acceptance stay at later gates.

## G3 integration: passed

Evidence directory `evidence/G3/20261028t011619z/` contains nine Notes API groups (`20261028T013439888375Z-notes-api.json`), eight administration groups (`20261028T023121221301Z-administrator-authority.json`), redacted audit readback, browser CRUD/navigation/export, session-draft recovery, membership revocation and administrator controls. `browser-admin-revocation.json` records the corrected polling race; `browser-administration.json` and `20261028T025256570025Z-r1-browser-admin-readback.log` record final synthetic member/configuration state. The current G3 decision below supersedes the earlier partial runs; unqualified later ID/API/UI observations remain pending.

G3 qualifying decision/source identity: [gate-G3.json](evidence/G3/20261028t011619z/gate-G3.json). Current10 Notes groups031305647053Z,8 admin groups031120165396Z,6 retained-boundary groups031329496667Z and real postcommit crash030918423461Z qualify the15 listed observations. Final bundle/browser confirmed; full later qualification remains as listed in the gate.

## G4 composition: passed

`evidence/G4/20261028t033154z/`: native install/reconciliation/patch metadata logs; six-group034121516830Z-composition-api.json; browser-composition-progress.json and keyboard-board-readback.json, Canvas/Labels screenshots. Failed prefetch proof retained. Remaining migration/import/custom faults and gate review pending. No G4 release acceptance is claimed yet.

G4 native0.2 migration035834796750Z, raw preservation verification035909761271Z and corrected package registration040158610595Z pass; current API040204057727Z passes6 groups. New custom recovery/cancel and full G4 gate remain pending.

Final G4 decision/source: [gate-G4.json](evidence/G4/20261028t033154z/gate-G4.json), superseding partial checkpoints.12 new observations; later limits explicit. G5 now active.

## G5 archive/catalog slice: passed; gate in progress

[Current E-01a record](evidence/G5/20261028T0508474407833Z/archive-catalog.json) binds source hashes, the pinned Linux dependency image and host version to18 passing hostile-byte/catalog/CLI groups on Windows and Linux. Actual private staging/output hashes and no-import marker, six exact size/count/ratio boundaries, path/link/collision/bomb rejections, digest/version conflicts, strict metadata, external runtime exclusions, current trust/quarantine/corruption and explicit unsigned warnings pass. PKG01..05 qualified;45/99 total. No DB/site mutation. Startup release inventory, pure solver/plans, independent approval OS isolation and recoverable lifecycle remain pending G5 work; this is not a G5 exit. Earlier0506342702143Z evidence is retained and superseded.

G5 E-01b core/CLI: [planning-core.json](evidence/G5/20261028T0523322202821Z/planning-core.json),67 host tests/46 Linux focused tests, exact source/dependency identities, unchanged66-file G2 freeze. Requalifies archive/catalog consumers after read-only catalog/CLI extension. Full E-01b/UI and G5 executor/lifecycle remain pending; acceptance45/99 unchanged.

Current G5 planner core supersedes initial scope assumptions: [71host/50Linux source qualification](evidence/G5/20261028T0538162201159Z/planning-core.json) and [actual independent read/harmless draft](evidence/G5/20261028T0538112431256Z/live-planning.json). Three site installations/six workspace rows/ten bindings/75 Python distributions; scoped provider choices, shared installation IDs, enable/dependent guards, exact target hashing and unchanged live authority. No approval/apply or G5 exit. First read query failure0529595491769Z retained; corrected existing column, not native schema. E-01c now active, E-01b UI integration pending.

G5 E-01c primitives: [84host/63Linux current source qualification](evidence/G5/20261028T0606301178838Z/planning-core.json) plus [real host CLI approval/revoke and appOS denial](evidence/G5/20261028T0604233716373Z/operator-live.json). OS identity/environment spoof, strict ACL/UID, live child crash locks/fencing/order, independent exact-hash/expiry/revocation/operatorgen/oneoperation state, backup-before-mutation, monotonic journal, postcommit-newowner recovery and completed-operation replay guards pass. The generic planning harness limitation text predates the operator component; actual qualified scope is these primitives, not the remaining UI/staged/native executor. Control store is initialized, final test approval revoked; no app DB mutation. G2 unchanged66files;45/99 release acceptance unchanged until full integration.

Current G2 revision7: [gate-G2.json](evidence/G2/20261028T0630513883922Z/gate-G2.json),74frozen files,26contract plus50affected metadata consumers, TypeScript. ADR0009/operator DTOs,172absoluteend pattern corrections, golden hash unchanged. G4image/source untouched; G5/G7 runtime tightening/UI stillpending. No newrelease acceptance.

G5 app operator frame subset: [HTTP six-group evidence](evidence/G5/20261028T090117143542Z-site/20261028T091648594867Z-operator-http.json) and [browser evidence](evidence/G5/20261028T090117143542Z-site/browser-operator-frame.json). Separate core-only G5 deployment; no managed reference addon installed. Authority/CSRF/canonical schema/native RPC/catalog and actual operator frame/session clear passed. Successful prepare/request/privileged apply/status remains pending. First embedded-schema bytes mismatch was rejected and corrected with new package patch versions; old G4 immutable identities preserved. No G5 exit or new release acceptance claimed.

Current-image native install: [successful corrected run](evidence/G5/20261028T0950064552054Z-native-install-corrected/native-install.json), [prior actual failed-safe readiness](evidence/G5/20261028T0936230141742Z-native-install/native-install-failure.json), [fresh-target recovery](evidence/G5/20261028T0936230141742Z-native-install/recovery-summary.json). Exact OS approval, real stop/drain/coordinated checkpoint, native install/metadata, readiness and same-ID replay observed. Original failed plan retired; new corrected plan completed. These are partial G5 observations, not full migration/fault/new-image/UI qualification or a G5 exit.

Managed-path source qualification: [host/Linux/freeze report](evidence/G5/20261028T0950064513077Z-executor-core/planning-core.json) passes. Actual Docker install/recovery is qualified separately in the linked live records; pure tests do not substitute for them.

G5 current feature/app-channel checkpoint: [98host/71Linux/freeze and source match](evidence/G5/20261028T1019594154741Z-feature-source/feature-slice.json). [Real fabricated app-side approval denied](evidence/G5/20261028T0959438545340Z-app-operation/forged-app-approval-denied.json) qualifies SEC-06;46/99 total. [Browser request/apply](evidence/G5/20261028T0959438545340Z-app-operation/app-operation.json), [browser final progress](evidence/G5/20261028T0959438545340Z-app-operation/browser-operation.json) and [automatic mirrored re-enable with restored access](evidence/G5/20261028T0959438545340Z-app-operation/enable-automatic-mirror.json) are separate actual-runtime proofs. Generic planning-report pending-integration language covers broader lifecycle, not a claim these feature observations were untested. No G5 exit. [ADR0010](architecture-decisions/0010-reuse-first-frontend.md) records UI reuse assessment only, with no source/runtime/contract or acceptance credit.

G5 recovery review/filestore controls: [8host/8Linux source/freeze](evidence/G5/20261028T1103235976970Z-recovery-controls/planning-core.json) and [actual protected mixed-checkpoint extraction](evidence/G5/20261028T1103235976970Z-recovery-controls/actual-checkpoint-filestore.json). Exact expiry boundary/future starts, hash tamper/cross-operation/state/policy/revoke, immutable review lifetime, safe one-site extraction/no overwrite/links/duplicates/traversal and new one-site archive child pass. Actual40selected files match their saved bytes;40retained-site files excluded in isolated Docker tmpfs. No live app/DB/filestore mutation; whole new-profile DB restore/offline failure remains pending. No new acceptance count from helper-only qualification.

Staged-image boundary: [current source/affected consumers](evidence/G5/20261028T1131523678990Z-staged-source/staged-boundary.json) and [actual different-image private staging/plan/approval/denials](evidence/G5/20261028T1134474357326Z-candidate-staging/staged-planning.json). Exact image ID is transitively hash bound, catalog ZIP/native source mapping checked, rehashed image substitution rejected, current executor refuses staged plans before reservation, actual state unchanged and test approval revoked. Candidate built separately, not deployed. Initial missing-new-workspace binding and Linux Node-harness failures are retained/superseded; final source hashes current. Actual new-image install/upgrade/replacement/restore and UI/client fences remain G5. No new acceptance from this partial boundary.

Guarded image lifecycle subset: [125host/98Linux/74freeze](evidence/G5/20261028T122000Z-guarded-workers/planning-core.json), [actual published-candidate pre-traffic failure/fresh-DB old-image recovery](evidence/G5/20261028T121200Z-staged-fault-restore/staged-execution.json), [normal promotion and completed replay](evidence/G5/20261028T121400Z-staged-promotion/staged-execution.json), [three actual pre-import guard denials with live state unchanged](evidence/G5/20261028T121800Z-worker-denials/worker-guards.json). MIG02/05 now qualified;48/99, roughly66%.40asset filestore files preserved; Notes/attachment rows were EMPTY, so this is not populated business-data or native version/schema upgrade proof. Automatic profile publication, default startup guard, client fencing, upgrade/uninstall and full fault matrix remain G5. [ADR0012](architecture-decisions/0012-guarded-workers-and-offline-recovery.md) records profile/limits. No frontend change or G5 exit.
