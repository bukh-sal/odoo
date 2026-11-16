# Phase2 - shared navigation, collections and record surfaces

Activated16November2026 after the first installed phase1 comparison. Runtime
source839136685d3/core46/Partners11 is on fresh18740/config6 with14contacts.
The empty eight-addon45 counterpart is on18741/config1. Original demos stay
protected. The full [roadmap](meridian-fidelity-plan.md) remains the objective;
this plan does not substitute a narrower product or accept final visual fidelity.

## Outcome and reference

Make native and custom views speak the same visual language: grouped context,
useful app navigation, quiet controls, collections with clear state and a
record reader whose identity/actions precede informational cards. Pages must
be able to use these pieces without copying Partners CSS. Keep the24px roomier
inset,264px sidebar,45px bordered rows, unified Lucide and visible focus.

Meridian sourcececb81593036 remains open in tab39/server94394. Current directory
pairs are browser045/046. A fresh1440x900 prototype record capture and its actual
DOM/geometry are in `.local/meridian-phase2-reference-01/`. The real app lacks
lead/vendor/finance/owner/activity domains: do not manufacture those rows,
balances, badge meanings, counts or inactive commands to fill the composition.

Source review found usable existing seams: native menu trees already represent
non-action groups; the manifest has page/icon declarations; shell_context and
the UI registry compose trusted application components; native Layout forwards
control-panel slots; FormController owns read/Edit/create/discard/leave; the
app's registered reader already owns contact/integration access checks. Use
these seams directly, preserving supported behavior rather than adding a new
navigation or authorization framework.

## Coherent implementation

### 1. Shared vocabulary and overlay surfaces

Extend role tokens in interface/foundation.css and foundation.dark.scss for
popover, subtle divider, neutral badge, overlay/elevation and optional bounded
accent tones. Keep app color names out of core. Tune surfaces.css,
record_sections.css, dialog/menu/command templates and their styles against the
prototype. Avoid another disconnected CSS theme. Preserve print and native
form/error behavior; use proper state tokens rather than removing semantic
success/warning/danger distinctions. Inspect actual rendered contrast.

Provide a small Badge export (escaped label, optional icon, bounded semantic
variant). Native badge fields consume the same ink/fill/border roles, including
uncolored Kind. No nearly-white neutral pill on dark backgrounds. Keep labels
and shapes so color is not the sole state signal. Controls share34px desktop
and44px coarse targets, consistent stroke/radius and focus treatment.

### 2. One sidebar pattern and useful shell controls

Add ContextNav as a data/slot component: labeled groups, icon/link/button rows,
current state, optional truthful count/badge, nested disclosure and footer.
Support real hrefs and modified-clicks; normal selection delegates to the owning
action/leave lifecycle. Validate keys and plain labels. Default native Shell
uses current filtered menu trees, rather than copying application markup.
AppLayout can use the same component. Its tree/disclosure variant supports
keyboard navigation and will be reused by Pages; implement only actual
presentation/state handling, not app data fetching.

Allow a trusted installed app to supply its native context component through a
private UI-registry composition keyed to the current plugin. It receives only
normal menu/action context and shared exports. It supplies domain counts via
ordinary scoped requests and handles loading/failure/disposal. The generic
shell performs no application-model queries. Menu icon data is projected from
the app's declared native pages/navigation; retain feature/page/ACL pruning,
foreign-root/cycle/blocked-action checks. No browser-authored count or registry
entry grants server access. Optional accent metadata is a bounded presentation
tone, with a neutral fallback; no arbitrary CSS/URL injection.

Use the same authorized apps in the launcher and command groups. Add accessible
pin/order preferences per browser/account/database/workspace, isolated from
authority. Null preference means default order; an explicit empty pin list is
valid. All apps stays reachable with zero pins. Offer checkboxes and move-up/
down controls instead of requiring drag. Filter stored IDs through current
accessible apps, bound/validate stored values, handle unavailable storage and
do not resurrect unavailable applications. Restore focus after customization.

Bring profile identity, appearance, sidebar customization and help onto the
reference menu grammar. Put keyboard hints in help/command results, not in
ordinary content headers. Expose no simulated inbox/chat/status controls when
no actual provider exists. Preserve fresh menu checks, release mismatch hiding,
new-tab workspace behavior and unsaved-action guards.

### 3. Native/custom collection grammar

Align title/subtitle/optional count metadata and a precise logical-end create
action. Provide an overridable native create-label getter and equivalent
shared header slots; default New remains valid without an author choice.
Partners chooses Create partner/Add person/Add organization. Search begins at
logical start, secondary filtering stays in one disclosure, and sort/selection/
bulk actions have a coherent toolbar state. Keep SearchModel, native queries,
ORM and authoritative sort/count/paging; never sort only the visible page.

Retain below-table Previous/numbered pages/Next; a single page shows a quiet
count. Fix scroll ownership so the query and footer do not create competing
vertical scrollers. Preserve genuine table-local horizontal overflow and sticky
headers. Prove optional columns, resize, filtered/no-results, grouping,
single/multi-select and at least two real pages. Avoid bulk actions the app
cannot safely perform with revision CAS; Partner's existing bulk-archive refusal
stays in place. Counts must distinguish any limited/estimated native result.

### 4. Record/header/aside and create/edit states

Add reusable RecordHeader/RecordLayout exports using title/initials, optional
state/metadata/actions and main/aside slots. The empty aside collapses. Native
FormView forwards a declarative record-heading slot supplied by an opted-in
controller; ControlPanel arranges the quiet breadcrumb above identity plus
existing action buttons. Use ordinary component slots rather than a global
DOM portal or duplicated app-owned Edit/Save implementation. Fallback forms,
new/edit/dialog modes still render their ordinary native controls.

