# Application capabilities and deliberate boundaries

The core exists to enable useful independent applications. A limitation requires
a reason and an owner; an untested path is not labelled impossible. Application
acceptance includes actual visible interactions as well as data, authorization
and lifecycle behavior. Source checks and backend-only results cannot establish
that a screen is useful or usable.

The [product/platform roadmap](product-platform-roadmap.md) now sequences the
next work. Its [research](roadmap-research.md) distinguishes source findings from
installed evidence. No future capability below is accepted merely by planning it.

| Requirement | Current state | Reason / next evidence |
| --- | --- | --- |
| Coherent task/customer/reminder experience and safe drafts | PP-01 accepted for exact Workboard0.2.5/Customer Work0.1.4/Partners0.1.0 on core0.2.1 | Actual create/link/discuss/conflict/reconcile/schedule-cancel/reload/keyboard-complete-reopen and viewer/optional-denial checks pass. Compact context and visible navigation improve the screens. Real review caught menu ownership and unsafe/missing keep-draft choices; both were corrected through ordinary app code and normal upgrades. Core unchanged; bounded agent desktop/narrow checks, not broad accessibility/mobile certification. |
| Upcoming reminder agenda | Application choice; not implemented by the delivered-notice inbox | Current task details show its scheduled/cancelled occurrence; My reminders lists delivered private notices. Owner=Workboard. If a useful upcoming/day agenda is needed, add a bounded current-actor app read service and UI; this is not a fundamental core prohibition or a reason to claim scheduled work was delivered. |
| Workspace-scoped binary upload/download and previews | Demonstrated bounded PP-02 workflow, current authority and real quota; remaining integration/recovery unproven | Core0.2.2/Docs0.1.2 actual useful workflow, current viewer/member/feature/actor loss and known-loss cache clearing, full-size5MiB and two-writer100MiB quota pass. Old token/attachment paths stay closed. Format breadth, optional links, coordinated byte restore and unavailable-copy repair remain before phase acceptance. |
| File format, size, preview and storage bounds | Intentional initial Documents app policy, not universal platform restrictions | App allows content-checked UTF8 TXT/Markdown/PDF/PNG/JPEG,5MiB revisions/100MiB raw per workspace/200files including trash/20versions. Only escaped text<=256KiB previews; others download-only/unscanned. No parser/antivirus safety claim, HTML/SVG/Office/archive execution, public links or sync. Core transport ceiling8MiB. Owner=Documents for allowlist/quotas/retention; revisit against useful demand and measured memory/storage/parser/recovery proof. |
| Clean builds with an unchanged Python source lock | Exact image support; bitwise dependency reproducibility unproven | PP-02 M preserves its current app environment; a new policy path invalidated builder dependency RUN cache and D rebuilt same-version psycopg2/python-ldap with different .so/distribution digests. Core maintenance guard remains strict; any D install must bind/review those changes through normal plugin planning. Owner=build/operator workflow (PP-04). No fabricated lock edit, digest relabel or unchanged-environment claim. |
| App-owned fine-grained sharing after checkpoint restore | Explicit checkpoint boundary, not a universal current-ACL overlay | AP-LIM-015: current native authentication/platform revocations reconcile, but app business ACL rows restore from checkpoint. Initial document app is workspace-shared; Codex must design and qualify newer app-ACL revocation handling before promising per-folder/person privacy across recovery. |
| Own models, views, app assets, service schemas and events without a domain branch in core | Demonstrated by independent Partners and the bounded Workboard workflow on provisional0.2.1 | Keep business code and presentation in independently packaged apps. Workboard adds16 app-owned inventory entries and preserves all3682 standalone-core inventory files. Its event delivery is not newly qualified. Record any genuine general gap in the core-change ledger before changing core. |
| Stock forms, native lists, workspace selection and revision-aware saves | Demonstrated in a real browser | Apps still own business concurrency semantics; repeated form-adapter work is a possible general usability improvement, not a reason to drop conflict protection. |
| Rich app-owned boards, configurable workflow stages and contextual task panels | Workboard0.1.1 desktop workflow demonstrated on core0.2.1 | Actual browser create/comment/custom stage, drag plus reload, select alternative, search and archive/restore passed. Visual review caught a malformed draggable attribute in0.1.0; app-only0.1.1 fixed it through normal image/approval/upgrade. No mandatory reference shell or core branch. |
| Model extension and app-to-app data links | Demonstrated by separate Customer Work integration between independent Workboard and unchanged Partners | The optional app stores owned UUID links and calls declared bound services under the original actor. Live customer renames appear without copied names. Stale links, foreign references and viewer writes refuse. Revoking its customer-read grant clears the customer panel while the task and discussion remain usable. Core contains no customer/task branch. |
| User-defined stages | Application responsibility, not an engine limitation | A three-state demo is not a permanent restriction. The app must define completion semantics and test referenced-stage changes, history and reminders. |
| Assignment to current team members | Workboard implements a bounded app-owned read-only directory; installed assignment and foreign-member refusal demonstrated | The existing membership-management API remains admin-only. Workboard uses trusted native fixed scoped reads, not sudo or relaxed management access. A reusable read-only directory service is a possible general improvement if other apps need the same policy; it is not currently a ready-made frontend API. No credentials or inactive/foreign members are exposed. |
| Personal-private tasks or per-list secrecy | Not implemented by Workboard; application policy choice | Current tasks are workspace-visible team work. My work filters assignment and does not promise privacy. Implement and test a separate ownership/sharing policy before adding a private mode; do not disguise missing policy as a platform impossibility. |
| Due date/time wire representation | Intentional existing UTC-Z protocol; local-time browser entry demonstrated | The UI converts local input to canonical UTC and displays it in the current time zone. An initial test offset timestamp was correctly rejected before task creation; correcting the test required no core/app change. This does not establish recurring reminders or time-zone travel behavior. |
| Durable personal reminders | Installed delivery, idempotent scheduling, reschedule/cancel and current-authority denial demonstrated | Existing managed job lanes deliver one private inbox notice. Changed/completed/archived tasks refuse effects. Actual prepare/compute followed by actor role loss denies fresh finish with no notice; role restoration is verified. This does not qualify event-consumer effects, external email/push or team-recipient reminders. |
| Honest background status | Repairable app defect found and fixed | Core correctly dead-lettered a forbidden job, but the app initially displayed Scheduled from its own stale row. The successor derives status through the existing current-authorized job API and renders failure/unavailability rather than inventing delivery. A normal immutable-image upgrade preserves populated business tables. |
| Reminder ownership and invalidation | Intentional bounded application policy | A reminder belongs to the scheduling human, not the assignee or workspace. Scheduling and acknowledgement require editor/admin under the existing workspace mutation contract; a viewer may read current own notices. Any task revision invalidates the occurrence. Finer relevance checks, recurrence and team recipients need explicit app policy and evidence. |
| Optional leaf app uninstall, source removal and same-archive return | Demonstrated for Customer Work0.1.3 with Workboard0.2.2 and Partners0.1.0 | Normal destructive native/metadata uninstall deletes only the owned link table; task/reminder/customer data remain. Exact11file subtraction leaves10addons/2archives,11audited final layers. Normal same-archive reinstall renews grants explicitly and starts an empty owned table. This does not qualify full Workboard/cascade removal. |
| Populated recovery with pending personal work | Demonstrated in a real fresh database and browser | A held unattempted reminder survives the coordinated fault/checkpoint/restore; newer membership revocation remains effective. Separate resume plus explicit reschedule delivers once. Mid-compute uncertain/external effects are not newly qualified. |
| Reusing request keys across app removal/reinstall | Intentionally refused when the binding incarnation changed | An unexpired old key returns409 rather than resurrect a deleted-record receipt. After confirming the new table is empty and current authority permits it, an explicit new intent uses a fresh key and deduplicates normally. Never automatically rotate keys after an ambiguous mutation. |
| Source removal with additional databases | Intentional completeness gate | Every non-template DB must match the protected observed site configuration plus empty maintenance DB. A retained failed test DB blocked removal; it was archived and deliberately retired, not hidden or bypassed. Unknown/foreign databases must remain untouched. Return with a fully supported complete sharing profile or explicit exact owned-test retirement. |
| Undo a completed native uninstall from its checkpoint | Not a supported current operator workflow; bounded capability required by PP-04 | The qualified fresh-restore path requires an unresolved failed operation and independent current-authority review. Reinstall does not restore deleted app rows. Data-preserving suspension is different. Codex must establish a reviewed fresh-target/effect/authority model for the exact qualified native cohort before implementing and promising completed-checkpoint restore; no arbitrary in-place rollback. |
| Arbitrary model changes and populated migrations | Explicit migrations supported; not universally qualified | A real application migration must preserve useful data and recover under current authority. Existence of a migration declaration earns no acceptance. |
| Trusted native Python and same-origin frontend extensions | Intentional R1 trust boundary | Native code shares the process and can execute privileged logic. Permissions and manifests do not sandbox hostile code. Isolation is a separate R2 requirement. |
| Hot-unloading native code or independent native versions in one shared process | Intentionally unsupported | Python imports/process hooks and native registry/schema lifecycles require an immutable image and controlled transition. Feature suspension, database uninstall and source removal are distinct operations. |
| Arbitrary third-party addon compatibility, stable ABI and LTS | No promise in provisional0.2.1 | Support covers exact qualified combinations. This owned fork preserves its supported contracts and data/recovery guarantees, not external upstream compatibility for its own sake. |
| Viewer empty states and responsive interaction | Role-specific copy and bounded363px customer/task/reminder/inbox interactions demonstrated; full mobile remains open | Role-specific board/inbox empty-state copy was repaired in the pressure successor; mobile remains unqualified. The first override did not resize the existing tab; a later real363px tab allowed bounded interaction checks. Drawer scrolling, keep-draft, schedule/cancel and inbox acknowledgement worked. Device coverage, touch ergonomics, keyboard/screen-reader breadth and full mobile workflow remain unqualified. |

