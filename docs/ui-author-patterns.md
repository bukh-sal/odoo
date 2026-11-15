# Shared application interface patterns

The owned web interface supplies common presentation for native views and
independent applications. Applications own their data, services, permissions,
routes and drafts. These components ship with provisional core0.2.12; an app
that imports them must declare that minimum in its platform compatibility.
Existing native field/form/list renderers remain the default record interface.

The current source integrations use the same components in tasks, personal
reminders, customer work and Documents. Native Partners retains its normal form
model, fields, validation, revision controller and save/leave lifecycle. Installed
core delivery is recorded in the [core qualification](evidence/G7/20261114-shared-work-surface-core-01/qualification.json).
The [installed app record](evidence/G7/20261114-shared-work-surface-apps-01/qualification.json)
now proves normal upgrade preservation, native metadata and the scoped API
journey. Rendered interaction and visual qualification remain open in the
[D05 plan](ui-work-surfaces-plan.md); source checks and API success are distinct
from that evidence.

## Header and actions

For balanced native record sections, use an outer `<group col="2">` containing
two ordinary inner `<group>` declarations. The native OuterGroup producer gives
each a `col-lg-6` width and stacks them on narrow screens. A flat `col="4"`
inner group sizes tracks from content and does not guarantee equal field columns;
the installed Partners1.4 counterexample demonstrates the difference. Keep
revision-CAS fields invisible but loaded when an app controller requires them.
Standard TextField supports char with `line_breaks: False` and autosizing for
soft-wrapped names; keep server length/content validation. Apps own the choice
of fields, sections and meaningful related actions; shared styles own appearance.

Import components through their public web module names:

```js
import { PageHeader } from "@web/interface/page_header";
import { StatusMessage } from "@web/interface/status_message";
import { AppLayout } from "@web/interface/app_layout";
import { _t } from "@web/core/l10n/translation";

// On the owning Owl component:
static components = { PageHeader, StatusMessage, AppLayout };
get pageTitle() { return _t("Shared work"); }
```

```xml
<PageHeader title="pageTitle" subtitle="state.description" count="state.total">
  <t t-set-slot="actions">
    <button t-if="state.canCreate" class="btn btn-primary"
            t-att-disabled="state.loading" t-on-click="create">New record</button>
  </t>
</PageHeader>
```

`title` is required. Optional props are `eyebrow`, `subtitle`, `count` and
`countLabel`; named slots are `breadcrumbs` and `actions`. Zero is a real count.
If supplying `countLabel`, provide the complete localized accessible description,
including its number; otherwise the visible number remains accessible. Titles
and descriptions are escaped. Counts and action availability must come from the
current app state; the component performs no request or authorization.

Use one primary action per working context. Other actions use native secondary
or outline buttons. A pinned revision's download and the current file's download
are distinct choices; their styling must not imply that a pin advanced. Allow
translated labels and identifiers to wrap. Use `_t` for labels passed as
JavaScript expressions, and preserve ordinary template translation for text.

## Context and work area

```xml
<AppLayout contextTitle="contextTitle" contentLabel="pageTitle">
  <t t-set-slot="context">
    <nav t-att-aria-label="contextTitle">
      <button data-mp-context-destination="" t-on-click="selectAll">All records</button>
      <!-- Current, authorized app destinations belong here. -->
    </nav>
  </t>
  <PageHeader title="pageTitle"/>
  <!-- The owning app renders its data and dialogs. -->
</AppLayout>
```

`contextTitle` labels the pane and narrow opener. Optional `contentLabel` names
the main work area, `showContext` controls whether the pane exists, and
`className` attaches app-specific root classes. Context is264px on desktop; the
core supplies a labelled opener at narrow widths. The content region remains
mounted when the context opens. Closing by Escape requests focus on the opener;
choosing an explicitly marked destination requests focus in the work area.
Modified/middle clicks retain ordinary new-tab behavior. A nested control that
already handled Escape keeps ownership of that event.

