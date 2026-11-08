# Implementation status

Current goal: application adoption AP-01..04 — complete. User authorized all four
phases to run sequentially unattended on8November2026. Preserve completed
AT14/14, AR16/16, CF12/12, BG/BX and R1 99/99 scopes and sealed49/47/46 artifacts.
No hosted/production deployment, publication, paid services or real-data import.

- Updated UTC: 2026-11-08T23:36:29.080319+00:00
- Specification SHA-256: `86e1a42f377415ab88854ceb61a6b5b14340cfe3186be54e0db424efd9ae2e93`
- Repository: `C:\Users\mesh\Documents\modular_platform`
- Branch: `platform/r1`; G0 checkpoint `3069e03f`; G1 checkpoint `73d8ebd2`; G2 initial `616b3e35`, revision2 `67cc4acf`; G2 revision3 `5ea5779c`; G3 checkpoint `e49d3a6b`. Read current Git HEAD/status on resumption.
- Upstream target: `5c7defb49e020fec8b6bb82403a2f54eb79e92e1`; runtime/base-image/Python/build locks established in `deploy/`; G0 qualified; G1 candidate uses a separate distribution policy/image/site.
- Current phase/gate: **AP-04 reusable workflow and clean delivery — passed.** Historical AR/CF/BG/R1 scopes remain complete.
- Active item: **None. All four authorized phases are complete;retain the named pilots and await a new selected requirement.** [Plan](../planning/application_adoption.md).
- Original R1 result: **99/99 required acceptance checks passed and 100 weighted points.** Five R2 checks remain excluded.
- The resumed in-app walkthrough verified native Notes, the updated Labels action, scoped viewer behavior and one-card Canvas. [Browser evidence](evidence/G7/20261105-section28-audit-01/in-app-browser.json) and [G7 decision](evidence/G7/20261105-section28-audit-01/gate-G7.json)

## Application adoption (completed goal)

[Phased plan](../planning/application_adoption.md) ·
[developer/usage limitations](application-adoption-limitations.md).
**100/100 verified points;16/16 acceptance checks passed.** Plan creation/source
review earns no implementation credit. Each phase splits its weight equally
across its four checks. No sub-agents are authorized.

| Phase | Weight | State | Next / evidence |
| --- | --- | --- | --- |
| AP-01 |20| passed | AP-A..D real daily workflows/repair, roles/concurrency/outage and limitations |
| AP-02 |30| passed | Independent app source/composition,actual app-only forward/fault/recovery/effects |
| AP-03 |30| passed | Independent Projects and optional Tasks links;actual app-set evolution/recovery/confidential errors |
| AP-04 |20| passed | Portable app/host delivery,clean downstream qualification,retained native pilot and exact owned cleanup |

| Check | State | Output / next verification |
| --- | --- | --- |
| AP-A | passed | [Fresh49 pilot/startup](evidence/post-r1/application-adoption/ap01-startup.json), independent Tasks install/1urgent+1bulk ready, [runbook](application-pilot.md) |
| AP-B | passed | [Actual native creation/edit/search/complete/reopen/reminder/read/Open](evidence/post-r1/application-adoption/ap01-daily-workflow.json), immutable app0.2.3 repair |
| AP-C | passed | [Direct denials/ownership,reassignment/two-session edits/actual lane outage](evidence/post-r1/application-adoption/ap01-role-concurrency-outage.json) |
| AP-D | passed | Limitations010 repaired/014 stale-edit boundary measured; app0.2.3 selected/qualified daily path; updated pilot walkthrough |
| AP-E | passed | [Independent source decision](evidence/post-r1/application-adoption/ap02-independent-source-decision.json), separate app Git and exact pinned49 composition |
| AP-F | passed | Immutable0.2.3 defaults repair;baseline bytes and successor inventory reproduced;real native creation/ownership |
| AP-G | passed | [New ordinary app-only forward](evidence/post-r1/application-adoption/ap02-release-decision.json),data/file/job identity/stale refusal/actual2once effects |
| AP-H | passed | [Real app-down/fresh original restore/current auth/separate resume](evidence/post-r1/application-adoption/ap02-release-decision.json),valid2effects/revoked0/useful pilot |
| AP-I | passed | [Source/contract/new-slot actual image+ordinary staged planning](evidence/post-r1/application-adoption/ap03-feasibility-decision.json),no app installed/probe retired/public freeze passed |
| AP-J | passed | [Independent Projects0.1.0/approved install/9actual backend groups/native create+member readonly UI](evidence/post-r1/application-adoption/ap03-projects-decision.json),Tasks/extension/workspaces absent |
| AP-K | passed | [Final error confidentiality correction/actual forward](evidence/post-r1/application-adoption/ap03-release-decision.json);ordinary7groups/native linking retained |
| AP-L | passed | [Actual fault70cba523/fresh original restore/current auth/separate resume/effects/new forwardaa2522a3/native date-filter](evidence/post-r1/application-adoption/ap03-release-decision.json) |
| AP-M | passed | [Fresh offline operator/three separate Git clones/six exact baseline+final archives/identical composed inventory](evidence/post-r1/application-adoption/ap04-clean-developer.json);developer/operator guides |
| AP-N | passed | [Fresh isolated routed CLI plan/register/exact approval/apply,roles,error confidentiality,reviewed fleet and planned stop/restart](evidence/post-r1/application-adoption/ap04-clean-operations.json) |
| AP-O | passed | [89clean host cases/88pass1skip](evidence/post-r1/application-adoption/ap04-clean-host-tests.json),[actual archive bounds](evidence/post-r1/application-adoption/ap04-clean-archive-boundaries.json),[finite credential/source audit](evidence/post-r1/application-adoption/ap04-delivery-hygiene.json);six exact app archives and identical runtime inventory |
| AP-P | passed | [Final57component delivery/retained pilots/checksums/35helper4image8alias cleanup](evidence/post-r1/application-adoption/final-delivery.json);[handoff](application-adoption-delivery.md) |


Blocker register: no user-input blocker. Missing ownership defaults (AP-B-001)
resolved in immutable Tasks0.2.3. Native restore release mismatch (AP-H-001)
resolved by ADR0079's host-only correction and real recovered effects. Debug-mode
link-name disclosure (AP-LIM-022) resolved in immutable extension0.1.1; ordinary
and developer-mode denial probes passed. Original counterexamples remain linked.

Resume capsule: **Goal complete;100points16/16checks.** No active item,pending
question,in-flight test/build/qualification or uncertain apply/recovery remains.
Do not restart completed AP/R1/BG/BX/CF/AR/AT gates or create another work item
without a selected requirement. [Final handoff](application-adoption-delivery.md)
and [final decision](evidence/post-r1/application-adoption/final-delivery.json)
bind the current scope and artifacts. Native UI remains the default.

Primary pilot8a22293a20e7/18178:foundation0.1.49,Tasks0.2.3,Projects0.1.1,
optional integration0.1.1;imageb0920ae4/inventoryfc709b84. Private current target,
credentials,intent and logs:
`.local/application-adoption/clean-operator-01/source/.local/application-adoption/ap04-clean-01`.
In-app tab19Alice/Project1:active,target_date2026-11-15,one readable linked Task;
no unsaved draft;marked deliverable/CUA summarized. Independent Tasks pilot
261d5d0954ee/18172 remains useful,private`ap01-pilot-01`. Each pilot retains
5running containers,6volumes,2networks,1urgent+1bulk lane/producer0. Review
retention before the next app/foundation release;explicit owned retirement when
superseded. The workers are intentional pilot services,not unfinished goal work.

Immutable kit`.local/releases/foundation49-application-adoption`:57components,
source0927861b195300651d1ddcb75f22b002ef35633b,manifest
07bf94533a487fc56aa48b5fefc26d79718a50b02a9801825a7cf1a94f598eb6.
Three independent Git bundles reproduce six exact baseline/final app archives.
Recomposition retains exact file/native/package inventory;OCI construction ID
is not claimed bit-identical. Updated host source contains ADR0079;sealed49/47/46
manifests/images and runtime authorization guards remain unchanged.

Actual app-only/app-set forward,fault,fresh original restore,current native auth
revocation,separate resume,useful work and once-only reminder effects passed.
Extension0.1.1fixes native developer-mode error disclosure while retaining both
resource rights;counterexample preserved. Clean offline isolated operator,
routed CLI install/planned stop-restart,89host cases(88pass1Windows skip),
eight actual archive groups and finite60value source/archive/app-history audit
passed. Agent walkthroughs are not human usability signoff.

All obsolete owned siblings retired. Finalcleanup removed35stopped helpers,
4unused app images and8redundant retention aliases;two pilots remain10running
containers/12volumes/4networks. Private checkpoints/logs,Git histories,qualified
kit images archive and unrelated assets remain. No blanket prune or publication.
Current development/usage limitations and deferred triggers are in the register;
there is no required unresolved defect for these four phases.

## Aurora Tasks release (completed goal)

[Plan](../planning/aurora_tasks_release.md). Authorized8 November2026.
**100/100 verified weighted points;14/14 acceptance checks passed; final seal,
refreshed-source privacy and delivery checks passed.** This counts the useful
application release only; AR16/16, CF12/12 and R1 99/99 retain their completed scope.

| Gate | Weight | State | Active/next work |
| --- | --- | --- | --- |
| AT-01 |15| passed | [Feasibility/freeze decision](evidence/post-r1/aurora-tasks/at01-decision.json); native probe12 checks; revision21 |
| AT-02 |20| passed | AT-D authoring and AT-E actual approved site-native install passed |
| AT-03 |25| passed | [Actual0.2.2 native10/edges8/classifier3/managed20](evidence/post-r1/aurora-tasks/at03-decision.json), no source overlay |
| AT-04 |30| passed | Exact49 clean/populated adoption, independent recovery, real native publication/jobs and final in-app native UI |
| AT-05 |10| passed |643host cases accounted for, reproduction/privacy, offline operator/authoring,57component sealed kit and exact owned retirement |

| Acceptance | Latest result | Evidence/procedure |
| --- | --- | --- |
| AT-A | passed | [Non-example archive feasibility](evidence/post-r1/aurora-tasks/at01-packaging.json): deterministic bytes, current validator, separate curated approval, six reference digests unchanged |
| AT-B | passed | [Native authority probe](evidence/post-r1/aurora-tasks/at01-native.json):12 checks, no workspaces/memberships/bindings, exact resources retired |
| AT-C | passed | [Application contract](aurora-tasks-contract.md), ADR0074/0075/0076, [current revision25](evidence/G2/20261108-at04-adoption-rev25-02/gate-G2.json) |
| AT-D | passed | [General authoring/composition](evidence/post-r1/aurora-tasks/at02-authoring.json): CLI, two apps, exact archive bytes, dependency refusals, curated catalog and solver;50tests/49pass/1Windows skip |
| AT-E | passed | [Actual image archive admission and approved site-native install](evidence/post-r1/aurora-tasks/at03-candidate01.json), zero workspace authority |
| AT-F | passed | [Actual native shared task workflow](evidence/post-r1/aurora-tasks/at03-candidate01.json); final browser passed AT-L |
| AT-G | passed | [Actual0.2.2 role/archive/internal-user/creator/outsider edges](evidence/post-r1/aurora-tasks/at03-decision.json) |
| AT-H | passed | [Real reminder/inbox/cancel/change/lease reclaim/stale result and20managed effects](evidence/post-r1/aurora-tasks/at03-decision.json); cross-release recovery passed AT-K |
| AT-I | passed | [Exact49 clean site-native install,10native/8edge groups, zero workspace authority](evidence/post-r1/aurora-tasks/at04-clean.json) |
| AT-J | passed | [Fresh approved47→49 native adoption, retained original rows/files and6declared stages](evidence/post-r1/aurora-tasks/at04-upgrade.json) |
| AT-K | passed | [Real publication fault, fresh47 restore/current revocation/separate resume and useful peer16jobs](evidence/post-r1/aurora-tasks/at04-recovery.json) |
| AT-L | passed | [Final49 in-app native complete/reopen, persisted private inbox/Open task and actual workload](evidence/post-r1/aurora-tasks/at04-browser-workload.json) |
| AT-M | passed | [643case coverage](evidence/post-r1/aurora-tasks/at05-regression.json), [10comparison reproduction](evidence/post-r1/aurora-tasks/at05-reproduction.json), [finite49value audit](evidence/post-r1/aurora-tasks/at05-privacy-full.json) |
| AT-N | passed | [Sealed57component delivery/checksums](evidence/post-r1/aurora-tasks/final-delivery.json), [offline operator+authoring](evidence/post-r1/aurora-tasks/at05-consumer.json), [handoff](aurora-tasks-release.md), [owned retirement](evidence/post-r1/aurora-tasks/at05-retirement.json) |

Blocker register: none. No active work item, running test/build/worker,
uncertain application mutation, recovery or user-input request remains.

Resume capsule: **Goal complete; do not restart completed AT/R1/AR/CF/BG gates.**
100/100points,14/14checks. Local kit`.local/releases/foundation-r1-core49-tasks`:
57components, sourcebcac9e3151609a5364a88b9fb0c32b89eb061a4d, manifest
396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404.
Imagecac49d72605fe62a13b262c4775a0c55da6052f1743fb2b6d6b667a8a877de7f,
inventoryd490c3d7701a4b0aa48edb6508a322bc3a7faf005ca976cf9dae6ce6b543a3a6;
stable alias`modular-platform:foundation-r1-core49-tasks`. App0.2.2 archive
71c97db1113cba7ba664171962208e429ecff66feb2ef8433e966a1ef20aa52c.
Sealed47/46 manifests and useful support images are unchanged. Source-archived
checklists are dated pre-seal records; exact qualification/checksums and final
delivery identify the sealed artifact. Later repository records do not mutate it.

Last material outcomes:
- Exact49 clean install/native10+edges8, populated47adoption, actual pending/
  claimed native job publication, final native in-app browser and independent
  fresh47 recovery/separate resume passed. Current post-checkpoint workspace
  revocation and native ownership both retained; Maintenance remained useful
  with native/scoped writes and16new jobs. [AT-04](evidence/post-r1/aurora-tasks/at04-decision.json).
- Exact643host-case coverage:641pass/2Windows skips. Initial launcher import
  errors and corrected27cases are separately recorded; no clean single full-run
  claim. Reusable isolated launcher added. No-cache/network-none replica matched
  all10declared runtime comparisons/6296inputs. Exported offline operator/catalog
  admitted22archives and rebuilt exact29211byte app. Revision25 freeze119files/
  10rows remains passed. [Regression](evidence/post-r1/aurora-tasks/at05-regression.json),
  [reproduction](evidence/post-r1/aurora-tasks/at05-reproduction.json).
- Final57component seal/checksum verification passed. Finite49persisted fixture
  values/147encodings found0matches across initial24249file observations/new
  layers and final18012source/artifact observations; unchanged image audit carried
  forward by exact archive hash. All3qualified targets retired120containers,
  18volumes/6networks; earlier feasibility/partition resources absent. Obsolete
  candidate/replica images and8terminal fixture aliases retired, stable images
  retained. Private checkpoints/logs/catalogs preserved under`.local/aurora-tasks`.
  [Final privacy](evidence/post-r1/aurora-tasks/at05-privacy-final.json),
  [delivery](evidence/post-r1/aurora-tasks/final-delivery.json),
  [alias retirement](evidence/post-r1/aurora-tasks/at05-image-alias-retirement.json).

The delivered app is list-bound shared Tasks with opt-in native database reminders,
not a full Aurora import/port. Native UI remains the default; Canvas is unchanged.
No production deployment/publication, hostile-plugin sandbox or automatic scaling
is claimed. Native technical-origin/recurring/provider features remain conditional.
For future application work start from the [authoring guide](application-authoring.md)
and [handoff](aurora-tasks-release.md), using fresh targets rather than retired
qualification fixtures. Detailed failed attempts remain in the append-only work log.

## Addon cleanup and restructuring (completed goal)

User authorized full implementation7 November2026. **No active item; goal complete.**
**100/100 weighted points;16/16 AR checks passed.** Documentation earns no
implementation points. Existing CF remains12/12 and original R1 remains99/99.

| Gate | Weight | State | Checklist |
| --- | --- | --- | --- |
| AR-01 |10| passed | [x] AR-A dependency/ownership audit; [x] AR-B transition/contract freeze |
| AR-02 |25| passed | [x] AR-C editor extraction; [x] AR-D settings/catalog; [x] AR-E communication/app separation; [x] AR-F native regressions/minimal boot |
| AR-03 |20| passed | [x] AR-G owned roots; [x] AR-H source prune/useful tests; [x] AR-I build/discovery/package/tool paths |
| AR-04 |25| passed | [x] AR-J reviewed populated upgrade; [x] AR-K app/role/job workflows; [x] AR-L independent recovery/useful peer |
| AR-05 |20| passed | [x] AR-M clean profiles; [x] AR-N reproduction/consumer/provenance; [x] AR-O affected source/native/browser/privacy; [x] AR-P handoff/retirement |

Blockers: none requiring user input. AR-01 [audit/freeze decision](evidence/post-r1/addon-cleanup/ar-01-decision.json)
and AR-02 [extraction decision](evidence/post-r1/addon-cleanup/ar02-decision.json)
passed. The15affected host checks and6retained native tests passed. Minimal core
installed13modules; Maintenance15(with generic mail, no Discuss/gateway/tours);
explicit communication17(with both extracted apps/tours). Editor imports/ICE,
local uploads/images/link previews, native Maintenance list/form/chatter and
optional action/cron identities verified. Old failures/fixes retain exact receipts.
AR-03 source prune is committed. Later AR-04/05 populated upgrades and sealed core47 are recorded below.

Historical AR completion capsule (superseded by active AT capsule above): **Goal complete; no active
item, pending mutation, running test/build or user blocker.** AR-01..05 passed
16/16checks/100weightedpoints. [Final decision](evidence/post-r1/addon-cleanup/qualification-decision.json),
[delivery verification](evidence/post-r1/addon-cleanup/final-delivery.json),
[handoff](addon-cleanup-release.md). Do not restart completed AR/R1/CF/BG gates.

Sealed local kit`.local/releases/foundation-r1-core47`:56components, source
9045faa8972458afcc433d80748aeb2f3f52e783, manifest
45fb20724d994a396121fcadd3ff6b6c088d243ccd56619f5732c851d53fd0e3.
Imagea572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a,
inventoryc69c1015d61b93e6ac79114915a3da82d12f6ca1813032b570c24115684135ad;
stable alias`modular-platform:foundation-r1-core47`. Source-archived status files
are dated development records; kit qualification/checksums identify the sealed
snapshot. Post-seal repository commits add delivery/proof records, not new image
inputs. Preserve sealed46kit/image; original46manifest485dc9b5 remains unchanged.

Owned roots authoritative:49addon dirs (15framework,4applications,5examples,
25explicit regression/feasibility fixtures),24available production/example addons;
628unused production trees plus IAP source removed, RPC test-only,22inherited
fixtures retained, original numeric parser regression preserved. No external
Odoo compatibility goal. Native default list/forms and existing1-card Canvas
custom-page capability retained; no theme/product expansion.

Exact final-image proofs: both populated Maintenance/Aurora46→47forward
operations completed with module/data/ownership/filestore preservation;50mail
record adoptions/own R1 aliases where installed,4lossless private IAP archives.
Native workflows/roles/scoped Notes passed. Three pending/stale jobs preserved
actor/workspace/timing and denied old claim. Exact47publication fault96ece65b,
failed app stopped, fresh independent46DB restore of Aurora/IAP/ownership/files,
separate reviewed resume and useful peer16new jobs passed. Earlier prototype
proofs keep separate scopes; current operator cannot stage those old recipes.
Revision20freeze111files/8rows passed, including real plugin-free site scope.

Cold final profiles13core/14Aurora/15Maintenance passed. No-cache/network-none
replica reproduced all10inventory comparisons and6,276inputs. Isolated offline
kit operator/21archive catalog/3nativeplugins6scopes/backend5checks passed.
Current full host601tests:600passes/1existing Windows skip (471.288s);9native
cases passed. In-app native owner/list/form, readonly viewer and minimal Canvas
passed with saved screenshots. Workspace links intentionally open new tabs;
launcher inspection corrected without UI changes. Exact47urgent/bulk lanes
completed8bulk jobs once and1notification once, then drained.

Finite known-value audit80generated AR login/master/database values found0matches
in decoded source/archives/new application layers. Final sealed-source repeat:
17,754files/15,859unique contents/552,259,176bytes/50archives,0findings. Declared
bounds/dependency carry-forward/no unknown-secret-detector or publisher-auth claim
are retained in[final privacy](evidence/post-r1/addon-cleanup/ar05-privacy-final.json).
Only source.zip changed in final refresh;54components reused. Real AR16check
qualification branch sealed the kit; no fabricated CF passes.

[Owned retirement](evidence/post-r1/addon-cleanup/ar05-retirement.json):259containers,
150volume-removal events (146unique names),48networks; no recorded AR container,
volume or network remains. Two failed Windows binds materialized late; exact
never-started provenance and4empty recreated volumes verified/removed. Four
obsolete prototype/reproduction images and14owned transient tags retired; earlier
AR-03 image retirements retain their scope. Stable47/sealed46/useful support and
unrelated assets retained. No global prune. Private checkpoints/exports/logs remain
under`.local/addon-cleanup`, excluded from kit. Test-created browser tabs closed.

Next work requires a new user-selected objective. For a new deployment, follow
kit verification/setup/native lifecycle in the handoff with a fresh private
operator and disposable target; never reset/replay retired fixtures. No production
deployment or publication occurred. Current project Python remains explicit
`.local/toolchain/operator-python16/Scripts/python.exe`; global Python unchanged.

## Latest direction: owned fork and addon retention

The user clarified that external Odoo compatibility is **not** a goal, including
when choosing core changes and folder structure. [ADR0071](architecture-decisions/0071-owned-fork-and-addon-boundaries.md)
and [retention assessment](addon-retention-review.md) are now recorded in the spec
and AGENTS.md. Actual inventory:665inherited addon directories in source;
13inherited+10owned shipped.629unused top-level addons are pruning candidates;
23internal test addons should be assessed as regression fixtures. Editor/IAP/
mail coupling required extraction before deleting IAP. The assessment itself
changed no runtime code; AR execution is now recorded above. Core46 remains sealed/unchanged with
12/12CFchecks/100points; extraction is now authorized under AR-01..05 above; its new qualification does
not invalidate the historical core46 evidence.

## Consolidated foundation release (completed goal)

User authorized the full goal on7 November2026. No active item; all CF work and final delivery checks complete.
Progress **100/100 weighted points;12/12 CF checks passed; sealed kit and final privacy/checksum verification passed**. Original R1 remains99/99.

| Gate | Weight | State | Required checks | Evidence/next action |
| --- | --- | --- | --- | --- |
| CF-01 |10| passed | [x] CF-A policy/freeze; [x] CF-B baseline feasibility | [Freeze](evidence/post-r1/foundation-release/cf-01-freeze.json). [Baseline decision](evidence/post-r1/foundation-release/cf-01-decision.json); core30 boot/current observation passed. |
| CF-02 |20| passed | [x] CF-C final46 image; [x] CF-D final46 kit | Final46 image72d51d32/e4e1f97d reproduce inventory14cc5a2c. Exact three-file45-to46 delta verified; sealed56-component kit and final privacy/checksums passed. |
| CF-03 |20| passed | [x] CF-E distinct installed apps; [x] CF-F populated workflows/permissions | Fresh owned Aurora/Maintenance targets. |
| CF-04 |35| passed | [x] CF-G migration; [x] CF-H final46 closed fault; [x] CF-I fresh restore/resume/forward; [x] CF-J useful peer | Independently approved common upgrade, real schema witnesses. |
| CF-05 |15| passed | [x] CF-K worker/regression/UI; [x] CF-L kit/handoff/retirement | Exact release qualification and owned cleanup. |

Resolved CF-RECOVERY-SKIP-01: bounded fix passed original45 and final46 native failed-upgrade/fresh-restore/separate-resume cases. No current external/user blocker. Docker Desktop Linux engine was stopped; local start
succeeded (engine29.9.2). No pre-existing container/data has been changed.

Resume capsule (CF takes precedence over historical capsules below): **goal
complete; no active item, running test/site/worker, uncertain mutation or user
blocker.** CF-01..05 passed12/12checks/100weightedpoints. Use the sealed kit
`.local/releases/foundation-r1-core46`:56components, sourcea340a901c9f32dbf2f6e829ef0aa903233e4edd9,
manifest485dc9b5ce785cae8a78cd586256ec3df1bbf031f7db26228c9fef094a5422b7,
image72d51d3282c93df591e01cf63c2d0fe66c06633f5d4b569d557da5f3c47d0e82,
inventory14cc5a2c5ef57ad27c8548e3f4150e402ba13dfb8920618b5e3137f060e54fe1.
[Qualification](evidence/post-r1/foundation-release/qualification-decision.json),
[seal](evidence/post-r1/foundation-release/sealed-kit.json),
[final privacy](evidence/post-r1/foundation-release/cf-05-final-privacy.json) and
[handoff](foundation-release.md) give exact scopes. Both native app sets,
actual failed-app-down recovery/separate resume and useful peer jobs passed;
585hostpasses/1existing skip,106contractfreeze,425source alignment. Final refresh
reused54unchanged components; sealed metadata and refreshed sources passed a
second finite24credential scan with0findings. Retired160owned containers,
18volumes,6networks,4superseded images/14tags and owned temporary worktree/draft.
Useful release image/dependencies/unrelated assets and private proof remain.
Future work starts from a new explicitly selected task and fresh disposable
target; do not restart completed CF/R1/BG/BX gates. Policy expansion/full Aurora,
new schema/major releases and different workloads retain the conditional checks
in`planning/remaining_checks.md`.

## Post-R1 work

**Background execution: complete.** BG-01 through BG-04 passed,
**8/8 acceptance checks and 100 weighted points**. Original R1 remains 99/99.
[Plan and exit checks](../planning/background_execution.md) ·
[Qualification decision](evidence/post-r1/background-execution/qualification-decision.json)

| Gate | Depends on | Status | Evidence |
| --- | --- | --- | --- |
| BG-01 | Qualified stock-r1 | Passed | [Verified workload](evidence/post-r1/background-execution/bg-01.json). |
| BG-02 | BG-01 | Passed | [ADR 0061](architecture-decisions/0061-scheduled-native-jobs-v1.md) · [native evidence](evidence/post-r1/background-execution/bg-02-native.json) · [primitives](evidence/post-r1/background-execution/bg-02-primitives.json). |
| BG-03 | BG-02 | Passed | [Worker and effect drills](evidence/post-r1/background-execution/bg-03-workers.json) · [populated upgrade/restore](evidence/post-r1/background-execution/bg-03-release.json). |
| BG-04 | BG-03 | Passed | [Paired load and restart](evidence/post-r1/background-execution/bg-04-qualified.json) · [Docker retirement](evidence/post-r1/background-execution/docker-retirement.json). |

Resume capsule: no active item, blocker, pending mutation, or live BG site.
The qualified reference used three stock Odoo web workers, four PostgreSQL
CPUs, one urgent lane and two bulk lanes. Reminder start p95 was 2.805 s;
mixed native list/detail p95 was 225.345/98.777 ms. Forty reports completed
in 41.609 s, and a restarted backlog drained in 19.594 s. All 150 expected
notifications were observed, and the Notes dataset was unchanged. The owned
Docker assets were retired; the stock-r1 image remains. Revalidate BG-04
when changing the workload, sizing, or queue/web behavior. The
[work log](work-log.md) retains the earlier attempts.

