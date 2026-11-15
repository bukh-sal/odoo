# Record experiences and shell cohesion

Owner clarification15November2026, against installed core0.2.28/config28. This
refines UI-D03/D05/D06 in the existing delivery goal; it does not replace their
data/authority/maintenance/recovery/interaction exit cards. Meridian remains the
starting reference, improved for spacing, real workflows and optional apps.

## Decisions

| Area | Direction | Current source and gap |
| --- | --- | --- |
| Directories | Coherent shared list/search/filter/selection/table/pagination patterns. Opening a row leads to its durable detail identity. | Native list already delegates its New callback to action-service `openFormView(false)`. Keep native load/sort/save/ACL behavior; do not force every app to implement a custom table. |
| Creation | Author chooses dialog, side sheet or full page. Choose from workflow complexity, not an automatic field-count heuristic. Small forms can create in context; complex creation can use a full page. | `FormViewDialog` and action `target=new` already exist, with native save/discard and optional expansion. Default list New still opens the form route; provide a consistent author-facing creation policy using those mechanisms. Separate create presentation from durable detail presentation. |
| Composite creation | A transaction may include related reminders or other useful steps in one guided experience. | Reuse real application services and explicit orchestration. Putting two operations in one dialog does not make them atomic; retries, idempotency, partial success and cross-app authority must follow actual backend semantics. No finance logic in core. |
| Record details | Informational first: identity/status/actions, useful overview, related work/content and activity. Explicit Edit owns the full native fields. | Current Partners compact native reader and full Edit provide the starting point. Do not rebuild the reader as disabled inputs or make tabs collections of forms by default. |
| Optional extensions | Record owner exposes ordered overview sections, tabs and actions. Companion apps contribute actual scoped content through an intentional seam. | Workboard's app-owned task-panel registry and Delivery's native widget/inherited view already demonstrate contributions. Generalize reusable navigation/lifecycle components, while the owning app defines its extension contract. No compulsory universal domain schema. |
| Customer example | Useful contact/organization summary; real work/activity. Finance/sales apps can later supply summaries, transactions or actions when installed and permitted. | Do not show fake financial stats, zero balances, unusable tabs or invented counts when providers are absent. Current Partners models/services must be inspected before offering additional contacts or new metrics. |
| Visual language | Replace legacy pink/purple branding and mixed icon families with a consistent neutral Meridian-derived system, semantic status colours and one modern icon family. | Current semantic tokens exist, but actual checksum text still inherits pink and measures3.546to1 dark. Native FA/OI icons and private app icons remain mixed. Audit real visible states, retain useful semantic danger/warning distinctions and attribution. |
| Sidebar | Remember desktop collapse per user and stable application identity; restore264px when expanded. Keep56px app rail. Always expose a labelled reopen control. | Native Shell and custom AppLayout currently have ephemeral narrow-only `contextOpen`. Native navigation already supplies stable `pluginID`; custom layouts need an explicit stable context key or validated action identity. Do not persist translated titles, business data or drafts. |
| Breadcrumbs | Quiet, styled path above the record title; clear separators/current item, sensible truncation/overflow and narrow Back. | Keep native `onSelected`/action leave guards and real URLs. Shared PageHeader currently has a raw breadcrumbs slot; native breadcrumb presentation differs. Add one reusable visual pattern rather than inventing new routing. |

## Meridian: carry and improve

Reference files inspected: `components/shell/app-rail.tsx`, `top-bar.tsx`,
`components/patterns/layout.tsx`, `features/partners/PartnerDetailPage.tsx`,
`Partner360Overview.tsx`, `PartnerBits.tsx` and `store/slices/ui.ts` in the owner's
dsf_exp_01 checkout. Carry the56px rail/264px context proportions, readable cards,
clear title/action hierarchy, compact overview, useful optional tabs and simple
chevron breadcrumbs. Improve cramped controls, long labels, the density and
technical copy in our integration panels, keyboard/RTL/draft behavior, and real
permission/availability states. Meridian's fixed domain `TAB_DEFS` and global
demo-store joins are design examples, not our generic extension or security model.

## Delivery order within the existing goal

1. **Shared shell cohesion:** pinned SVG icon primitive, palette/legacy-colour
   reconciliation, persistent collapsible context and native/shared breadcrumbs.
   Detailed plan: [shell cohesion](ui-shell-cohesion-plan.md). Preserve native
   routes/drafts and current app views; compare real screenshots to Meridian.
2. **Creation surfaces:** fresh source/contract plan at entry; dialog/sheet/page
   author choice, validation/cancel/dirty/uncertain behavior and optional full-page
   expansion. Demonstrate a useful small create and a richer guided create.
3. **Informational record composition:** fresh plan after creation findings;
   customer overview plus real optional sections/tabs/actions, independent Edit,
   deep-link/history/focus/current-authority/absence behavior. Start with existing
   real work/document providers, not a pretend financial implementation.
4. **Integrated qualification:** actual light/dark/Arabic/narrow/truezoom/keyboard/
   motion/contrast, changing authority and optional-app lifecycle, preserved
   populated maintenance/recovery guarantees, current eight-addon default and
   final frozen-source canonical. Earlier source checks are not installed proof.

Only the first section gets its implementation plan now. Later plans must use
the actual then-current source and findings. Record any limitation intentionally,
with its reason and possible route; inherited Odoo UI defaults are not a product
requirement. No publication/production or unknown-data cleanup.

## Icon research and provenance

Recommend Lucide SVGs through an Owl-native shared component, without React,
DOM-replacement scanning or a runtime CDN. The reference has locally installed
`lucide-react`0.468.0; its exact icon data and licence can be pinned and hashed
before vendoring a reviewed subset. Preserve its ISC and Feather-attribution
notice verbatim. Do not silently label it as the latest version or substitute
today's licence text for the pinned source.

Primary references checked15November2026: [framework-independent Lucide](https://lucide.dev/guide/lucide),
[accessibility guidance](https://lucide.dev/how-to/accessibility),
[upstream licence](https://github.com/lucide-icons/lucide/blob/main/LICENSE).
Use meaningful labels on buttons, decorative SVGs hidden from assistive tech,
consistent size/stroke/currentColor and appropriate RTL mirroring only for
directional controls. Shapes do not replace names, current state or authority.