Mark actual destinations, rather than a whole pane, a search field, filter or
create button. Let the app own selection, query, paging and action state. Do not
add a second context column or custom mobile opener inside this component.
When `showContext` becomes false, its context slot is removed; the default slot
remains. This is presentation behavior, not a permission boundary or draft store.
The source focus-request checks do not substitute for browser focus/draft checks.

### Shell additions in candidate0.2.29

These additions are source/preview qualified; installed qualification is pending.
The previously installed core0.2.28 remains the control until normal delivery.
Installed029 subsequently exposed a frontend asset-closure failure. ADR0092
corrects the shared primitive packaging in candidate0.2.30; do not treat029 as
clean installed UI support. The component API is unchanged.

Pass `contextKey="'your.stable.plugin.id'"` to `AppLayout` to remember desktop
collapse. The key must be a stable identifier, never a translated title, record ID,
URL or draft. The native shell uses the existing menu's `pluginID` automatically.
The preference is a device-local boolean scoped to browser origin, authenticated
user and application; it is shared across that user's workspaces on the origin,
not synced to other devices. Missing identity or blocked storage leaves an
ephemeral working control. It confers no authority and stores no business state.

Expanded context remains264px. Desktop collapse removes that column while
retaining the work area and its component/draft. The single labelled control is
in the shell topbar for both native and custom actions; action teardown removes
the custom portal. Outside Shell/in dialogs, AppLayout provides its local control.
Nested layouts do not inherit the outer shell's portal destination. Narrow
navigation remains an independent transient drawer, with Escape/selection/focus
behavior, rather than inheriting an unusable collapsed desktop state.

Use the shared local SVG primitive instead of new font-icon dependencies:

```js
import { Icon } from "@web/interface/icon";
// static components = { Icon, ...otherComponents };
```

```xml
<button type="button" aria-label="Previous record" t-on-click="previous">
  <Icon name="'chevron-left'" directional="true"/>
</button>
```

`name` is a pinned semantic name; `size` defaults18, `className` is optional.
Icons are decorative unless a meaningful `label` is supplied. The containing
control still needs a name. Mark only directional navigation icons `directional`;
ordinary objects must not mirror in RTL. Explicit FA/OI aliases bridge existing
native declarations; unknown names use the neutral box fallback. Image icon paths
on native ViewButton remain image paths. Existing legacy fonts are retained for
unmigrated native/app uses; this does not claim every icon has been replaced.
Geometry is Lucide0.468.0, without React/runtime lookup/CDN; exact ISC/Feather
notice and per-module hashes are in `web/static/lib/lucide/`.

`PageHeader` also accepts a `breadcrumbs` array of `{id, label, href?, onSelected?}`.
Use stable IDs, escaped readable labels and real root-relative/HTTP(S) links.
Unsafe schemes, protocol-relative/control-character/backslash destinations are
not rendered as links. The final item is current. `onSelected` delegates an
ordinary click to the owner's existing route/dirty-leave lifecycle; modified
clicks retain the link's normal behavior. The trail never stores or optimistically
changes a selected record. The previous `breadcrumbs` slot remains supported.
This is shared presentation, not a universal record schema or contribution API.

Native actions already use the core Shell's contextual navigation. Keep their
single action container and inherited save/leave handlers; do not wrap a native
form in a second application shell.

## Feedback, drafts and unavailable state

```xml
<StatusMessage t-if="state.error" kind="'error'" message="state.error">
  <t t-set-slot="actions">
    <button class="btn btn-outline-secondary" t-on-click="reload">Reload</button>
  </t>
</StatusMessage>
```

Kinds are `loading`, `empty`, `info`, `success`, `warning` and `error`; optional
props are `title` and `message`. The default slot accepts caller content and the
`actions` slot accepts caller buttons. Error uses `role="alert"`; other kinds
use `role="status"`. Text is escaped. Announce meaningful transitions, avoiding
unnecessary repeated live messages during ordinary typing.