The [bounded work-application evidence](evidence/G7/20261111-work-application-01/qualification.json)
records source, installed, visual and unproven scopes separately. This is a
useful team-work first slice, not full customer/project/reminder product parity.

For each next application, retain a short decision record containing the user
journey, observed interaction, capability status, rationale, tradeoff, repair
owner and next qualification. Use these statuses: **demonstrated**, **intentional
boundary**, **gap to repair**, **unproven**, and **application choice**. Temporary
scope choices must have a reason and a return condition; they are not platform
limitations by default.

Visual reviews should follow a realistic create/find/edit/complete/reopen flow,
check clear ownership and status, visible loading/error feedback, keyboard
alternatives to dragging, discoverable actions, retained drafts and useful
context. Reference products can inform these requirements without embedding
their private code, branding or business model in core.

## Customer-work pressure findings (11November2026)

The useful journey is customer kickoff: find a customer, link the independent task,
discuss the handoff, receive a private reminder, and return to the current task.
Aurora informed the contextual-work comparison; no Aurora business code or model
was added to core. The optional integration uses the Workboard-owned trusted
component slot; it is not a new generic core registry or sandbox.

Actual visual review also caught a navigation failure: ad hoc query parameters
were discarded by the native action router, and following a customer link lost
an unsent task comment. The app successors use existing declared client-action
paths, action parameters and action-state persistence, with a separate customer
tab and a comment navigation guard. Actual final UI qualification passed: customer/task reload, retained drafts, honest
failed status, schedule/cancel, inbox acknowledgement and return-to-task. See the
[pressure-round evidence](evidence/G7/20261111-customer-work-01/qualification.json). This is an app authoring lesson,
not evidence that the core needs customer-specific routing.

