# Product and platform roadmap

Established 13 November 2026 (Asia/Riyadh), from source baseline
`69a053bd64b11a30835c2f7ff7b4ed3260373847` and the [research record](roadmap-research.md).
This is the next implementation roadmap. The completed app-free-core/R1 and
CW-L01 records remain historical acceptance, not unfinished phases of this work.

## North star and starting point

Enable independently owned applications that people can use together to do
useful work, on a small application-free core. Applications own their business
models and interactions; reusable platform capabilities belong in core. Judge
the result by a complete user journey, visible usability, authority and data
integrity, and a practical application/deployment lifecycle.

The demonstrated default is the eight-addon core in
[candidate support](candidate-support.md), provisional core0.2.1. Partners,
Workboard and optional Customer Work already demonstrate ordinary independent
packages and a useful customer/task/discussion/reminder journey. The
[pressure round](evidence/G7/20261111-customer-work-01/qualification.json) and
[CW-L01 lifecycle](evidence/G7/20261112-customer-work-lifecycle-01/qualification.json)
are the baseline. They do not establish universal plugin support, file handling,
complete mobile/accessibility coverage or arbitrary completed-checkpoint restore.

Retain the owner's [fork direction](architecture-decisions/0071-owned-fork-and-addon-boundaries.md)
and [candidate decisions](architecture-decisions/0083-provisional-app-free-core-candidate.md):
eight default addons, optional apps/shell, provisional qualified combinations,
current labels/notices, private independent apps. No new version, ABI or support
promise is chosen here. Useful direct core changes are allowed; preserving
upstream compatibility or adding a permanent adapter is not the objective.

## Sequence and acceptance

These are outcome milestones, **not phase implementation plans**. There is one
active item. Follow PP-01 through PP-05; an evidenced core prerequisite belongs
inside the phase that needs it. Do not defer a necessary security fix until
PP-03, or build a speculative framework in anticipation of later apps.

| Phase | Weight | Deliverable | Dependency | Current acceptance |
| --- | ---: | --- | --- | --- |
| PP-01 Product experience | 25% | A coherent, visibly improved daily customer-work journey | Existing qualified apps | [Accepted, 4/4 bounded outcomes](evidence/G7/20261113-pp01-product-experience-01/qualification.json) |
| PP-02 Application breadth | 25% | Useful independent workspace document library, including secure generic binary support | PP-01 interaction findings; scoped-binary prerequisite | [Accepted,5/5 bounded outcomes](evidence/G7/20261113-pp02-application-breadth-01/qualification.json) |
| PP-03 Platform evolution and reuse | 20% | Reusable capabilities proven across the qualified apps, meaningful migration and event effects | Actual needs from PP-01/02 | [Accepted,5/5 bounded outcomes](evidence/G7/20261113-pp03-platform-reuse-01/qualification.json): populated migration, useful event effects/replay/authority/recovery/UI and generic ownership audit |
| PP-04 Developer and operator workflow | 20% | Current app authoring/lifecycle path and bounded coordinated checkpoint restoration | The actual app/core contracts from PP-01..03 | [Accepted, all bounded A/B/C outcomes](evidence/G7/20261113-pp04-developer-operator-01/qualification.json). Historical section records: [public bootstrap](evidence/G7/20261113-pp04-bootstrap-native-01/qualification.json), [independent author/install/repair/populated upgrade/UI A](evidence/G7/20261113-pp04-independent-authoring-01/qualification.json) and [actual completed-checkpoint recovery B](evidence/G7/20261113-pp04-completed-checkpoint-native-01/qualification.json) verified; [measured rebuild boundary](build-reproducibility.md) and reconciliation pass |
| PP-05 Candidate release readiness | 10% | Exact supported cohort, measured budgets, final UI/lifecycle/regression and handoff | PP-01..04 accepted | [Accepted,5/5 bounded outcomes](evidence/G7/20261113-pp05-candidate-final-01/qualification.json): exact cohort, budgets, native recovery/lifecycle, final regression/UI and retention handoff |