Partners consumes those exports for its organization/person reader. Preserve
the reader's scoped context, contribution registry, current availability,
contact query bounds, dirty contribution guards and normal Edit. Put actual
contact information and notes in the main card, actual related contacts in an
approximately304px aside; omit the aside when absent. Existing work summaries
remain provider-backed; no fake finance summary. A contact opens normally and
Back retains context. Do not replace the native revision-checked form with a
second persistence implementation.

Restyle small create dialog, organization sheet and full create page as one
family: title, close, padded body, bottom actions, validation, busy/error/dirty
state. Preserve full-page creation for complex inputs and nested contact
creation/return. Exercise save, discard/keep draft, stale revision, required
fields and viewer denial. A field failure must retain input and focus the
invalid control. Keep current RecordTabs keyboard/leave behavior.

### 5. Real consumer and packaging order

Implement/test core47 first with exact Partners11 unchanged, commit locally,
build the normal clean nine-addon maintenance candidate and review/apply only
its exact core change. Then implement private Partners12: registered shared
context, declared native menu groups/icons, useful directory columns and count,
precise create labels and RecordHeader/Layout adoption. Minimum supported core
is47; native/plugin identity and deterministic archive advance legitimately.
App data/service/security/schema remain unchanged unless an observed workflow
requires a separately recorded correction.

Build the app-enabled candidate from that exact source and admit/stage/plan/
review/register/ack/apply the app upgrade separately. Do not mix new app bytes
into a core-upgrade operation that requires unchanged archives. Final empty-core
qualification uses the current eight-addon candidate through the ordinary
maintenance path; no live source/assets injection, reader guard relaxation or
old operation replay. Keep all checkpoints, failed diagnostics and prior images.

## Qualification and exit checklist

First source checkpoint: shared ContextNav/Badge/RecordHeader/RecordLayout and
their theme roles are implemented; native Shell now consumes ContextNav's
filtered menu-tree projection. Native neutral/decorated badge presentation uses
shared roles.45Node cases,22Python cases,122-file/11-row freeze and7actual Owl
templates/10fake-DOM mounted checks pass. A final handled-key guard was checked
with the seven affected ContextNav cases. No47image or installed47claim yet.
The asset-fence test initially supplied only historical file hashes; the
unchanged production guard correctly refused them, and the fixture now tests
all actual appends plus each missing hash. Two private jsdom realm/layout
fixture corrections are recorded, not presented as installed behavior.

Second coherent source checkpoint adds isolated rail pin/order preferences and
editor, profile identity/help, trusted optional context composition with normal
menu fallback, native declared page icons and bounded tone roles. Native list/
form create labels, collection metadata, readonly record-header slot forwarding
and a renderer-independent top-level footer share the ordinary controllers.
Measured neutral surfaces, card roles, dialog/popover/palette/toast presentation
and a reachable palette close/namespace controls complete the core source slice.
128affected Node cases and29Python cases pass;26actual Owl templates compile,
and seven mounted fake-DOM scenarios cover editor/default/empty/refusal/help,
failed optional context and actual FormView/Layout/ControlPanel slot forwarding.
Freeze remains122files/11rows. Evidence is
`.local/meridian-phase2-composition047-01/`; the private witness initially lacked
uniqueId and assigned a cross-realm object, corrected in its fake boundary.
This is source proof, not installed contrast, geometry or authority acceptance.

Phase2 is roughly25% from the shared source implementation and focused checks;
milestones remain1/5. Core47 is unbuilt; Partners11 stays exact until its core47
maintenance image is built. Next freeze/commit/build core47, normal maintenance,
then private12 adoption and separate app upgrade. Full installed collection/
record/create/RTL/zoom/motion checks and the current empty-core counterpart
remain. No phase2 exit or wider app adoption is claimed.

1. Production-component/hook tests cover key validation, pin isolation/empty
   state/order/revocation/storage failure, native menu pruning, canceled/failed
   requests, modifier navigation, focus/disclosure and read/Edit/header fallback.
   Exercise actual component behavior, not only string-match assertions.
2. Affected shell/action/context/list/fields/dialog/record/create/asset and
   identity source checks, template compiler and unchanged contract freeze pass.
   Targeted iteration only; frozen-source canonical host run belongs to phase5.
3. Real installed organization/person, two or more directory pages, filter/clear/
   sort/selection/columns, reader/Edit/save/discard/conflict, small-dialog/sheet/
   full-create and nested creation. Use durable normal-path synthetic fixtures
   with per-write receipts and idempotency/reconciliation; retain original14.
4. Pair reference/live directory, selected/filter/menu states, record, create and
   error originals at1440x900 in both themes. Also1280,390, actual200%, RTL and
   reduced motion; record exact dimensions and limitations. Narrow/zoom create
   actions and footer remain reachable, with useful focus and no document-wide
   horizontal overflow. Preserve any user-selected preview zoom.
5. After each native operation/fixture/browser section, compare current business,
   grants/membership and protected targets with the appropriate baseline. Check
   current app/authority loss and empty core; no stale counters/provider labels.
6. Update ui-author-patterns.md with worked ContextNav/Badge/RecordHeader/Layout
   recipes and native opt-in/fallback contracts. A reader should implement the
   same quality using exports instead of copying Partners markup/CSS. Pages and
   existing-app adoption in phases3/4 provide the broader independent-consumer
   proof; do not claim it prematurely.

Exit requires installed proof and a visual critique closing material phase2
findings, not merely green source tests. Phase3's detailed authoring/editor/
access plan is written when this phase exits, using the resulting real APIs.
