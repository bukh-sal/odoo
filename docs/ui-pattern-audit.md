# UI-D01: inherited UI pattern audit and decision matrix

14November2026. Source baseline `043034d1ad7`. **Audit and recommendations only;
no platform UI implementation or visual acceptance.** Prior PP01..05 and UI-C01
qualification retain their recorded scopes. The user's rejected first visual
study is not the recommended direction. The replacement study starts from the
actual Meridian build, with small explicit refinements; see
[shared direction and screenshot packet](ui-design-direction.md).

## Findings that determine the direction

1. **Useful framework machinery already exists.** Native lists/forms/kanban,
   typed field widgets, pagers, search models, dialogs, dropdowns, popovers,
   tooltips, commands, hotkeys, localization and action navigation are present.
   Rebuilding these wholesale would discard useful behavior and regression value.
2. **Shared style exists, but adoption is fragmented.** The web addon has SCSS/
   Bootstrap variables and common controls. Optional `mp_shell` already defines
   a small `--mp-*` light/dark palette, page patterns, focus and native-view CSS.
   Those assets are coupled to an optional reference shell, not a complete
   documented design system shipped independently to current native/custom apps.
   Workboard and Documents consequently own separate root tokens/layout rules.
   This is a reuse/ownership/cohesion gap, not evidence of absent framework styling.
3. **The shell mixes navigation levels.** App launcher, app name/sections,
   workspace, company and user controls occupy the stock top bar. Workboard adds
   its own cross-app strip and contextual sidebar; Documents presents a different
   page structure. Native Partners has a third visual treatment. Users must learn
   where similar navigation/actions live in each app.
4. **Custom and generated UI must share the outcome.** Restyling buttons alone
   leaves native control panels, form sheets and custom app layouts inconsistent.
   The design needs both common components and a presentation bridge to existing
   native renderers, preserving their behavior.
5. **Meridian is a strong visual starting point, with bounded applicability.**
   Its latest v0.5 uses a56px icon rail, contextual sidebar, unified search,
   contextual creation and profile at the rail foot. Its initial specification's
   labelled rail/global create were superseded by v0.4 critique. Its business,
   permissions, search, badges, chat and activity are mocked. They are not platform
   capability evidence. Its prototype is desktop-first/LTR; its automated scan
   claims were read, not independently reproduced here.
6. **The first visual study failed user review.** A structurally reasonable
   shell is insufficient. The user rejected the independently styled proposal and
   instructed starting from Meridian's actual style. Its screenshot/style output
   was archived as rejected. The current study retains Meridian fonts, icons,
   components and shell, refining measured sizing/spacing/surface treatment.

## Evidence and reading key

Source inspection plus actual read-only browser navigation of UI-C01: Workboard,
native Partners list/form and Documents master-detail. Meridian actual tasks,
directory, record and task sheet were inspected. No production record was edited.

- Shell: [NavBar](../framework_addons/web/static/src/webclient/navbar/navbar.xml),
  [ControlPanel](../framework_addons/web/static/src/search/control_panel/control_panel.xml),
  [workspace menu](../framework_addons/mp_core/static/src/workspace_menu.js).
- Native views: [ListRenderer](../framework_addons/web/static/src/views/list/list_renderer.js),
  [FormRenderer](../framework_addons/web/static/src/views/form/form_renderer.js),
  [FormController](../framework_addons/web/static/src/views/form/form_controller.js).
- Primitives/services: [Dialog](../framework_addons/web/static/src/core/dialog/dialog.js),
  [commands](../framework_addons/web/static/src/core/commands/command_service.js),
  [notifications](../framework_addons/web/static/src/core/notifications/notification_service.js),
  [web core inventory](../framework_addons/web/static/src/core).
- Style: [web variables](../framework_addons/web/static/src/scss/primary_variables.scss),
  [asset bundles](../framework_addons/web/__manifest__.py),
  [optional shell stylesheet](../framework_addons/mp_shell/static/src/host.css),
  [host SDK](../packages/host_sdk/src/index.ts).
- Private app evidence: UI-C01 [qualification](evidence/G7/20261114-workboard-concept-01/qualification.json).
  Private Workboard source reuses Owl/Dialog/ConfirmationDialog and Bootstrap
  controls while defining its own tokens/layout/drawer CSS. Partners uses native
  list/form/search XML and app-owned revision controllers. Documents owns its
  library/version/privacy behavior.
- Local reference: `C:/Users/mesh/Documents/DSH_WS/ui_concepts/dsf_exp_01`,
  source `cecb81593036b5f332dd4302b99f10a884ccafcb`. Read current source plus
  `critique-v0.4.md`, `update-plan-v0.5.md` and `components/patterns/layout.tsx`.
  Original reference checkout remains untouched.

