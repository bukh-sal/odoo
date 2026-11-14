# UI-D05 shared work surfaces implementation

Activated 14 November 2026, before source edits, against platforma2438476e35.
The coherent review site remains port18610/configuration4/core0.2.11. Its private
app sources are Workboard5d93503 (.2.12), Documents82fe5ae (.1.8),
Deliveryeef17af (.1.5), Partners2998aac (.1.0), Taskfiles7bbbd84 (.1.5).
All five repositories are clean. Preserve their independent ownership/notices.

The separate legacy fixture18611/config5 now proves the normal web1.1 to
canonical web19.0.2.11.0 upgrade with unchanged historical app pins. A real
post-native-commit interruption, normal fresh restore/separate resume, newer
authority preservation and exact data/bytes also pass. See
[maintenance evidence](evidence/G7/20261114-legacy-web-recovery-01/qualification.json).
There is no running operation or open access/language fixture. Keep the source,
failed databases, checkpoints, comparison18608 and current18610 intact.

UI-D03 and D04 acceptance cards remain open for the missing browser checks.
The in-app preview is visible to the owner, but its interaction tools have not
attached after pause/resume. Source work can advance against the proven
maintenance path; this does not waive history, focus, RTL, visual or D06 checks.
Use the in-app browser when available; do not substitute another browser.

## Actual gaps and decisions

| Source finding | Decision for this slice |
| --- | --- |
| Workboard, Documents and Customer work independently render headers, notices and detail sections. Some private blue/green colours bypass the neutral shared tokens. | Provide a small shared header, feedback component and record/action styles. Adopt them in the real apps; keep their data, permissions and drafts app-owned. |
| Workboard has its own narrow context opener. Customer work and My reminders use an aside that disappears at the narrow breakpoint without an equivalent opener. | Add a reusable custom-page context layout with264px desktop pane and a labelled narrow opener. Preserve Workboard's dynamic lists and Documents' actual library state. Native Shell keeps its existing action/leave ownership and uses the same visual rules. |
| Native Partners has list/form/search but no contextual route to related customer work. Delivery already owns that relationship and depends on Partners. | Add the bridge in Delivery, using ordinary native view inheritance and a registered view widget. No business destination/model name goes into core. |
| Taskfiles already opens an exact document/version in a new tab, with an accessible new-tab hint. The original task remains open. | Retain this supported return path. Verify the original list/filter/task context on returning to the original tab; do not add an arbitrary return-URL mechanism. |
| Documents can show Upload, Download linked and Download current as competing primary actions. | Keep one primary per working context. Upload is primary in the empty collection; when a file is selected it is secondary. Linked-version download is primary for a pinned entry, current download otherwise; other actions stay secondary. Preserve explicit version identity and byte checks. |
| Web maintenance currently permits only a manifest version change. New files under the logical shared interface directory cannot be declared in its asset bundle. | Add the narrow asset-declaration rule below, not a misleading file/module placement workaround. |
| An existing dark file supplies the base palette, but new feedback/control semantics need matching tokens and Documents still has several independent colour literals. | Preserve the existing light/dark base palettes, extend their semantic tokens, and replace private presentation literals where these semantics apply. Installed dark/contrast proof belongs to D06. |

Keep the accepted56px rail,264px contextual pane,26/34px page title,34px controls,
36px search and minimum44px row. Rows and long text can grow. Preserve the
native form model/renderers, save/validation/leave behavior and revision hooks.
Do not introduce global business search, notification features, a theme registry,
new service DTOs or a second shell.

## 1. Deliver the shared core source

1. Refine the owned-web guard in
   `packages/platform_sdk/modular_platform/release_staging.py`. All manifest
   declarations remain identical except version and the narrowly admitted
   assets extension: existing asset entries and bundles stay exact; only append
   unique literal references to existing inventoried files under
   `web/static/src/interface/` in `web.assets_backend`. Admit ordinary JS, XML,
   CSS and SCSS paths with canonical spelling. Refuse traversal, external URLs,
   wildcards, directives, duplicates, missing inventory members, other bundles,
   removals/reordering or any dependency/data/other declaration change. Keep the
   reviewed legacy-manifest rule, monotonic versions, full source delta,
   independent reconstruction and native ready checks. The caller still
   reviews trusted code; this is not an untrusted-theme sandbox.
2. Implement `PageHeader`, `StatusMessage` and `AppLayout` under the shared
   interface directory. Use normal Owl components and slots. Header content,
   counts, primary action, scope and data are supplied by the app. Feedback
   distinguishes loading, empty, filtered-empty, unavailable/error and status;
   actions are caller-supplied. It never fetches, retries a write or determines
   authority. Keep uncertain submissions in their existing app workflows.