The [background execution follow-up plan](../planning/background_execution.md#follow-up-plan-for-sustained-background-workloads)
tracks BX-01 through BX-05. **All five follow-up gates passed:100% by equal gate weights.**
[Final decision](evidence/post-r1/background-execution/followup-decision.json).
The guarded CLI reported an empty job table and then the lower bound
above the lifecycle limit on a rebuilt site with 100,002 synthetic rows.
The PostgreSQL race probe reproduced a duplicate with a split lookup and
verified that writing the shared identity row forces a stale transaction to
retry. [CLI and concurrency evidence](evidence/post-r1/background-execution/bx-01-history-cli-and-race.json)
· [Retention protocol](architecture-decisions/0062-background-history-retention.md).
Native enqueue and private archival passed on a rebuilt Odoo site. An
identical retry after archival returned the original ID, changed input was
refused, and another workspace received its own job ID. A PostgreSQL probe
covered both stale transaction orders, rollback, excluded jobs and a digest
of 100,007 identity rows. The owned site and candidate were retired.
[Native archival evidence](evidence/post-r1/background-execution/bx-01-native-archive.json)

The core 0.1.30 to 0.1.31 upgrade passed with pending and previously claimed
jobs. A fault after publication first restored the old schema into a fresh
database. A second fault after a later deployment restored 100,002 retained
identities with the exact checkpoint digest and original archived job ID.
Both restores kept traffic closed until a separate resume review. The owned
site, three candidates and isolated base worktree were retired.
[Populated lifecycle evidence](evidence/post-r1/background-execution/bx-01-retention-lifecycle.json)

The reviewed job archive passed on a rebuilt site above the live-table
limit. It refused a stale batch, recovered the exact result of an interrupted
apply from live and retained rows, denied reuse of the attempted review, and
processed the next batch. The seven-day minimum and 100-row batch bound are
recorded in ADR 0062. The owned site, candidate and PostgreSQL fixture were
retired. [Operator archive evidence](evidence/post-r1/background-execution/bx-01-archive-operator.json)

The stock Odoo history action passed native HTTP and in-app browser checks.
Live and archived receipts were isolated by actor, workspace and site. The
native pager advanced above the 10,000-count display cap, the Archived filter
showed the original job ID, and the operator saw the live-table pressure
alert. The hot workspace page took 21.135 ms in one database plan, using
parallel scans and a sort. Cleanup under concurrent web load is still open.
The owned site and candidate were retired.
[Scoped history evidence](evidence/post-r1/background-execution/bx-01-scoped-history.json)

All four reviewed event archive kinds passed. An expired effect could not
replay, a recent native effect still applied, and the held and grace-period
events stayed live. A stale transaction was forced to retry. The fresh restore
matched the checkpoint digest for 100,007 compact records and preserved the
native projection and consumption receipt. The core 0.1.32 to 0.1.33 fault
restored the old schema and receipt, and the subsequent reviewed upgrade
preserved them. Both sites and the older image were retired.
[Event retention evidence](evidence/post-r1/background-execution/bx-01-event-retention.json)

The first cleanup benchmark missed its baseline target before cleanup.
Repeated direct-ID guards scanned the hot history union. The mixed phase
committed all five batches, with measured control-lock upper bounds of
16–121 ms, but expired idle read connections interrupted latency measurement.
That fixture and image were retired. [Diagnostic evidence](evidence/post-r1/background-execution/bx-01-cleanup-initial.json)

The primary-key guard passed mixed live/archived reads and foreign-ID denial.
Two paired cleanup samples met every fixed latency target. Worst mixed p95
was 34.839 ms for Notes list, 17.516 ms for detail and 59.201 ms for the hot
history list. Control-lock upper bounds stayed within 129 ms. A supplemental
40 request/s detail pair verified actual job-lock overlap below the proxy's
installed traffic limit. The read dataset was unchanged and all 184 producer
updates had matching events. Both benchmark sites and candidates were retired.
[Cleanup qualification](evidence/post-r1/background-execution/bx-01-cleanup-qualified.json)
and [BX-01 decision](evidence/post-r1/background-execution/bx-01-decision.json)

BX-02 passed. The protected reviewed
profile, resumable intent, selected-lane drain and desired/running/ready counts
use the existing deployment/site locks. Native maintenance and restore require
the fleet paused and stopped. Seven profile boundary regressions, 23 dispatch
regressions and 21 executor regressions passed; the 106-file contract freeze
passed. [Worker fleet decision](architecture-decisions/0063-reviewed-native-worker-fleets.md).

All seven BX-02 implementation checks passed native qualification, including
five-second forced drain, stale claim denial, both resize/upgrade lock races
and core 0.1.35 to 0.1.36 profile adoption. Idle lanes used about 105–107 MiB
each; the connection snapshot is a bounded observation, not a capacity target.
[Worker drills](evidence/post-r1/background-execution/bx-02-worker-profiles.json)
· [Release and retirement](evidence/post-r1/background-execution/bx-02-release-and-retirement.json).

The full host sweep passed 549 tests with one existing Windows-specific skip;
the 106-file contract freeze passed. [BX-02 decision](evidence/post-r1/background-execution/bx-02-decision.json).

BX-03 passed all eight implementation checks. The full host sweep passed 568
tests with one existing Windows skip (569 total), and the 106-file contract
freeze passed. [Gate decision](evidence/post-r1/background-execution/bx-03-decision.json).
The owned core39/core40 fixture has been retired.
No live producer, worker, database, mutation or recovery remains.
The [private contract](architecture-decisions/0064-native-recurring-schedules.md)
has ten deterministic time/identity tests, fifteen PostgreSQL authority checks,
fifteen SQL storage checks, native schema proof and nine native API checks.
The managed producer emitted 203 distinct receipts with one outstanding job,
automatic process restart, pause and drain. Reviewed populated upgrades passed.
[Native role evidence](evidence/post-r1/background-execution/bx-03-native-roles.json).

The actual core39→40 post-publication fault reached recovery_required with
ingress closed. Unexpected source receipt history refused restore before a new
database was created. The coordinated checkpoint restored into a fresh database
on retained core39, preserving 204 original receipts, cursor/high-water marks,
revision and the outstanding job. Credentials were revoked and work held until
separate resume and explicit repair. Old-authority refusal, owned cancellation
of the old held job, new occurrence completion and stale/new profile adoption
passed. [Recovery evidence](evidence/post-r1/background-execution/bx-03-recovery.json).
Thirty-four containers, six volumes, two networks and both current candidate
images were retired, in addition to the earlier obsolete images and helpers.
[Retirement](evidence/post-r1/background-execution/bx-03-retirement.json).

Resume capsule: BX-04 owns the one live fixture and sustained test below. BX-04 is the
one active item. [ADR0065](architecture-decisions/0065-background-capacity-advice.md)
fixes the sustained workload, latency/headroom targets and scaling comparison.
Bounded SQL observations passed seven actual PostgreSQL checks, including the
100,001-row and 1,025-group refusal boundaries; the tmpfs fixture was retired.
[Primitive evidence](evidence/post-r1/background-execution/bx-04-capacity-primitives.json).
The read-only advisor passed twelve boundary tests. Thirteen fleet tests and
the 106-file freeze passed. Source adds conservative preparation/commit timing,
per-handler worker duration, pinned `jobs capacity` and `jobs advise` commands,
and a bounded variable-CPU reference handler. Native proof is recorded below.
Initial core41 candidate `fd7f44c6a21e` qualified on disposable project
`mp-r0-r1releaseb152ddffba06`, port18126, database
`mp_disposable_r0_r1_release_b152ddffba06`. Native telemetry passed six jobs,
claim/end generation matching, full preparation plus attempt timing, pinned
snapshot and read-only CLI missing-health hold. Fleet startup was 14.500635 s.
[Native evidence](evidence/post-r1/background-execution/bx-04-native-telemetry.json).
The BG-04 paired rerun passed: reminder start p95 2.104 s, oldest ready
2.185 s, bulk drain 34.522 s; mixed list/detail p95 173.592/72.035 ms met both
absolute and relative targets. All 150 notifications and 40 report outputs were
scoped; Notes stayed exact. Manual bulk restart drained in15.406 s.
[Repeat evidence](evidence/post-r1/background-execution/bx-04-bg04-repeat.json).
Seventy workspaces were independently activated in operation
`4cba5909-2c14-4c1f-95b3-0cd1a3c684d9`, with ten report rows each.
Adding the CPU fixture handler required an artifact version bump. Corrected
reference0.2.1/core41 candidate `4a9a06242dfd` passed a separate approved package
upgrade `b794ebf1-b905-41ad-af35-43a9b8366888`, preserving all70 scopes/data.
Current target generation4 uses that image; old fd7f candidate remains only as
its recovery dependency. [Setup evidence](evidence/post-r1/background-execution/bx-04-workspace-setup.json).
The first sustained measurement lost an expired keepalive connection at the
scheduled start. It is incomplete, preserved, and retired:185 jobs completed,
37 remaining jobs cancelled after full drain. Added the proven BG04 reconnect/
warm-up before eligibility, with distinct attempt keys; no target was relaxed.
[Diagnostic](evidence/post-r1/background-execution/bx-04-initial-sustained-diagnostic.json).
The fresh180-second hot case passed all eight fixed targets. All222 jobs
completed once:150 scoped notifications,54 exact native reports and18 variable
CPU results, Notes unchanged. Reminder start p95 2.096s (max2.594s), bulk start
p95 187ms. Both web p95 bounds, connection/CPU/lock headroom and listener checks
passed. The profile drained. [Hot evidence](evidence/post-r1/background-execution/bx-04-sustained-hot.json).
Its source is checkpoint0c110ef8fba, private result `bx04-sustained-hot-02.json`;
this trace preloaded future eligibility, and makes no fresh-enqueue claim.
The70-workspace live case passed all eight fixed targets:222 single-attempt
jobs including72 fresh bulk commits,150 scoped notifications, exact report/CPU
outputs and unchanged Notes. Urgent start p95 2.035s/max2.520s; bulk start p95
291ms/max348ms. Commit delay p95 90.597ms/max121.474ms, connection fraction peak
28.125%, PostgreSQL CPU peak11.771%, no lock waits or listen drops. Mixed web
p95 list/detail187/78ms passed both relative and absolute bounds. The native
producer exited and all roles drained. [Live evidence](evidence/post-r1/background-execution/bx-04-sustained-many-live.json).
Read-only capture preserved222 paired generation1 claims/ends before container
removal; private trace is `many-live-worker-trace/` under this qualification realm.

Core42 upgrade `4a2aa8e7-f6b9-4788-b06e-5ad12167fec4` preserved all task,
notification and Notes rows, reference0.2.1 unchanged. Forty same-release runtime
samples supported a controlled identical72-job/70-workspace burst comparison.
Two lanes (fixed and work-based advice) drained in24.027s using48.054 lane-seconds;
three (count advice) drained in16.906s using50.718 lane-seconds. Both passed all
service/headroom targets, including≥64 simultaneous ready workspaces. No expiry
or extra useful-job benefit from the third lane was observed; no autoscaler is
authorized by these estimates. [Comparison](evidence/post-r1/background-execution/bx-04-burst-comparison.json).

Adversarial fairness was fixed and natively qualified on core43. Before the
change, the two hot workspaces consumed60 claims before a peer started. After
rotation, the first peer started after two hot claims, and all68 peers started
while each hot workspace had claimed only once. Child death/restart also
passed; the interrupted job reclaimed at a new generation and old apply was
denied while the new claim was running. [Native rotation](evidence/post-r1/background-execution/bx-04-fairness-native.json).
Core43 upgrade `ec8b996a-e687-44fc-916c-18efc985e314` preserved business data.
Ten PostgreSQL hint/rollback/CAS/ring tests and the106-file freeze passed.

The isolated slot-session defect was corrected on core44. The original probe
admitted two valid claims after losing only the advisory backend. The corrected
native probe peaked at one, and both jobs completed with no external effect.
[ADR0067](architecture-decisions/0067-pooled-claim-guard.md) preserves preparation
atomicity using a separate preparation-connection guard and a fresh snapshot,
plus running-row exclusion after reaping. Ten PostgreSQL race/visibility cases
passed and the SQL fixture was retired. Fairness and child restart were
requalified under this guard:all68 peers served, old apply denied while the
replacement claim ran, no source authority/effect changes.
[Core44 guard proof](evidence/post-r1/background-execution/bx-04-core44-guards.json).

Core44 populated upgrade `877c98e4-5da2-4de8-b4fd-150be1fdc550` preserved all
business rows; reference0.2.1 unchanged. The full host sweep passed584 tests
with one existing Windows skip (585 total,422.209s), and106-file freeze passed.

Core44 paired load passed:urgent start p95 2.171s, oldest2.695s, bulk37.074s;
stock Odoo idle/mixed list172.261/190.763ms and detail86.974/79.063ms.
All150 notifications/40 reports and restarted40 reports matched, Notes unchanged;
restart backlog31.109s. [Affected load](evidence/post-r1/background-execution/bx-04-core44-load.json).

Native pressure/stale CLI checks passed:50/64 connections (fault interval),
all advice held growth with null lane recommendations; genuinely aged and
missing health also held. Twenty queued reports completed once, Notes unchanged,
fleet container IDs unchanged and the pressure helper closed all connections.
[Pressure and stale evidence](evidence/post-r1/background-execution/bx-04-pressure-stale.json).

Recurring producer bursts passed on core44:ten schedules emitted70 reports
over180s, all single-attempt completions, no duplicate nominal occurrences or
sampled per-schedule overlap. Start p95 5.417s; stock paired list188/188ms,
detail79/78ms, all headroom/listener targets passed.
[Recurring burst evidence](evidence/post-r1/background-execution/bx-04-recurring-bursts.json).

Core44 identical burst comparison passed at both counts. Two lanes drained in
24.631s using49.262 lane-seconds; three in17.624s using52.873 lane-seconds.
Full-window lane use was120.429 versus180.385 lane-seconds. Both completed
all222 useful jobs with no expiry and passed all ten service/headroom targets.
Work advice selected2, count advice3. This establishes no automatic-sizing
benefit for the tested workload; it does not test a dynamic one-lane baseline.
[Current comparison](evidence/post-r1/background-execution/bx-04-core44-burst-comparison.json).

Cold-only burst passed:actual growth26.407s exceeded the ten-second validity
window. All20 jobs expired before any claim; read-only native advice warned
about late start and expiry. This deliberate overload is separate from admitted
workload results. [Cold-start evidence](evidence/post-r1/background-execution/bx-04-cold-start.json).

Fresh restore and separate resume passed for operatione296bac7. It restored
core44 into a fresh DB, preserved business/history/cursor/rotation digests,
revoked every service credential and held service work. Human idempotent work
was carried forward with a new generation and no old lease. Traffic stayed
closed until the independent resume review; no worker/producer was started.

Post-restore proof passed:old claim and old rotation epoch denied, new rotation
reset and reservation succeeded, old profile pins refused. The authorized human
job completed after reclaim (two attempts total); two new jobs completed once.
Service credentials remained revoked, business data unchanged, fleet drained.

Fresh forward upgrade`47abfa02-fb35-4c1e-b56b-6c7af68439fa` passed on core45.
The candidate differs from core44 only in platform/native version metadata;
worker/queue/authorization bytes are identical. Three recovered/new reports
matched ten rows/45 points, business rows remained exact. Eight core-upgrade
regressions and the106-file freeze passed.
[Recovery/forward proof](evidence/post-r1/background-execution/bx-04-guard-recovery.json).

BX-04's final cleanup removed48 containers, six volumes and two networks plus
core44/three tags. Intermediate cleanup removed42 terminal helpers and
core42/core43/four tags. No running service or volume remains for that realm.
At BX-04 exit, retained only core45 imagee03dc57213c5 as the useful BX-05 clean baseline;
stock dependency base and unrelated existing assets were preserved.
[Retirement](evidence/post-r1/background-execution/bx-04-retirement.json).
[BX-04 decision and acceptance mapping](evidence/post-r1/background-execution/bx-04-decision.json).

Resume capsule: no active item, check, site, worker, producer, uncertain mutation
or external effect. BX-01–BX-05 are complete. BX-05's disposable project
`mp-r0-r1release868dbb340ae2` and both remaining candidate images were retired.
Last qualified source is core45/reference0.3.3; build digest25f071befa83 is
evidence, not a retained running image. Do not replay retired fixture commands.

[ADR0068](architecture-decisions/0068-app-owned-report-continuations.md) fixes
5,000 snapshot rows/100 per job, original expiry, current source/owner guards,
atomic cursor/successor and job-before-run cancellation locking. Private run
storage and report_chunk:1 reuse existing native job fencing; report:2 and native
Odoo screens remain unchanged. Native proof completed13 chunks/1,201 rows/
519,600 points and exact digest despite later source edits. Compatible partial
upgrade preserved the1,200-row prefix before the final chunk. Terminal cleanup,
active-array constraint, scope-filtered range and5,001 refusal passed.

Atomicity proof passed initial/caught-enqueue rollback with unrelated commit,
same-workspace other-actor denial, unknown contract and revoked origin denial,
four concurrent submissions yielding one run/job, and failure after successful
successor insertion rolling back cursor, job and successor identity together.
[Native evidence](evidence/post-r1/background-execution/bx-05-native-basics.json).

Two actual app defects were fixed:flush the advanced cursor before successor
preflight; permit SQL NULL only for terminal snapshot cleanup. Their original
failure records remain private; the original run was retried/reclaimed without
seed replay or progress reset. Upgrade operations:0c1bd811 (0.3.0),df9977ec
(0.3.1),825c81ec (0.3.2). Logs and immutable old packages are retained privately.
Cleanup retired48 terminal helpers and three superseded images/seven tags,
including the initial install's retained tag after checking its completed journal.
Those app/edge/database assets were retained during qualification and retired
at the final BX-05 exit below.

Managed process loss passed:automatic child restart, old apply denied while
generation2 was running, exact50 chunks/5,000 rows/2,497,500 points/digest,
then drained. Partial cancellation passed at100 committed rows:obsolete compute
did not advance, no successor, earlier work retained. Deleted source denied
before progress. [Process](evidence/post-r1/background-execution/bx-05-process.json) ·
[Cancellation](evidence/post-r1/background-execution/bx-05-cancellation.json).

Populated recovery passed from cursor800. Publication fault20561ee8 restored
into a fresh DB with task/report/note digests exact, traffic/dispatch closed and
new claim generation. Separate resume refused old claim/profile, then completed
all50 chunks/5,000 rows/2,497,500 points with the exact digest and no prefix
replay. Fresh forward operationac35d2f6 qualified reference0.3.3; only version
metadata differs from0.3.2. [Recovery](evidence/post-r1/background-execution/bx-05-recovery.json).
Full host585 tests:584 passed, one existing Windows skip,425.409s. Current
contract freeze106files/8rows/major1 passed. Final cleanup removed46containers,
six volumes, two networks and the last two candidate images/four tags; earlier
cleanup removed48helpers and three images/seven tags. Unrelated Docker assets,
stock dependency base and private packages/checkpoints were preserved.
[Retirement](evidence/post-r1/background-execution/bx-05-retirement.json).
[BX-05 acceptance mapping](evidence/post-r1/background-execution/bx-05-decision.json).

Remote delivery/fan-out/common orchestration remain conditional and unselected
because this app needs none. Automatic sizing/brokers/pool expansion were not
selected under BX-04's measured envelope; reviewed manual profiles and read-only
advice are implemented. These decisions satisfy their explicit plan gates.
All five gates passed,100% by equal gate weights, separately from original
R1's unchanged99/99 acceptance checks and100 points. No user input needed.

BX-04 checklist:

- [x] Fix admitted workload, failure cases and quantitative latency/headroom targets.
- [x] Verify bounded SQL classification and pure advisor boundary behavior.
- [x] Qualify native telemetry, timing, pins and read-only CLI advice.
- [x] Repeat the original BG-04 paired native web/reminder/bulk workload.
- [x] Measure sustained hot-workspace, 70-workspace and variable-duration load.
- [x] Compare fixed, count-based and estimated-work advice against actual drain/useful work/cost (core42 and corrected core44).
- [x] Verify physical cold growth misses a shorter useful window and advice warns.
- [x] Qualify process loss, fairness, recurring bursts, connection saturation and stale metrics.
- [x] Finalize populated release/fresh recovery proof and successful forward-upgrade evidence.
- [x] Decide automatic-sizing/broker/pool changes from evidence:retain manual profiles/advice; no controller selected.
- [x] Record final evidence and retire owned qualification assets; retain one useful BX-05 baseline image.

BX-05 checklist:

- [x] Freeze the selected app's bounded cursor, consistency and continuation contract (ADR0068).
- [x] Implement app-owned progress and atomic cursor/successor updates with scoped authority; actual native rollback/duplicates verified.
- [x] Prove rollback, retry/process loss, duplicates and cancellation after partial progress.
- [x] Qualify compatible upgrade and fresh restore of partially completed work.
- [x] Record app results, conditional-extension decisions and retire owned test assets.

BX-03 checklist:

- [x] Define and test fixed UTC selection, expiry, missed policies and stable nominal identity.
- [x] Qualify private schedule/cursor/receipt storage and concurrent atomic enqueue.
- [x] Install versioned native tables and recognize their lifecycle footprint.
- [x] Wire scoped service authorization, edits, pause/resume, rotation and overlap.
- [x] Add the optional pinned producer role with readiness, maintenance exclusion and drain.
- [x] Qualify the narrow native-credential lifecycle profile and retained schema compatibility.
- [x] Qualify populated upgrade and fresh restore with a previously emitted occurrence.
- [x] Record native evidence and retire all owned qualification assets.

BX-02 checklist, independently of gate exits:

- [x] Implement reviewed profiles and resumable desired state; verify boundary regressions.
- [x] Start pinned native roles and refuse incorrect database/site/release/inventory pins.
- [x] Verify count resizing, selected drain and recovery after partial start.
- [x] Verify connection-loss readiness and recovery.
- [x] Verify graceful and forced active-attempt drain with stale claim denial.
- [x] Verify resize/upgrade exclusion and new-release profile adoption.
- [x] Measure connection/resource usage and retire qualification assets.

BX-01 checklist, tracked independently of the five gate exits.

- [x] Measure the live-table threshold on a guarded site.
- [x] Verify native archival, duplicate identity, transaction races and rollback.
- [x] Verify upgrades and fresh restores with historical totals above the cap.
- [x] Review and qualify the operator cutoff, retention sizing and resumable batch.
- [x] Verify paginated scoped status and aggregate alerts.
- [x] Qualify event and outbox replay and consumed-effect retention.
- [x] Measure lock duration and web latency during bounded cleanup.

The shared foundation stress test is tracked separately from the completed R1
gate. The selected systems are stock Odoo Maintenance and a bounded Aurora
Tasks slice. Both passed offline registry and access checks, and both changed
persisted workflow state through the stock Odoo interface. The shared Notes
fixture verified separate workspace tabs and viewer restrictions. Both adopted
the same core27 image with independent approvals and checkpoints. Aurora
restored to a fresh database and separately resumed while Maintenance remained
live on core27. Both saved a new change through stock Odoo after the update.
All four stress checkpoints passed, and the disposable Docker assets were
retired. [Lifecycle evidence](evidence/post-r1/shared-foundation/lifecycle.json)
[Plan and checkpoint](../planning/shared_foundation_stress_test.md)

The platform now has an independent fork release policy. Future major upgrade
checks target the platform's own releases. See [ADR 0060](architecture-decisions/0060-independent-fork-release-policy.md)
and the [remaining-check inventory](../planning/remaining_checks.md).

The stock WebClient follow-up verified the new release notice across a staged
release change, including the original unsaved form and a persisted edit in the
new tab. Notes 0.2.9 passed current save, stale save and viewer denial. The test
site's Docker assets were retired. The next item is to define the supported
stock release profile and bind its qualification to an exact kit. Background
execution is deferred. [Evidence](evidence/post-r1/shared-foundation/stock-webclient-follow-up.json)

The stock WebClient release passed **SW-01 through SW-05** (100% of the
stock release goal). The selected `stock-r1` kit uses image `07cacdf4`
and manifest `cf8c53b9`. The exact 10,000-note run with 20 concurrent
sessions measured list p95 367.832 ms and detail p95 169.833 ms. The
disposable work retired 316 containers, 40 volumes, 10 networks and
38 temporary image tags. [Stock release gates](../planning/stock_webclient_release.md)
and [qualification decision](evidence/G7/20261105-stock-release-repro/qualification-decision.json)

## Last backend continuation — Windows regression fixtures corrected

- The supplemental Windows sweep ran 538 tests with one failure, two errors and one skip. Two metadata upgrade tests selected the current Stats version instead of a successor. A retained-scope enablement test still expected the old no-checkpoint path. The corrected tests keep downgrade refusal and explicit permission acknowledgment coverage, require the current checkpoint/restart, and verify that the executable release stays pinned. Runtime source is unchanged. The two affected test modules pass all 27 tests. [Regression triage](evidence/G7/20261105-section28-audit-01/regression-triage.json)
- The full Windows rerun completed with 537 passes and one platform skip. All seven startup tests passed on the exact core26 Linux image, including the skipped symlink case. The temporary container auto-removed. The Node suite's 46 passes and TypeScript 7.0.2 check remain recorded. [Regression evidence](evidence/G7/20261105-section28-audit-01/regression-results.json)
- The selected kit now carries Git source `d0746974f8bd6905a1c61415475db2f941342060` and manifest SHA-256 `399fe59efd43b4af5fce746874c19e9258880f4802a374129ae29b9d5e90f1fd`. Only the source archive changed. The other 51 components remain exact. Expanded privacy verified 54,508 Git files, 18 changed OCI layers against the historical baseline and 413 history blobs with zero findings. The repeated read-only backend audit confirmed the same kit images, runtime identities, contract freeze and operation journal. [Source refresh](evidence/G7/20261105-core26-release-kit-01/source-refresh-regression.json), [privacy](evidence/G7/20261105-core26-release-kit-01/privacy-delta-regression.json) and [backend audit](evidence/G7/20261105-section28-audit-01/backend-audit-regression.json)

## Previous continuation — §28 backend audit complete

- The current backend audit verified both running reference images and independent workers, matched every specification acceptance ID to the ledger, verified the 52-component kit and matched all 377 recorded build inputs to the current checkout and archived source. It confirmed the completed developer-upgrade journal with the extracted CLI and checked twelve runbooks and fifteen CLI commands. [Backend audit](evidence/G7/20261105-section28-audit-01/backend-audit.json)
- The actual dependency-changing fixture upgrade failed after its native commit. Fifteen hashed records verify the observed failure, new-database restore and separate resume. Nine host lifecycle modules still match. The later core23 fault and current core26 source binding cover the changed native executor. The fault itself retains its original environment. [Failed-upgrade evidence](evidence/G7/20261103-fresh-release-01/dependency-recovery/qualification-corrected.json) and [recovery binding](evidence/G7/20261105-core26-release-kit-01/retained-recovery-binding.json)
- The audited §28 deliverable map and local handoff identify the two loopback URLs, credential setup and current evidence. The remaining execution is the deferred browser walkthrough of the two installed developer variants. Final gate recording follows that check. [Release checklist](r1-release-checklist.md) and [handoff](r1-handoff.md)
- The Node source regression suite passed 46 tests and the TypeScript check passed with 7.0.2. Initial Windows sweep `34056` ended with the fixture failures described above.

## Previous continuation — developer examples installed and verified over HTTP

- The documented packaging path produced exact Labels 0.2.5 and Canvas 0.1.5 bytes in the clean operator. A fresh candidate build copied five modified inputs into an isolated source context and retained the exact core26 dependency environment. The first attempt stopped before build because the isolated operator lock directory was missing. The first built image used the default policy and omitted the installed Notes Stats connector. The staged planner refused it before registration. The corrected build used the selected release's exact policy, preserved Notes and the connector, and superseded the refused image. [Candidate](evidence/G7/20261105-core26-developer-install-01/candidate-build.json) and [refused image retirement](evidence/G7/20261105-core26-developer-install-01/refused-image-retired.json)
- Exact operation `e68a26a9-a065-40a2-a237-bc09cd28275e` checkpointed and upgraded the two variants across four workspace scopes with no permission, binding or endpoint change. The fresh rehearsal on port 18101 runs generation5 and image `sha256:a5b4b8edd67175221442ad7ba006603b06626cd9270985c3a9488ad19143b2e3`. The selected core26 kit and original reference on port 18100 retain the shipped versions. [Independent review](evidence/G7/20261105-core26-developer-install-01/review.json) and [apply result](evidence/G7/20261105-core26-developer-install-01/apply.json)
- HTTP verified the updated Labels action for the editor and its absence for a viewer, native Odoo Notes list/form, foreign Note denial, the existing Canvas board, and the served bundle containing the modified Canvas subtitle. The Notes and board rows, completed job outcome and independent worker identity were preserved. Retired ten exact exited containers, including the superseded app, after 32 diagnostic streams passed the bounded scan. [Installed backend](evidence/G7/20261105-core26-developer-install-01/backend-verification.json) and [helper retirement](evidence/G7/20261105-core26-developer-install-01/helper-retirement.json)
- The local handoff records startup, fixture credential locations, branch, tests, recovery and residual risks. The remaining G-01e verification is the fresh browser walkthrough and final gate audit. The scope remains 99/99 and 99 weighted points. [Local handoff](r1-handoff.md)

## Previous continuation — fresh core26 backend qualified

- The clean consumer installed Core26 and three native reference plugins in a fresh disposable database. Five actual HTTP checks passed, including scoped native Odoo Notes list/form descriptors, Labels, minimal Canvas and foreign access denial. The separate locked worker completed one original-actor job in one attempt. Only the loopback edge publishes a port. [Backend evidence](evidence/G7/20261105-core26-release-kit-01/fresh-backend.json)
- Docker default address pools were exhausted before the first fresh project created assets. Two verified empty networks from a retired project were removed. The next prepare succeeded. The first initialization reached clean core provisioning and stopped because the guide omitted the reviewed catalog import. All 19 exact digests were imported through the clean CLI, then publication resumed from the verified pre-install state. The corrected initializer refuses missing or incomplete catalogs before database startup. [Network evidence](evidence/G7/20261105-core26-release-kit-01/network-capacity.json), [reconciliation](evidence/G7/20261105-core26-release-kit-01/catalog-and-publication-reconciliation.json) and [preflight test](evidence/G7/20261105-core26-release-kit-01/catalog-preflight.json)
- The extracted developer environment validated and reproduced versioned Labels and Canvas archives. The clean consumer exercised the shipped variants. The modified examples were packaged only. The fresh browser walkthrough is deferred at the user's direction. [Packaging evidence](evidence/G7/20261105-core26-release-kit-01/developer-packaging.json)
- Current image provenance passed with 377 build inputs, 3,939 upstream and generated source hashes, 77 Python distributions, 113 OS packages and 274 application notices. The pre-refresh kit's expanded privacy scan passed. Fresh command and Docker diagnostics had zero findings across 151 streams and 142 known values. Removed 32 exact exited helpers and superseded apps. Kept current services and data. [Provenance](evidence/G7/20261105-core26-release-kit-01/provenance.json), [kit privacy](evidence/G7/20261105-core26-release-kit-01/privacy-delta.json) and [fresh diagnostics](evidence/G7/20261105-core26-release-kit-01/fresh-log-privacy.json)
- The draft now binds Git source `38ca47098c68c8bd0ea0fe8839386d2052560ac5` to manifest SHA-256 `0f1723649020a736ef6f2a1b0c388b84d6726b407af44a83012c6f9f845bfc26`. The source refresh added the catalog preflight and current documentation while preserving 51 exact components, including all images, plugin archives, notices and wheels. The expanded final scan verified 54,490 Git files, 18 changed OCI layers and 373 history blobs against the retained proof with zero findings. The clean install used the pre-refresh snapshot and the new preflight passed separately at the database boundary. [Source refresh](evidence/G7/20261105-core26-release-kit-01/source-refresh.json) and [final privacy scan](evidence/G7/20261105-core26-release-kit-01/privacy-delta-final.json)
- OPS-03 passes on the selected core26 image and refreshed local kit. The real fault, fresh restore and separate resume ran on core23. Seven recovery modules match across both build receipts and the current source. The CLI observation wrapper has separate qualification. The older fault test stays scoped to its actual image. [Recovery binding](evidence/G7/20261105-core26-release-kit-01/retained-recovery-binding.json)

## Previous continuation: core26 kit assembled and clean operator ready

- The kit at `.local/releases/r1-0.1.26` verifies all 52 components. Its source is `e7a5458d856d7d0e7b9815d3b6bf47d358c3c214` and its manifest digest is `b4ce8f9c2f14043d7f34872fd18f40638fed1b6ee4d899c83161022d0c7a6c3c`. It carries 19 plugin archives, the selected application and four support images, 13 wheels and exact build and reproduction receipts. Assembly exited successfully. [Assembly](evidence/G7/20261105-core26-release-kit-01/assembly.json).
- The independent setup in `.local/release-kit-core26-rehearsal` installed the pinned wheels offline and extracted the recorded Git source. The clean Python3.12.16 operator independently verified its private OS boundary, CLI help and 106-file freeze. Setup exited successfully. [Operator setup](evidence/G7/20261105-core26-release-kit-01/operator-setup.json).
- G-01d2 remains active at 98/99 checks and 97.5 points. Next use the existing clean operator workdir for a fresh loopback reference and worker walkthrough. Verify layered privacy, current provenance and final evidence before restoring OPS-03. The kit assembly added no persistent Docker assets.

## Previous continuation: core26 installed and UI09 qualified

- The independently reviewed operation `966c6bbf-37bd-412f-b1fe-c5d55ed7d207` installed core26/Shell13 in seven native scopes. Verification checked 54 checkpoint files and all 17 tables with the declared completed-job fence updates. The separate worker binding and process were preserved. Logs were retained before removal of seven completed helpers and the superseded app container. [Preservation](evidence/G7/20261105-core26-maintenance-01/preservation.json) and [retirement](evidence/G7/20261105-core26-maintenance-01/helper-retirement.json).
- The installed shell retained the same empty accessibility nodes through loading and error transitions. Edge exposed polite and assertive atomic updates. The PID-scoped Windows accessibility listener received distinct live-region events during the held navigation and denied Note request. This verifies delivery to the Windows accessibility interface. Spoken output from a specific screen reader was outside this probe. [Installed observations](evidence/G7/20261105-core26-maintenance-01/installed-observations.json).
- Settings rendered three members with English and Arabic plural forms. The installed Operations formatter produced localized UTC journal dates in both languages. Native label and required-field validation, dialog names and focus, glyph contrast, reduced motion, 100% and 200% zoom, 320 CSS pixel reflow, Arabic RTL, long mixed-direction Canvas input, keyboard lane change and keyboard exit to Settings were checked. Canvas changes were discarded. All 17 tables matched after the browser tests. The shipped reference uses the shell layout.
- The initial browser probe sampled loading before it settled. The first Windows observer invocation omitted its PID. The next attempt captured native events but sampled the previous visible count after the document locale had changed. The corrected probe waits for the visible count and loading state. All browser processes exited and original zoom preferences were restored.
- The network-disabled no-cache build reproduced imagefb02's inventory2747 and exact dependency environment. The duplicate tag was retired. [Reproduction](evidence/G7/20261105-core26-repro-01/qualification.json).
- UI09 and BOOT-02 pass on the current reference. Final kit, OPS-03 and the full G7 audit remain. Progress is 98/99 checks and 97.5 weighted points.

## Previous continuation: UI09 announcement and localization correction

- The installed core25 browser probe held an actual Notes navigation response and exercised a denied foreign Note. The loaded shell had no status or alert region before either message. Edge exposed the respective roles after insertion. This proves the timing gap in the live-region markup. [Baseline probe](evidence/G7/20261105-ui09-live-region-01/baseline.json).
- Shell13 keeps the shell and Operations loading and error regions mounted with atomic announcements. Settings now uses the browser's locale-aware number and plural formatting for the member count. Operations formats existing timestamps in the selected language and explicitly displays UTC for the deployment journal. Machine-readable timestamps and the SDK wire contracts retain their existing format.
- The first timestamp test assumed Arabic-Indic digits. The installed ICU selected Latin digits and localized the month. The revised test checks localization and UTC semantics. The affected Node suites passed 12 tests, the core upgrade suite passed 8, and the freeze verified 106 files across eight rows. Both edited XML templates parse. [Source checks](evidence/G7/20261105-ui09-live-region-01/source-checks.json).
- Core26/Shell13 requires an immutable build and independent maintenance before installed proof. Core25/configuration6 remains the selected runtime, so its BOOT-02 evidence still applies. UI09 and OPS-03 remain open. 97/99 passed and 95.5 weighted points.

## Previous continuation: core25 installed and reproduced

- During the pause the four reference containers stopped and Docker lost the unreferenced core25 candidate and worker image. The existing containers restarted with their data volumes. The verified 50-file kit restored the worker image. The rebuilt candidate matched all 377 source input hashes and the full admitted runtime inventory. Two ordinary probe calls timed out during Docker auto-removal. A named read-only probe verified the inventory and was removed. After Docker cleared both auto-removal containers, the ordinary observer passed.
- The separately reviewed operation `943509b3-e2b1-4dce-95cd-5771cd5e6642` applied the five owned changes across seven native scopes. The verifier checked all 50 checkpoint files, the independent worker binding and the 17 tables. The completed job had the expected release and dispatch fence updates. Seven successful helpers and the superseded app container were removed after their logs were retained. [Upgrade preservation](evidence/G7/20261105-core25-maintenance-01/preservation.json) and [helper retirement](evidence/G7/20261105-core25-maintenance-01/helper-retirement.json).
- The installed confirmation has the accessible name “Delete note” in both themes at 100% and 200%. Both close glyphs are visible and their rendered stroke peaks measure 4.06:1 in light mode and 4.807:1 in dark mode. The original text sampler flagged the dark icon's unused CSS text color. The separate measurement uses the pixels of the visible glyph. The 320 CSS pixel samples showed no horizontal overflow. Three browser runs exited successfully and the prior zoom preferences were restored. [Installed observations](evidence/G7/20261105-core25-maintenance-01/installed-observations.json).
- The independent no-cache build with network disabled matched the selected image's runtime inventory and dependencies. The reproduction tag was retired after verification. BOOT-02 is passed and contributes 0.5 points. [Reproduction](evidence/G7/20261105-core25-repro-01/qualification.json).
- UI09 still needs a scope check for localized dates, numbers, time zones and pluralization, plus assistive technology verification of loading and error announcements. Keep the release kit and final audit open until the final selected source and image are qualified.

## Previous continuation: core25 candidate built and statically admitted

- Source/evidence committed76c9b3f1, then one actual code-only build36511terminal0 from current exact567d. Candidate image602865058c7c3addb4c98bfd415c2964c954001743959664c4b0ec757c1b29d6/inventory1b12d51b9e584021ca22eb9c69c5d71c7e828833e563e60f5d07e91bb6f3e745/tag modular-platform:stage-20261104t085307833780z. No running app overlay, package rebuild or dependency recompile. BuildKit defaultARG warnings retained; verified exact base alias was removed.
- [Static admission](evidence/G7/20261104-core25-accessibility-image-01/candidate-admission.json) passes: five expected inventoried owned correction/version changes; core24→25/Shell11→12/no migrations. Actual77Python distributions/interpreter/architecture/markers/lock byteexact, packagedartifacts/policy exact, no sourceinventory drift/all current buildinputs hashes exact. New reference-packaging helper is additionally included by existing Docker tools COPY and source receipt, outside inventoried core source delta; no app route/approval change. All four current runtime process/image/mount/network identities exact, one uniquely tagged candidate retained, no new persistent container/volume/network.
- G-01b3 passed_static_candidate_not_installed; next G-01b4 normal stage/independent exactreview/checkpoint/apply/preservation/installed UI09. Current managed reference remains567d/config5/worker87, not6028. No operation staged/approved/applied. Actual compiled title-label/nativeclose proof, finalnarrow/locale/ATscope and corrected final-image reproduction/kit/privacy/developer audit stillrequired.96passed/2invalid/1failedUI09/95.0points unchanged; no static-source credit. All actual build/admission/browser handles terminal.

## Previous continuation: actual engine zoom/current UI audit and core25 source correction

- Previous2c1efa43 was real backend release-guard progress. Backend-independent preflights completed; resumed the necessary UI09 boundary using the SAME owned Edge profile, independent of the unavailable in-app browser. No new browser profile/Docker asset. Current567d/config5 unchanged; all17tables/four runtimes/independent worker exact after both actual runs, both exit0/no ownedprofile processes. Selected owned-profile zoom keys restored to their original absence/values.
- [Installed audit](evidence/G7/20261104-core24-ui-audit-01/qualification.json): two actual36case observations at100/200percent. Same1280px browser window1256→628CSSpx and DPR1→2, without CDP device metrics override; primary Chromium zoom-pref semantics plus actual runtime metrics resolve the previous emulated-only limitation. English/fully loaded Arabic Settings no horizontal document overflow; sampled headings/controls/fields/Labels text contrast0findings, native confirmation trap/Escape/initiator restore and Labels names/Escape/restore, reducedmotion/AXmain+field+command/error semantics pass. No Save/Delete/Labels submission or app overlay; browsernetwork0foreign/exceptions. This is bounded diagnostic proof, not full WCAG/AT certification.
- Actual baseline screenshot still shows blank dark native close glyph. Newly measured native confirmationAXname empty in boththemes/zooms; upstream Dialog has no title label. ADR0057 follow-up fixes only owned assets: exclude .btn-close from generic button fill via zero-specificity :where; owned QWeb extension labels native web.Dialog with existing props.title. Preserve full host.js/native_interactions/client_release/bootstrap bytes/native behavior. No upstream edit/public DTO/packaged reference plugin change. Source platform0.1.25/core25/Shell12, not installed.
- [Source25 checks](evidence/G7/20261104-core24-ui-audit-01/source25-checks.json):17affectedPython tests+native-interaction JS suite pass, XML exact unique inheritance target and existing106freeze/eightrows pass,133privacy0. Actual template compilation/close glyph/name/browser proof still requires normal immutable candidate/independent maintenance. Current source-only work earns no point;96passed/2invalidBOOT02OPS03/1failedUI09/95.0 unchanged. Narrow/mixed text/locale-formatting/pluralization/actual assistive-technology announcement scope remain explicit; do not silently claim them passed.
- NEXT G-01b3 one code-only candidate from exact current567d under ADR0052, with current reviewed distribution policy; no rebuild24. Then normal stage/separate exactreview/checkpoint/core_upgrade/preservation/installed correction+remainingUI09, final-image reproduction and ADR0058-bound finalkit/privacy/developerpath/audit. Never replay completed04fa operation or cleanup. All actual browser/prep/check handles terminal; current app/worker remain selected and healthy.

## Previous continuation: explicit release inputs and real stale-receipt refusals qualified

- Previousdc7506c2 was real developer-path packaging progress. Backend release audit found assemble.py hardcoded the core23 reproduction receipt; refresh_draft.py could replace source without proving compatibility with the existing kit image. ADR0058 corrects these provenance gaps outside the application context; no public contract/native runtime changes.
- Both commands now require explicit application build/reproduction receipts. Validate complete passed BOOT02 comparisons and immutable app/base/inventory, matching build identities, complete source path set/current hashes, bounded duplicate-free receipts/canonical paths. Assembly retains exact receipt bytes and verifies selected image inventory; source-only refresh refuses a different app/base/inventory before archive mutation. Operator selection remains required; metadata never grants execution approval/authenticates a publisher.
- Nine affected tests PASS, including real tiny-kit refresh mismatches preserving allbytes. [Actual command qualification](evidence/G7/20261104-kit-input-binding-01/qualification.json) on committed802dd108: both CLIs with actual old core23 build/repro receipts refuse checkout/build source set drift before output/receipt/archive/image-export creation. Existing draft all50 components byte-verify unchanged.133known-value privacy0findings. No Docker assets/native source/DB/approval/catalog/worker mutation; no final kit assembled/refreshed.
- G-01d2c passed_bounded_guard. Source-only/documentation work earns no weighted point:96passed/2invalidBOOT02OPS03/1failedUI09/95.0 unchanged. Actual corrected final candidate reproduction/kit privacy/installation remains required; do not use historical receipts or regenerate known residual567d to regain points. Backend-independent preflights now have concrete evidence; next gate-critical work is installed UI09 observation and the bounded close correction, followed by final source/image kit closure.

## Previous continuation: developer entry point and versioned packaging exercised

- Previous1b7bbd88 was real backend qualification progress, not a wait. Added PLATFORM.md/developer-guide.md and a small tools/package_reference.py CLI around the existing deterministic reference assembler. It accepts only the five repository examples, reads native code as data, refuses existing outputs and never grants trust or installs code. No native plugin/source version or public contract change.
- [Actual packaging qualification](evidence/G7/20261104-developer-packaging-01/qualification.json): same isolated kit Python, eight real CLI processes, two synthetic source-copy changes (Labels0.2.5 contribution label and Canvas0.1.5 subtitle). Both exact archives pass independent curated validation and second-build byte equality. Two mismatched native/package versions leave no output; two overwrite attempts refuse and preserve original bytes. New presentation bytes exist in the archives.133known-value scan0findings. No Docker command/new asset/browser/live catalog/authority/database/deployment/worker mutation.
- Guide links the current isolated kit setup, native Notes/Labels model/view/service guards, custom-page lifecycle, ordinary exact-hash staging/review, permissions and recovery/independent worker. All these instructions retain final-kit/full installed developer-walkthrough limits. Packaging proof is not BOOT02, a fresh native extension install, UI09, OPS03 or full§28 completion. Existing draft lacks new helper/docs as well as heartbeat/source/image updates; final refresh remains required.
- Added G-01d2b passed_bounded_packaging. No extra acceptance/weighted credit:96/99passed,2invalidBOOT02OPS03,1failedUI09/95.0points. Active G-01d2 final-kit reconciliation; UI09 browser work remains deferred per user. Next compare remaining guide/install path with actual supported candidate/catalog initializer inputs, then continue qualified final-image closure after UI09 correction. Do not loop on already-passed packaging or rebuild current known residual567d.

## Previous continuation: backend operator/kit compatibility checked

- User requests backend checks while browser verification is deferred. Current managed realm remains core24/Shell11/image567d/inventory0d4b/config5. No application change, browser launch, database write, lifecycle replay or new Docker asset in this continuation.
- [Operator release preflight](evidence/G7/20261104-operator-release-preflight-01/qualification.json): all50 kit components verify; eight code differences from the draft source are explicit (six shell/version paths and two operator CLI paths). Current CLI runs in the kit’s isolated Python environment;19 affected tests pass. Both old-kit and current CLI read the actual completed04fa operation with identical legacy journal fields; only current CLI adds returned heartbeat observation. All174 durable control files and four stable process/image/mount/network identities remain exact;133known-value scan has0findings.
- Initial final runtime assertion included changing health-check timestamps. Original check01.py retained; corrected comparator checks stable identity/state. Actual completed readbacks and test streams reused without rerun. No product defect or uncertain mutation resulted.
- Draft kit still packages14de and lacks the heartbeat addition. Do not refresh/export an intermediate candidate repeatedly. Final refresh must include qualified source/tools/runbooks/image, privacy deltas and developer-path reconciliation. [Release closure checklist](r1-release-checklist.md) maps all15 §28 deliverables and separates required work from optional polish. Stale conflicting resume instructions below replaced with one current capsule.
- No new acceptance or weighted credit:96/99passed,2invalidated(BOOT02,OPS03),1failed(UI09),95.0weighted≈95%. Required remaining5points unchanged. G-01d2 backend reconciliation active; UI09 pending, not passed. All processes from this continuation terminal; no uncertain lifecycle state.

## Previous continuation: core24 actually installed/preserved; UI close residual remains

- Previouse724ad0f real staticadmission progressed. Actualexisting kit-owned catalog is .local/release-kit-rehearsal/private/catalog; firstprepare refusedbeforeanyobservation/stage afteronlynewobservingrecord. Recorded/refinedcontext and resumedonlyexactempty-observation state; no catalog/store/site reset. Ordinary stage/plan/register/separateindependentreview actual7native scopes/fournativeplugins, externalprovider untouched. Operation04fa2cfb-b2d1-4ae3-b251-75b9c931630a/hash2b0ca4cdec06d747c56a1ef87c8f6b0695241d945e63602b39aef02f1bd5f871 explicitly approved current900s policy/exacthash/trust+destructiveack/backuprequired/no permissionchange. Source/native diffs exactly6files/mp_core23→24+mp_shell10→11/no migrations; bindings/endpoints/artifacts unchanged.
- Actual apply62489terminal0 completedonce/currentgen5/image567d/inventory0d4b; statusmutation+traffictrue. Real independentCLIheartbeat observed during checkpointedmaintenance: fresh0.905s/elapsed65.157s, not a work-success assertion. Verify98665terminal0: dispatch9→10→11→12; all16business/authority/event tables exact plus solecompletedjob onlyrelease_digest/claim_generation+1/dispatch_generation11 (attempt/state/resultunchanged). Fullcheckpoint46filesbyteexact/alloldfilesretained. Nativeversionsonlycore24/Shell11, installations/features/bindings/endpoints exact. Externalworker4daa/image87/process/key/pub1/mount/network exact; onlyindependenthelper pin aligned14de→567d afterverification. Parentreference state/currenttarget updated, no actor/record/worker recreation.
- Newprotected .local/g7-ui-core24-01 inputs/snapshots pointtoSAMEownedprofile; old14de input/proofs preserved. ActualinstalledsmokePID44980exit0/no profileprocess,0foreignHTTP/0exceptions, no Save/Delete/Labels submission,17tablesexactafterreads/workerexact. NewHTMLlangEN/AR/Settings preference strings/headings/inputfocusring/nativeclosebackgroundimage observed. Arabic screenshot stillloading adminstate: not a full localizedadminproof. Visualmanual review catches residualdarkclose glyph: filter invertsgenericfilledbuttonbackground aswellasicon, so imageURLpresent is insufficient. UI09stillFAILED; next fullcurrentUI09 audit/scope reconciliation thenonefocusednativeclose/presentation correction, not a dialogrewrite or Canvasexpansion.
- Qualify_partial3533terminal0 bindsactuallogs/publicrecords/smoke/visualresidual,133knownvalues0findings. Deliberatewholetable stdout/snapshots andDB/config/filestorecheckpoints remainprivateintentionalinputs, notcleanlogs. Retired8EXACTexited0containers:7scopedophelpers+replaced14deapp afterprivate diagnostics/manifest/evidence; no image/volume/network/database removed. Existingbenchmark14de/legacy/currentworker87/original/failureDB/issuer/checkpointdata intact. Current app567d,DB/edge/worker live; no uncertainmutation/livesession.
- Currenttargetchanged: BOOT02 invalidated pending independent final-image reproduction; withhold0.5reproductionpoint (prior14de no-cache proofretainedunchangedscope), do not redo knownresidual567d justtorestorepoints.96/99passed/2invalidBOOT02OPS03/1failedUI09;95.0weighted≈95%,accessibility0/2. Requiredremaining5points: final-image reproduction0.5+release/security/network/sourcekit1.5+UI092+finalaudit1. Existingoldkit0.1.23 requires finalsource/image/privacy/developer-path reconciliation; source/static/smoke are not fullreleasepass.
- NEXT fullcurrentUI09 neededbeforeanothercandidate: stableSettings admin/data loaded, contrastallheadings/dialogs/essentialcontrols andfocus, actualcloseglyph, ARRTL/mixedtext/narrow/longlabels; reconciletrue200%zoom (rendererCtrlPlusdidnotzoom; emulatedreflowdisclosed)/AT/SDKlocalescope without blanketclaims. Check primaryW3C1.4.11 for controlboundaries versus visiblecontent, do not inventuniversalborderrequirements. Nativeclose should keepnativeappearanceoutsidegenericfill (zero-specificity exclusion is a narrow candidate), then ordinaryversionedgates/currentproof. Preserve oneactiveleaf/G7weights, no lifecycle/cleanupreplay, no newrealm/Canvasproduct. Allhandles terminal.

## Previous continuation: core24/Shell11 immutable candidate built and admitted

- Previousa6d5585a source/diagnostic commit is real progress. Actual onecode-only build20575 terminal0, sourcea6d5585ae46e9e1e5d491df3ff5e88e8ba98f651, exact dependencybase14de. Candidate image567d2e6affdcb6a3d79789689d9d40d4c077c28e839d4f7b36f47dad3d32a1bd/inventory0d4b7b4a419d39db4679d14285ab1b5ad9fe0d80a5ecf7230e9e30ab80bef1df/tag modular-platform:stage-20261104t073123247936z. Buildcopiedfreshallowlistedsource and preservedactualdependencyenvironment; no nativebinaryrecompile/new downloads. BuildKit emptydefaultARGwarnings retained; real exactFROMalias bound14de and removed byidentity afterbuild.
- Actual staticadmission terminal0:6andonly6expectedsource/version differences; nativecore23→24/Shell10→11/no migrations. All77actualPythonmetadata/distributiondigests+lock exact, no dependency changes; packagedartifacts/policy/sourceinputs byte-exact and no modified/missing/unexpected addonfiles. Criticalnative source seams alreadycheckedunchanged atsource24-checks.json; no freshinstalledUIclaim. Candidatebuild/admission/log133known-value privacy0findings. Fouractualrunning app/DB/edge/worker process/image/mount/network identities exact; no new persistentcontainer/volume/network. Oneuniquetaggedcandidate retained for real nextstep, no unusedthrowaway image series.
- G-01b1 passed STATICONLY/no point. ActiveleafG-01b2 normal stage/independent core_upgrade review/checkpoint/apply/currentUI09. Current managedrealm remains14de/config4 and allotheroriginal/benchmark/recovery realms intact; candidate is not staged/deployed/approved.97passed/1invalidOPS03/1failedUI09/95.5points≈96% unchanged. NativeOdoo views/dialog/actions and packagedreferenceplugins remain unchanged. No Canvasproductwork or live overlay.
- NEXT inspect actualmanagedtarget/control/catalog/nativefeature scopes and sourcecore23maintenance/StageStore CLI procedure before preparing newnomination; externalworker metadata remains separately managed and muststayexact. Use admitted567d, do not rebuildor replay. Then ordinary closedsource/coremaintenance gate, exactlocalapproval/checkpoint/apply/native mp_core+mp_shell, preservation and actualinstalledUI09. Newprivatecore24browserinput/snapshotroot canreuse SAMEownedprofile, preserving old14de input/results. Currenthotkeys/protocol keyboardEnter/discard resolved; outstanding zoom/AT/SDKlocale scope mustbereconciled. Finalrepro/source-kit/privacy/release andsection28audit remain. Allhandles terminal/no uncertainmutation.

## Previous continuation: actual UI09 defects recorded; core24/Shell11 correction source checked

- Previous037d0ec4 is real progress (currentID08pass). UI09 threeowned Edge runs on same profile/current14de/config4 allterminal0 (42116/11660 and sourceprivate process records); process inventoryempty,17business/authority/job/event tables/fourruntime identities exact.133known-value privacy0findings; public BODYfocus descriptions reduced, controlledscreenshots reviewed. No new profile/Docker asset or persisted business edit; Labels/Delete canceled, Canvas local lane/84character mixed input explicitly discarded with real Unsavedboard confirmation.
- Primary11case actualdiagnostics plus targeted resolution: loadingroleStatus/foreign-note denyroleAlert/no foreigntitle, native namedTitle/Note fields/native main, commandcomboboxnameCommands/CtrlK/Escape/focusrestore, nativeOdooConfirm keyboardtrap/Escape/restore, Labels nativeHTMLdialog names/Escape/restore/inertbackground boundary, Canvas keyboardinbox→doing/reload, longmixed localinput, reducedmotion no activeanimation/transition, EnglishLTR/ArabicRTL/reflow640@2DPR+320narrow no root/headeroverflow. ActualCtrlPlus renderer command doesnotchangezoom; equivalentviewport reflow disclosed, physicalbrowserchromezoom/screenreader/SDKlocale-formatting scope still open. Canvas move loses local selector focus but remainskeyboardoperable; finalscope review distinguishes required behavior from optionalpolish.
- Confirmed failures: light subtitle4.38<4.5; dark Membersh3/native confirmationh4 blackondark; HTMLlangunset inEN/AR; Settings ownheadings/help/names EnglishinAR; textinputexplicitfocusoutline missing and existingcloseimage erased bygenericbuttonbackground shorthand. PrimaryEnter lacked character event; corrected protocol actuallyopenskeyboarddialogs. InitialCanvasreload expectedno confirm; correctedexplicitdiscard path passes. HTMLdialogBODYsentinel doesnotletbackgroundappcontrolreceivefocus; no replacementfocus trap/Canvas expansion.
- ADR0057 owned-shell-only correction: mutedtoken#5f6b7b/allheadings textcolor/background-color preservesnativeimage/Bootstrap darkclosefilter/input+textarea focusring, bootstrapENlanguage+applyAppearanceHTMLlang/dir, Settings translationdictionary/accessible labels. Core24/Shell11/platform0.1.24, no packagedplugin/dependencylock/publicDTO/schema/authority change.23affectedtests (8coreupgrade+3compat+6deploy+6nativeinteractions), syntax/ownedXML and106freeze/eightrows pass; fourcriticalnativeguard/routing/retire/authority/activation segments and entire nativeView function exact. source24-checks.json. Actualcandidatebuild/admission/independent normalcoreupgrade/installedUI09 still required; currentapp14de untouched.
- UI09 nowFAILED, notnot_run:97/99passed/1invalidOPS03/1failedUI09;95.5points≈96% unchanged, accessibility0/2. No source-only credit. Source/observations bound byui09-diagnostics.json; activechildG-01b1 build/admit correction, then normalcoreupgrade/currentUI09. OtherGateG7securitynetwork/sourcekit1.5/accessibility2/final1 remain4.5points. Finalkit5456/old14de inputs need reconciliation only after a qualified final candidate, not wholesale reinstall/recovery replay.
- NEXT one code-only candidate from exact retained14de underADR0052 and activecapsulecommand; staticadmission/source/digests, normal separateexactreview/checkpoint/core_upgrade on currentmanagedreference, installedUI09 required fixes and remaining scope. KeepNotesnativeviews/LabelsnativeHTML+OdooConfirm/Canvasminimal. No directliveoverlay/newrealm/unknownDockerprune. All current/original/benchmark realms/issuers/checkpoints intact. No liveprocess or uncertainmutation beforebuild.

## Previous continuation: ID08/current native two-tab isolation requalified

- Previous4c0f86e8 is real network/source review progress. Current actual Edge156 same protected profile on managed14de/inventory1a411/config4: one Alice session, two native Notes tabs Aadministrator/Bviewer. Initial own-workspace lists exact; native forms retain own records and Aeditable/Breadonly. Real Bnative web_search_read HTTP200 response held at browser response stage while returning A; original request canceled by real disposal. After release attempt, both tabs show own lists/roles, with0foreign HTTP/WebSockets/0runtimeexceptions and positive foreign-request blocking control. No response-body inspection/replacement or application-function patching. Currentnativeforms screenshots visually reviewed, Labels action present for A/absent B. Native Odoo views retained.
- Actual qualifierterminal0: all17business/authority/job/event tables exact, all4runtime process/image/mount/network identities exact;133known-value privacy0findings. BrowserPID21328 exited0 and independent process inventory shows no owned-profile process. No new browser profile/Docker assets or business mutation. identity-qualification.json binds actual scripts/data/network/screenshots. Failed attemptPID30944 also exited0; separate actual lists/HTTP200held/cancellation were observed but harness waited for Afullyready before releasing interception and used hidden-tab screenshots. Originalscript/result retained; corrected identity02 foregrounds tabs and releases after actual route selection, without altering product code or redoing any lifecycle/setup/readbenchmark.
- ID08 nowPASS:97/99passed,1invalidOPS03/UI09not_run;95.5weighted≈96% unchanged (overlapping identity proof earns no new gate point). Required4.5points remain security/network/operator-source-kit1.5,accessibility2,finalaudit/handoff1. Current source kit5456 still lacks qualified heartbeat/tool/runbook additions and later evidence; bounded final source/privacy update remains required. No full G7 claim.
- Transition sole active leaf to G-01b accessibility/RTL UI09. G-01d2 implemented_unverified awaits Labels/RTL/network and final operator-source-kit closure. NEXT one bounded actual UI09 observation pass on same owned profile/current managed realm: keyboard/focus/Labels+nativeOdoo dialogs, semantics/status/errors, light-dark contrast, reducedmotion, EnglishLTR/ArabicRTL/mixedtext/localization/longlabels,200%zoom+narrowviewport and minimal Canvas keyboard path. Record findings honestly before only necessary fixes. No Canvas product expansion or wholesale UI rewrite. No personal browser/IAB dependency; do not remove five prior protected profiles after rejection. All realms/issuers/checkpoints preserved; no live process or uncertain mutation.

## Previous continuation: backend/static network independence qualified

- Previous7014e1b4 is real progress (qualified performance/operator observation). Current G-01d2 stays sole active leaf. Actual current14de/config4 inventory4159files byte-verified; Odoo/OpenERP root-domain review24runtime source families/486translation/16test files. Corrected host boundaries explicitly excluded11substring false positives such as odoo.Command/odoo.netsvc. Active publisher-warranty consumer not found in retained Python/XML/JS; parser default and fiveconfig-manager test fixture mentions explicitly retained, actualcron0/list_dbFalse/proxymodeTrue. Odoo account/catalog/upsell/support links classified as optional, native framework and source/license attribution preserved; no frontend rewrite or Canvas work.
- Actual current app/DB/worker networks internal-only, edge alone also on named ingress bridge. App has no IPv4default route; internalDB5432TCP succeeds/public1.1.1.1:443TCP blocked (OSError,0applicationbytes,0.008s). Current proxy bytes exactly match selected nginx-r0.conf. All17business/authority/job/event tables and fourprocess/image/mount/network identities exact; no containers restarted/new Docker assets/business mutation. Freshboot/referenceworkerjob and actual blocked-origin English reference UI proof reused at exact immutable identities, no lifecycle/job/bootstrap/100cycle replay.
- Broader branded-host scan found one additional meaningful family: fonts.odoocdn.com automatic Unicode font URLs in optional web.report_assets_common. Actual manifest places fonts.scss only there; normal current twoCSS assets (751605B/374552B) hashes match and contain0remoteCSSurl()/imports. W3C xmlns strings in embeddedSVG are not requests. No R1reference reporting feature exposed; future reports need localfont substitution/explicit policy+requalification. Symbolic testhost od oo and inherited translation service.odoo.co.in classified separately; ownership not asserted. Backend finite domain-scope proof supplemented, not falsely generalized.
- Initial readonlyobserver refused assumption everyedge network was internal; corrected per-role actual topology and reused source candidates. Classifier Windowsargument limit prevented process launch; fixed stdin data transport. Next assertion caught fiveconfigtest mentions; inspected and reused original returned scan, no rescan/probe replay. Each attempt recorded. backend-qualification.json+alias-qualification.json/privacy133knownvalues0findings; docs/network-independence.md records current decisions/limits. No additional weighted point or OPS03pass:95.5points≈96%,96passed/2invalid(ID08,OPS03)/UI09not_run unchanged.
- NEXT verify retained ownedprofile process absence and execute current native Notes Aadmin/Bviewer two-tab/cache/late-response isolation plus nativeform/Labels/blocked-origin network coverage. Then UI09keyboard/contrast/zoom/RTL and final operator-tool source-kit/privacy/release closure/section28audit. Reuse existing profile/current managed realm, no personal browser/IAB/new realm. Do not repeat qualifiedbackend/lifecycle/read/shell100cycles/progresskill tests. All current/original/benchmark realms/issuers/checkpoints preserved; no live process handle or uncertain mutation.

## Previous continuation: remaining performance/observability qualified

- G-01c4 passed; next sole active leaf G-01d2 release/security/network closure. Actual current shell/100cycle proof at709f8cc2 retained. Read-only audit binds21actual live current14de files;10whole files exactly match qualified G6 including job_dispatch/durable/job_runner/worker_dispatch/external_job/host. Actual four runtime identities and all17business/authority/job/event tables remained exact. Read-only aggregate sample records one completed job/threepending outbox events, actual ages/attempts/DBconnection counts/max connections and four runtime CPU/memory samples. No bodies/queries/credentials logged.
- Found actual independent CLI heartbeat gap; ADR0056/tool-only fix adds owner-protected atomic5second observation and20second stale warning to apply/restore/resume/show. Separate observation writer lock; no authority/replay/undo/PID-death assertion or public HTTP DTO/SDK/app image changes. Actual selected Python subprocess heartbeat advanced5.031s; forced-death staleness19.860s afterkill (20s since last pulse), concurrent writer refused, return/exception distinct. Current real completed journal readback exact/not_recorded/no observation directory creation.19affected tests pass;106files/eightrows G2freeze unchanged.133known values/source/actualstream privacy0findings. qualification.json.
- Initial process probe refused Windows venv-launcher PID mismatch; original synthetic files preserved, no remaining probe process. Corrected harness uses exact selected base interpreter plus selected venv packages. Read-only bounds review later stopped on incorrect nested session-control field after actual source/resource capture; corrected actual direct field and reused original sample, no SQL/stats recapture. Both attempts recorded. No Docker assets or lifecycle replay/business mutations. All final owned processes exited.
- Current R0session31ms coarse vs7.724ms contextual; no controlled speedup claim/matched old Notesdataset. Current passing targets cover explicit cost of added authority/release checks. Jobs default30slease/120sdeadline/1srunnerpoll; stopped runner has no automatic reaping bound. UI observation ends pending/unknown, not fabricated failure. Native child300s/generalDocker60s/readiness90s bounds are observation/wait bounds, not rollback/native preemption. Internalread snapshot20ms limited to same private serializer and invalidated on exit/write. Full limits in docs/performance.md/source-bound-review.json.
- Award1remainingperformance point:95.5weighted≈96%;96/99passed/2invalidID08OPS03/UI09not_run unchanged. Required remaining4.5points: security/network/operator-source-kit closure1.5,accessibility2,finalsection28audit/handoff1. The earlier5456abf4draftsource kit does not yet include new operator tools/runbook additions; final bounded source refresh/privacy delta remains required, without rebuilding unchanged app/worker or redoing installation. No full G7 claim.
- NEXT G-01d2 backend/static/server outbound classification and final release compatibility/security reconciliation; browser-network/ID08/UI09 then finalaudit remain. Keep standard CRUD native Odoo and Canvas minimal. Reuse owned profile .local/g7-ui-qualification-01/profile for justified later browser work; personal browser and5prior rejected-removal profiles untouched. No passed-test/setup replay or new disposable realm needed. Keep all realms/checkpoints/issuers intact; no global Docker prune.

## Previous continuation: current shell and100-cycle disposal checks passed

- G-01c4 remains the one active leaf. Actual owned Edge156/Node24 measurement terminal0 on current managed kit realm14de/config4: cold login→interactive native Notes/Odoo commands990.425ms; warm586.731/887.474/742.008ms, all below3seconds. Production minified assets, no replacement app functions or personal browser. One new protected profile reused throughout; browser PID30084 exited0 and independent process inventory confirms no owned-profile process remains.
- Five warmups then100actual Canvas→Settings mount/dispose cycles; every Canvas root absent after disposal. Post-GC heap7,283,236→7,378,804bytes (+95,568), documents33/nodes2630/listeners151 unchanged, all predeclared ADR0055 checks passed. Full six-point curve retained, zero runtime exceptions. Exact positive-control foreign HTTP request refused, no app foreign requests/WebSockets observed on these paths; this is not yet complete section27 closure or ID08/UI09.
- Read-only qualifier terminal0: all17business/authority/job/event tables exact, all4runtime process/image/mount/network identities exact. Reviewed screenshots and13source/diagnostic/publication candidates checked against133known values, zero findings. No new Docker assets or business mutations. performance-qualification.json binds actual executed source and results. Profile/session/whole-table snapshots remain protected, never release diagnostics.
- No additional weighted point until remaining R0/heartbeat/revocation/diagnostics/readiness mapping closes;94.5points≈95%,96/99passed/2invalid(ID08,OPS03)/UI09not_run unchanged. Source review found deployment phase mirrors only before/after native execution; app is intentionally stopped during native maintenance. Establish independent progress/heartbeat/failure bounds rather than treating a stale UI observation as executor failure.
- NEXT inspect actual tools/modular.py executor/show entry points plus operator_store/native_executor/deployment source; map job leases/timeouts and current authorization/readiness diagnostics to retained actual proofs. Correct a confirmed deployment heartbeat gap minimally if necessary, without replaying completed lifecycle work or rebuilding unrelated app/UI code. Then ID08/UI09/network/finalsection28. Owned profile may be reused later; never touch personal browser or the5prior profiles whose removal was rejected. No live process handle or uncertain mutation.

## Previous continuation: current10k read target passed; remaining performance next

- Previousb60f8e30 is progress (actualcompletekit). ADR0054 bounds retained unmanagedfixture setup; no productlifecycleapproval claim/SDKadapterbypass/newimage. Preflight actualonly nativeversiondifference mp_core19.0.0.1.20→.23; DockerAliasesnull readonlyobserver refusal corrected, prior image/snapshotdata reused and actual identities rechecked, no setupreplay. Existing10006Notes/10000A/9976synthetic held. Onlybenchapp/proxy stopped; own DB4,585,991B+combined-volume4,167,689B privatecheckpoints retained undercheckpoints/, not cleanlogs.
- Actualcoreinitialization terminal0/current14de:17bench+17originaltables exact, pausedcontrol/revokedcredentials/noissuer preserved. ExistingpureSDK sanitizedprofile republished generation30 with explicitno-external-endpoint fixturepolicy; no executor/scheduler/issuer copied/registered. Newguarded appb8e4897bf9da483df29db685f1ee23409c4d8ed7e501b675be282ab445526598 and proxya2e23e723a16e057f7035fd42a0f69b22b79f27d9a1c7174b697d50b659db424 use samelegacybenchname/volume/networks/port18089. No originalapp alias/projectidentity used. SharedPG4709d81/currentproxydece exactselectedrelease; originalec8worker87 process/net/key unchanged. No datasetreseed or newDB/volume/network/image.
- Actualbenchmark35797 terminal0:20independentAlice sessions,800requests/200percase, warmup3/10paced batches, normalnative/gateway/CSRF/binding/release/proxyadmission. Native list80 p95303.779ms/detail107.879; gatewaylist25360.509/detail162.812,0errors. Serverfilter/disjointpagination/9600Bdetail validated. All17bench+17originaltables/dataSHA7eee/fences/worker/PGidentity exactafterread. ActualDocker16CPUs/8,290,824,192B; app2CPU/1536MiB/twoworkers/sharedPG1CPU512MiB.37over500ms/max~1.1s retained. Gatewaylistp95higher thanprior31whilemedianstable; differentrecordedcontexts/no causalclaim. Upstreamsessioncontrol7.724ms vscoarse/differentR031ms contextual, notfullcomparisonpass. read-qualification.json/resources.json/read-benchmark.json.
- Qualifierterminal0/readpoint awarded1:94.5weighted≈95%,performance1/2; release2.5/4/acceptance96passed2invalidID08OPS03/UI09notrun unchanged. Threeexactexited0oldapp/proxy/nativehelperretired aftercheckpoint/inspect/native diagnostics; currentbenchmark2services/combinedvolume/network/existingDB/checkpoints retained.56actualcurrent clean diagnosticstreams+publicsources checked133known values/0findings; DB/config archives and2whole-table preservation snapshots explicitlyprivate/reclassified outsidecleanlogs. Futurewrappers write directlytoprivatepaths; no native/setupreplay. Measurement sourceunchanged/exacthash; finalizedfixture-source differences only documented observation/private-output handling. docs/performance.md records full limits.
- NEXT G-01c4 read docs/evidence/G6/20261102-headless-ui-01/{README.md,environment.json,lifecycle.py,probe.mjs,qualification.json} and current§24.1–24.3 mappings. First reconcile current-source R0/heartbeat/revocation bounds, then use ONEnewownedheadlessprofile (reuse for100cycles) for warm production-assets shell<3s/100mount-dispose leak checks; mayalso closeID08/UI09/network with real evidence. No needIAB/personalbrowser, no newCanvasproductwork. Do not repeatpassedreadbenchmark/setup merelytofilltime or altercaps/targets forpass. Existingbenchcurrentalignmentphase=current_read_target_qualified_remaining_performance; no livehandle/uncertainmutation. Remainingsecuritynetwork1.5/performance1/accessibility2/final1=5.5points.

## Previous continuation: complete kit privacy/runbook qualification passed; backend performance next

- Prior5456abf4/runbook/source08 is progress. Actual main audit45604 terminal0:101736expandedmember/historyinstances/78026uniquecontents,8genericfindings/0issuedsecretfindings. Exact8toolchain npm/Python documentation/compiled-source equivalents reviewed byfileSHA/offset/rule/fingerprint; XXXX key-format examples, inertbase64passwordplaceholder, urllib3 URLdoc and CPythonBasicAuthmodule-doc codeobjects compileexact from bundledsource/no execution/no trailingmarshal bytes. No vendor docs/detector rules removed. kit-static-triage.json.
- Older image121proof extended independently for2latercore23values:5276actualcurrentcontenthashes/431MB/0hits, bothprivateinventories matchcommittedqualifiedSHAs. Mainauditchecks10later knownvalues/encodings onallunique reusedbytes; finalreconciliationcoversalllegacyhashes.6288priorimplementationhistory blobs new10 checked;103newreachablehistoryblobs scanned; all54196sourceZIPfiles exactly matchGitobjectIDs at5456abf4.
- Nested88500 terminal1 stoppedBEFOREroot-source traversal at1GiBsizeguard; actual checksum-bound Git ZIP1,190,686,365expandedbytes/63106entries reviewed. Onlythat exactrootgets2GiB; otherlimits preserved. Readonly second24965 terminal0 withprogresssnapshots:590recognizedZIP/TAR/gzipcontainers/36532nestedmemberinstances,1264newuniquecontents/0findings. Diagnosticmutable-mode summary initially1203; finalset-difference/first-full-scan reconciliation proves1264, countercorrected without re-executing archive/runtime work. Maincollector121/123mode wording corrected; finalproof explicitly binds2valueextension. No lifecycle/job/bootstrap replay/Dockerassets.
- Finalqualifier terminal0: kit-qualified.json bindsactual50components/79290combineduniquecontents/133knownvalues/8reviewedstaticmatches/0unreviewed/0issuedsecrets, exactsource/installation/bootstrap/runbook proofhashes and finite limits. Kit source5456abf4/manifestd3b6e745 staysDRAFTforG7; laterreceipts not falselyinsideearlierZIP.15actualCLIhelps/12casefunctional-evidence cross-check passed; fullnewdeveloper backend/worker andcorrectedofflinebootstrap qualified. Award0.5actualreleasekit/runbooks:93.5points≈94%,release2.5/4. Acceptance96/99passed/2invalidID08OPS03/UI09notrun/5R2excluded unchanged. Remaining security/network closure1.5,performance2,accessibility2,final1=6.5points.
- NEXT G-01c3 inspect .local/g7-performance-10k-01/state.json plus docs/evidence/G7/20261102-performance-10k-01/{fixture.py,read-qualification.json,qualify_reads.py}. Existingprojectmp-g7-perf-6fafdba2c44c/DBmp_disposable_r0_r1_g7_perf_6fafdba2c44c/18089 isold31/experimental/sharedPGprocess. Understand actual app/network/config/authority boundaries and select safe controlled current14de update preserving10kdata andsharedoriginalPG/otherDBs; do not runoldsetup/reseed/reset. No current performance point. Backendfirst peruser; browsernetwork/ID08/UI09 later via ownedheadlesssurface. All prior/current/newkit realms/issuer/checkpoints intact; no livehandles or uncertainmutation.

## Previous continuation: final kit source08 fixed; actual expanded privacy audit running

- Previous35fced8e is progress: actual portable backend/worker job/full bootstrap and29helperretirement qualified. CurrentHEAD5456abf4; clean source at start. Readonly runbook cross-check passed15actual selected-operator CLIhelp commands/12cases with exact retained functional-evidence hashes and scope limits. First evidence lookup found actual core23 upgrade has completed/preservation/http receipts rather than qualification.json; corrected paths after directory inspection and reused original help streams. No lifecycle/fault/recovery replay. runbook-cross-check.json.
- Source-refresh08/session1528 terminal0: existing draft now source5456abf4/includes12runbooks/latesthelpers/audit code, onlysourceZIP changed/49largecomponents reused/all50checksums verified. No Dockerassets or runtime changes.
- LIVE audit45604: kit_privacy.py under selectedPython16, .local/g7-release-kit-privacy-01 newly owned output. Actual top-level bytes completed with0findings; expanding source/plugin/notice/wheel/WindowsPython+Node members, allOCI layer members/metadata/link targets and new+priorimplementationhistory.133knownvalues/new10encodings. Exact qualified sourceGitblobs/imageSHA reuse only for priorgeneric123proof; everyunique reused byte sequence checkedfornew10. Collects redacted findings/privateexactcandidatebytes; no suppression/assetexecution/extractiontoarchivepaths. DO NOT rerun existing audit directory or refresh kit while this process runs; poll same45604 handle/inspect actual process if observation fails. No privacy pass or progress credit until terminal/evidence/triage.
- NEXT await45604 terminal, inspect kit-expanded-privacy.json and private findings; review each actual finding by exact hash/offset/fingerprint, no broad ignores. Then close releasekit/runbook slice with actualproof; browsernetwork/ID08/UI09, existing10kperf/final§28 remain.96passed/2invalid/UI09notrun/93weighted unchanged; all current/original/fresh/perf/reference realms/issuer/checkpoints preserved.

## Previous continuation: fresh kit backend/worker job and full offline bootstrap qualified

- Actual register51840/connect72368/job78936 all terminal0, source kitd6ba6241/helper-sync07. Provider0.1.3 metadata and Notes Stats0.1.1 native connector each independently exact-hash approved/applied; new realm config4/same14de/inventory1a411. Jobfc31f5dc-6f67-4593-9f51-401c6e156836 completed1attempt as actual Alice/A, Note revision2/statistics30characters3words1line exact. Independent worker4daa/process/image87/key/address/publication1 remains byte-exact across operations/job. Actual SQL4principals/2workspaces/6memberships/5siteinstallations/8features/2Notes/1board/1job. Three lifecycle journals completed/mutation+traffictrue; HTTPapp no issuer mount. Raw Notes COPY rows exactly match real pre-provider checkpoint (SQL NULL empty Json vs DTO[] diagnosed; no backend mutation/replay). worker-integration.json.
- Full corrected setup44677/verify terminal0 in NEW HOST-ONLY .local/release-kit-bootstrap-check: selectedPython3.12.16/all13packageversions/no runtimepip/privateownerverified/privatechildempty/all374qualifiedbuildinputs exact. No site/authority/catalog or Docker asset created. full-bootstrap-qualified.json supersedes earlier unexecuted-full-command limitation; main rehearsal operator/data preserved.
- Qualifier16978 terminal0: actual142command/stage/projector/runtime streams clean against133known values (new issuer PEM/DER included). Retired29EXACTexited0 native/checkpoint/asset/metadata helpers/replacedapps after evidence,0unqualifiedterminal retained. Four actual current services/8ownedvolumes/2networks/3checkpoints/requiredimages/authority retained; no globalprune or unknown data cleanup. integration-helper-retirement.json. Added12case operator-runbooks.md; source/link/CLI cross-check and full-kit recursive privacy/finalartifact closure remain; docs alone earn no progress.
- NEXT commit current docs/evidence, perform bounded final runbook cross-check, refresh ONLY committed source/bootstrap/doc component08 of existing draft ONCE when ready (49largeinputs reused), then actual complete-kit privacy by expanded members/exact prior proof identities; source ZIP currentlyd6ba6241, do not pretend latest uncommitted runbooks already included. No new application build/realm/operation or setup replay needed. Existing current/original/perf/recovery targets untouched.96/99passed/2invalidID08OPS03/UI09notrun/93weighted unchanged; browser network/ID08/UI09/perf/final§28 remain. No livehandle or uncertainmutation.

## Previous continuation: portable worker independently published; metadata/connector/job next

- Actual source-refresh06/session98896 terminal0: kit source4e2ee524/one sourceZIP updated/49reused; helper-sync06 binds only new committed initialize_worker.py overlay. Actual selected kit interpreter worker13569 terminal0: one worker4daa036c0e3a871ec20c95de8a4784f9432fbf3bd131bb31eb5d7839181af9f8/projectmp-disposable-document-stats-release-0afebf4f833b, existing internal network, two new dedicated owned volumes, fresh private/public issuer keys. Ordinary CLI provision/prepare/review/exacthashpublish passed. Generation1/endpoint1 scoped A, observed image87/user/mounts/internal address/public key/health exact. worker-provision.json. No metadata installed or job executed yet.
- New connect_worker.py prepared for separate provider metadata exact-pin install with enabled feature, approved native Notes connector install, then one saved-revision/original-actor job. Reuses current source manifests/catalog pins/SDK/ordinary CLI; no inferred version pins or new product behavior. NEXT commit and draft source-refresh07, sync exact committed helper, run register/connect/job in sequence; inspect marker/journal before any continuation. Keep current realm/core data/worker identity. No livehandles or uncertainmutation;96passed/2invalidID08OPS03/UI09notrun/93points unchanged.

## Previous continuation: fresh kit backend reference qualified; worker transport next

- Actual prepare99544/initialize82718/install54258 all terminal0 in NEW projectmp-r0-r1release0afebf4f833b/DBmp_disposable_r0_r1_release_0afebf4f833b/port18100; kit-selected14de/proxydece/PGd81, fresh credentials/private control and empty storage, no old catalog/authority/site copied. Exact independent operation2e415c49-254a-4543-bedb-7cf9ac8c9f4a completed with mutation/traffic journal true. Three native plugins/six workspace activations.
- Actual HTTP walkthrough terminal0: five checks, two Notes/one minimal one-card Canvas, fresh Alice/Bob authentication, native Odoo list/form descriptors/scoped reads, viewer-write and foreign-record denials, Labels binding. First walkthrough stopped on Windows getaddrinfo11001 before network/data; original pre-data marker retained, SQL confirmed0Notes/0boards, only walkthrough resumed with explicit loopback/Host; no core or install replay. application-bootstrap.json binds source/kit/mixed-source receipts and actual SQL/runtime/journal. 57command/stdout streams plus three actual service stderr streams clean against131known secrets. Three exact exited0 helpers/replacedapp retired; three running services and all volumes/networks retained.
- Kit draft source746781d6; source-refresh03/04/05 each changesonlysourceZIP/49largeinputs reused; helper-sync receipts bind overlays to committed kit source. All374qualified build inputs unchanged. Existing corrected full setup_operator command still not rerun from empty; actual diagnosed endstate scope explicit.96/99passed/2invalidID08OPS03/UI09notrun/93weighted unchanged.
- NEXT portable external-worker setup/job and twelve operational runbooks/full-kit privacy. Image transport fixed: actual digest-form export also omitted names (attempt01 archived/retired), named stable worker tag export preserves binding while exact five imageIDs/48othercomponents match. Actual load into previously ABSENT probe repository reconstructed digest reference from tag metadata/78verbatim OCIblobs; exact probe tag/archive retired, canonical release alias retained. image-transport-repair/load/probe-retirement.json; no blank-daemon claim. New portable initialize_worker.py prepared/unexecuted. NEXT commit/source refresh06, sync exact committed worker helper into existing source, run it ONCE with selected kit operator. Uses existing internal network, one runtime/two new owned volumes maximum. No image rebuild/SDK/G2 change/new realm. Browser/perf/final remain; no livehandle/uncertainmutation.

## Previous continuation: portable initializer prepared for first actual application rehearsal

- New host-only release/initialize_reference.py and reference_seed.py implement explicit reference preparation, empty database/native core bootstrap and ordinary independent register/approve/apply for six workspace activations. Existing SDK/CLI contracts and qualified application inputs unchanged; all new credentials/control/storage, no copied live site. Source review corrected missing CAP_CHOWN for new-volume filestore ownership before execution. Syntax and 123-known-value source privacy passed.
- NEXT commit helpers, refresh draft source03 once, hash-verify/sync only committed helper files into existing rehearsal source, then execute prepare/initialize/install sequentially with the selected kit operator. No Docker mutation has started; P3 unqualified, counts and 93 weighted points unchanged. Preserve original/fresh/perf realms.

## Previous continuation: draft refreshed and ready for portable application rehearsal

- Source refresh02/session29644 terminal0 nowputs latestprivate-childbootstrapfix inonekit/source5f8d6b35; exactly2componentsupdated/48reused/no imageexport/download/envreinstall. Current50componentchecksumsverified. Source-parity.json provesexistingrehearsalsource94c4ecd0 stillmatchesall374qualified14deapplication/SDK/tool/deploybuildinputs. Differences are nonapplication packaging/docs; do not pretendwholeworkingcopyis5f8. Existingoperator-setup.json recordsactualsource94c andnewprivatechild paths.
- Actual offlineoperator13packages/SDKprivatechild/new19artifactcatalog remain qualified byoperator-qualification.json/catalog-from-kit.json; no app/database/site/operatorstoreapproval/worker initialized. P1draft+P2endstate done, P3portable application/referencedexamples/worker/P4runbookclosure remain required. Rootcorrectedsetupfullcommandnotrerunfromempty; diagnosedactualinstall/finalizationeffects andscopeexplicit. No environment/sourceextraction/networkretirement repeats needed.
- NEXT implement `release/initialize_reference.py` (notcreatedyet) using currentSDK/ordinaryCLI and actual existing genericbootstrap patterns asreferences, notauthor-private fixture imports. Rehearsalusesexistingkit-interpreter/source/private/catalog; createfreshnamedrealm, emptyDB/volumes/newauthority/humancredentials. Verify/loadthefivekitimages anduse selected14de/proxydece/PGd81/worker87. Commithelperthenrefreshonlydraftsource/bootstrapcomponents, syncneededcommittedhelperfiles intoexistingrehearsal sourcewithhashprovenance beforeexecution; preserveallprivate/catalog data. Do not buildnewappimage/relaxschema/permission/actor contracts forhost-only packagingwork. Allcurrent/original/perf/failedDB/checkpoints untouched; no livehandle.96/99passed/2invalidID08OPS03/UI09notrun/93points≈93%unchanged.

## Previous continuation: offline kit operator and new artifact catalog qualified

- Previous94c4ecd0 captures realassembly/cachefix. Draftsource refresh49346 terminal0 updatesonlysourceZIP/bootstrapscript (2components), reuses48 components; currentkit/source94c4ecd0, source-refresh01.json. No assembler/imageexport/download replay. Offlinebootstrap42689 terminal1 installsall13pinnedWindowsdependencies fromkit --no-index andextractsfullsource, thencanonicalSDK rejectsworkspace-rootACL (actualOWNER_RIGHTS S-1-3-4,owner/protectiontrue). No activecredentials/control/app/Dockercreated. Root is publicsource/toolchainworkspace, notprivatecontrolstore.
- Distinctdiagnosis: SDKprotect_directory correctlyinspects/refusesexistingACL ratherthanresettingit. FixsetupcreatesNEW `work/private` through SDK. Actualfinalize_existing_operator.py terminal0 reusesinstalled13/source, createscanonicalprivatechild andverifiescurrentOSowner; packagesmatchqualifiedoperator13 exactly/no runtimepip. No reinstall/sourceextraction/ACLreset. operator-qualification.json explicitlyrecordsdiagnosedcontinuation, notfullcorrectedcommandrerun. NewCatalog from19kitarchives nowcreatedvia ONLYfreshkitinterpreter+SDK; digestsallmatch/no priorSQLite/store/approvalcopied orcreated. catalog-from-kit.json. P2end-statequalified/P3appinstallationnotstarted.
- Roothelperprivate-childfix notyetinthekit atthischeckpoint. NEXTcommitfixthenrefreshdraft02ONCE; keep731MBonekit/48unchangedinputs,existingoperator/source/private/catalog. Do NOT rerunsetup againstexistingworkdir. Implement/qualifyportablefreshcore/examples/workerinitializer usingthisnewprivatecontrolroot andexistingSDK/CLI. Refreshonlycommittedhelper/sourcecomponentsandrecordworkingcopyprovenancebeforeexecution; no nativeimage/sourceSDK changes.96passed2invalidID08OPS03/UI09notrun/93pointsunchanged; artifact/operator/catalog progress earnsnofullkit/OPS03credit. No livehandle/uncertainmutation.

## Previous continuation: draft assembled; bootstrap cache failure diagnosed

- Producer6a1b9cf1/session88261 terminal0 assembled and verified one `.local/releases/r1-0.1.23`:50components/731003896bytes,5exactimages,19verifiedarchives,6noticebundles,selectedPython16/Node24.22.1 and13hashlockedWindowswheels, full committedsourceZIP. Originalmanifest6edeb39d...; assembly.json/assembly.state.json recordcompletedcomponents. No Dockerassets created, no activecatalogSQLite/control/config/DB/filestore/issuer copied. P1actualassemblydone; not OPS03/kitqualification.
- First offlineoperator setup refused BEFORE workdircreation: importing verifier generated exactly scripts/__pycache__/verify.cpython-312.pyc, which strict componentinventory rejected. No env/app/Docker initialized. Actual extra-set={thatfile}; its sourceSHA/header/compiler codeobject equal the copied verified source, exactcache privately preserved then removed alongwithnow-emptycache directory. Originalmanifest/all50componenthashes reverified unchanged. cache-retirement.json. No unknownfile ignored/no verifier relaxation.
- Fix sys.dont_write_bytecode before verifierimport in setup_operator.py. `release/refresh_draft.py` prepares committed source/bootstrap refresh of thisunsealedkit, reusingalllargeinputs insteadofnewkit/export/download/install loops. Roothelperfixnotyetappliedtokit atthischeckpoint. NEXT commitfix, refreshdraftONCE toreceipt source-refresh01.json, thenrerunsetupwithfreshworkdir `.local/release-kit-rehearsal` (authoritatively absent). P2offlineoperator/P3portablefreshapp+examples+worker/P4runbooks stillrequired.96passed2invalidUI09/93points unchanged/no generatedfilecredit. No livehandle or uncertainmutation.

## Previous continuation: release-kit prerequisites and portable draft helpers

- Previous d46d1530 is progress:actualBOOT02currentreproduction. Releasekit remains G-01d2's only active subtask. P0done: two exact endpoint-free networks of archived/retired projectmp-r0-r1lifef99acae9d906 removed after recorded ownership, zero projectcontainers and repeated endpoint/label checks. All other existing network IDs preserved; no container/image/volume/globalprune/data changes. `evidence/G7/20261104-release-kit-01/network-retention.json`. This frees two default-pool slots for one new clean realm, rather than pruning unknown/shared resources.
- Historical setup fixtures depend on author-machine private controls/protected target paths and cannot be the fresh-developer interface. ADR0053 defines a local public-input kit separate from site recovery authority/data. New `release/assemble.py` stages committedsource/fivequalifiedimages/19curatedarchives/notices/Python16+Node+lockedWindowswheels; no catalogSQLite/control/config/DB/filestore/issuer/privatecredential copying. Existing digest-curation format is reused; it is not execution approval or a new SDK contract.
- `release/verify.py` and setup_operator.py provide draft checksum verification and offline project-local Windows operator creation using selectedPython3.12.16/13hashlockedbinarydependencies. Helpers are outside the app Dockerallowlist, so current14de/sourceinputs/G2remain unchanged. No new UI/product/Canvas scope. P1codeprepared, artifactassembly notyetexecuted at this checkpoint; P2operatorrehearsal/P3cleanapp+examples/P4runbookclosure still required. Do not mark OPS03/kit/R1passed for these files.
-96/99passed/2invalidID08OPS03/UI09notrun/93weighted≈93% unchanged. NEXT commit helper source then run the documented assembler ONCE into fresh `.local/releases/r1-0.1.23`, receiptG7/20261104-release-kit-01/assembly.json. Inspect livehandle/phase/components on interruption/failure; never rerun against a partial directory. Then actual offlineoperator setup and one empty realm/currentreference install from kit. Existing original/current/perf/failedDB/checkpoints/issuer untouched.

## Previous continuation: current no-cache inventory reproduction passed

- Previous cc45081f qualifies current repository/assets/diagnostic privacy. Actual second core23 source build session1292 terminal0 uses --no-cache/--network=none and exact qualified ae8 dependency input, with all374 recorded build source inputs unchanged. New candidate25035 actual complete4159-file declared inventory and77 Python metadata records/interpreter/architecture/markers/lock equal current14de; inventory1a411 exact. All ten comparisons passed, not merely a successful docker command. `evidence/G7/20261104-core23-repro-01/qualification.json`.
- Required dependency image is explicit underADR0052; this is an independent fresh source build, not recompilation of native dependencies under floating OS/compiler inputs or a claim of byte-identical image IDs/timestamps. Required FROM argument lint warnings are harmless here: exact alias was supplied/ID-verified before build and removed afterward. No fallback/default base, guard relaxation, deployment or lifecycle action. Both inspection helpers auto--rm; temporary reproduction tag retired after fsynced proof/zero container references, reference14de/ae8/worker/DB/proxy/checkpoints untouched. Private state=qualified_disposable_tag_retired; no livehandle/uncertainaction.
- BOOT02 nowPASS:96/99passed,2invalidated(ID08,OPS03),UI09not_run. Restore0.5 current reproducibility weight:93points≈93% (G0–G6=90;G7native1/dependencymaintenance0.5/faultrestore0.5/freshreference0.5/reproduction0.5). Release slice2/4. Remaining security/license/network/provenance1.5,releasekit/runbooks0.5,performance2,accessibility2,final1=7points. No source-report/generated-file credit.
- NEXT assemble one current release artifact/runbook/evidence kit and prove clean installation from it, using exact qualified images/source/locks/notices and current recovery procedures. Inspect existing artifact/fixture helpers and bounded owned Docker retention/network records before creating a new disposable realm; do not reset existing targets or accumulate obsolete assets. Browser network/ID08/UI09, existing10kperf and finalsection28 remain. G-01d2 sole active item; native Odoo CRUD/minimalCanvas retained.

## Previous continuation: current repository/assets/log privacy delta passed

- Previous d0580ed9 completed known native review. Current `evidence/G7/20261104-release-privacy-delta-01/qualification.json` extends exact prior8ad57 proof through d0580ed9:54124 tracked files,466 new reachable history blobs and5822 prior implementation blobs checked for both new values/all scanner-supported encodings. Zero history findings. Byte-identical prior tree/history proof reused by exact identities, not path suppression; no Git rewrite/publication.
- Actual current19 curated archives/259 expanded members,2 served CSS/JS bundles and8 running fresh+original app/worker/DB/edge logs scanned with123 known values. All17tables/worker/original configurations exact. Single served JS match is the same byte-identical pinned Owl state binding previously reviewed; new asset URL does not imply changed bytes. No actual credential match. Finalizer's own copied binding initially self-matched; retained exact diagnostic/source, composed the test expression as in prior triage, no scanner rule weakened and no HTTP/snapshot replay.
- Actual6340 retained G6/G7 diagnostic streams scanned clean. Prior aggregate had no per-file reuse hashes, so current corpus checked once with123 values rather than trusting mtimes; new private per-file hash inventory recorded. Four earlier positive secret transports remain owner-protected in prior audit store, not silently reclassified. Source/asset/log sessions8595/95249/63021 terminal0; no new Dockerasset/service/data change.
-95/99passed/3invalidBOOT02ID08OPS03/UI09notrun/92.5weighted≈93% unchanged; SEC03 already passed, no duplicate credit. NEXT execute prepared core23 second no-cache source build from exact qualified ae8 dependency image, compare declared inventory and actual dependency metadata with14de, then retire exact disposable tag after proof. Driver `evidence/G7/20261104-core23-repro-01/reproduce.py` is not yet executed at this checkpoint. Current source build inputs unchanged; no installation/lifecycle replay or deployed image replacement. Then releasekit/runbooks, existing10kperf/browser/accessibility/network/finalaudit. G-01d2 sole active item.

## Previous continuation: known native findings mapped and dated

- Previous b064feb5 is progress:159 OS decisions and actual current image secret delta. This turn completed the known native queue in `evidence/G7/20261104-native-review-02/native-dispositions.json`:72 component-scoped decisions with rationale/evidence/review-byNov11/change triggers. Actual app binding observed once in an offline/no-mount/no-key/readonly/nonroot helper; helper auto-removed. No dangerous payload, runtime/dependency version change, lifecycle replay, image/volume/network creation or service mutation.
- Expat2.9.0 four findings separately classified. Selected wrappers have no Reset API or primary source Reset call; external-subparser API is present and not globally excluded. Current openpyxl DEFUSEDXMLtrue/default entities/external forbidden; retained actual native import/entity-refusal reused. Attribute/namespace overflow remains a real memory-safety residual; defusedxml is not a blanket fix.
- Actual lxml6.1.3 embeds libxml2.14.6/libxslt1.1.43. All17 retained2026 libxml2 records considered, including four marked Debian-not-affected for its older source. Exact-tag build mapping/patch and vendor release notes document libxslt7424/11731 backports; no libxml2 backport is presumed. Other XML/XSLT input risks explicitly accepted for local reference with review/change conditions. Actual codec versions map all15 retained2026 candidates for seven named Pillow sources; separate CLI components/upstream ranges/conditional pixel bounds distinguished. Node c-ares/nghttp2/Brotli, SQLite, compression variants and unconfigured optional proxy modules/log limitations mapped. Existing crypto/libpq/Alpine evidence retained. Method scope is explicit, not an exhaustive historical native-CVE database or arbitrary-input safety promise.
- Incremental privacy/syntax passed9 changed/untracked public files and2 actual private observer streams against123 known values,zero findings. Runtime/contracts untouched; prior G2 revision18/106files/eightrows remains applicable.
- Known OS/native decision queues are complete at their retained snapshot/source scope. Material parser/codec memory-safety/availability residuals are documented in dependency-inventory.md; no production approval or fullOPS03/G7 claim.95/99passed/3invalidBOOT02ID08OPS03/UI09notrun/92.5weighted≈93% unchanged; no generated-file credit. NEXT current Git/history/served-assets/diagnostic delta, reproducibility/releasekit, then existing10kperf and remaining browser/accessibility/network/final audit. G-01d2 remains sole active item; no livehandle/uncertainmutation.

## Previous continuation: OS decisions complete and current app secret delta passed

- Previous c3eceaa6 made real review/probe progress. The remaining122 Debian rows are now explicitly decided in `evidence/G7/20261104-cve-dispositions-01/complete-debian-dispositions.json`:159 total,28 specific exclusions,129 accepted local-reference residuals and two vendor/upstream applicability discrepancies. All have rationale/evidence/review-by2026-11-11 or earlier on listed changes. No urgency-only waiver or zero-vulnerability claim; possible authenticated-import iconv hangs and conditional memory-safety/crypto risks remain explicit.
- Actual process/tool/image security observations distinguish client libraries from missing daemons/components. App/worker readonly/drop-ALL/no-new-privileges; PostgreSQL is not claimed equally hardened. Kernel hardlink protection1; database trust rules only local/loopback, remote-network rule SCRAM; auth_ldap not registered and zero XML-typed user columns. SQL expressions and arbitrary trusted native code are not called unreachable. Docker top first required PID; corrected projection succeeded before helper creation. Database query succeeded but assertion expected an uninstalled rather than absent LDAP row; saved result finalized without replay. Three offline helpers auto-removed; no services/data/images/volumes/networks changed.
- Current image14de layer/config/history delta passed:23913 regular members,23893 byte-identical prior-audited members,20 new byte sequences fully scanned, all members checked for the two newly generated secret values;123 known values,zero findings. Immutable dependency-base layers exact. `evidence/G7/20261104-core23-secret-delta-01/qualification.json`; terminal session96662/exit0. Exact210151936-byte export retired only after verified/fsynced proof; private inventory remains. Prior worker/PG/selected-proxy exact-image proof retained. Git history/served assets/diagnostics scope remains separate.
- Native/bundled CVE review still open. Six primary notes retained: four Debian TEMP pages, lxml6.1.3 changelog and libxml2.15.4 release notes. Actual lxml6.1.3 bundles libxml2.14.6 and patched libxslt1.1.43; documented CVE2025-11731 backport prevents a version-only false positive. Further libxml2 parser fixes and four Expat findings must be assessed independently; do not inherit PostgreSQL XML decisions for application inputs.
- Incremental privacy/syntax passed16 changed/untracked public files and17 actual private diagnostic streams against123 known values,zero findings (`privacy-syntax-final02.json`). No runtime/contract source changed; retained G2 revision18/106files/eightrows remains applicable.
-95/99passed,3invalidated(BOOT02,ID08,OPS03),UI09not_run;92.5weighted≈93% unchanged. No generated-file credit or fullG7/OPS03 claim. NEXT finite native/bundled findings, then current Git/history/assets/log delta, reproducibility/releasekit, existing10kperf fixture, backend-authorized browser/network/accessibility and final audit. One active item G-01d2; no live handle or uncertain mutation.

## Previous continuation: expanded OS advisory coverage and dated decisions

- G-01d2 remains the only active item. `evidence/G7/20261104-cve-dispositions-01/` compares the retained primary Debian snapshot against app113/worker105/PostgreSQL144 OS records: 101 source/version groups, 2,103 advisory rows, 1,687 fixed at installed versions, 257 vendor not affected, 159 requiring review. This closes the earlier app/worker-only match coverage gap; it does not establish complete vulnerability qualification.
- Current read-only database probe: TLS off, JIT on, plpgsql only, sasldb mechanism only; named XML/LDAP/KDC tools absent. PostgreSQL OpenSSL revision u1 is older than the app/worker u2 and has six published fixes outstanding. Exact prerequisites and local-reference residual decisions are recorded, not silently classified patched. SQLite owned callers contain44 constant SQL calls using private operator inputs, with existing actual SEC08 namespace/kernel/ACL evidence.
- `dated-dispositions.json` contains37 decisions (six specific exclusions,31 accepted local-reference residuals), review by2026-11-11 or earlier on component/configuration/deployment change. **122 Debian rows remain open**, plus native/bundled/Expat review. No waiver based only on vendor urgency. Report-completion uncertainty was resolved by reading the existing output; the guard refused a duplicate launch. First database probe failed before SQL because optional bootstrap variables were absent; corrected explicit connection succeeded read-only. No runtime/service/data/image/volume/network changes or live handles.
- Acceptance remains95/99 passed,3invalidated(BOOT02,ID08,OPS03),UI09not_run;92.5weighted≈93%. No progress credit for generated reports. NEXT finish the finite122-row queue and native/bundled mappings; then current image delta/reproducibility/release kit, existing performance fixture, browser/accessibility and final audit. Backend-only work continues per user direction.

## Previous continuation: selected host notice and official Node binding complete

- Previous b24d2b15/cc9b4cf1 made actual source/notice progress; no completed lifecycle or image build repeated. New evidence/G7/20261104-host-notices-01/host-notices-final.json preserves218files for13selected Python distributions,44base interpreter notices (including separately inventoried bootstrap pip26.2.2, excluded fromoperator sys.path), Node24.22.1/npm11.19.1 and two TypeScript7.0.2 packages. Python/Node globals were not changed; downloaded code was never executed.
- Official Node Windows ZIP verified against vendor SHA256 manifest; installed node.exe matches actual archive bytes. All145bundled package manifests and all furnished bundled notices match official ZIP. Four missing-notice registry artifacts verified viaSHA512; actualsourcecontent matches officialNodeZIP exactly andregistrycontent differs onlybyCRLF. First byte-equality probe stopped onmanifest/source newline differences; inspection establishedsemanticJSONidentity/CRLFonly, retainedattempts andcheckedcachedartifact/SRI withoutreinstall/refetch or runtimeguardrelaxation.
- Four exactregistry gitHead source roots preserved: sigstoreApachelicense+README; npmagent ISC declaration/publisher/sourceREADME with no standalone furnishedlicense (noinventedcopyrightgrant); SPDXdata exactREADMEs preserveLinuxFoundation attribution/CC-BY3.0 andCC0declarations. VersionedCC reference terms retained fromofficialSPDXdata atpinnedcommit aftercanonicalPythonfetch403; canonicalwebtextverified. No legal compatibility opinion. Final218entryZIP verifiesallhashes/CRC, preservesinitial207entries; exact supersededinitialZIPremoved afterproof. No newDockerasset/service/volume/network or operator mutation.
- OPS03 remainsINVALIDATED and95/99passed/3invalidBOOT02ID08OPS03/UI09not_run/92.5weighted≈93%. Source/notice generation earnsno extra credit. NEXT finish datedCVE-specific residual/supportOS decisions and remainingvendor-component mappings, then currentimage-layer/history/secret delta/currentrepro/releasekit. Useexistingprimarytracker andactualinventories; no blanketwaivers or version-onlyfalsepositives. Laterexisting10kperf/ID08UI09/browsernetwork/finalsection28 remain.

## Previous continuation: current source and selected proxy notice dispositions recorded

- Previous425ea239 progressed actual native fault/fresh restore/separate resume. G-01d2 remains sole active leaf; no lifecycle replay. Current core23 collector46247terminal0 binds11expected owned source changes/complete recorded build inputs,77actual Python digests+lock/113OS copyright records/17native declarations,3937official+2reproduced generated source files,274actual notice bytes inexistingZIP. Current17tables/worker/originalconfigs exact; helper--rm/no image/volume/network changes. evidence/G7/20261104-core23-provenance-01/source-dependency-binding.json.
- PostgreSQL144copyright paths resolve141actualfiles+3directoryaliases. Selectedproxydece71packages/59origins now mapped in third_party/alpine-notices/index.json to214deduplicated original notice/attribution text files plus6officialnginx COPYRIGHTcompanions inexistingimageboundZIP.52exactAlpine recipes fetched/allliteralversionsmatch.47primarysource archives matchrecipeSHA512 andyieldnotices; CAverifiedarchivehasembeddednotices,32base/keysourcefilesverifyexactrecipechecksums. Generatedmetadata/publickey/no-standalone-notice casesexplicit, no invented permissions.
- Libyuv TARchecksum differed; exactrecipe explicitly documents varyingtimestamps and insteadprescribes sortedregular-file-contentSHA512. That digest matched190files;3noticespreserved. No genericchecksumrelaxation.4declaredadditionalarchives andFreeTypeFTL/GPLterms preserved. Extraarchivecollector firstexpectedstandalonenoticeinFTdemo andstoppedafterverifiedtransfer; correctedexplicitabsence/reusedhashcheckedcache, no upstreamrecipe execution or blindrefetch.214blobs indexed/byteverified, GCCruntimeexception andFreeType referencedterms present.
- ExpatAlpine exactcommitmirror404/canonicalGitLab418+cgit403 retained. Exactupstream2.10release resolvesa70841d9ffa64ddde29ab824ed6305035ebe4c47; Changesbyteexactretainedprimary/COPYING1144bytespreserved. Its packagingrecipe availability remains explicit, not replaced by movingrevision or claimed reproduced. ~266MBverifiedupstreamsourcearchives retained ascurrentrelease/provenance inputs; no Dockerassets/newimages or duplicateZIPs.
- OPS03stillINVALIDATED: remainingselectedhost/vendornotices/full datedCVE-specific residual/supportOS review/currentimage-layer-history-secret/repro/kit.133app/workerDebian source/CVEpairs and4Expat2.10fixes read butnotblanketwaived.95passed/3invalidBOOT02ID08OPS03/UI09notrun;92.5weighted unchanged, no generatedfilecredit. NEXT selectedWindowsPython16/Node/vendornotice reconciliation anddatedCVE/supportOS dispositions; then currentimage-delta/repro/kit/runbooks, existing10kperf fixture update/retest, ID08/UI09/browsernetwork/finalsection28. No runtimeversionchurn absent requiredfix.

## Previous continuation: native uninstall/fresh restore/separate resume qualified

- Previous turn made concrete progress657f9352:core23 installed and nativeHTTP/preservation verified. This turn used NEW ordinary installed manager Labels request857c7072-15c2-470e-8aa9-d3c527ff1cd6/hashd5025377a298e68e199a0eaa97eca3e907d592a523bd24b5b5452cb819fdcd39. Exact2scopes/known7table dispatch/destructivecheckpoint; independent import/reconstruction/review/runtimepreflight and real missing-destructive-ACK refusal/journalexact, then exact approval93798terminal0.
- Fault70124terminal0 ONCE: real native child committed Labels uninstall and verified exact closed dispatch checkpoint snapshot before/after commit; wrapper thenraised controlled exception before metadata/traffic. Real Labelscolumnloss/2Notes/1Canvas; native versions/queue/control/history unchanged beyond approved native effects, separateworker exact. Journalrecovery_required/mutationtrue/trafficfalse; no same-operation replay.
- Ordinary prepare-restore41546 and restore9974terminal0: exact private decision/payload, wronghashrefused/journalunchanged; fresh NEW DBmp_disposable_r0_r1_restore_857c707215c2470e8aa9d3c527ff1cd6/config8/image14de retainedfailedsourceDB. Closedverification passed: actualnative relations/columns/constraints/counts/versions exact beforeuninstall,38checkpointfilesexact, all17tables exact except workspacepolicy+1 anddeclaredonecompletedjob release/claim4→5/dispatch20→24. Current public/private nativeauth exact; sessionsecretrotated/credentialsrevoked; independentworker87/key/pub1/process exact. No generic external undo.
- Separate prepare-resume61407/resume47430terminal0 with exact privatepayload; wronghashrefused. Dispatch21→failurefence22→restorefence23→reconcile24→enabled25. Fresh AliceA/BobB native list/form/API work; oldsession401/oldgatewaypin409/oldnativepinClientReleaseMismatch; failedplanrevoked/replayrefusedwithjournalexact. Required Notesprovider actualindependent+manager preview shows4nativeplugins/8scopes; cascadefalse400 andoneUNREQUESTEDdraft, noindependentoperation/approval/executionforNotes. Verifier firstexpected3plugins/6scopes, stoppedafterreadonlychecks: actualpublishedgraphincludesCanvas→Notes. Correctedexpectationfromgraph/preservedattempt01 andusednewexclusive-loglabels; no lifecyclefault/restore/resume replay.
- Ordinary Alice original-actor realjobdc496929-b928-45e7-b724-a7bd3a90a489 completed viaCLI84611terminal0,1attempt/exactstatistics/currentauthority. Alloldjobhistory/other16tablesexact, no newNote/Canvas/outbox. Freshcurrent2Notes/Canvasrev2/11outbox/2completedjobs. Retired27exact exited0helpers/observers/replacedapp afterprivatediagnostics; jobhelperauto--rm; noimage/volume/network/failedDB/checkpoint/issuerremoved. Existingordinary operations mirror-status2966terminal0 published fresh revoked/recovered state and authorized managerAPI readback passed,17tablesexact.139priorprivate diagnostic streams/123knownvalues scan0; final incremental scan follows. No livehandle/uncertainstate. Private .local/g7-native-uninstall-recovery-01/state.json=qualified_native_uninstall_fresh_restore_resumed; freshphasecore23_native_recovery_qualified. Evidence/G7/20261104-native-uninstall-recovery-01/qualification.json.
- LIFE03/04/OPS02/MIG09 nowPASS;95/99passed,3invalidated(BOOT02,ID08,OPS03),UI09not_run. Restore0.5withheldG5integrationpoint:90prior+2.5G7=92.5≈93%; no added documentation/generated-file credit. Historical normal native uninstall/reinstall/source-removal remains retained at unchangedsource boundaries; current combined child/fault/restore/resume proved. No fullG7claim.
- NEXT finish current source/CVE-specific residual review/support-package and vendored license/notices/provenance, current immutable-image delta/secret evidence, then currentreproducibility/releasekit/runbooks. Reuse retained target/currentbase; no new version/image absent actual required fix, and no completed native/MIG/API/security/build reruns absent changedsource/newfailure. Existing10kperf fixture mustupdate/retest afteractiveG-01d2. BrowserID08/UI09/network/finalsection28 remain. NativeOdoo CRUD/minimalCanvas preserved; R2excluded.

## Progress estimate

**100 weighted points overall.** G0–G6 contribute 90 and G7 contributes 10. All 99 required acceptance checks passed and five R2 checks are excluded.

## Gate checklist

| Gate | Deliverable | State | Weight % | Prerequisite / evidence |
| --- | --- | --- | --- | --- |
| G0 | A: baseline | passed | 10 | `evidence/G0/20261027t234238z/gate-G0.json` |
| G1 | A1: feasibility | passed | 10 | Original G1 evidence plus evidence/G6/20261101-identity12-upgrade-01/qualification.json; unchanged two-tab/cache frontend boundary, installed native/current two-worker authority revalidation |
| G2 | B: contract freeze | passed | 10 | Revision18/106files/eightrows; ADR0051 schema/old-payload/consumer/TypeScript/freeze evidence/G2/20261104-native-uninstall18/gate-G2.json. Current combined lifecycle qualified in G7/20261104-native-uninstall-recovery-01/qualification.json. |
| G3 | C: Notes and shell | passed | 15 | `evidence/G5/20261028-client-release-ingress-requalification/requalification.json`; changed UI/current-pin/runtime checks plus retained original unaffected evidence  identity1.2 authority requalification: evidence/G6/20261101-identity12-upgrade-01/qualification.json |
| G4 | D: composition and Canvas | passed | 10 | Same requalification/current source; packaged/native extension checks retained, actual core operation/UI07 remain G5 |
| G5 | E: lifecycle and packaging | passed_qualified_profiles_current_integration_requalified | 25 | Historical gate-G5/native normal uninstall/reinstall/source-removal plus current core23 combined native child/fault/fresh restore/separate resume in G7/20261104-native-uninstall-recovery-01/qualification.json. Final current-release OPS03 remains G7. |
| G6 | F: jobs/events/services | passed | 10 | `evidence/G6/20261102-headless-ui-01/gate-G6.json`; all11JOB/EVT/SVC checks. Current backend coverage plus actual native UI timeout/crash/navigation/recovery and exact preservation. |
| G7 | G: qualification | passed | 10 | In-app browser, backend audit and §28 handoff passed. See 20261105-section28-audit-01/gate-G7.json. |

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
| UI-REUSE-01 | Adapt generic interactions to native services before frontend expansion | passed | bounded reuse work; no new acceptance credit | UI-ALIGN-01 | Native interactions/Canvas/session qualified; action-seam experiment163000Z retains direct native View, ADR0010 |
| UI-RELEASE-01 | Fence incompatible release calls, controlled refresh and immutable assets | passed | UI-07; section19; core lifecycle | UI-REUSE-01 | Actual controlled refresh21/22, native retained assets, fault/restore24, normal core25 and SDK guard26 qualified; `evidence/G5/20261028-asset-retention-requalification/requalification.json`. No UI rewrite. |
| E-01a | Validate immutable archives and curated catalog before import | passed | PKG; BOOT-05; OPS-03 | G4 | hostile archives, digest/version/trust |
| E-01b | Resolve dependencies/versions/bindings into exact plans | passed | DEP; VER; TEN | E-01a | X02..04 and X07 qualified; actual resolver/migration/manager/registry/HTTP/shared-version evidence retained |
| G5-X02 | Manager install/upgrade, upload and plugin inspection | passed | Sections8/10.6/20.1-20.3; SEC-01/05/06 and ID-06 regressions | E-01a; G2rev11 | `evidence/G5/20261029-manager-inspection-http-01/qualification.json`; lifecycle removal/recovery screens remain X05/X06/X09 |
| G5-X03 | Resolver/version decisions | passed | §§6.2/6.4/6.5/7.4/8; DEP-01..06/08; VER-01 | E-01a; G2rev11 | `evidence/G5/20261029-resolution-matrix/qualification.json`; current source/actual image/core5 qualified; VER-02 remains separate |
| G5-X04 | Adjacent/skipped/fresh migrations | passed | Sections6.2/6.5/12.3; VER-02 | G5-X03; retained manager path | `evidence/G5/20261029-migration-order-rollout-01/qualification.json`;24real scripts/4DBs/8native children/current SDK/approved deploy6 |
| G5-X05 | Lifecycle and removal | passed | Sections9/10/20; LIFE-01..06; MIG-07 R1 | G5-X04 | LIFE-01..06 passed: permission-upgrade-01/qualification.json plus prior native-uninstall/reinstall/source-removal evidence; current combined native/fresh restore qualification: G7/20261104-native-uninstall-recovery-01/qualification.json |
| G5-X05a | Record-bearing scoped suspension/closure/retention | passed | Sections9.1/9.2/20; LIFE-01/02; partial LIFE-03 | G5-X04 | `evidence/G5/20261029-lifecycle-01/qualification.json`; real UI/CLI/SQL/native two-workspace/worker proof, all availability restored |
| G5-X05b | Native uninstall, impact and artifact removal | passed | Sections9.3-9.5/10/20; LIFE-03/04/06; MIG-07 R1 | X05a; ADR0023 | Passed source removal8→9/native-skipped/schema-business-history exact/worker/assets/client/nativeOdoo/API; source-live-01/qualification.json. Native uninstall/scoped reinstall retained. LIFE-05 also qualified in permission-upgrade-01; no lifecycle replay. Current core23 combined native child commits with exact queue/control/history; actual fresh restore/separate resume and4plugin/8scope required Notes preview qualified in G7/20261104-native-uninstall-recovery-01/qualification.json. |
| G5-X06 | Pre-mutation failure, actual process crash, concurrency and fences | passed | Sections10.2-10.5/12.4; MIG-01/03/04/08/09 | G5-X05 | All qualified: premutation-fault-01, executor-crash-01, concurrency-01, worker-fence-01 and dispatch-fence-01/qualification.json; MIG06 requalified |
| G5-X07 | Two-database isolation and shared-runtime compatibility | passed | Sections5.3/11.1/12.1; TEN-01/02 | G5-X06 | `evidence/G5/20261029-tenant-isolation-01/qualification.json`; actual two-registry/64concurrent/nativeRPC/selector/session and genuine older-version refusal |
| G5-X08 | HTTP/security defaults and independent authority matrix | passed | Sections7.3/10.6/11.3-11.5/15/20; SEC02/03/04/07/08 | G5-X07 | SEC01..08 passed: HTTP/security02, secret-scan01, approval-security01 and operator-isolation01. Same native Odoo auth/views, no frontend expansion |
| G5-X09 | Clean recovery and release provenance | passed | §§4.3/7.4/10.5/21.4/24.4/27; OPS-02/03 | X08; ADR0028 | OPS02: clean-recovery-01/qualification.json; OPS03: provenance-01/qualification.json; G5 gate-G5.json |
| G5-X10 | Minimal Canvas reference setup | passed | §§22.3/22.5/25.5 E; UI-02/05/10 regressions | Fresh approved packaged installation | clean-recovery-01/minimal-Canvas-fixture.json and qualification.json; scoped setup/repeat/save/conflict/recovery, no product expansion |
| E-01c | Independent local approval and privileged journal | passed | SEC-06..08; LIFE; OPS-01 | E-01b core | SEC01..08 and LIFE/OPS01 qualified, current independent authority/store/application isolation evidence retained |
| E-01d | Recoverable native execution, backup/restore and release fencing | passed | MIG; LIFE; BOOT-06; OPS-02 | E-01c | MIG01..09 and OPS02 qualified for current G5 profile; clean-recovery-01/qualification.json. OPS03 provenance also qualified in provenance-01/qualification.json |
| F-01 | Deliver jobs/outbox and separately operated worker | passed | EVT; JOB; SVC | G5 | F-01a/b/c/d/e1/e2/f qualified. Final gate: headless-ui-01/gate-G6.json; trusted R1 boundaries retained. |
| F-01a | Native durable job/outbox primitive | passed | prerequisites JOB-01/03, EVT-01 | G5; ADR0029 | evidence/G6/20261029-durable-01/qualification.json;11 nativePG +4 Linux validation/4 Windows/12 HTTP CRUD denials, paused dispatch, retained records |
| F-01b | Supported job authorization and scoped events | passed | JOB-01..03; EVT-01..03 | F-01a | Actual native/current external auth/jobs/event delivery retained; JOB03 real effect/crash/unknown DTO/nonretry/refused resume qualified in job03-01/qualification.json. Final whole-G6/G7 regression remains. |
| F-01b1 | Registered authorized native jobs and guarded runner | passed | JOB-01/02 | F-01a; ADR0030/0034 | Current core1.12 qualification: core12-runner-01/qualification.json.12 installed rollback authority cases,7 actual error/cancel cases +normal CLI; retained actual SIGKILL137/reclaim once/stale claim/committed-demotion with exact AST/file boundaries. Cancellation defect fixed via normal immutable rollout, no weakening of failure enum/fence. |
| F-01b2 | Commit-safe producer events, scoped delivery and deduplication | passed | EVT-01..03 | F-01b1; G2rev13; F-01e1 | evidence/G6/20261101-host-events-01/qualification.json:14 retained native/9 HTTP/13JS/7 corrected-source browser cases with audited exact source boundaries;3 current native rollback/scope cases and4 actual host/browser/WebSocket checks. Two retained browser Notes; all original data/envelopes preserved. |
| F-01e1 | Native populated-queue drain/fences and reviewed recovery | passed | native extension of MIG-06/08/09/OPS-02; F-01b2 prerequisite | F-01a/b1; ADR0032/0033 | Prior actual populated install/native recovery/upgrades plus core13-native-features-01 real terminal-history feature cycle/current runner/native views. Current exact native source boundaries retained explicitly. Full external/pending remote profile remains F-01e2; no new race claim. |
| F-01c | Minimal deterministic external worker and host integration | passed | SVC-01/02/03 | F-01b2/e1/d/e2 | headless-ui-01/qualification.json: actual cached/fresh native form result, paused-worker timeout/SIGKILL crash warning, usable native list and explicit recovery. Existing slot/Odoo notifications; Canvas unchanged. |
| F-01d | Metadata-only artifact and approved external runtime | passed | SVC-04/05 | F-01c worker/authority backend; independent executor | worker-image-success-01/qualification.json plus linked actual transition/fault/fresh restore/stale-review/fresh-resume evidence. NEW normal upgrade23/enable114/current credentials/ordinary Alice job complete. Old05/runtime volume and22terminal containers retired; current/checkpoint image roles retained. |
| F-01e2 | External completion/credential reconciliation | passed | JOB-03; SVC; shared recovery | F-01c/d and F-01e1 | Actual reference-restore-01 terminal-history fault/freshDB/current-key/approval/fresh-review/ordinary-job resume plus job03-01 real non-idempotent effect/crash/unknown reporting/no retry/guarded resume refusal qualify bounded R1 behavior. Effect-specific manual reconciliation required; no generic automatic undo/resolver claim. |
| F-01f | Complete G6 integration and qualification | passed | all JOB/EVT/SVC; applicable ID/API/security/recovery | F-01c/d/e2 | current-backend-audit-01/coverage.json plus headless-ui-01/gate-G6.json: all11G6 acceptance IDs bound to current source/real native+UI evidence. |
| F-01f-a | Audit current installed backend coverage | passed | JOB/EVT/SVC backend evidence; no UI acceptance credit | Current24/117 and retained qualified profiles | current-backend-audit-01/coverage.json and retirement.json:12nativecases,14event-hostpaths,6matrixfiles,16SDKfiles; unchanged data/worker,4terminalchildren removed. |
| G-01 | Qualify full R1 and reproduce release/runbooks | passed | all R0/R1 | G6 | G-01e completed with §28 walkthrough and handoff. |
| G-01a | Audit supported native scope paths | passed | ID-03; §§11/23 | G6 | notes8-labels4-read-01/qualification.json: actual29/132/Notes8/Labels4/core20/identity1.5,63native/31HTTP/Canvas; pending Labels installation/feature revocation fixed, original binary/server-action proofs retained. Data/schema/files/worker preserved.1G7point. |
| G-01b | Accessibility and RTL walkthrough | passed | UI-09; §17.4 | G6; current ID08 | Installed core26 closes UI09. See G-01b5 and 20261105-core26-maintenance-01/installed-observations.json. |
| G-01b1 | Correct measured shell accessibility through immutable core maintenance | passed | UI09 prerequisite; no gate point | ADR0057/0052 | Core24/Shell11 candidate admission and actual rollout are retained as intermediate evidence. |
| G-01b2 | Install admitted shell correction and qualify current UI09 | completed_diagnostic | UI09; §§17.4/24/27 | G-01b1; current managed reference | Core24 maintenance and installed smoke completed. The dark close glyph remained indistinct and was corrected and qualified in G-01b4 and G-01b5. |
| G-01b3 | Build/admit remaining owned close/title accessibility correction | passed_static_candidate_not_installed | UI09 prerequisite; no point | G-01b2 audit; ADR0057/0052 | Current567d actual36observations/real200percent/17tables+4runtimes preserved. Source25/Shell12 CSSnativeclose+ownedDialogtitle extension,17Python+JS/XML/106freeze pass. Actual onebuild36511exit0/candidate6028+inventory1b12 admitted5sourcechanges/77distributionsexact/artifacts+policyexact/fourruntimesexact/133privacy0; ordinaryupgrade/installedproof pending. |
| G-01b4 | Install core25 and verify native dialog corrections | passed | UI09 prerequisite | G-01b3 | Reviewed upgrade and preservation passed. Installed name, glyph, zoom and reflow evidence retained. |
| G-01b5 | Close UI09 scope | passed | UI09 and §17.4 | G-01b4 | Core26 installed with preserved data. Localized counts and dates, native accessibility events, dialogs, zoom, RTL and keyboard workflows verified. |
| G-01c | Performance and reliability qualification | passed | §§24.1–24.3 | G6 | Current14de10k/20session reads, shell586–990ms/100disposal cycles and source-bound observability qualified.20261104-observability-01/qualification.json binds actual evidence and limits;2/2performancepoints. |
| G-01c1 | Record resources and measure read preflight | completed_diagnostic_target_not_run | §24.1 prerequisite; no target credit at30Notes | G-01a; G-01d0; G-01d1 | performance-preflight-01/resources.json/read-preflight.json/query-profile.json: engine16CPU/8.291GB, app2CPU1.5GiB+DB1CPU512MiB,2workers; listlatency2.0/3.5s,519/816SQL queries for24rows,0errors.30Notes not10kqualification. |
| G-01c2 | Bound authorization reuse during pure read serialization | passed_bounded_correction | §24.1 prerequisite; ID03 requalified | G-01c1 | Core20/Notes8/Labels4 installed scope/security/preservation pass, realHTTP30Note20concurrent p95native178/120ms and gateway187/156ms,0errors. No10k target/extra performance points. |
| G-01c2a | Qualify core finite read window | passed | Preserve ID03/FEAS02; §24.1 prerequisite | G-01c1 | read-window-02/qualification.json: actual28/129,55native31HTTP/Canvas/52host97freeze, data/schema/worker exact except reviewed epochs.23helpers/3unusedimages retired; no target credit. |
| G-01c2b | Adapt Notes/Labels finite read serialization | passed | §24.1 prerequisite; ID03 requalified | G-01c2a | notes8-labels4-read-01/qualification.json: ordinary five-scope29/132,63native31HTTP/Canvas/50host97freeze,2policycases, preserved data/schema/worker,21helpers/3images retired. RealHTTP/10k targets remain. |
| G-01c2c | Measure read-correction HTTP discriminator | passed_diagnostic_only | §24.1 prerequisite; not10k qualification | G-01c2b | read-http-discriminator-01/comparison.json:20sessions/40samplespercase/30Notes24A, p95native178.482/119.953ms/gateway187.228/156.274ms,0errors; all17tables/worker exact. Rare max~1.1s recorded. |
| G-01c3 | Qualify10kNotes/20concurrent reference benchmark | passed | §24.1 read target | G-01c2 | Actualcurrent14de/d81/dece generation30/currentguardedfixture:800requests/20sessions/10000A/p95native304,108/gateway361,163ms,0errors; all17bench+17originaltables/worker/dataSHA exact. ADR0054 explicitunmanagedfixturealignment, no productlifecycleclaim. read-qualification.json;1readpoint/37over500ms/max~1.1s retained. |
| G-01c4 | Qualify remaining performance and observability bounds | passed | §§24.1–24.3 | G-01c3 | Actual current shell/100cycles plus21live source bindings/10G6 exact files, structured aggregates/resource sample, R0/lease/revocation/readiness bounds. Added private operator5second heartbeat/20second stale diagnostic; forced-death19.860s/concurrent refusal/19tests/106freeze/133valueprivacy0findings/17tables exact.20261104-observability-01/qualification.json. Final operator source-kit update remains G-01d2. |
| G-01d | Fresh release/runbooks/security/provenance rehearsal | passed | §§23/24.4/27/28 | G6; G-01a/b/c where relevant | Current core26 reproduction, release kit, clean backend/worker, provenance, scoped network and privacy proof. Retained fault restore is separately bound. Fresh browser/developer completion belongs to G-01e. |
| G-01d0 | Retire obsolete owned local Docker fixtures | passed_bounded_ownership | User cleanup constraint; §§4.3/24.4/27 | Qualified current27/126 and checkpoints | docker-retention-01/qualification.json:105exitedcontainers,61unusedvolumes(aftercomplete private byte-verified archives),28unusedrecordedimages/70tags removed. All current/recovery/worker/unselected resources preserved. Unknown/shared resources and global BuildKit cache retained. No acceptance/progress credit. |
| G-01d1 | Fix valid empty Canvas persistence | passed | §§22.3/22.5; boards.schema.json; required reference behavior | G-01a | canvas4-source-01/qualification.json: actual Canvas4 upgrade27/126/one nonempty preupgrade board preserved,9native/10HTTP checks, actual committed[]/freshget/restore revision3, strict CAS/roles/scope/reference/inputs and native Notes views. No frontend changes/product expansion/new acceptance credit. |
| G-01d2 | Audit current release security/dependencies/licenses/network/secrets/provenance | passed | §§23/24.4/27 | Current images and UI09 | Core26 image and notice inventory, internal runtime topology, final kit source/archive/history and fresh diagnostic privacy passed. |
| G-01d2a | Check current operator in kit environment without lifecycle replay | passed_bounded_preflight | OPS03 prerequisite; no point | G-01d2 | 20261104-operator-release-preflight-01/qualification.json:50 kit components/eight code deltas/19tests/current completed journal exact/174control files/fourruntimes exact/133valueprivacy0. Final source/image kit still pending. |
| G-01d2b | Developer entry point and versioned reference packaging | passed_bounded_packaging | §28/OPS03 prerequisite; no point | G-01d2a | PLATFORM.md/developer-guide.md/package_reference.py; actual kitPython/eightCLI/two versioned archives validated+byte-reproduced, mismatch-nooutput/overwrite-preserved,133privacy0. Full final-kit installed developer workflow remains required. |
| G-01d2c | Bind release producer/source refresh to explicit application proof | passed_bounded_guard | BOOT02/OPS03/§28 prerequisite; no point | G-01d2b; ADR0058 | 9tests/real assemble+refresh oldreceipt refusals beforeoutput/current50kitcomponents unchanged/133privacy0. Current final candidate/reproduction/kit stillrequired. |
| G-01e | Final release evidence and handoff | passed | All R1; §28 | G-01a..d | Fresh browser, backend and 15-deliverable audit passed. |

## G5 exit criteria: complete

**No required G5 work remains.** All45 G5-owned acceptance checks and X10's explicit minimal reference-fixture requirement passed. `evidence/G5/20261029-provenance-01/gate-G5.json` binds the full exit review; the acceptance ledger below remains authoritative. X01..08 retain their linked current-source install, version resolution, migration, native lifecycle/removal, worker/client/queue fencing, tenancy and security evidence. These recent final criteria close the gate:

| Criterion | Completed required work | Spec / acceptance mapping | Evidence |
| --- | --- | --- | --- |
| G5-X09: clean recovery | Fresh emptycore/approvedreferenceinstallation, actual nativecommitfault/checkpoint, ordinary exact reviewed fresh restore and separate resume; exact DB/files/code/config/currentnativeauth/authority/HTTP/fences; complete160fileprivate recovery kit | §§10.5,21.4,24.4; OPS-02 and MIG-06 requalification | clean-recovery-01/qualification.json; recovery-rehearsal.md; ADR0028 |
| G5-X09: release provenance | Actual image/source/build/dependency/host locks,3937exactofficialfiles+2reproducedgeneratedpatches,8artifacts,16nativeaddon/76Python/113OSlicense records,287retainednotices including3hash-lockedsource supplements; unchanged release data and internal backend | §§4.3,7.4,24.4,27; OPS-03 | provenance-01/qualification.json; provenance.md; third_party/python notices |
| G5-X10: minimal Canvas reference setup | Explicit scoped fresh provisioning, repeat/no duplicates, get/save/idempotent replay/stale conflict/foreign-ID and actual recovery preservation. Only two deliberate same-content test saves after exact restore comparison | §§22.3,22.5,25.5 E; UI-02/05/10 regressions; G5-CANVAS-FIRSTUSE-01 | clean-recovery-01/minimal-Canvas-fixture.json and qualification.json |

The existing native Odoo list/form integration remains the standard CRUD path. Canvas and optional custom pages remain minimal reference capabilities; no frontend rewrite or product expansion occurred. G6 jobs/events/external services have since passed. Remaining **required R1** work is G7 final complete qualification, including refreshed final-image provenance/reinstall/security/browser-network/accessibility/performance checks. It is separate from this passed gate.

MIG-08/09 retain their qualified G5 profile: bounded queues and external completion receipts stay fenced until explicit fixture-only reconciliation and fresh independent resume. Unknown restored queues cannot silently resume. The G6 native extension now proves actual populated install and pre/post-native recovery, with original-user queue reconciliation; new-image upgrades and managed worker/external effect/credential integration still must requalify the complete shared cases before G7. The legacy default rejects dispatch tables, while the recognized native-only extension continues to refuse API keys, live technical credentials, external runtimes and uncertain effects.

Already qualified: PKG-01..05, BOOT-05/06, DEP-01..08, VER-01/02, LIFE-01..06, MIG-01..09, TEN-01/02, SEC-01..08 and OPS-01..03; actual adjacent native/core upgrades, populated fresh-DB recovery, exact-hash approval, static deployments and controlled client refresh provide additional integration evidence. Reuse those results where their source boundary remains unchanged; do not rerun them as a substitute for the open cases.

**Optional, not G5 exit work:** additional Canvas features, whiteboard/collaboration/CRDT functionality, Canvas appearance polish, a WebClient replacement, and a broader design-system rewrite. Required accessibility/error-recovery fixes are not optional. G6 jobs/events/external-worker implementation and G7 full accessibility/RTL/performance/final reinstall audits are later required R1 work, not discarded requirements. R2 isolation, marketplace billing/ratings and public publication remain outside this goal.

## Required work after G5

These are later R1 gates; they are not remaining G5 exit criteria.

| Required work | Current state / remaining observation | Spec / acceptance |
| --- | --- | --- |
| Deployed event host and scoped delivery | Passed EVT01..03 with actual deployed host/native WebSocket/replay/disposal plus current native rollback/scope and exact-boundary retained integration; G6 current-source audit passed; final G7 release audit remains | §§14.1,16,25.5 F; EVT-01..03; shared UI/ID |
| External worker and registration | G6 passed: SVC01..05 current-source/backend and actual browser timeout/crash/native-survival/recovery proof; no remaining G6 implementation | §§14.3/14.5/14.6/20.2/20.3/22.4; SVC-01..05 |
| External effect/credential recovery | Passed bounded R1 reference behavior: actual non-idempotent effect/crash/unknown/nonretry and refused resume; actual old/new-image fresh restore/current revocation/stale-review/fresh resume. No generic remote rollback/resolver claim. G6 gate passed; final G7 release audit remains | §§10.5,13.4,14.2,24.4; JOB-03; shared MIG-06/08/09/OPS-02 |
| Final complete R1 qualification | Broader native batch/path audit, accessibility/RTL/performance, final image provenance/fresh reinstall/recovery/runbooks/release bundle | §§23,24,25.5 G,27,28; ID-03, UI-09 and full R1 ledger |

## Blockers and limitations

Current AR goal is complete; no active item, user blocker or uncertain mutation.
Two Windows bind approaches were retired after pre-container timeouts; tracked
volume streaming passed native regressions. The inherited golden mismatch is
fixed with preserved historical/current revision fixtures and qualified gates.
Consolidated core46/R1/BG retain their completed historical scopes. The five
previously protected closed browser profiles remain under
`.local/g6-events/headless-ui-01..05/profile`, excluded from release, after
automatic approval review rejected deletion; no alternate deletion was attempted.

| ID | Scope / state | Evidence / resolution |
| --- | --- | --- |
| CF-RECOVERY-SKIP-01 | Resolved by exact bounded core46 guard and real native recovery | Original45 refusal retained. Exact30-to45/46 four-empty-known-table paths passed failed-app-down fresh restore and separate resume while peer remained useful; arbitrary schema/history changes still refused. ADR0070 and cf-04-decision.json. |
| BX-05-CONTINUATION | Closed by native app/lifecycle proof | Successor preflight ordering and terminal JSON cleanup corrected. Native rollback/concurrent submissions/current authority/process death/partial cancellation/compatible upgrade/fresh restore/forward release passed. ADR0068, bx-05-decision.json. |
| BX-04-FAIRNESS | Corrected and natively requalified | Two hot workspaces previously consumed60 claims before68 peers. Core44 rotating selection serves peers within the fixed fairness bounds and survives child restart. ADR0066/core44 guard evidence. |
| BX-04-CLAIM-GUARD | Closed by native load and populated recovery proof | Isolated compute-slot connection loss previously admitted two valid workspace/pool claims. Preparation guard plus running-row exclusion passed ten PG races, exact native loss, fairness/restart, paired load and fresh recovery/forward release. ADR0067 and bx-04-decision.json. |
| BX-02 | Resolved | Reviewed roles, partial recovery, connection loss, graceful/forced drain and actual release races passed; all owned Docker assets retired. See BX-02 decision. |
| BX-03-LIFECYCLE | Closed by native proof | Exact paused role selection, scoped credential review, populated upgrade, history-delta refusal, fresh restore, separate resume and explicit credential repair passed. Generic profile remains strict; changed post-checkpoint history still requires independent reconciliation. ADR 0064 and bx-03-recovery.json. |
| STOCK-RTL-01 | Resolved | The bounded launcher mirrors the full stylesheet under the HTTP worker limit. Preflight and both browsers passed on the selected image. |
| STOCK-PERF-01 | Resolved | The selected image passed the analyzed 10,000-note workload with p95 367.832 ms for list and 169.833 ms for detail. |
| G7-UI09-01 | Resolved | Installed core26 browser, Windows accessibility event, locale and keyboard qualification passed. See 20261105-core26-maintenance-01/installed-observations.json. |
| G7-FRESH-BROWSER-01 | Resolved | User selected the in-app browser. Generation5 native Notes, Labels and Canvas walkthrough passed. |
| G7-ID08-CURRENT-01 | resolved; current ID08 passed |20261104-ui-qualification-01/identity-qualification.json actual sameAlice Aadmin/Bviewer native lists/forms/lateHTTP200 response cancellation, no crosstab cache/data/role contamination.17tables/fourruntimes exact; no foreign requests/exceptions; ownedprofile process exited0. UI09/fullrelease still open. |
| G7-NETWORK-INDEPENDENCE-01 | backend/static qualified; current browser/release closure still open |20261104-network-independence-01/backend-qualification.json+alias-qualification.json: actual internal app/DB/worker topology/TCPcontrols,4159source hashes,24root families+optional reportfont CDN, actual2CSS0remote resources,17tables/fourruntimes exact. No arbitrary native/browser/OS containment claim. OPS03 not yet requalified. |
| G7-OPERATOR-KIT-01 | explicit final-release gap; environment preflight passed | Draft source lacks current heartbeat and still packages14de. Current-source CLI works in kit Python/19tests; actual completed readbacks agree and174control files/fourruntimes exact. Final qualified source/image refresh and delta privacy required, including heartbeat/package_reference/developer guide/PLATFORM and ADR0058 release-input helpers. Nine tests/actual stale-receipt refusal prove producer guard only; no lifecycle replay. |
| G7-EXECUTOR-OBSERVATION-01 | resolved for supported operator CLI | ADR0056/current20261104-observability-01/qualification.json: actual5second heartbeat/20second stale pulse, real forced-death/concurrent-writer tests,19tests and106freeze. Observation never grants retry/rollback; legacy/directSDK not recorded. Final operator-source-kit inclusion remains G-01d2. |
| G7-CURRENT-10K-READ-01 | qualified currentread subset | 20261104-performance-current-01/read-qualification.json current14de/d81/dece/800requests/20sessions/10000A/0errors/allp95<500; rawtails37over500/max1.1s remain. Source/sharedDB/worker/data17tablechecks exact. UI/shell/mount/bounds/R0/fullG7 remain; no productupgradeclaim fromexperimentalfixturealignment. |
| G7-KIT-PRIVACY-RUNBOOK-01 | qualified backend artifact slice; G7 still open | kit-qualified.json reconciles133values/old121-to123hashes/main+nestedactualcontent/8staticexamples/exactGit/fullbootstrap/native+workerjob/12runbooks. Sizeguardrefusal source1.19GB reviewed exactroot2GiB; no productlimits relaxed. Browsernetwork/currentreleaseclosure/perf/UI/finalremain. |
| G7-KIT-WORKER-TRANSPORT-01 | resolved transport and portable integration | ID/digest export omitted names; stable checked tag retains binding. Actual new-repository load/78verbatimblobs/digest identity passed; probe tag/archive retired. image-transport-repair.json/image-transport-load.json. No blank-daemon claim. Actual portable provider/connector/original-actor job now qualified at worker-integration.json; no full kit/G7 claim. |
| G7-DATED-CVE-REVIEW-01 | known OS/native decisions complete at recorded snapshot scopes |159 OS rows plus72 native component decisions, exact versions/source/vendor evidence/review-byNov11/change triggers. Native Expat/XML/XSLT/codec/Node/compression/SQLite/proxy distinctions recorded in native-review-02/. Material residuals and finite feed/method limitations explicit; no universal patch/safety claim. OPS03 still invalidated for other current release evidence. |
| G7-NATIVE-UNINSTALL-DISPATCH-01 | resolved; current combined profile qualified | ADR0051/rev18/core23 actual manager approval, native columnloss with exact fenced queue/control/history, freshNEWDBrestore/currentauth/38files, separatelyreviewedresume, oldsession/pin/plan refusals,4plugin/8scope closure and ordinary originalactor job. G7/20261104-native-uninstall-recovery-01/qualification.json. Unknown external effects remain closed. |
| G6-BROWSER-SURFACE-01 | dedicated owned headless surface available; remaining walkthrough pending | User chose backend checks when IAB unavailable. G6 subsequently qualified real UI in isolated Edge/NodeCDP, personal browser untouched. UI09/manager walkthrough remain G7; continue backend now. |
| G6-EXTERNAL-MINIMUM-01 | resolved; real same-image upgrade qualified | New immutable0.1.1/minimum.13 curated with old0.1.0history preserved; actual reviewed upgrade config13/dispatch61 preserves enabled feature/native schema/modules/data/jobs/files and independent worker. provider-upgrade-01/qualification.json; changed-worker-image case remains separate. |
| G6-METADATA-MAINTENANCE-DISPLAY-01 | installed correction/HTTP preview passed; browser rendering pending | Core15 actual upgrade preserves data/worker; same real installed HTTP metadata preview now returns restarttrue/nativefalse and accepts request. Shared rule/G2rev15/source117 pass. IAB bridge unavailable/native user active; user chose backend checks, no browser-rendering claim. |
| G6-CURRENT-BACKEND-AUDIT-01 | qualified and incorporated into passed G6 | current-backend-audit-01/coverage.json binds all11JOB/EVT/SVC IDs to installed24/117. Native12cases/current source/retained scope preserved; actual SVC02 UI is now closed by headless-ui-01/gate-G6.json. |
| G7-PROXY-OS-MAINTENANCE-01 | resolved; default selected after current dev and production profiles | ADR0048/support-images-01 plus production-profile-01/qualification.json requalifySEC02/04. Defaultdece6f selected, workingoriginal/freshedges retained; host-only offlinebuilder exactcontext/safety verified. Fixture4containers/9volumes/2networks archived/retired. Fullprovenance/security/kit/reprobuild pending. |
| G7-RELEASE-SECRET-STORES-01 | corrected private capture classification; image audit still live | image-secret-audit-01/secret-export-relocation.json records four exact config/backup exports moved out of log namespace. Original14known positive retained; remaining5922logstreams zero. Repository/history/current assets+archives+container logs reviewed. Full image-layer scan74244/PID18172 still running; no SEC03 pass. |
| G7-CORE22-PROVENANCE-NETWORK-01 | bounded subsets passed; full release audit open | core22-provenance-01/qualification.json and worker-notice-bundle.json bind source/app274 and worker164 notices. offline-runtime-01/qualification.json proves internal-only topology,4 external denials/4 local successes and current reference reads with17tables unchanged. Browser capture/full SEC03/OPS03 pending. |
| G7-XML-INPUT-01 | supported XLSX mitigation qualified; dated native risks recorded | ADR0050/core22 native actual import/entity refusal retained. Native-review-02 actual current defused selection/wrapper APIs and four Expat decisions; attribute overflow not called fixed, external-subparser API present. Separate embedded XML/XSLT findings/backports recorded. No blanket Expat/parser safety claim. |
| G7-RELEASE-DEPENDENCY-AUDIT-01 | open review; operator maintenance qualified | release-runtime-audit-01: actual76/13Python and113/105OS inventory/notices; primary source triage133pairs,1newer SASL fix. DIGEST-MD5 mechanism absent in shipped app; no automatic waiver. ADR0047/G2rev17: crypto50Windows232checks/TS/freeze/oldkeys pass. PG/nginx/vendor/network/history/secrets/license/reprobuild remain, no final SEC/OPS pass. |
| G7-DEPENDENCY-MAINTENANCE-01 | normal host/worker and actual dependency fault/restore qualified; full fresh release pending | ADR0046/G2revision16, actual570/worker87 and fresh realm real570native commit/fault/reviewed fresh previous31 restore/separate resume pass. MIG02/06 requalified; terminal-native scope, fullfresh/security/remoteeffects/runbooks remain. |
| G7-NATIVE-SHORTCUTS-01 | resolved: actual immutable corrections qualified | native-paths-01 old HTTP/binary and cached-field counterexamples retained. ADR0039/0040: normal core18 then19, actual26/123:40native/29HTTP/Canvas paths pass, core18 binary HTTP and server actions retained by exact unchanged source. ID03 passed; all36jobs/other16tables/schema/files/worker preserved. |
| G7-CANVAS-EMPTY-01 | resolved: minimal Canvas4 actual upgrade/qualification | ADR0041, canvas4-source-01/qualification.json: only cards NOTNULL removed, public[] retained.9native/10HTTP, existing seeded board/other data/worker preserved; first test expected wrong INVALID_INPUT while actual correct VALIDATION_FAILED, resumed from known committed revision2 without write replay, restored own cards atrevision3. |
| G7-DOCKER-RETENTION-01 | resolved bounded owned-resource cleanup; explicit retained limits | ADR0042 and docker-retention-01/qualification.json:105oldterminalcontainers/61unusedownedvolumes/28unusedrecordedimages retired; all61volumes privately archived2.289GB→495.9MB, everyfile pre/post/tar hashes and UID/GID/mode/mtime/link verified, archives rehashed/fsynced. Current4runtime/17tables/worker/current+latestcheckpoint and previousworker images retained; all unmatched/unselected assets and global shared BuildKit cache untouched. Cold archive is not historical restore qualification; no Windows VHD compaction claim. |
| G7-LABELS-PENDING-POLICY-01 | resolved actual Labels4 ordinary upgrade; ID03 requalified | Old installed Labels3 counterexample preserved; targeted queried policy flush fixes pending ORM installation availability before cached-field access. Corrected actual29/132/63native31HTTP/Canvas/preservation plus2candidate policy cases pass. notes8-labels4-read-01/qualification.json. |
| G7-CURRENT-DEPENDENCY-ADVISORIES-01 | host/worker remediation installed; final audit pending | App570 has17family updates/76package solution; actual worker87 hascrypto50/pip26.3/13packages. Initial18matchedentries/178records/102aliasgroups remain historical observations, not exploit counts. Final OS/vendor/vendored/host-tooling advisory/license/network/layer/notice review remains. |
| G7-PERF-READ-01 | historical pass; target dependency revalidation pending | Old31 actual800requests/20concurrent/10kNote p95323/120 native254/182gateway,0errors retained. Current570 activehost changed; benchmark fixture stillold31, no newtargetreadpoint claimed until same procedure reruns. |
| G6-MINIMAL-ANALYSIS-UI-01 | resolved; actual browser proof passed | headless-ui-01/qualification.json and gate-G6.json: real native list/form, cached/fresh statistics, post-navigation completion suppressed, timeout+SIGKILL degraded warning, native host survives, explicit post-recovery results. Personal browser untouched; no UI/product expansion. |
| G6-EXTERNAL-MANAGER-01 | SVC04/05 qualified; manager-browser walkthrough remains G7 | Retained normal manager unregister/stopped-worker re-register/source preservation plus current changed-image request/review/upgrade/enable/completed HTTP mirrors all pass. worker-image-success-01/qualification.json. Browser rendering remains pending at user request; no frontend-rendering claim. |
| G6-REFERENCE-REREGISTER-01 | resolved for actual stopped-runtime reference profile | Actual stopped-worker HTTP request2b5f4ed3 failed before mutation at removed-endpoint guard. failed-apply-audit.json; ADR0037 admits only inert same-image pre-registration with grants/bindings closed.67related/43version checks/current realprofile/actual fresh exact unchanged resume15/76 pass; no DBrestore or worker replacement. reference-reregistration-fix-01/. Actual core16 immutable rollout and NEWre-register02/config17/control82 preservation/HTTP/mirror pass; installer leavesworker stopped, separateoperatorstart restoreshealthwithoutactivation. manager-reregister-02/qualification.json. Oldfailedopclosed; fullremote/requiredconsumer/recovery/image/browser remain. |
| G6-REFERENCE-RECOVERY-01 | qualified bounded R1 recovery/unknown behavior | reference-restore-01 current-key rotation/fresh resume plus JOB03 actual effect/crash/unknown/nonretry/refused resume retained. worker-image-upgrade-01 adds actual changed-image commit fault/fresh DB22/current revocation10/stale-review/fresh resume; worker-image-success-01 adds NEW successful upgrade/enable/ordinary job and current unknown guard. Revocation timing is after closed SQL restore. No generic remote rollback/effect resolver claim. |
| G6-REFERENCE-STAGING-01 | qualified for the reference/native connector profiles | Retained native staging/connector source84 and actual core14/15/BB1 retention proofs remain. Current core17/default profile and SVC05 actual changed-image metadata/recovery/new success path qualified in worker-image-success-01. No remaining image-transition blocker. Future UI plugin upgrade must still use ordinary immutable staging/approval. |
| G6-QUEUED-NATIVE-FEATURE-01 | actual installed terminal-history profile qualified | core13-native-features-01:real suspend/enable checkpoints/fences/reconciliation/readiness, native C denial/restoration with A/B list/form, exact17table/18oldjobs/46files, new original-actor normal read-only job. Source10PG/53host retained. No fresh pending/in-flight race claim; external revocation/uncertain profiles remain required. |
| G6-CURRENT-INSTALL-CLI-01 | resolved for required read-only planning path | Explicit optional --operator-store selects fresh protected external reader while --store stays catalog, legacy native behavior retained.3 source option/authority negatives plus actual current-image native plan with registered/suspended metadata root independently reconstruct and preserve17tables/worker/pins. manager-feature-02/current-image-cli-qualification.json. No native install or Canvas change. |
| G6-EXTERNAL-IMAGE-01 | resolved for R1 reference; SVC05 passed | worker-image-success-01/qualification.json binds actual unapproved/old/third-image/default refusals, private installed transition, real newmetadata commit fault/fresh restore/current revocation/stale-review/fresh resume, NEW successful upgrade/enable/current credentials/ordinary remote job and strict default/unknown guard. No API-major/storage migration or arbitrary effect rollback claim. |
| G6-EXTERNAL-FINALIZE-01 | installed authority and committed actor/revision profiles qualified; independent credential/publication resume fence now qualified; unknown effects separate | Current installed-authority-01:8 native rollback controls around actual remote result, unchanged runner finalizes normally afterward. Real committed role01 before/after I/O and revision01 races reject FORBIDDEN/CONFLICT/no stale result. Prior22source cases retained with correct candidate/temporary-authority limits. Current18/94/BB1 connector installed; reference-restore-01 adds actual stale-review/publication/key rotation and current recovered remote job; no generic unknown-effect recovery claim. |
| G6-METADATA-TEST-HELPER-01 | bounded discriminator passed; full Windows bind remains unqualified | Earlier helper with full Windows repository bind stalled before a named container appeared. Same exact image/no bind/no volumes now runs in <1s and auto-removes; runtime-probe.json shows no retained container. Supports usable Docker execution without that bind, not proof the bind issue was fixed. Current PG source cases use isolated existing-container processes. No daemon restart/global prune/retry. |
| G6-WORKER-COMPOSE-START-01 | worker runtime/shutdown resolved; old daemon cleanup pending | Linux public-config volume enables actual Compose/auth/outage/restart; realPID1SIGTERM137 fixed in new immutable1d919d0c/actualstop0. New worker fixtures retired after proof. Original f846Created Docker removal and unusedstage image removal timedout; no globaldaemonrestart/retry. Currentnative200/protectedconfigs exact. evidence/G6/20261101-worker-shutdown-03/checkpoint.json |
| G6-EVENT-FREEZE-01 | resolved prerequisite; G2rev13 passed |94files/eight rows/105 source tests/TypeScript. First broad run found stale positive CLI platform0.1.0 against current Notes>=0.1.8, corrected to a consistent compatible empty core plus explicit legacy refusal; unchanged passing records reused. Original failed gate retained; no runtime policy weakened. |
| G6-BROWSER-TIMER-01 | resolved; actual installed host/native bus/browser qualified | Approved core10/identity12/Notes.7 current image has wrapper;13JS/7 source-browser cases retained with exact current hashes. Actual deployed host facade receives old/new committed events via real Odoo WebSocket bus; replay/disposal/native Notes/viewer checks pass; evidence/G6/20261101-host-events-01/qualification.json. No Canvas source/UI change. |
| G6-PENDING-AUTHORITY-01 | resolved; installed identity1.2 qualified | ADR0033 policy-only native ORM flush;20 installed cases plus native/REST/asymmetric/technical/warmed-new-session/two-worker demotion-revocation pass. Original authority/groups/business restored; Scope/SQL/cache logic and94 frozen files unchanged. evidence/G6/20261101-identity12-upgrade-01/qualification.json. |
| G6-NATIVE-PENDING-REVISION-01 | resolved bounded native batch; ID-03 final audit still required | Separate independently approved Notes.6→.7 operationa3b2a10f/config8/control37 passes10 actual installed native direct/bound batches/repeated writes/unlink/stale CAS/whole-attempt rollback/mixed-workspace/role/identity protection. All test writes rolled back; evidence/G6/20261101-notes7-upgrade-01/qualification.json. No source substitution or Canvas change. |
| G6-PLATFORM-RANGE-01 | resolved; native qualification passed | Unselected Notes0.2.4 counterexample retained. Notes0.2.5 requires image-observed platform>=0.1.8/core1.8;47 source checks, actual approved fresh installations and legacy exact lock/metadata projection pass. Global catalog/trust/old deployments unchanged. |
| G6-JOB-STARTUP-01 | resolved; actual corrected process qualified | Candidate02 namespace failure retained before claim, paused unclaimed job attempts0/revision1. Explicit native Registry/config initialization in candidate03 passes actual default guarded runner, SIGKILL/reclaim/old-claim denial. Only inventoried runner changed between02/03; package/core/dispatcher exact. No populated queue lifecycle bypass. |
| G6-RECOVERY-ADAPTER-01 | native F-01e1 resolved; full external F-01e2 still required | Actual populated native install, pre/post-native faults/fresh restore/separate resume, core10/identity12/Notes.7 upgrades and compatible historical delivery/nativebatch/host-bus-browser pass; evidence/G6/20261101-host-events-01/qualification.json. External managed-worker drain/completion/credential reconciliation is a separate mandatory requirement. |
| G6-EVENT-RELEASE-HISTORY-01 | resolved; installed native and actual host historical delivery qualified | Actual immutable upgrades retain producer envelopes/current scope; old-release delivery/replay/foreign refusal/native tombstone duplicate/paused close and current host29callbacks/realreplay pass. All42 original immutable envelopes retained;9 mutable states pending→published are expected on delivery. evidence/G6/20261101-host-events-01/qualification.json. |
| G6-JOB-REPEAT-PREFLIGHT-01 | resolved installed core10/identity12 | Actual original-user runner attempt2/one effect, saved semantic outcome and first trace after revision advances, changed-input refusal, no failed reservation, current role recheck pass; original-job-regression.json and checkpoint-trace.json. Old claim denied while original lease live in core10 pre-runner proof; runner never replayed. |
| G5-NATIVE-NUMERIC-01 | resolved; VER-01 passed | Original eight-digit counterexample preserved. ADR0021 exact generated correction, source69/69, actual0afd445c parser/applicability, independently approved core96a53908/compat1.1 and post-activation equality all pass; `evidence/G5/20261029-resolution-matrix/qualification.json`. VER-02 actual database/script matrix also passes in migration-order-rollout-01/qualification.json. Main28/native checkout untouched. |
| G5-MIGRATION-ORDER-01 | resolved; VER-02 passed | Original skipped/wide planner-order mismatch retained. ADR0022 phase-first correction70/70/84freeze, exact SDK-only031017e3 deployment6 and current-image/24real SQL-witness audit pass. `evidence/G5/20261029-migration-order-rollout-01/qualification.json`; no native replay |
| G5-NATIVE-REMOVAL-01 | resolved; LIFE-06 passed | Actual in-use manager+CLI refusal followed by separate independently approved native uninstall7→8/source-only removal8→9. Exact7files absent, no native child, fixed publisher preserves schema/business/history/bindings; worker/client/assets/nativeOdoo/Notes/Canvas proof and protected target audit pass. `evidence/G5/20261029-source-removal-live-01/qualification.json`. |
| G5-PREMUTATION-RECOVERY-01 | resolved; MIG-01 passed | Actual fault exposed missing unchanged-release return path; fresh-target restore correctly refused. ADR0024 existing CLI/reviews/locks/store now retire failed authority and resume exact guarded base without DB/files/epoch changes. Three real fault positions,26Windows/26Linux/87freeze, APIs/assets/replay and protected audit pass: `evidence/G5/20261029-premutation-fault-01/qualification.json`. |
| G5-NATIVE-AUTH-RESTORE-01 | resolved; OPS02 passed / MIG06 requalified | Original canonical-authority counterexample retained. ADR0028 private combined snapshot/digest/current native overlay/resultproof/finalresume fence,41Windows/35Linux/87freeze, actual fresh restore and separate resume/fullauth+HTTP+data/files pass; `evidence/G5/20261029-clean-recovery-01/qualification.json`. No public/native/image/UI changes. |
| G5-MAINTENANCE-LOG-01 | resolved; SEC03 passed | Docker retained20credential occurrences/10config readers and43binarycheckpoint streams. ADR0027 host-only no-daemon-log children, real exact attached/private capture, preserved private diagnostics and exact stopped-helper cleanup; fresh202container+837private-log scan clean. `evidence/G5/20261029-secret-scan-01/qualification.json`. |
| G5-HTTP-DEFAULTS-01 | resolved; SEC02/04 passed for current profiles | ADR0026 explicit host/Origin/proxy/cookie/TLS/rate and production account/endpoint defaults; http-security-02/qualification.json. Actual request matrices/typed platform and native errors/preflight/Compose/source/protected audit pass. Existing development deployments retain historical proxy bytes; no external production deployment. |
| G5-RESTORE-EFFECTS-01 | resolved; MIG09 passed / MIG06 requalified | ADR0025 host-only effects/authority bindings and final safe-boundary observation; old read-only counterexample, preparation/start/late negatives, supported real restore/resume and protected target/receipt audit pass.35Windows/49Linux/87freeze; `evidence/G5/20261029-dispatch-fence-01/qualification.json`. G6 adapters must requalify. |
| G5-METADATA-GUARD-01 | resolved; MIG08 passed / BOOT06 requalified | Real partial-native DBs accepted by old guard are now rejected before native import. New bidirectional native/package consistency check,23Windows+1OSskip/24Linux/87freeze,5realdefault-entrypoint copies, exact1fileSDKactivation18 and actualold17image refusal against active18 pass. Full data/schema/protected targets exact. `evidence/G5/20261029-worker-fence-01/qualification.json`. |
| G5-CRASH-PREFLIGHT-01 | resolved; MIG-03 passed | Host runtime preflight masked lost executor when app stopped. Journal/lock-owner reconciliation now precedes runtime/stage/base observation for possible mutation; fresh preflight/completed replay preserved. Actual OS termination and fresh recovery plus6Windows/70Linux/87freeze pass: `evidence/G5/20261029-executor-crash-01/qualification.json`. |
| G5-COMPILED-RUNTIME-01 | resolved for G5; final release reproducibility remains G7 | Same-lock compiler variant changed psycopg2/python-ldap .so hashes. Rejected835 preserved; exact base-layer derivationea6c34ce passes unchanged strict guard/Python/config/layer checks. BuildKit FROM alias issue diagnosed before RUN and fixed with content-bound alias/postchecks. No deployed/runtime data change from failed attempts. |
| G5-TRUST-RELEASE-01 | resolved | ADR0013, SDK150/123 regression; immutable published lock/current trust fence and actual adoption/rollout/restore retained. Policy/trust remain2/3 with7curated artifacts. |
| G5-PLATFORM-UPDATE-01 | core maintenance/recovery, controlled refresh and manager prerequisite qualified; broader G5 matrix remains | ADR0015/0016 restrictions retained; actual core27 and same-image scoped native install28 use checkpoint/readiness before traffic. Manager status survives explicit refresh; native views remain default. Manager first-native/adjacent package upgrade qualified in manager-upgrade-01, current inspection/upload/core4 in manager-inspection-http-01; skipped/fresh now passed in X04; uninstall/crash/concurrency/remaining security remain in the exit map. |
| G5-UI-REGRESSION-01 | controlled reload and changed UI/ID/API cases qualified | Actual static fault/restore21 and changed-asset activation22, exact two-page drafts, cancellation/explicit refresh and unchanged business state: client-refresh-static-normal-01/browser/browser-qualification.json and postbrowser.json. UI07 passed. Strict immutable asset retention is now separately qualified below. |
| G5-ASSET-IMMUTABILITY-01 | resolved for current/future published host assets | ADR0018 and `evidence/G5/20261028-asset-retention-requalification/requalification.json`: native adapter retains old public metadata/blobs, full image-bound versions; actual native clone, pre-ready fault/fresh restore24, normal core25 and SDK guard26 all pass exact nonredirect old/new bytes/cache/MIME. Already-deleted legacy42de0c7 URL remains historical limitation; no reconstruction claim. |
| G5-CANVAS-FIRSTUSE-01 | resolved; X10 passed; no product expansion | `clean_recovery_data.py board --workspace A|B`, documented fresh setup on new empty core/approved packages. Actual scoped creation/repeat-no-duplicate/get/save/replay/stale-conflict/foreign-ID and checkpoint/failure/recovery preservation pass; minimal-Canvas-fixture.json and qualification.json. Canvas code/appearance unchanged. |

Retained legacy SDK0 images preserve their old cache during restore and use the independent CLI until compatible publication. Current G5 uses SDK reader1. Native plugins remain fully trusted; no grant-metadata sandbox claim.

Current external integration gate is complete. G6 evidence was qualified on native24/117/current worker06/config9/pub11; normal core18/19 upgrades and current ID03 regressions preserve its data/authority on26/123. UI timeout, crash, navigation retirement and recovery now have real browser proof. Remaining required work is G7; do not replay G6 transitions as a substitute for the native-path/accessibility/performance/fresh-release audits.

## Last material outcomes

1. The exact versioned developer upgrade completed on the fresh rehearsal. It serves the changed Labels action and Canvas asset with the existing data and worker.
2. Retired the refused candidate image and ten completed containers. The fresh reference, original release reference and retained recovery storage remain available.
3. The in-app browser verified the modified examples. The §28 handoff and G7 decision record closure.

## Resume capsule

- Stock WebClient qualification is complete. The local kit is
  `.local/releases/stock-r1`, source `ad5ae338`, image `07cacdf4`.
  The five stock test projects and temporary tags are retired. Start new
  work with a fresh isolated target and the recorded kit procedure. The
  [stock handoff](../planning/stock_webclient_release.md#operator-handoff)
  links the exact acceptance evidence.
- Post-R1 shared foundation stress test complete. The two Docker deployments were retired after the successor browser checks. Start any new proof with fresh disposable targets. The private site journals and checkpoint receipts remain in `.local/foundation-stress/sites-02`, with build records in `.local/foundation-stress/builds`. Scoped baseline `a0b2f85f` and successor `20f71fb9` are retired. See the [stress checklist](../planning/shared_foundation_stress_test.md) and [lifecycle evidence](evidence/post-r1/shared-foundation/lifecycle.json).
- Local R1 is qualified. Read [the handoff](r1-handoff.md), [closure map](r1-release-checklist.md) and [gate decision](evidence/G7/20261105-section28-audit-01/gate-G7.json). The developer reference tab remains open at Canvas.
- Target is `.local/release-kit-rehearsal/private/reference/operator/target.json`, configuration7, core26/Shell13, image `sha256:fb022dc0ba37e5105d7143a60b79edefcb62f7eb7da112c5964fe05530cd2415`, inventory `sha256:274766b60952a67d87646a9b0c4ff30d03aca4df10a93d26f6f73b93aaf768cb`. Project `mp-r0-r1release0afebf4f833b` uses port18100 and catalog `.local/release-kit-rehearsal/private/catalog`. Worker4daa retained image87 and publication1.
- Operation `966c6bbf-37bd-412f-b1fe-c5d55ed7d207` completed. Its preservation and eight container retirements are recorded in `evidence/G7/20261105-core26-maintenance-01/`. All apply, browser and reproduction handles are terminal. Follow the recorded state for new work.
- Preserve prior recovery realms, selected dependency images and protected browser profiles. The existing kit r1-0.1.23 is retained as historical evidence.

## Acceptance ledger

Every spec ID is assigned an owning phase. `not_run` is not a pass. Exact commands/procedures and source/environment evidence are bound as the owning phase is implemented; G2 freezes contract fixtures.

Current G6 backend evidence for JOB-01..03, EVT-01..03 and SVC-01..05 is bound to native24/117/current executable hashes in `evidence/G6/20261102-current-backend-audit-01/coverage.json`. It preserves each prior test scope. SVC-02 actual UI is now qualified in `evidence/G6/20261102-headless-ui-01/qualification.json`; gate-G6 binds the combined proof.

| ID | Primary phase | Result | Required observation | Procedure / evidence |
| --- | --- | --- | --- | --- |
| FEAS-01 | A1/G1 | passed | Asymmetric workspace roles and record ownership are enforced through gateway and legacy model paths | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json`  Current identity1.2 installed20/nativeHTTP/two-worker requalification: evidence/G6/20261101-identity12-upgrade-01/qualification.json; retained unaffected historical evidence. |
| FEAS-02 | A1/G1 | passed | Two tabs, warmed caches and cross-worker revocation preserve workspace/role boundaries | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json`  Current identity1.2 installed20/nativeHTTP/two-worker requalification: evidence/G6/20261101-identity12-upgrade-01/qualification.json; retained unaffected historical evidence. |
| FEAS-03 | A1/G1 | passed | Minimal custom non-Owl page and native action coexist through the host adapter with correct routing/disposal | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FEAS-04 | A1/G1 | passed | Browser attribution and supported call chains cannot expand authenticated authority | `tools/g1_probe.py` and real-browser procedure; `evidence/G1/20261028t003753z/gate-G1.json` |
| FREEZE-01 | B/G2 | passed | All seven section 5.5 contract rows have versioned schema/type/example paths and digests, with no critical authority/lifecycle TODO | ADR0046/revision16 requalified affected source consumers:180host/65Linux tests plusTypeScript/freeze; exact solution/conflict/no-downgrade/retired-root/plugin-constraint/rehashed-review/independent-reconstruction boundaries. evidence/G2/20261103-python16/gate-G2.json and G7/20261103-python-maintenance-source-01/qualification.json. Prior installed path evidence retained; actual new dependency image/lifecycle/recovery/security remain G7. |
| FREEZE-02 | B/G2 | passed | Manifest, restricted version mapping, alias bindings and approval canonicalization fixtures pass | ADR0046/revision16 requalified affected source consumers:180host/65Linux tests plusTypeScript/freeze; exact solution/conflict/no-downgrade/retired-root/plugin-constraint/rehashed-review/independent-reconstruction boundaries. evidence/G2/20261103-python16/gate-G2.json and G7/20261103-python-maintenance-source-01/qualification.json. Prior installed path evidence retained; actual new dependency image/lifecycle/recovery/security remain G7. |
| FREEZE-03 | B/G2 | passed | Frozen workspace/identity/UI contracts agree with passing G1 behavior and documented patch surface | ADR0046/revision16 requalified affected source consumers:180host/65Linux tests plusTypeScript/freeze; exact solution/conflict/no-downgrade/retired-root/plugin-constraint/rehashed-review/independent-reconstruction boundaries. evidence/G2/20261103-python16/gate-G2.json and G7/20261103-python-maintenance-source-01/qualification.json. Prior installed path evidence retained; actual new dependency image/lifecycle/recovery/security remain G7. |
| FREEZE-04 | B/G2 | passed | Contract inventory maps owning phases, acceptance IDs, compatibility fixtures and change/invalidation rules | ADR0046/revision16 requalified affected source consumers:180host/65Linux tests plusTypeScript/freeze; exact solution/conflict/no-downgrade/retired-root/plugin-constraint/rehashed-review/independent-reconstruction boundaries. evidence/G2/20261103-python16/gate-G2.json and G7/20261103-python-maintenance-source-01/qualification.json. Prior installed path evidence retained; actual new dependency image/lifecycle/recovery/security remain G7. |
| BOOT-01 | A/G0 | passed | Empty volumes initialize and an administrator can log in | Candidate57027571/core21 initialized one recorded template0 DB and new config/data volume; native13-module registry, ORM-set nondefault admin, CSRF form login/native sessionuid2 and actualCSS/JS HTTP passed. PG16 process/image/sharednetwork retained, prior empty-PG bootstrap evidence unchanged. fresh-registry.json/fresh-http.json under G7/20261103-core21-dependencies-image-01; not full fresh platform installation or guarded production startup. Owned fixtures archived/retired, original17tables/worker exact. |
| BOOT-02 | A/G0 | passed | Dependency pins and build inputs reproduce the declared runtime inventory | Independent no-cache, network-disabled build reproduced selected imagefb02 inventory2747 and full dependencies. See 20261105-core26-repro-01/qualification.json. |
| BOOT-03 | A/G0 | passed | Explicit server-wide module choice works, including RPC omission if selected | Current30/135/image570 actual bounded requalification: Current selected base/web guarded workers and actual omitted legacy /jsonrpc404; same image policy. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| BOOT-04 | A/G0 | passed | No excluded ERP application is unexpectedly installed | Current30/135/image570 actual bounded requalification: Strict full native module state matches baseline except core version, installed native set17 remains exact allowed image graph; no ERP activation. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| BOOT-05 | E/G5 | passed | Unexpected addon search-path content cannot bypass release inventory policy | Current30/135/image570 actual bounded requalification: Actual current image rejects injected writable data-dir addon before native import; exact inventoried source/startup readers unchanged. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| BOOT-06 | E/G5 | passed | Worker startup does not silently migrate production state | Current30/135/image570 actual bounded requalification: Actual old31 image refused before native import/serving; current two guarded workers start without initialization/migration flags and schema stays exact. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| PKG-01 | E/G5 | passed | Manifest validation does not import plugin code | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-02 | E/G5 | passed | Traversal, symlinks, duplicate normalized paths and ZIP bombs are rejected | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-03 | E/G5 | passed | Digest mismatch and same-version/different-artifact conflict are rejected | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-04 | E/G5 | passed | Unsigned artifacts follow the actual configured trust policy | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| PKG-05 | E/G5 | passed | Unknown sensitive schema fields and contract majors fail safely | `tools/qualify_artifacts.py`; `evidence/G5/20261028T0508474407833Z/archive-catalog.json` (Windows/Linux/CLI) |
| DEP-01 | E/G5 | passed | Missing transitive dependency fails before any runtime mutation | Actual immutable-curated archive -> CLI matrix on Windows/Linux; exact test_missing_transitive_dependency_fails_before_any_mutation assertions plus unchanged catalog/trust bytes; `evidence/G5/20261029-resolution-matrix/dependency-acceptance.json` and resolution-source69/69. |
| DEP-02 | E/G5 | passed | Version conflict explains the incompatible constraints | Actual immutable-curated archive -> CLI matrix on Windows/Linux; exact test_version_conflict_explains_both_incompatible_constraints assertions plus unchanged catalog/trust bytes; `evidence/G5/20261029-resolution-matrix/dependency-acceptance.json` and resolution-source69/69. |
| DEP-03 | E/G5 | passed | Hard dependency cycle reports the cycle | Actual immutable-curated archive -> CLI matrix on Windows/Linux; exact test_cycle_reports_the_complete_hard_dependency_cycle assertions plus unchanged catalog/trust bytes; `evidence/G5/20261029-resolution-matrix/dependency-acceptance.json` and resolution-source69/69. |
| DEP-04 | E/G5 | passed | Python dependency conflict fails the native release plan | ADR0046/revision16 requalified affected source consumers:180host/65Linux tests plusTypeScript/freeze; exact solution/conflict/no-downgrade/retired-root/plugin-constraint/rehashed-review/independent-reconstruction boundaries. evidence/G2/20261103-python16/gate-G2.json and G7/20261103-python-maintenance-source-01/qualification.json. Prior installed path evidence retained; actual new dependency image/lifecycle/recovery/security remain G7. |
| DEP-05 | E/G5 | passed | Multiple service providers require an explicit binding | Actual immutable-curated archive -> CLI matrix on Windows/Linux; exact test_ambiguous_provider_rejects_then_explicit_binding_selects_only_one assertions plus unchanged catalog/trust bytes; `evidence/G5/20261029-resolution-matrix/dependency-acceptance.json` and resolution-source69/69. |
| DEP-06 | E/G5 | passed | Optional absent/incompatible integration does not break the base plugin | Actual immutable-curated archive -> CLI matrix on Windows/Linux; exact test_optional_absent_and_incompatible_leave_base_plan_valid assertions plus unchanged catalog/trust bytes; `evidence/G5/20261029-resolution-matrix/dependency-acceptance.json` and resolution-source69/69. |
| DEP-07 | E/G5 | passed | Stale plan is rejected | `evidence/G5/20261028T133700Z-release-reader-rollout/stale-app-plan-denied.json`; actual CLI re-observes deployment/catalog under alternate current policy, stable published identity but old app preimage denied before registration/mutation; current47host/47Linux fence tests132700Z. |
| DEP-08 | E/G5 | passed | Existing compatible locked versions are preserved unless update requested | ADR0046/revision16 requalified affected source consumers:180host/65Linux tests plusTypeScript/freeze; exact solution/conflict/no-downgrade/retired-root/plugin-constraint/rehashed-review/independent-reconstruction boundaries. evidence/G2/20261103-python16/gate-G2.json and G7/20261103-python-maintenance-source-01/qualification.json. Prior installed path evidence retained; actual new dependency image/lifecycle/recovery/security remain G7. |
| VER-01 | E/G5 | passed | Invalid package version forms are rejected and numeric package/native order agrees | `evidence/G5/20261029-resolution-matrix/qualification.json`: original native counterexample retained; source69/69/84freeze plus actual corrected0afd445c parser/order/applicability, exact approved compat1.1 core5 and retained state/files/authority pass. Public syntax/native spelling unchanged; VER-02 separate |
| VER-02 | E/G5 | passed | Adjacent and skipped-release migrations run applicable scripts; fresh install does not simulate an upgrade | `evidence/G5/20261029-migration-order-rollout-01/qualification.json`: actual adjacent/skipped/fresh/wide24scripts/4DBs, exact archive/script/schema/data witnesses; corrected current SDK70/70/84freeze and approved deployment6. Actual manager first-native/adjacent path retained; no crash/clean-restore claim |
| ORM-01 | D/G4 | passed | One packaged addon creates a model and another extends it | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ORM-02 | D/G4 | passed | Extension upgrade preserves original and extension-owned values as specified | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ORM-03 | D/G4 | passed | Duplicate field/contribution conflict is caught or deterministically rejected | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ORM-04 | D/G4 | passed | Export/import preserves supported data and rejects unsafe scope reassignment | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| ID-01 | C/G3 | passed | Two workspaces cannot read/write/create/delete each other's private records | Current30/135/image570 actual bounded requalification: Actual native63/HTTP31 and two-worker positive CRUD/private workspace isolation; captured originals preserved. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-02 | C/G3 | passed | Forged actor, database, company and workspace inputs do not grant access | Current30/135/image570 actual bounded requalification: Actual forged uid/su/database/company/private frames/workspace inputs denied in two-worker and native regressions. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-03 | C/G3 | passed | Export/search/attachments/autocomplete/batch/job paths enforce scope | Current30/135/image570 actual bounded requalification: Actual native export/import/binary/token/id-only/cache/job paths and current HTTP31/Canvas reference guards. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-04 | C/G3 | passed | Service principal has no implicit administrator authority | Current30/135/image570 actual bounded requalification: Actual service cookie/native technical identity cannot map to implicit administrator authority; current job guards. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-05 | C/G3 | passed | Revocation affects new and cached requests within the declared bound | Current30/135/image570 actual bounded requalification: Committed demotion/removal/restoration honored on first warmed/new requests on both distinct guarded workers; pending/cache read guard regressions. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-06 | C/G3 | passed | Workspace admin cannot install native code or run deployment operations | Current30/135/image570 actual bounded requalification: Workspace administrator actual manager API403 and native installation read/create AccessError; exact OS-approved operator path preserved. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-07 | C/G3 | passed | Direct legacy RPC/model calls cannot bypass scope, authorization or supported suspension gates | Current30/135/image570 actual bounded requalification: Current direct native RPC/model and suspension/cache guard checks; strict image inventory entrypoint. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-08 | C/G3 | passed | Two tabs on different workspaces and their caches/replies remain isolated |20261104-ui-qualification-01/identity-qualification.json: actual current14de/config4 sameAlice Aadmin/Bviewer two native Notes lists/forms. Actual B HTTP200native response held, disposal canceled it after return to A; both tabs retained own data/role. All17tables/fourruntimes exact/133valueprivacy0/no foreign requests/exceptions. Ownedbrowser21328 exited0/no profile process remains; initial hidden-tab/interception wait harness refusal retained. |
| ID-09 | C/G3 | passed | One user is editor in A and viewer in B without global-group privilege leakage, including direct RPC | Current30/135/image570 actual bounded requalification: Same actual Alice temporarily editorA/viewerB with native/API checks; global native groups and original authority restored exactly. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| ID-10 | C/G3 | passed | Cross-worker membership/policy changes invalidate scoped rules and cached authorization within the declared bounds | Current30/135/image570 actual bounded requalification: Both actual guarded worker container IDs warm reads, then deny after committed demotion/revocation; source actor scope counters remain monotonic. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| TEN-01 | E/G5 | passed | Two test databases do not leak data or registry context | Actual native registries in SAME process/both importorders/64concurrentreads; Labels field only in installed DB despite shared import, colliding actor/workspace/record IDs keep own data/config/caches/CAS transactions; foreign Scope and site frames denied. Two default workers HTTP DBauth/header403/query/session-cookie separation; exact business/schema afterward. tenant-isolation-01/qualification.json. |
| TEN-02 | E/G5 | passed | Incompatible native versions sharing one runtime are rejected | Genuine installed Labels0.2.1 main28snapshot copied independently vs0.2.2 runtime/A: complete3DBobserver/proposal rejects verifiedartifact mismatch; omittedDBinventory denied. Immutable default startup refuses originalinventory and genuine nativeversions after isolated temporarypin substitution (restored), before native imports/no fabricated versionrows; tenant-isolation-01/compatibility-qualification.json. |
| LIFE-01 | E/G5 | passed | Feature suspension retains native schema/data and blocks documented entry points | `evidence/G5/20261029-lifecycle-01/qualification.json`: actual approved scoped cascade, retained native schema/4Notes/2boards/labels; page/navigation/context/command/slot/gateway/native denial, unaffected Research, two-worker extension denials and exact restoration. G6 must requalify dispatch/drain when jobs/events are added. |
| LIFE-02 | E/G5 | passed | UI/docs do not claim native overrides/imports are unloaded | `evidence/G5/20261029-lifecycle-01/qualification.json`: actual operator preview and dimensions explicitly retain native registration/data/imports/overrides; docs/operations.md same terminology; same schema/image/worker and unaffected native Labels in Research prove no unload claim. |
| LIFE-03 | E/G5 | passed | Required-provider suspension/removal shows the dependent closure | Actual core23 populated reference profile: independent and installed manager required Notesprovider preview4nativeplugins/8scopes includingCanvas, cascadefalse400; oneunrequesteddraft notapproved/executed. ActualLabels2scopeuninstall. G7/20261104-native-uninstall-recovery-01/required-provider-preview.json andqualification.json; priorreal suspension/native closure evidence retained. |
| LIFE-04 | E/G5 | passed | Native uninstall requires explicit destructive approval and backup | Installed manager Labels2scope request857c7072/hashd50253 through same independent executor. Missing destructiveACK CLIrefused/journalexact, exact approval/coordinated DB+filestore checkpoint then genuine upstreamnativeuninstall/columnloss. Exactcloseddispatch snapshot preservedacrosscommit. Controlledfault then actualNEWDBrestore/separateresume/currentauth/files. G7/20261104-native-uninstall-recovery-01/qualification.json; historical normal native uninstall/reinstall remains unchanged-source-bound. |
| LIFE-05 | E/G5 | passed | Upgrade permission expansion requires reapproval | Actual manager Labels0.2.1->0.2.2 test-fixture upgrade shows both workspace targets/exact2newnotes.write grants; old hash and missing-permission-ack refused before exact acknowledged independent approval/SAME executor. Native Labels-only upgrade/checkpoint/oldgrants/data/schema/IDs/nativeOdoo/APIs/assets/client/protected-sites pass: `evidence/G5/20261029-permission-upgrade-01/qualification.json`. Default product privileges unchanged. |
| LIFE-06 | E/G5 | passed | Artifact removal is blocked while a site still needs it | Actual installed manager+CLI refusal in artifact-removal-inuse-01; separately approved native uninstall then exact7file source-only removal8→9 through SAME executor. Full schema/business/history/bindings exact, newworker/clientepoch, retained catalog/images/checkpoint/assets and nativeOdoo/Notes/Canvas proof: `evidence/G5/20261029-source-removal-live-01/qualification.json`. Complete sharing inventory source/runtime guard retained; twoDB compatibility remains TEN-01/02. |
| MIG-01 | E/G5 | passed | Failure before mutation preserves the previous working release | Current core22 actual drain/fence/checkpoint thencontrolledbefore_mutationfailure; same baseconfig5/imageae8/publication/38files/businessrows preserved. Exact separate unchangedresume reusesguardedcontainer, onlyonecompletedjob claim/dispatchfenceupdates15→18control, sameoutcomes. Wronghashdenied/revokedplanreplayrefused/nativeviews+HTTP pass;13helpersretired. G7/20261104-premutation-recovery-01/qualification.json. No DBrestore/OPS02/MIG09claim. |
| MIG-02 | E/G5 | passed | Failure after an internal commit enters recovery_required, not false rollback success | Actual exact old31→new570/core20→21/19distribution dependency maintenance: target immutable native child exit0 and actual SQL core21 commit, host-only injected failure before metadata/traffic. Durable recovery_required/mutation_started true, no false rollback, paused checkpoint/dispatch and closed ingress. See evidence/G7/20261103-fresh-release-01/dependency-recovery/qualification-corrected.json; native-only terminal-job scope, no unknown remote-effect claim. |
| MIG-03 | E/G5 | passed | Executor crash is reconciled before a retry | Actual PID14540 OS-terminated after native child exit0/LabelsDDL commit; durable journal remains running/mutation_started/noPythoncleanup, next apply records lost-owner recovery_required BEFORE stopped-app/stale-state preflight and never replays native work. Exact freshDB restore/resume15, fullbusiness/schema/grants/files, oldclient/assets/native/API, retiredplan/recoverydecision denials and protected sites pass;6Windows/70Linux/87freeze: `evidence/G5/20261029-executor-crash-01/qualification.json`. Initial launcher failure excluded. |
| MIG-04 | E/G5 | passed | Concurrent operations serialize or reject safely | Four real-process topology cases Windows4/Linux24/87freeze; live approved native owner PID30840 holds locks after child commit while duplicate-owner/native/feature CLI contenders all rejectbusy/exit2, journals unchanged/no stages or children. Owner completes16; competitors stale/refused/revoked, completed replay exact/no repeat. Separately approved reinstall17 preserves full reference data/schema/grant permissions/publicbindings; native/API/assets/client/protected audit passes: `evidence/G5/20261029-concurrency-01/qualification.json`. |
| MIG-05 | E/G5 | passed | Reusing operation ID does not repeat migrations | Current normal core25 and SDK26 completed replay return identical saved status without native/asset child: `evidence/G5/20261028-asset-retention-normal-01/completed-replay.json`, `evidence/G5/20261028-asset-retention-binding-01/completed-replay.json`; current source identity in asset-retention-requalification. Historical plugin migration replay retained. |
| MIG-06 | E/G5 | passed | Restore recreates DB, filestore and previous release consistently | Ordinary independently reviewed fresh DB restore plus separate reviewed resume: actual old31/core20/previous Python lock/inventory/native modules/schema/38files and fourNotes/minimalCanvas/completed original-actor job preserved. Current BobB revocation/native credentials overlaid exactly; old approval revoked; actual native views/attachment read and original working site17table/config hashes unchanged. See evidence/G7/20261103-fresh-release-01/dependency-recovery/qualification-corrected.json; native-only terminal-job scope, no unknown remote-effect claim. |
| MIG-07 | E/G5 | passed | Destructive fixture uninstall proves the real deletion semantics | Baseline G0 retained; R1 actual independently approved upstream uninstall deletes x_notes_labels with2non-null values and records schema/data effects, preserving allothercolumns/constraints/4Notes/2boards/native survivors. `evidence/G5/20261029-native-uninstall-01/qualification.json`, native-effects.json and survivor-http-assets.json. Scoped current-version reinstall reinitializes schema, not deleted values; `evidence/G5/20261029-native-reinstall-01/reinstall-A/qualification.json`. |
| MIG-08 | E/G5 | passed | Old workers/jobs do not serve incompatible new schema | Current30/135/image570 actual bounded requalification: Actual previous image refuses current release inventory; old33job claims advance epoch, all previous outcomes/inputs/attempts preserved, readiness/drain generation132→135. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| MIG-09 | E/G5 | passed | Restored queues remain fenced until externally completed effects are reconciled | Actual current typed outbound-stateless reference checkpoint/fault/freshrestore keeps queues/control fenced throughclosedverification and independent exactresume; old completedresult/history preservedwithdeclared epochs/currentpub1workerunchanged; wronghashes/refusedplan/oldsessionpins and ordinaryjob afterresume. G7/20261104-native-uninstall-recovery-01/qualification.json. Existingactualnon-idempotent unknown-effect refusal/JOB03 retained at unchangedsource; no genericremoteundo. |
| API-01 | C/G3 | passed | Gateway exposes only declared methods and validates schemas | Current30/135/image570 actual bounded requalification: Actual declared methods work, undeclared sudo404, forbidden authority field400; native registered bound chain/DTO validation regressions. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| API-02 | C/G3 | passed | Idempotency repeats return the same outcome; changed input conflicts | Current30/135/image570 actual bounded requalification: Actual remote analyze same-key response replay returns identical outcome; changed same-key input returns409 without extra job. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| API-03 | C/G3 | passed | Deadline/cancellation errors do not falsely imply rollback | Current core22 real HTTP and unchanged SDK json/callService/release fence in Node: pre-aborted CANCELLED/not_started makes zero fetches; cancellation triggered only after server postcommit marker+SQL effect returns CANCELLED/unknown and same-key retry savedDTO. Deadline0 returns504/not_started/no effect. Exact source bound to immutableimage; backend/SDK proof, no rendered-browser/ID08 claim. request-faults-01/qualification.json. |
| API-04 | C/G3 | passed | Private ORM objects and stack traces do not cross public boundary | Current30/135/image570 actual bounded requalification: Current public validation/not-found/forbidden responses, normalized native errors and typed DTO checks; no debug/traceback in tested wire denial. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| API-05 | C/G3 | passed | Concurrent same-key mutations and a crash before response do not duplicate the reference database effect | Current core22 eight concurrent same-key creates produce identicalDTO/oneeffect; bounded existing faultaddon postcommit exit86/lostHTTP502, same-key retry twice returnssavedresult. Three exact durableoutcome rows also cover committed cancellation; owned Notesdeleted, sixexpectedoutboxevents retained andold17tables/primary/worker exact. request-faults-01/qualification.json/source-and-log-attestation.json. Not arbitrary external-effect exactly-once. |
| API-06 | C/G3 | passed | Consumers use named bindings to call v1 and v2 concurrently; missing/mismatched bindings never select latest | Actual fresh570 simultaneous independently authenticated v1/v2 named DTO reads, Labels/Canvas composition; wrong-v1 binding400 VALIDATION_FAILED, missingbinding503 DEPENDENCY_UNAVAILABLE, no latest fallback/all17tables exact. fresh-target21-01/qualification.json and fresh-smoke/binding-concurrent.json; unchanged qualified resolver/provider-negative source retained. |
| API-07 | C/G3 | passed | Forged browser plugin attribution and supported provider call chains cannot acquire broader actor/token/grant authority | Current core22 five installed rollback tests prove actor/workspace/site/non-sudo child model, original write actor, revoked integration grant denial, viewer provider denial and frame metadata refusal; five actual HTTP/legacy RPC attribution/private-context controls pass.17tables/worker exact. G7/20261104-provider-authority-01/qualification.json. Trusted native code remains outside sandbox claims. |
| EVT-01 | F/G6 | passed | Rolled-back writes produce no externally delivered success event | evidence/G6/20261101-host-events-01/qualification.json; actual current native rollback/bus/foreign/pending-feature checks + actual deployed host/WebSocket/replay/disposal/viewer/nativeOdoo; retained exact-boundary14native/9HTTP/13JS/7source-browser and current history/native-consumer duplicate evidence. |
| EVT-02 | F/G6 | passed | Duplicate delivery does not duplicate a deduplicated consumer effect | evidence/G6/20261101-host-events-01/qualification.json; actual current native rollback/bus/foreign/pending-feature checks + actual deployed host/WebSocket/replay/disposal/viewer/nativeOdoo; retained exact-boundary14native/9HTTP/13JS/7source-browser and current history/native-consumer duplicate evidence. |
| EVT-03 | F/G6 | passed | Unauthorized subscription or cross-workspace payload access fails | evidence/G6/20261101-host-events-01/qualification.json; actual current native rollback/bus/foreign/pending-feature checks + actual deployed host/WebSocket/replay/disposal/viewer/nativeOdoo; retained exact-boundary14native/9HTTP/13JS/7source-browser and current history/native-consumer duplicate evidence. |
| JOB-01 | F/G6 | passed | Reference idempotent DB job survives lease reclaim without duplicate effect; obsolete claims cannot commit | Current qualification core12-runner-01/qualification.json: retained actual current-line SIGKILL137 after committed claim, real lease expiry/normal CLI reclaim attempt2, exactly one originalUID6 revision increment and stale original claim refusal; exact source/AST boundaries to unchanged1.12 claim/prepare/finalization/normal compute paths. Current normal CLI/installed runner and12 native authority cases pass. External non-idempotent uncertainty remains JOB03/F-01e2. |
| JOB-02 | F/G6 | passed | Revoked/suspended actor/plugin is checked before dispatch | Current core1.12:12 installed rollback cases cover principal/user/member/feature/binding/installation/grant before claim, current role/feature/binding/installation before apply, live/revoked/expired scoped technical credential and no technical admin, revision CAS/status actor/workspace/current authority. Retained actual committed demotion blocks write with exact unchanged source paths.7 current actual error/cancel runner cases +normal CLI pass, no runner/auth/finalization substitution; core12-runner-01/qualification.json. Full external dispatch/lifecycle still F-01c/d/f. | Actual external addition: real original-actor membership revocation before ordinary dispatch/after worker result rejectsFORBIDDEN and real revision race rejectsCONFLICT/no stale result, role01/revision01; other authority-matrix integration review remains.
| JOB-03 | F/G6 | passed | Non-idempotent uncertain outcomes are reported for reconciliation | Actual isolated owned DB/native test definition through installed authorization/JobDefinition/job_runner, separate public-only recipient commits/fsyncs non-idempotent counter1 then withholds response; exact native SIGKILL137 after committed effect_started, real30slease expiry within180sdeadline/max3budget yields native schema-valid outcome_unknown/LEASE_EXPIRED/attempt1/no result. Two subsequent runner passes idle/counter1, independent READ COMMITTED fence/enable rejects uncertain state. Receipts/native diagnostic archived and allfixturecontainers/DB/configvolume/dumps removed; live17tables/worker exact. evidence/G6/20261102-job03-01/qualification.json. No automatic reconciliation/remote rollback/exactly-once claim. |
| UI-01 | C/G3 | passed | Standard CRUD plugin uses the shared shell and components | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| UI-02 | D/G4 | passed | Custom non-Owl page works without a new core patch | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| UI-03 | D/G4 | passed | Direct links, refresh and back/forward work | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| UI-04 | D/G4 | passed | Unauthorized/disabled pages and service calls fail even if URL is known | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| UI-05 | D/G4 | passed | Repeated mount/dispose does not accumulate listeners or stale updates | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| UI-06 | D/G4 | passed | Failed plugin page offers recovery and does not trap the user | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| UI-07 | D/G4 | passed | Native release mismatch triggers controlled reload | Actual static deployment/restore21 and changed-byte normal22 verified saved drafts, cancelled native dialog, explicit reload and updated assets without a loop. See `evidence/G5/20261028-client-refresh-static-normal-01/browser/browser-qualification.json`. Section 19 asset retention is separately qualified in `evidence/G5/20261028-asset-retention-requalification/requalification.json`. |
| UI-08 | D/G4 | passed | Generic SDK does not require company/partner/session internals | `evidence/G4/20261028t033154z/gate-G4.json` and linked real procedures |
| UI-09 | C/G3 | passed | Standard shell passes keyboard, contrast, zoom and RTL checks | Installed core26 verification includes locale, Windows accessibility events, named dialogs, rendered glyph contrast, 100%/200% zoom, 320 CSS pixel reflow and Canvas keyboard exit. See 20261105-core26-maintenance-01/installed-observations.json. |
| UI-10 | D/G4 | passed | Unsaved-work and expired-session flows preserve a safe recovery path | Exacta34c retained clone/current transport: `evidence/G5/20261028-client-release-clone-01/browser-qualification.json`, procedure/screenshots/precise drafts; data/filestore `evidence/G5/20261028-client-release-clone-postbrowser/postbrowser.json`. Historical evidence retained. |
| SVC-01 | F/G6 | passed | Reference worker runs without Odoo import or database credentials | Current actual worker dependency transition: Actual active immutable87 image: no Odoo import,13 distributions and13 copied source/provenance files exact. Sole RO public config mount/image-default environment; no DB/issuer/operator/socket mounts. Actual original-user job completes once. See evidence/G7/20261103-worker-security-transition-01/qualification.json; broader recovery/security limits explicit. |
| SVC-02 | F/G6 | passed | Worker timeout/crash leaves host healthy and feature degraded | headless-ui-01/qualification.json and gate-G6.json: actual isolated headless Edge, real paused-worker timeout and SIGKILL137 crash, Odoo warning, usable native list/form, post-navigation result suppressed, explicit recovered results; old30jobs/30Notes/other16tables exact under6new terminal test jobs. |
| SVC-03 | F/G6 | passed | Scoped token cannot change workspace/site by altering payload | Current actual worker dependency transition: Actual current valid RS256 token plus altered payload workspace/site returns401; independently foreign signed workspace also403. Normal configured scope works and host original actor job is separately checked. See evidence/G7/20261103-worker-security-transition-01/qualification.json; broader recovery/security limits explicit. |
| SVC-04 | F/G6 | passed | Metadata register/suspend/unregister does not create a native addon, launch/stop a runtime or erase remote data | Qualified R1 stateless reference: actual metadata unregister/core15 source carryforward4files, corrected core16 stopped-worker re-register/separate start; current18/94 installed connector required Notes refusal/closure and exact independently reviewed optional Stats suspend/enable, real job PLUGIN_SUSPENDED then success, native/schema/files/worker unchanged,20terminalcontainers retired. evidence/G6/20261102-connector-lifecycle-01/qualification.json. Unknown external effects/recovery/changed-image and UI remain separate. |
| SVC-05 | F/G6 | passed | Operator-approved endpoint/image generation and audience/scoped credentials are verified; artifact metadata cannot override them | Current actual worker dependency transition: Actual reviewed revocation12/newendpoint11/publication13; unapproved metadata image400, old/third image and unreviewed default mismatch refused, exact private transition then ordinary metadata0.1.3 upgrade/enable. Current token200, staleendpoint403/wrongaudience401/retiredkey401 and retiredissuer refusal. Strict default profile restored. See evidence/G7/20261103-worker-security-transition-01/qualification.json; broader recovery/security limits explicit. |
| SEC-01 | E/G5 | passed | Plugin metadata cannot execute script in manager UI | Current411101a9 actual inert publisher markup remains literal/0injectedDOMelements in trust/details; dynamic manager text uses native Owl escaping, no rawHTML/eval/dynamicURL sinks. `evidence/G5/20261029-manager-inspection-http-01/acceptance.json`, browser proof and postbrowser source audit. Trusted plugin JavaScript is a separate boundary. |
| SEC-02 | E/G5 | passed | CSRF/CORS/session/proxy/host defaults match the threat model | Current570/dece6f actual dev+production HTTP/CSRF/origin/cookies/hosts/proxy, preflight/currentmountedconfig/rotatedaccounts, TLS1.2/1.3/1.1refusal,396rate requests/nativeOdoo errorreuse, uploadlimits/TLSWS101/foreignOrigin403 andsourcepreservation. evidence/G7/20261104-production-profile-01/qualification.json; globalSEC03 separate. |
| SEC-03 | E/G5 | passed | Secrets/private keys are absent from public assets, logs and packages | Retains current layer/source/assets/log proof at release-privacy-delta-01/qualification.json. New complete kit-qualified.json:133knownvalues/101736main+36532nestedinstances/79290uniquecontents/54196exactGitfiles/6288priorhistory new10/5276olderimage two-value extension,8exact vendorstaticreviews/0issuedsecrets/0unreviewed.142currentreference diagnostics separately qualified; prior explicit secret transports remain protected/excluded. Finite encoding/archive scope, authenticated dynamic session transport/private controls excluded; browsernetwork is separate. |
| SEC-04 | E/G5 | passed | Production profile disables database manager/listing and dev endpoints | Current570/dece6f real production preflight comparesmountedconfig/internalnonrootreadonly app/currentrelease/frozencanonicalURL/disabledinitiallogins; database/debug/test/excludedRPC refusals, canonicalHTTPS/loopbackproxy-onlyports andcurrentCompose exactselectedproxy/no build. evidence/G7/20261104-production-profile-01/qualification.json; localfixtureonly/no externalproductiondeployment. |
| SEC-05 | E/G5 | passed | Native trust warning accurately describes full process authority | R1 review of actual details/extension/plan warnings: native/same-origin full trust, grants only supported APIs, native host authority retained, suspension does not unload overrides. `evidence/G5/20261029-manager-inspection-http-01/acceptance.json`, rendered details and operations runbook; no sandbox claim. |
| SEC-06 | E/G5 | passed | A fabricated app-queue approval cannot authorize privileged executor actions | Current-source actual manager native request/independent import/forged approved app mirror denied with OS store awaiting and unchanged base, then exact local approval/apply28; `evidence/G5/20261028-manager-install-01/acceptance.json`, forged-app-approval-denied.json and browser/browser-proof.json. Historical feature case retained. |
| SEC-07 | E/G5 | passed | Exact-hash approvals expire/revoke correctly; stale targets/policy/authority and cross-operation replay are rejected | Current30/135/image570 actual bounded requalification: Same exact independently reconstructed new Python diff approved/applied; current8new source cases cover rehashed review omission/forgery. Host authority implementation exactly matches180host/65Linux qualified revision16, retaining expiry/revoke/stale/replay vectors; no claim all old runtime cases rerun. See G7/20261103-core21-maintenance-01/qualification.json for exact evidence/retention limits. |
| SEC-08 | E/G5 | passed | Application OS/container identity cannot write/read privileged approval/operator/secret stores beyond the redacted status channel | Current core22 isolation qualification:32actual appnamespace denials across current+preserved apps,8kernel foreign-UID denials/forged-approval refusal on rwfixture,3494Windows ACL/28catalog integrity records,9Windows+9Linux tests. Existing positive redacted mirror exact source-bound to current core22; current CLI-ID404/ordinary403/anonymous401.17tables/worker exact,4containers+1volume retired. G7/20261104-operator-isolation-01/qualification.json. |
| OPS-01 | E/G5 | passed | Operator can inspect journal when main app cannot boot | `evidence/G5/20261028T135000Z-pinned-cache-restore/independent-cli-no-app.json`; actual independent CLI shows recovery journal with no running app process, no registry/app dependency; actual incompatible old-code guard refusal124000Z also retained. |
| OPS-02 | E/G5 | passed | Documented restore works in a clean disposable environment | Current core23 freshly restored NEW namedDB after actualLabels nativecommitfault, retainedfailedDB/authority, alignedimage/catalog/checkpoint,38files/nativeschema-values/17tables verified whileclosed; ordinary independent exactCLI restore/separate resume with negativehash tests, nativeHTTP/session/plan fences and ordinaryAlice job. docs/recovery-rehearsal.md current procedure andG7/20261104-native-uninstall-recovery-01/qualification.json. Final releasekit/provenance remains G7. |
| OPS-03 | E/G5 | passed | Build/source/license provenance is preserved | Core26 reproduction, actual image provenance, exact license notices, verified refreshed source and expanded artifact/privacy proof. See 20261105-core26-release-kit-01/provenance.json, source-refresh.json and privacy-delta-final.json. |
| ISO-01 | H/R2 | excluded_R2 | Hostile service cannot access host mounts, DB credentials or privileged sockets | not_run; procedure to be bound in owning phase |
| ISO-02 | H/R2 | excluded_R2 | Resource and network controls behave under abuse | not_run; procedure to be bound in owning phase |
| ISO-03 | H/R2 | excluded_R2 | Frontend origin/source/nonce/replay/stale-frame tests pass | not_run; procedure to be bound in owning phase |
| ISO-04 | H/R2 | excluded_R2 | Host cookies and DOM are unavailable to sandboxed frontend | not_run; procedure to be bound in owning phase |
| ISO-05 | H/R2 | excluded_R2 | Revocation and teardown invalidate runtime/bridge authority | not_run; procedure to be bound in owning phase |