Weights estimate outcome importance, not elapsed time or test counts. Current
new-roadmap accepted progress is **100/100 phase points; 5/5 phases accepted**.
PP-01 delivered the coherent customer-work journey. PP-02 delivered useful
independent Documents, actual binary/quota/current-authority pressure, optional
immutable references, populated upgrades and coordinated fresh recovery with
newer authority preserved. Actual browser desktop/393px keyboard/download/reload
evidence supports its bounded acceptance. PP-03 now passes real populated storage
migration/failure/fresh recovery/use and the useful registered file-update review.
Actual original-human effects, saved-key and duplicate delivery, current-source
authority, populated projection/tombstone/pending-event recovery and keyboard/UI
reload/download pass; the ownership audit keeps business policy in apps. Its
bounded acceptance does not establish arbitrary migrations, permanent event
history, completed-operation restore or formal accessibility. Rough implementation
is100/100 for this bounded roadmap, with100/100 accepted phase points. PP-04's developer/operator A
outcome has actual independent-app install, diagnosed repair, populated date
evolution, authority and desktop/390px keyboard/reload evidence. B now verifies a
real completed destructive uninstall, safe interrupted quiesce/fresh continuation,
current-authority/document-byte fresh restoration, separate resume and usable UI.
C now verifies repeated app archives, normal/cache and actual forced recompilation
with exact declared installed content/runtime layers, while preserving accurate
provenance and intermediate-wheel limits. PP-04 is accepted in that bounded scope.
PP-05 now passes its predeclared dataset/budgets, actual installed/UI/recovery/
source-removal and final regression requirements. [Final acceptance](evidence/G7/20261113-pp05-candidate-final-01/qualification.json)
records the original failures, repairs, new measured cycles and exact retention.
Research, documents and source-only checks did not earn outcome acceptance.
Report partial progress only against real delivered outcomes; keep original R1
99/99 and its score separate. Re-estimate effort when the fresh phase plan exists.

### PP-01 — Make the daily workflow feel like one useful product

Outcome: a user can enter the right workspace, find a customer and current work,
create or update a task, discuss/hand off, manage a personal reminder and return
to the same context without losing work or guessing what happened.

Exit evidence:

- A fresh inspection of the current screens identifies and delivers concrete
  improvements in navigation, discoverability, product language and feedback.
  Compare the actual workflow with Aurora's useful interactions, without copying
  private code/branding or making its business models mandatory core features.
- Actual browser walkthrough covers creation, finding, editing, discussion,
  reminder/inbox and return after reload. Check viewer and unavailable-optional-app
  states. Drafts, conflicts and ambiguous mutation outcomes receive honest behavior.
- Check desktop and a declared narrow viewport, keyboard-only alternatives,
  dialog focus/return, visible unobscured focus, scrolling and usable action targets.
  Record the relevant accessibility criteria and results; screenshots or backend
  checks alone do not prove interaction or formal accessibility conformance.
- Capture a concise before/after review packet and remaining usability defects.
  Agent review is labelled as such; do not invent human satisfaction or approval.

Keep this an app-led product improvement, not a mandatory new shell or a fresh
round of unchanged CW-L01 lifecycle tests. Optional interactions must degrade
without breaking the underlying independent apps.

### PP-02 — Add a substantially different useful application

Outcome: an independent workspace document library supports bringing a document
into customer work, finding it later, retrieving the intended revision and
recovering a mistaken application-level deletion. An optional integration can
reference a document from a task/customer; the library remains useful alone.