The app distinguishes an empty collection, no filter matches and unavailable
data. A denied request must not turn old data into successful empty guidance.
Known authority loss must clear or hide protected content, with fresh recovery
through the normal scoped APIs. Feedback itself never fetches, retries or grants
access. Scope switching and deployment/release checks remain mandatory.

Keep dirty and uncertain submissions in the owning app. Use the native Dialog
and action leave hooks for confirmation, with explicit cancel/keep choices and
focus restoration. Preserve one submission identity and its original input after
an uncertain response. Do not silently resend with a new identity, discard a
draft on refresh, or present an unconfirmed write as saved.

## Native records and optional related work

Prefer normal native list/form/search declarations, fields and widgets. Use
`oe_title` around the real name field, labelled native groups for sections, and
the platform's revision-aware model/controller where required. Preserve required
field, readonly, save and conflict behavior.

An optional companion can inherit a provider's native view and register its own
`view_widgets` component. Declare the view contribution and extension target in
the companion manifest, with explicit provider dependencies. Use
`standardWidgetProps`; read a loaded public record UUID rather than treating the
native integer `resId` as a service identity. Do not add a computed business field
or a core business destination merely to create a related-work link.

Check current companion availability before showing and acting. A stale success
must not overwrite a newer denial or a changed record. Use the normal action
service and validated action context; the destination still authorizes the
original actor, workspace and record. Keep the native action service's dirty
record guard. Browser verification must cover save/cancel and companion absence;
source widget tests only establish the producer/consumer and refusal logic.

Use `.mp-record-title`, `.mp-record-surface`, `.mp-record-section`,
`.mp-record-section-title`, `.mp-record-actions` and `.mp-identifier` where useful.
Identifiers can be directionally isolated; human names follow the document's
language and direction. Specialized task boards and version histories remain
app-owned content within this common structure.

## Cross-app document references

An app can expose an explicit, authorized document/version link in a new tab,
with `rel="noopener noreferrer"` and an accessible new-tab hint. Retain exact
workspace, public document identity and pinned version; validate them at the
destination. Returning to the original tab should preserve task, list and query
state. A missing or revoked pin must not silently substitute current bytes.
Do not introduce arbitrary return URLs or rewrite a stored reference to simulate
navigation history. Download and compare actual version bytes in qualification.

## Styles, theme and fallback

Use core tokens for canvas, surfaces, ink, muted text, borders, action colours,
links, focus and semantic error/warning/success colours. Light defaults and the
existing native dark bundle both define these tokens. Use logical inline/block
spacing, the shared26/34px title,34px controls,36px search,44px minimum rows and
264px context. Let content grow; constrain internal boards rather than causing
page overflow. Preserve native field widgets, paging, filter menus and names.

Keep app styles scoped to their root or owned dialog content. Avoid broad
`h1`, `h2`, button or field overrides that restyle shared children. Use a native
secondary action rather than adding another visual button vocabulary. The
core's guarded manifest extension permits appended explicit inventoried files
under `web/static/src/interface/`; it does not make arbitrary asset graph edits
or native declaration changes presentation-only. All trusted source still needs
normal reviewed immutable packaging and lifecycle approval.

For an app that cannot require these component exports yet, existing native
views and shared token/class styling are the fallback. Do not import unavailable
modules and hope a runtime branch will hide the error. State the actual supported
core/app combinations. Desktop/narrow, dark/light, Arabic/RTL, long labels,
keyboard,200%zoom, reduced motion and rendered contrast are still required
qualification; token reuse or passing source mocks establishes none of them.


Pending dialog drafts belong to the client action, not only a modal's close
button. Register the action with useSetupAction from @web/search/action_hook;
track pending editor/comment callbacks, include saving and uncertain states,
and unregister on modal unmount. Refuse action leave while pending; the existing
explicit Keep editing/Discard flow remains the choice boundary. Workboard0.2.14
now follows this same existing pattern as Documents. beforeunload alone does
not protect browser-history or app-action navigation.