**Keep** preserves the useful behavior/implementation. **Restyle** changes its
presentation. **Rework** changes interaction/composition with explicit regression
proof. **Replace** substitutes a pattern while retaining required semantics.
Every row is a proposed disposition, not a claim that it has been implemented.

## A. Shell, navigation and context

| Pattern / current observation | Disposition and reason | Shared ownership and app freedom | Required implementation proof |
| --- | --- | --- | --- |
| A01 App launcher + horizontal app sections; custom app links duplicate switching | **Replace presentation** with Meridian-style app rail + contextual navigation. Retain useful action/menu resolution. One place for each navigation level. | Generic web shell; app-owned registered labels/icons/routes and optional sections. No fixed Tasks/Accounting/Chat list in core. | Native and custom apps; many/long translated app names; no-app core; keyboard/tooltip/More apps; current installation/feature visibility. |
| A02 Workspace selector currently opens a new scoped tab to protect forms | **Rework placement**, preserve its safe behavior initially. Same-tab workspace switching is a separate guarded interaction, not a cosmetic swap. | Authenticated workspace source remains generic; app drafts/context belong to their owner. | Membership changes, stale context, separate tabs, unsaved native/custom drafts, technical effects and current release checks. No ambient session workspace mutation. |
| A03 Company and workspace both shown in stock chrome, including disabled My Company | **Rework** visible identity to emphasize actual workspace. Company/substrate identity is not automatically the same concept. | Show company controls only when a real supported workflow needs them; preserve underlying data/model behavior. | Verify meaning/visibility from current services. Do not delete company fields/models just to clean the header. |
| A04 App menu subsections currently in top bar; custom sidebar per app | **Rework** into one contextual-nav pattern. Native menu trees and custom app destinations use consistent spacing/selection. | Shell owns the region; apps own sections/views/trees and their business counts. | Optional/no-sidebar app, deep menus, current selection, route reload, translated labels and mobile panels. |
| A05 Command service exists; Meridian combines app/action/record search | **Keep + restyle** command engine and one discoverable search surface. Start with supported app/command providers. | Apps register bounded providers with scoped server queries when needed. No universal read-all-records endpoint. | Keyboard discovery, result scope, focus/escape, current-authority checks, stale/empty/error states and large result bounds. Record search is not earned by a search-shaped control. |
| A06 Bare core has workspace selection and own jobs, no business dashboard | **Keep + restyle** honest empty/default landing. Do not copy Meridian's mocked attention dashboard into mandatory core. | Optional home/attention app or declared contributions may supply real content. | Zero apps, no workspace, suspended apps, operator/human scope; no fabricated counts. |
| A07 Global creation competes with contextual New; Meridian removed global create | **Keep contextual actions**, restyle hierarchy. A global create menu is deferred until a real cross-app need exists. | Page/app supplies primary action; shell does not invent create permissions. | One primary action per context; keyboard access; read-only states; destructive acknowledgments stay distinct. |
| A08 Native action stack/breadcrumbs and custom bounded URL hints | **Keep semantics, rework composition** into one page-header/breadcrumb pattern. Avoid duplicate app/page titles. | Generic action/history/focus service; apps own meaningful record/page labels and validated hint state. | Back/forward/reload/deep-link, filter/page/scroll context, missing/foreign record, no sensitive draft in URL. |

## B. Data and record workflows