3. AppLayout owns only presentation and narrow context state: labelled opener,
   stable controls ID, expanded state, keyboard Escape/return focus and context
   selection dismissal. Context and canvas use slots; app list/query/selection
   state stays in the caller. No duplicate264px column or mobile orphan pane.
   Reuse native dialog/dropdown behavior and keep one visible navigation level.
   Avoid rebuilding ActionContainer or discarding a mounted draft.
4. Extend semantic CSS for headers, record titles/sections, action rows, notices,
   native control-panel/form alignment, long text and logical spacing. Use the
   existing dark asset bundle's `**/*.dark.scss` inclusion for a dark token
   override; do not add dark-only files to the light backend list. Preserve
   native field widgets, paging, filters, dirty controls and accessible names.
5. Reserve provisional core0.2.12/native mp_core19.0.0.2.12 and
   web19.0.2.12.0 after checking they are unused (history check currently finds
   no assignment). No engine, schema, Python lock or attribution change is
   intended. Inspect the freeze inventory/ADRs before edits; no wire change is
   planned. Record the maintenance rule and source edits honestly.

Verify the real guard and independent validator with positive local additions
and the refusal cases above. Preserve current core-upgrade/legacy regressions.
Parse templates and compile the actual selected bundle with the pinned tools
before native rollout. Use the smallest useful component/interaction regressions;
do not create implementation-mirroring CSS tests or call source mocks a UI pass.

## 2. Commit and deliver core before changing app inputs

Commit reviewed core source, then build a normal clean composition containing
the **unchanged current18610 five app archives**. Build it before editing those
app sources, so the core operation cannot silently include app updates. Verify
all pins, Python environment, actual inventory and exact allowed delta.

Use normal stage-image, core_upgrade nomination for all ten native scopes,
independent review, exact acknowledgments, checkpoint/apply and fresh observer.
Compare all eighteen business/authority tables, native authentication/authority
digest, document bytes, pins and dispatch business fields. No publish replay,
source injection or legacy fixture mutation. Retain protected target hashes and
the current failed/closed historical fixtures. A refusal is inspected/resolved
before a fresh operation; it is never an excuse to bypass a guard.

## 3. Integrate real app surfaces and the missing record bridge

* Workboard adopts the common header/feedback/context layout for tasks and My
  reminders. Keep its existing query codec, real counts,24-to5-to24 filter path,
  personal reminders, lists, task sheet, conflict/uncertain flow and optional
  task panels. Preserve the public module exports used by Delivery/Taskfiles.
* Documents adopts the same header/feedback/action/record styling and a usable
  narrow library context. Keep all version/byte/quota/trash/draft/focus behavior,
  deep links and the distinction between a requested pin and current version.
  Do not silently advance a pin or show denied data as an empty library.
* Delivery adopts the shared layout/header. Add a native view inheritance of
  `mp_partners.view_partner_form` with a small related-work view widget and the
  required invisible public UUID field. Declare its view contribution and
  `partners.partner` extension target; keep explicit provider dependencies.
  The widget checks fresh current Delivery context before showing/acting, hides
  unavailable scoped contributions, and uses the normal action service with
  validated customer UUID in action context. CustomerWork consumes that context
  as well as its existing route parameters. Provider services still authorize
  the original actor/workspace; a forged/foreign UUID must fail there. No new
  computed model field, privileged bridge or core-specific app branch is needed.
* Improve Partners' native form using ordinary title/section markup around its
  existing native name/fields/revision controller. This gives a real native
  record comparison without replacing the renderer or moving business logic
  into core. Keep permissions and field behavior unchanged.

Use legitimate successors for changed bytes: Workboard0.2.13, Documents0.1.9,
Delivery0.1.6, Partners0.1.1, with matching native versions. Apps importing new
shared components require core>=0.2.12,<0.3. Do not raise another app's minimum
without a technical dependency. Taskfiles0.1.5 remains unchanged unless source
inspection proves a needed correction; its existing new-tab behavior needs no
new return-link framework. Preserve licenses/notices and old archives.

Run affected app controller/XML/API/security tests. Add a producer/consumer
regression for native widget record/context, fresh denial and chosen customer;
keep required-field/revision behavior. Assemble/validate archives deterministically.
Build one new app composition after source review, admit exact new digests,
stage/review a normal app upgrade (core remains exact), acknowledge the actual
generated changes, apply once and compare data/bytes/current authority. XML view
installation is not a data migration; do not invent a no-op migration script.