**Blocking capability prerequisite:** current core deliberately denies workspace
attachments, including old public/token binary paths. The phase's fresh plan
must design and review a generic current-authority binary capability before
implementing upload/download. Reuse useful inherited storage behavior where
appropriate; do not remove the denial, use unscoped ownership, expose raw
filestore paths or add an app-only bypass. See [research finding R-02](roadmap-research.md#r-02-scoped-binary-support-is-a-real-core-prerequisite).

Exit evidence:

- Real upload/find/download, explicit revision history and restoration, and
  soft-delete/trash restoration work in the browser with sensible empty/error
  states. Safe bounded preview is provided only for explicitly supported types;
  other allowed types have a clear download-only disposition.
- The implementation plan fixes allowed types, sizes, quotas/resource bounds,
  filename handling, content checks, preview policy and retention before coding.
  Explain scanning/parser decisions and remaining risks; no unapproved external
  scanning service or paid storage is assumed.
- Default app policy is workspace-shared, editors write/viewers read. Prove
  foreign IDs, current membership/feature/role loss and alternate native/token
  routes cannot bypass the scoped binary policy. Per-folder/person secrecy and
  public sharing require a separately intentional policy and recovery design.
- Binary bytes, metadata, versions and references remain coherent under an
  actual populated upgrade and coordinated fresh restore. Document trash/version
  recovery, destructive uninstall and operator restore are distinct behaviors.
- Package/install through normal immutable image, catalog and independent
  approval paths. Actual visual interaction and optional-link degradation pass.

This is a bounded native document application, not the previously excluded full
Storage product, a new cloud storage service, Office co-editing, desktop sync,
OCR, public links or hostile-file execution. New dependencies require provenance,
license and affected qualification; application data stays private.

### PP-03 — Turn observed needs into reusable platform capability

Outcome: the platform enables the different apps without task/customer/document
branches in generic core. The capability register explains what works, what is
deliberately unavailable and what needs repair.

Exit evidence:

- Audit actual PP-01/02 core changes for generic ownership, contracts and at
  least two relevant application uses or consumers. Keep app business policy in
  apps; do not generalize a single screen into a new framework without need.
- Demonstrate one useful real cross-app event-consumer effect, its duplicate
  handling, current-authority denial and recovery behavior. Existing producer
  or transport-only evidence is not a consumer-effect qualification.
- Deliver a genuine populated schema/data migration required by useful app
  evolution, including failure/recovery and surviving-app preservation. A
  version-only bump or no-op migration earns no migration acceptance.
- Reconcile each discovered limit in the capability register: status, reason,
  responsible component, user-visible impact and condition for revisiting it.
  Preserve exact authority, installation, image, contract and approval boundaries.
- App-owned ACL rows currently have checkpoint semantics, not a universal
  current-authority overlay. If finer document sharing is added, explicitly
  resolve and qualify post-checkpoint revocation behavior before supporting it.

No hostile-native-code sandbox, universal plugin ABI, arbitrary third-party
compatibility or marketplace is implied. Frozen contract changes, when needed,
get an explicit decision, revision and affected qualification at that time.

### PP-04 — Make creating and operating apps a supported workflow

Outcome: a fresh developer/operator can follow the current documented path
without private qualification scripts, knowledge of the author's machine or
accidentally following a historical sealed-kit guide.

Exit evidence:

- A fresh independent app workflow covers creation, packaging/validation,
  declared dependencies, install/update, diagnosis and current UI use through
  supported documented entrypoints. Preserve historical kit instructions, but
  clearly route new work to the current candidate.
- Plans and failures explain required acknowledgments, current operation state,
  stale review, ambiguous effects and safe reconciliation. Improve ordinary
  workflows; never silently acknowledge trust, rotate ambiguous keys, replay an
  apply or give browser apps access to OS approval stores/issuer secrets.
- Close the documented completed-checkpoint recovery gap for the exact native
  cohort: independently reviewed coordinated restore into a fresh target after
  a completed operation, with current authority/effects/source identity checks,
  retained failed/current source and separate reviewed resume. This is a new
  capability, not an existing promise or arbitrary in-place rollback. Its fresh
  implementation plan must first establish the supported target/effect model.
- Qualify that recovery with meaningful app data and document bytes; explain
  snapshot retention and deletion consequences. Preserve unknown databases and
  all foreign resources; cleanup uses exact durable ownership, never a sweep.
- Define and measure the build reproducibility boundary: app archives,
  executable inventory/native dependency bytes and OCI construction are separate
  claims. Locked versions alone do not prove identical rebuilt binaries.

The current unresolved-failure restore path remains supported and protected.
Do not replace it with automatic rollback or a new general orchestration layer
unless the actual requirement and source justify that design.

### PP-05 — Qualify and hand off an honest local candidate

Outcome: an exact, useful app/core combination is reproducibly identifiable and
operable with clear support limits and evidence a reviewer can follow.

Exit evidence:

- Record exact core/app versions, immutable packages/images, optional combinations,
  supported operations, known limitations, notices and migration/recovery notes.
  Preserve existing license choices; resolve broader version/support decisions
  explicitly rather than silently declaring a stable ABI or LTS release.
- Set dataset, concurrency, file-size/storage and interaction/operation budgets
  before measurements; record hardware and actual results. Fix material failures
  or obtain an explicit scope decision, not post-hoc thresholds to pass a run.
- Run the appropriate canonical regression at the final source boundary plus
  changed-boundary negatives, clean installation, meaningful populated upgrade,
  current-authority recovery and actual end-to-end visual/operator walkthrough.
  Reuse unchanged evidence where justified; classify failures instead of looping
  full suites or calling unit fixtures installed qualification.
- Review the clean default artifact and selected app compositions, including
  final-layer/source ownership and exact lifecycle/removal where affected.
  Retain a coherent evidence index and safe exact cleanup/retention outcome.
- No unclassified critical correctness, authority or data-loss issue remains.
  Deferred work has a reason, owner and return condition. Final acceptance is
  bounded to the actual qualified cohort; publication/production is not included.

## Just-in-time implementation plans

**No phase or large-section implementation plan is created by this roadmap.**
When the phase becomes active, before its implementation starts, Codex will
re-read current source/status, preceding findings and applicable contracts,
research remaining uncertainties, then write and review that phase's plan.
Create a further plan before a genuinely separate large section when its scope
becomes concrete, not a batch of speculative future plans now.

Each plan must bind the current source/artifact/environment baseline, intended
user outcome, decisions and limits, exact scope/dependencies, affected code and
contracts/migrations, execution sequence, authority/data effects, meaningful
tests and actual visual acceptance, evidence/cleanup and stop/reconcile rules.
Include an effort estimate and concrete completion criteria. Private app/resource
details belong in local-only planning; publish only sanitized platform records.

Refresh an active plan before material scope or contract changes. Do not execute
a stale plan simply because it was once reviewed. Routine work already within
the user's authorization proceeds; ask only for an actual unresolved policy or
action outside that authorization. A blocked promised outcome remains open until
implemented or explicitly changed by the owner, not silently waived.

## Execution and goal completion

Codex implements and reviews, without delegation. Keep one active item and update
[status](implementation-status.md), [capabilities](application-capability-register.md),
[work log](work-log.md), evidence and the private resume capsule after meaningful
results. Prefer coherent useful slices over tiny handoff/test loops. Run affected
checks when the change warrants them; repeat or broaden only for a new boundary,
failure, material change or release decision.

Local commits and clearly owned disposable qualification are authorized. No push,
publication, production, paid service, global Python change, unknown-resource
deletion or destruction of existing user data is authorized. Private app sources
and sealed evidence remain private/immutable. R2/R3 remain outside this goal.

The implementation goal is complete when all five phases meet their recorded
outcomes and acceptance, final support/limitations and evidence are reconciled,
and the handoff/owned-resource disposition is recorded. Roadmap creation does not
complete it. The setup turn created no implementation plans. PP-01 subsequently
activated with its fresh local plan and is accepted in its recorded bounded
scope. PP-02 subsequently passed its bounded installed qualification. PP-03 is
accepted after its fresh phase/section plans and actual installed qualification.
Follow [current status](implementation-status.md);
no PP-02..05 implementation plans were created in advance.


## Post-roadmap UI-D01: shared redesign audit and visual review

14November2026 user authorization: audit inherited patterns, classify keep/restyle/
rework/replace, propose a Meridian-based shell/shared design with screenshot-backed
visual judgments. The completed PP01..05 score stays100/100,5/5. This new design
work earns no additional implementation/qualification points from documents or mocks.

[Audit/matrix](ui-pattern-audit.md) covers34 patterns and real native/custom source
and read-only screen inspection. [Visual direction](ui-design-direction.md) records
the rejected first study and the user-instructed restart from actual Meridian style.
The replacement retains its fonts/components/icons/shell and applies small measured
refinements. The owner accepted its roomier sizing with a 264 px sidebar. See [the first shared implementation](ui-foundation-implementation.md).

Subsequent outcome order: confirm visual baseline; generic tokens/catalogue/native
presentation bridge; common shell/navigation/safe overlays; native Partners plus
custom Workboard/Documents adoption; actual end-to-end/authority/RTL/narrow/keyboard/
contrast/assets/lifecycle qualification. These are outcome milestones, not current
implementation plans. Write each detailed plan fresh when activated. Patterns must
be usable by all independent apps without importing private Workboard or optional
reference Notes shell. Default8-addon core and app-owned business semantics remain.

## Next delivery sequence after the shared foundation

UI-D02 supplies the installed native and app baseline. The [shared shell delivery plan](ui-shell-delivery-plan.md) sequences UI-D03 shell/navigation, UI-D04 populated web maintenance, UI-D05 shared application workflows and UI-D06 integrated qualification. D03 is ready to implement. Write each subsequent section plan at activation using results from its predecessor.