| Pattern / current observation | Disposition and reason | Shared ownership and app freedom | Required implementation proof |
| --- | --- | --- | --- |
| B01 Native list has sorting/paging/selection/field widgets; custom task list has grouping | **Keep engines + restyle**, expose common list/group/selection/empty/header surfaces. Avoid rebuilding data behavior as a visual rewrite. | Native presentation bridge and reusable custom view pieces; app query/model remains authoritative. | Server paging/filter/count equivalence, selection across pages, column behavior, read-only/bulk actions, relational fields and keyboard. |
| B02 Native control panel packs actions/search/pager; custom pages arrange them differently | **Rework** consistent PageHeader + QueryToolbar + result navigation. Retain useful control-panel slots. | Shared composition; app chooses supported filters/views. No requirement to show every possible control. | Narrow wrapping, primary action visibility, filtered-empty/count truth, full labels, native/custom parity. |
| B03 Native search domains/filters/grouping; Meridian chips and saved views | **Keep search model, restyle filter affordances.** Treat saved-view persistence as separately scoped behavior. | Shared query UI can consume adapters; app declares query semantics and reusable defaults. | Exact native/custom query binding, clear/reset, permissions, scope/owner of saved views; no unbounded client-side search. |
| B04 Native form fields appear editable without a prominent initial edit explanation | **Rework edit-state clarity**; keep field/model/validation and supported save/discard machinery. Specify explicit edit/save versus declared inline autosave policies. | Common field/layout/edit-state language; app/view owns transaction semantics. | Native relational/required/conditional fields, dirty escape/navigation, concurrent CAS, uncertain outcome and no silent retry. No blanket save-policy change by CSS. |
| B05 Native form sheet/group/notebook vs custom drawer/detail facts | **Restyle shared typography/layout; rework record composition** where necessary. Use clear header, facts, sections/tabs and related contributions. | Record layout primitives available to any app. A customer360 workflow stays app-owned, not mandatory core customer logic. | Native form and complex custom record; long/localized values; missing optional providers; preserved actions/validation. |
| B06 Workboard board + inherited kanban behavior | **Keep + restyle** card/column primitives and visible stage policy. Real app stages remain semantic. | Apps own workflows/status transitions; shared visual board does not impose To do/Done models. | Drag and keyboard alternatives, precise drop restrictions, current revision, horizontal scrolling/empty columns and touch. |
| B07 Native Many2one/record selectors/date/number widgets | **Keep + restyle first.** Replace a widget only for an observed usability/behavior problem. | Generic widgets/localization; providers enforce scoped selection and permitted fields. | Foreign ID/privacy, keyboard/typeahead bounds, locale/timezone, mixed-direction data, invalid dates/numbers. |
| B08 Documents library/history/pinned revision preview | **Keep app behavior; adopt shared master-detail/file-detail presentation.** Meridian rich Docs editor is a different workload. | Common layout/preview states/actions; Documents owns bytes/version/quota/safety. | Actual pinned/current/history/download distinction, scoped bytes, no active unsafe preview; rich editing is not implied by matching style. |
| B09 Related records and customer/file panels are real optional integrations | **Rework shared link/tab/panel presentation**, preserve declared ownership/current-source authorization. | Named optional contributions; app/slot contracts own DTOs and semantics. No hardcoded Customer/Tasks/Docs tabs in core. | Provider absent/suspended/revoked, cached response denial, foreign record/title leakage, stale state and independent app usefulness. |
| B10 Discussion/activity/history differ between domains | **Keep domain semantics, share presentation** for actor/time/event/reference rows. | App-owned append/edit/retention/audit rules; UI pattern does not create a universal activity backend. | Correct authorship/time/locale and authority; correction/immutable history distinctions. No fake recency or guessed notification totals. |

## C. Controls, overlays and feedback

| Pattern / current observation | Disposition and reason | Shared ownership and app freedom | Required implementation proof |
| --- | --- | --- | --- |
| C01 Existing Bootstrap/Owl buttons/inputs/selects; app-specific overrides | **Keep behavior + restyle through shared semantic tokens/variants.** Stop each app inventing basic controls. | Platform CSS + optional Owl components; plain HTML/native views can share tokens. App business widgets may compose them. | Every state, label/error/help association, touch targets, contrast, reduced motion, read-only/disabled distinction. |
| C02 Dialog/ConfirmationDialog/dropdown/popover/tooltip services exist | **Keep + restyle.** Adapt useful implementations instead of replacing focus/positioning logic with hand-built CSS overlays. | Shared stable public UI surface over owned primitives; no arbitrary template strings in manifests. | Nested overlays, focus trap/return, escape policy, portalled tooltip collision, pointer and keyboard. |
| C03 Workboard sheet is an app CSS adaptation of a dialog | **Rework** first-class contextual Drawer/SidePanel on the existing overlay stack. | Shared close/focus/size/dirty hooks; app supplies authorized content. | Native/custom records, full-screen narrow behavior, footer visibility, scroll, safe discard/unknown outcome, record route restoration. |
| C04 Different empty/loading/error/permission feedback | **Rework** named common states with action guidance. No large application-specific artwork is required. | Shared visual/announcement primitives; apps supply truthful domain wording and recovery actions. | Empty vs filtered-empty vs unavailable vs denied vs unknown outcome; stale response fencing and screen-reader announcements. |
| C05 Draft decisions/conflicts/ambiguous writes already qualified in Workboard | **Keep semantics + restyle reusable feedback/choices.** Preserve explicit Keep draft/Load latest and immutable submission identity. | Common presentation and lifecycle hooks, app-controlled revision/idempotency semantics. | Actual saved conflict/draft, latest read failure, uncertain write and double-submit; no styling-only Saved claim. |
| C06 Native toasts and host notifications facade exist; Meridian has unified inbox | **Keep + restyle bounded notifications.** Defer unified attention/inbox semantics until supplied by real providers. | Shell handles display/announcements; owning app supplies metric, current scope and actions. | Bounded stacking/dismissal, important persistent errors, minimized/private data; no chat/bell badges without a real capability. |
| C07 Current ARIA booleans needed explicit strings in Workboard | **Rework shared toggle patterns**, not all boolean serialization. | Correct accessible Toggle/Disclosure/ViewSwitcher with native semantic adapters. | Actual DOM true/false, tab/pressed/expanded semantics, focus/disabled/name; preserve ordinary HTML boolean behavior. |
| C08 Visual identity and status currently mixed per-app palettes | **Restyle** one action hierarchy and semantic status palette. App accent is optional and subordinate. | Global core chrome/action/focus tokens; app chooses named semantic statuses and restrained scoped accent. | Labels accompany colour, light/dark contrast, colour-vision checks and consistent danger confirmation. |