For a single native multiline field without a label, declare a single-column
group (col="1") so the normal form grid allocates the full width. Partners0.1.2
uses this for Notes. Do not add an app-named shared CSS exception.


Native collection candidate0.2.16 uses the existing ControlPanel display object
with a table presentation variant; optional description is plain text. Standard
native lists use the shared header/query/footer layout without an app selector.
Custom collections may import TablePagination from @web/interface/table_pagination
and declare core>=0.2.16. Supply actual offset/limit/total and an awaited onUpdate
callback; the component never advances model state optimistically. updateTotal
means the count is limited and permits an explicit exact-count action, not a
fabricated last page. Groups and embedded tables must supply their own callback
scope and disable duplicate global pager hotkeys. A custom native renderer that
replaces ListRenderer owns accepting/rendering the optional pagination input.
Native form record traversal and non-table Kanban navigation remain separate.
The current shared paginator uses modern container sizing for narrow grouped
footers; installed browser support is provisional until the actual matrix passes.


Native collection pagination uses the current model offset/limit/total and existing onUpdate callback. TablePagination accepts optional isGrouped for honest group totals; nested consumers supply their own grouping/count scope. The flag changes wording only, never queries or permissions. Single pages show a quiet count; limited counts never invent a final page.


Native record forms select the shared ControlPanel record frame automatically; in-dialog forms retain their ordinary footer. RecordNavigation consumes the existing loaded-ID offset/limit1/count/onUpdate, names the loaded scope honestly and does not wrap or advance optimistically. The ordinary form save, validation, revision CAS and save-on-leave behavior remain. FormStatusIndicator describes its own explicit pending commands and the actual model/local-field dirty/valid state; failed/refused callbacks do not become Saved. Native input hooks provide a title fallback from field metadata without overriding app labels/ARIA/title. Authors should still supply visible labels or section context; this is not a replacement for app semantics.

## Native read-first source candidate0.2.20

Standard full-page native existing records read before editing; named Edit enters the existing model mode, explicit successful Save/Discard returns to reading. New/dialog/custom persistence/forcedreadonly flows keep their own contract. Native widgets still own their behavior; reading mode is presentation, never write authority or an immutable-view/sandbox guarantee. Backend current scope/revision guards decide every mutation. Original native save-on-leave/visibility remains while editing; do not advertise manual-save-only semantics. No app ID or extra author registry/flag is needed. Source/component proof only until normal installed qualification.

## Related-record preview styles, candidate0.2.23

Inside an existing `.mp-record-surface`, use `.mp-record-section-header` for a
named `.mp-record-section-title` and normal action. A semantic list can use
`.mp-related-records`/`.mp-related-record`, a real link or button with
`.mp-related-record-title`, and an optional `.mp-record-state`. Styles only own
logical spacing, wrapping, tokens and focus; the app owns current-authority
reads, empty/error/loading states, honest bounded results and destinations.
Show a returned subset as a preview, never infer a total from page length.
Clear stale rows on scope/record/access loss and recheck before acting. These
styles require the qualified successor; do not import unavailable exports or
invent a disabled feature solely to fill the design.

A native client action should provide its existing static translated displayName
so the action service can name browser title/breadcrumbs. Use ordinary action
service/additionalContext for a cross-app task handoff, and let the receiving app
explicitly validate/consume that UUID before its normal scoped read. A plain
full browser link is not a substitute for the native action dirty-leave guard.
Delivery1.7 demonstrates shared related-record styles with actual current reads,
bounded has_more guidance and a fresh existing context check before task action;
no core business registry is required. Installed qualification is still pending.