One build rebuilt psycopg2/python-ldap wheel fingerprints with the same locked
versions. That normal staged transition was reviewed rather than relabelled.
Project core bytes remained exact; byte-reproducible native dependencies remain
a packaging improvement. No general dependency reproducibility claim follows.

Still unproven for this combination: complex populated migrations, event delivery,
full Workboard/cascade uninstall, high volume, mobile and broad
accessibility. Existing historical core/Partners lifecycle evidence is not copied
into these new app scopes. Feature-suspension races, recurrence, external side
effects and offline drafts need their own qualification. They are not labelled
platform impossibilities.


## Leaf integration lifecycle findings (12November2026)

[CW-L01](evidence/G7/20261112-customer-work-lifecycle-01/qualification.json) closes six bounded lifecycle/recovery groups
for the exact unchanged three-app combination. No core or app-source customization
was needed. The actual UI continued working without integration source, then the
same archive returned its customer panel and action. Four personal notices and
all original task/customer records survived; a newly linked relationship has a
new identity after destructive uninstall. Old relationship data remains in the
retained checkpoint, not silently restored into the new table.

The source-removal guard first refused the retained failed database. After useful
recovery and an explicit verified full failed-state archive, only that exact owned
synthetic database was retired without FORCE. The current database and checkpoints,
filestore, stages and images remained. The original guard then passed unchanged.
This records a deliberate safe cleanup decision, not a database omission or a
policy exception that applications may request themselves.

