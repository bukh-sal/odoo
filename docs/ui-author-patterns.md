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