## D. Foundation, extension and delivery

| Pattern / current observation | Disposition and reason | Shared ownership and app freedom | Required implementation proof |
| --- | --- | --- | --- |
| D01 Web Sass/Bootstrap variables + optional shell CSS tokens | **Rework ownership** into a standalone generic token/component foundation, then bridge native Sass/widgets. Reuse useful existing definitions. | Available without private apps or optional Notes shell. Prefer existing web presentation ownership; exact package/API location is an implementation decision. Default8-addon core remains8. | Empty core + native list/form + two custom apps; no mp_shell/Notes dependency, selected-file/all-layer packaging, no CSS leakage. |
| D02 Meridian Geist/JetBrains typography vs inherited system fonts | **Retain Meridian typography as visual baseline**, make a deliberate font/license/Arabic-fallback decision before production shipping. | One platform type scale; apps may use named semantic variants. No copying fonts without notice or assuming Latin Geist covers Arabic. | Real glyph/weight/fallback/200% zoom/long-label checks; offline/local assets and preserved licenses; no unsolicited CDN. |
| D03 Desktop density with many fixed small controls | **Rework measured density scale**, retain Meridian compact rail/layout. Current study compares40/44px rows and28/34px primary action. | Shared density/control tokens, not ad hoc per-app zoom. Coarse pointers get appropriate targets. | Same viewport comparison, keyboard focus, realistic data/long labels, table/board/form and narrow target measurements. |
| D04 Theme/locale APIs exist in optional host; native/custom styling not unified | **Keep useful APIs, rework common token application.** No mandatory second host or theme engine. | Generic theme/locale service; framework-neutral CSS for all apps and native renderer adapter. | Light/dark switch consistency; no inherited frozen facade drift; clear migration for changed public contracts. |
| D05 Meridian prototype is LTR/desktop; many physical CSS directions | **Rework responsive/RTL patterns deliberately.** Do not qualify them from attractive English desktop screenshots. | Shared logical layout, bidi/locale helpers and accessible app/content regions. | Actual Arabic mixed identifiers/dates, long labels, narrow/zoom, keyboard; immersive pages retain clear exit/context. |
| D06 Public host canLeave/draft APIs vs custom/native navigation hooks | **Keep and reconcile lifecycle semantics** before unified navigation. | Host owns transition orchestration and ownership; apps own minimized in-memory drafts. Business content is not automatically persisted to localStorage. | Cross-app/workspace/back/reload, native/custom safe leave, expired scope/release, no secret/foreign draft leakage. |
| D07 Styling a private prototype is not a supported app UI contract | **Rework documented reusable API/catalogue**, with ordinary examples and source adapters. | Semantic CSS tokens + Owl components/pattern recipes; custom HTML may use tokens without a second framework. No React/Tailwind migration just to match a screenshot. | Two independently owned consumers plus native views; ordinary authoring guide; visible states/theme/RTL catalogue and defined versioning boundary. |
| D08 Sass incompatibility found after native install; build source tests missed it | **Rework earlier asset validation** as a delivery prerequisite. Retain late actual runtime checks. | Generic build/operator validation; separate compiler modernization decision. | Real selected app assets/native context before mutation; compile failure prevents install mutation; locked/offline build and runtime validation remain. |

## Gate disposition and next work

The pattern audit and reference-source comparison are complete in the stated scope.
The visual direction is **pending user judgment**, especially after rejection of
the first draft. No new implementation/visual/accessibility gate is passed.

Recommended subsequent outcomes, each with a fresh detailed plan when activated:

1. Confirm the Meridian-derived visual baseline and measured density changes.
2. Establish generic semantic tokens/catalogue and native presentation bridge.
3. Deliver the common shell/navigation/edit-safe overlays without losing scope.
4. Migrate native Partners and custom Workboard/Documents to the shared patterns.
5. Qualify the coherent end-to-end journey, Arabic/RTL, zoom/narrow/keyboard,
   contrast and real install/upgrade/recovery effects for the changed boundary.

No broad data behavior rewrite or speculative universal UI framework is authorized
by a pleasing prototype. Shared visual support is intended for all apps; optional
business features remain in their owning apps. Exact new public contract changes,
identity/build implications and source removals require their normal reviewed
implementation/qualification rather than a silent styling patch.