An application can build a compact read-first summary directly in native XML:
readonly fields in a semantic definition list, a shared mp-record-surface and
mp-record-section-header, honest missing-value text and shared status styling.
Keep the full existing fields in explicit Edit/new; mode classes control only
presentation. Partners0.1.6 demonstrates this without a new widget or request.
Retain loaded readonly revision/CAS and server authority. Native labels/fields
remain localized/escaped through the ordinary renderer. Verify no duplicated
visible controls in either mode. Native relation links still need the recorded
shared dark contrast correction; token reuse around a field does not restyle
the field's own legacy Sass declaration automatically.

The native Shell and Owl AppLayout use the normal web host's reactive UI service
for breakpoint presentation. Standalone AppLayout and dialog fallback mean no
shell portal is required; they still use the ordinary web service environment.
Do not build another matchMedia store or read env.isSmall alone for a component
that must redraw on resize. This changes no application routes or authority.

## Author-selected creation, candidate0.2.31

Use action context `create_surface` with `page`, `dialog` or `sheet`. Absence
preserves existing native behavior, including editable lists; an explicit choice
overrides inline creation after the existing edited-row leave decision succeeds.
For dialog/sheet, optional `create_form_view_ref` selects a creation-only native
form. Page uses the action's declared ordinary form. Existing-record links keep
their ordinary durable reader and explicit Edit. Choose by workflow, not field
count. An invalid surface refuses before opening a form.

Dialog/sheet use the actual native View, application model override and server
validation. Expand changes the same mounted form to fullscreen, with no save,
navigation or draft serialization. Cancel, header close and Escape share the
dirty-draft decision; these creation surfaces suppress automatic visibility or
leave saves. Native ORM creation is not idempotent: a lost response is uncertain
and blocks blind retry. A confirmed save followed by failed list refresh is
labelled created. Presentation never grants authority.

Custom app forms can reuse `CreationSurfaceDialog` and `RecordCreationHeader`
from `@web/views/view_dialogs/record_create_dialog`, with a required guarded
`requestClose` and ordinary web UI service. The app still owns persistence and
partial outcomes. Workboard's task-plus-personal-reminder flow confirms task
identity first, then schedules with a separate immutable key; it can retry the
reminder or finish with the saved task without pretending to roll it back.
These are source-qualified contracts until the installed successor passes.
# Informational records and app-owned sections

Use `RecordSection` for a truthful informational card (title, optional icon,
heading level, action/default slots), and controlled `RecordTabs` for section
navigation. The owner supplies stable unique tab/panel IDs, current selection and
an awaited selection callback. Tabs support manual keyboard activation, logical
arrow navigation and Home/End. Keep panels mounted while hidden when their draft
must survive selection; await the owner's existing leave veto. The components do
not fetch records, infer permissions, register business contributions or persist
application state.

An author supplying a primary readonly body title can opt into the native
control-panel `recordBodyTitle` presentation. Ordinary forms, New, native
save/validation/revision handling and record traversal keep their defaults. Keep
an explicit Edit surface rather than pretending informational widgets are native
edit fields.

Partners demonstrates a **trusted, app-owned native seam**:
`registry.category("dev.local.partners.record_sections")`. A descriptor has a
unique namespaced `id`, plain `label`, finite `order` and Owl `Component`. The
owner passes the loaded native `record`, `readonly`,
`onAvailabilityChange({ available, summary })` and `registerLeaveGuard(fn)` (which
returns an unregister callback). Availability follows a fresh authorized read,
including after focus or identity changes. Report after initial mount; keep props
and callbacks stable so selecting a tab does not restart provider requests. Clear
old data on denial, ignore stale replies and hide unavailable providers. A provider
error must not destroy the owner's overview. No unavailable app is represented by
a fabricated zero or a placeholder finance summary.

This seam is not the frozen `ui.slots` protocol, which remains actions-only, and
does not grant access or sandbox trusted code. Other record-owning apps may expose
their own explicit content seam while reusing the same core cards/navigation.
Document the exact qualified owner/provider combination. Backend scope, current
capabilities, release identity and revision checks remain authoritative.
