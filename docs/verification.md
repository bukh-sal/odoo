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