The old request-key409 was the existing CR-0019 contract, not a new product defect.
The private test's initial expectation was corrected; no receipt, binding generation
or business row was manually repaired. Exact operation outcomes and failed helper
receipts remain available. Further product copy polish (including technical helper
text), full mobile/accessibility and the remaining application policies stay future
work; source qualification alone is not product maturity.

## PP-02 actual file workflow and storage findings (13November2026)

[Installed evidence](evidence/G7/20261113-pp02-file-workflow-01/qualification.json)
distinguishes useful browser behavior, source regressions and remaining pressure.
The independent library works with native scoped binary transport; versions and
recoverable trash are app-owned. Existing business/authority and uploaded bytes
survived normal immutable app successors. This is no meaningful schema-migration
or operator-checkpoint byte-restore proof; those remain explicit required work.

- **Intentional protocol boundary:** app service `date-time` uses the platform's
  canonical UTC Z checker. Documents emitted +00:00 and its overly broad test
  missed that runtime contract. App serialization/test were repaired; actual
  runtime checker/schema stayed unchanged. Authors must exercise the real checker.
- **App storage customization, now demonstrated:** inherited native Binary sniffs
  SVG and restricts it to system users. This unexpectedly rejected literal XML/SVG
  examples in an otherwise supported escaped .txt file. Documents specializes only
  its opaque bytea field to retain byte adaptation without this image-oriented
  check. Its scoped private mutation marker, immutable versions, type/size/hash
  checks, forced download and escaped preview stay in force; native forged writes
  and legacy content/token routes refuse. Core has no Documents/SVG exception.
  Ordinary native Binary retains its SVG policy; .svg/active rendering is still
  unavailable by intentional app file policy. This uses trusted native field
  customization and makes no sandbox or malware-scanning claim.
- **Actual interaction repair:** explicit selection now focuses the detail after
  Owl patches its async ref; a zero-timeout missed it in the actual narrow view.
  Completed status says Saved rather than indefinitely refreshing. Existing draft
  protection and safe dialog focus pass. Requested390px measured393px, no overflow;
  this bounded agent check does not establish broad accessibility/mobile maturity.

Fresh authority snapshots correct an earlier stale narrative: Alice/B is an
active viewer in this qualification baseline, not revoked. Rows stayed exact;
current-loss tests must use and restore those actual observed states.

## PP-02 installed authority and quota findings (13November2026)

[Pressure evidence](evidence/G7/20261113-pp02-authority-quota-01/qualification.json)
now proves current viewer/membership/feature/actor refusal with existing sessions,
exact fixture restoration, actual read-only controls and cache clearing on known
denial. Previously downloaded content cannot be revoked; this is current-request
authority, not DRM or push deletion of user-held copies. One UI copy defect remains:
the denied library must not describe unavailable data as an ordinary empty library.

The app-owned mutation fence is supported by real RR pressure: two native uploads
waited at the owned workspace lock with established snapshots; PostgreSQL logged
one concurrent-update serialization failure; the normal native retry re-evaluated
quota, accepting one5MiB and refusing the other. Exact100MiB stored/decoded bytes,
known-key dedup and changed-input conflict were observed. This is a bounded two-
writer test for this cohort, not arbitrary load/performance or every quota policy.
Initial5MiB/100MiB policy remains intentional and app-owned, not a universal core
file limit. Empty/oversized rejection and Unicode forced-download headers pass.

Only the20new synthetic pressure files were removed with normal app trash/purge;
all original data remains. Their20receipt tombstones intentionally last until the
24h receipt policy expires and consume receipt slots; an old key cannot resurrect
purged data during that window (actual409). Receipt retention and irreversible
purge are distinct from file trash/version recovery and operator-checkpoint restore.
No product, core, dependency, trust policy, image or source adjustment was required
for this pressure round; scoped temporary controls were restored exactly.