## 4. Prove the useful journey and publish the author catalogue

On the coherent current site, exercise original-human behavior:

1. Open an organization in native Partners. Related work opens the same allowed
   customer in Customer work; no lost workspace or integer/public-ID confusion.
2. Open linked work, filter the real list, select a task and use its detail sheet.
   Save one intentional edit, cancel another, reject a stale revision and confirm
   viewer/foreign refusal with no accidental extra write.
3. Open the pinned brief in Documents. Inspect/download the pinned revision and
   current revision separately and verify actual hashes. Return to the original
   task tab with the selected task, list and filters intact.
4. Check readable native form/custom sheet/header/action hierarchy, loading,
   empty, filtered-empty, unavailable, conflict and uncertain states. Verify
   scope changes and optional companion unavailability without fabricated data.
5. Inspect desktop/narrow and keyboard close/focus behavior in the in-app browser.
   Capture matched before/after views and consequential design choices. Do not
   mark this phase accepted while those tools/evidence are missing.

Write `docs/ui-author-patterns.md` from the actual components and their use:
header/actions, contextual layout, query disclosure, native list/form and optional
record action, record section/sheet, feedback/drafts, pinned cross-app link,
theme/RTL/focus. Provide minimal generic imports/templates, ownership rules,
state/accessibility/localization requirements and tokens-only fallback. Do not
copy private application implementation into public documentation.

UI-D05 exit requires the installed journey and reuse on native Partners plus at
least two independent custom apps, normal maintenance/data preservation, affected
checks, screenshots and the usable author catalogue. D06's detailed plan is
written when that phase activates, using these actual findings; its existing
brief still requires the complete integrated browser/build/lifecycle/regression
matrix. No broad support, accessibility, all-layer or production claim follows
from this implementation plan.

## Core source checkpoint, 14 November 2026

Implemented the three shared components, semantic light/dark tokens, native
record/control alignment and a narrowly appended shared-interface asset rule.
Core0.2.12/web19.0.2.12.0 identifies the changed shipped bytes; private app
sources and archives remain unchanged at this checkpoint. Eighteen actual
core-upgrade tests pass, including independent reconstruction and forged/foreign
asset refusals. The existing nine release-staging and seven native-version
checks pass. Six AppLayout logic/focus-request checks pass with mocked hooks;
they do not establish DOM focus, retained drafts or rendered accessibility.

Actual default materialization contains exactly eight addons and no app archive,
including all seven new declared assets. Four templates parse; the existing
image's pinned Sass0.22.0 and Node24.22.2/RTLcss4.3.0 compile all three shared
styles. The original compiler-check failure is retained: its private caller
omitted RTLcss's required stdin flag. Corrected source check passes in a fresh
receipt directory. Freeze inventory remains122files/11rows and passes.
Installed full bundles and the core-only populated upgrade are the next checks;
visual/app integration and all phase exit requirements remain open.

## App source checkpoint

The core-only operationd8b48206 completed normally on18610/config5 before app
edits; its [evidence](evidence/G7/20261114-shared-work-surface-core-01/qualification.json)
binds all unchanged pins,18tables, native authentication/authority, job/outbox
business data and selected assets. The app source now adopts the common layout,
header and feedback in tasks, reminders, customer work and Documents. Workboard
and Documents use the common semantic palette, preserving their content geometry.
Native Partners retains its revision-aware form with a real title and sections;
Delivery's optional native widget hands the public UUID through ordinary action
context and rechecks current availability before showing/acting. Five new
controller witnesses cover that handoff and stale/denied/invalid identities.

Affected app checks pass68Node and62Python tests;23native/inline templates parse,
both styles compile with the pinned Sass/RTL tools, and deterministic packages
validate. The first aggregate wrapper stopped at an incorrect expected test-file
count before running tests; its intent is retained. Two focused fixture mistakes
were corrected: merged registry categories in a Documents action assertion and
a missing binding in the new Workboard request fixture. Production guards were
unchanged. The old local mobile-focus assertion is now owned by the shared
AppLayout logic checks; its app consumer verifies real selected-scope/filter
requests instead. No rendered focus or installed new-app claim follows.

The [author catalogue](ui-author-patterns.md) describes the actual exports,
native and optional seams, tokens, localization, draft/authority ownership and
fallback. Final archive pins, combined immutable image, normal app upgrade and
installed useful journey remain next; in-app browser controls are still absent.
