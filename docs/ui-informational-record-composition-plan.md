# Informational records and optional app contributions

Activated15November2026 after creation qualification on isolated18730/core32 /
config6. This is the next UI-D05 work item inside the full UI-D03–D06 goal;
the original matrix, current authority, app absence, recovery and final canonical
exit cards remain required. Main18610/human/new and all protected demos stay intact.

## Actual sources and intentional boundaries

Meridian's PartnerDetailPage, Partner360Overview and PartnerBits under the owner's
`dsf_exp_01/app/src/features/partners` provide a useful identity/actions header,
underline section navigation, relationship summary and optional work previews.
Keep the agreed larger type/spacing and264px context. Its hardcoded TAB_DEFS,
global demo-store joins, financial totals and unsupported owner/tags/website fields
are not our data model or authorization implementation.

Partners currently has a compact native readonly summary plus full native Edit;
its model already supports many people linked to an organization, but the reader
offers no contact preview/add action. Revision-aware PartnerFormModel owns CAS.
Delivery's CustomerWorkLink uses fresh current context, bounded customer_work and
record/generation checks; its native inherited view appends the widget. Workboard
already has a trusted app-owned task_panels registry. Reuse these proven models.

The frozen `ui.slots` protocol has kind=actions only; `/api/v1/ui/slot` resolves
and gates those declarations. Do not relabel a rich component as an action, change
that schema, or invent a generic core domain registry. Native record sections are
an explicitly app-owned trusted frontend extension seam. Core supplies reusable
navigation/cards and the existing native action/view/model machinery. This does
not sandbox trusted frontend/Python or confer authority.

## Coherent implementation

1. Add shared `RecordTabs` and `RecordSection` Owl presentation components under
   web/static/src/interface, using existing surface/ink/line/focus tokens and
   local SVG Icon. Append only their actual inventoried assets to the existing
   backend bundle; verify actual native asset consumer and frontend/minimal
   independence. Tabs take explicit safe unique keys/labels, selected key and
   owner's awaited selection callback; no plugin fetching, business state,
   browser persistence or permissions. Use semantic tablist/tab/tabpanel IDs,
   roving focus, logical Left/Right, Home/End and manual Enter/Space activation.
   Parent retains mounted panels while hidden so a contribution's draft is not
   destroyed merely by tab selection; an awaited leave veto must be respected.
   Card headings/actions are slots, counts are supplied real numbers only.

2. Native record header: expose an optional presentation flag for an author who
   supplies the primary body title. Such a reader gets one quiet breadcrumb path
   with chevrons/current identity and existing back/modified-link/leave behavior,
   rather than a separate repeated title row. Ordinary forms without a body title,
   New, dialogs, status/actions and native record traversal retain defaults. Use
   the existing action/display mechanism, not an app name in core. Keep the full
   native save, validation, revision and readonly/edit machinery.

3. Partners successor0.1.9/mincore33: own a native readonly overview widget, with
   actual record fields/native Field formatting and a clear name/type/status
   identity; relationship/contact details and Notes in shared informational cards.
   Full fields remain in explicit Edit/new. Keep PartnerFormModel and all backend
   models/services/schemas/security unchanged. Declare needed hidden native field
   dependencies in the owner view, including public_id, even without Delivery.
   Use a small app-owned `dev.local.partners.record_sections` registry for ordered
   trusted companion components. Owner validates stable IDs/order and rejects
   duplicate registration; it owns selected/focus/fallback state per record.
   Provider availability must come from its fresh authorized read, not presence
   in a JS registry. No inactive/unknown/forbidden provider tab or fabricated zero.
   Clear old content on identity/workspace/release/access change and ignore late
   replies. A provider failure must leave the ordinary owner overview usable.

4. Contacts are useful owner behavior, not a new platform domain. For an existing
   organization, use the normal scoped native ORM with the loaded record's exact
   context to read at most four people by organization_id/kind, display at most
   three and honest more-available guidance. Do not infer a total. Fresh owner
   `/api/v1/context` capability determines the Add contact affordance; native
   current scope/CAS/server guards remain authoritative. Use existing
   openRecordCreation with the compact native view and default_kind=person /
   default_organization_id=current native ID. On save refresh only the preview;
   never update the organization as a side effect. Open contacts through normal
   native actions/leave guards. New/foreign/unsaved identities and viewers cannot
   gain a write affordance. No copied workspace ID or direct technical ORM.

5. Delivery successor0.1.10/mincore33 and Partners>=0.1.9: register a real Related
   work section at the owner seam, preserving CustomerWorkLink's current backend
   checks, generation/identity protection and fresh checks before navigation.
   A bounded preview remains on Overview when useful; the Work section offers the
   existing real destination, without guessing totals or adding service methods.
   Retire the old append-only inherited view from new package declarations. The
   actual native ir.model.data._process_end removes obsolete non-noupdate XML data
   during module update; qualify its exact old view/XMLID disappearance and all
   surviving views before exposing traffic. Inspect before deleting source;
   source/data/import/asset ownership checks and archive inventory are required.
   No manual DB deletion or fake compatibility alias. Old archives/images remain.

6. Workboard successor0.2.19: correct the observed in-flight reminder prose so
   retry controls/guidance appear only after a failed/uncertain secondary outcome,
   not while it is saving. Keep the confirmed-task marker and every immutable
   key/retry/partial/authority rule. Use shared informational section styling for
   the existing task reader where it reduces technical clutter; keep actual
   optional panels and comment draft/leave behavior. Do not add fake finance,
   provider fields or a second registry/service implementation.

Reserve provisional core/web/native0.2.33 for the shipped shared components/header.
No platform backend, schema/freeze, dependency/Python lock or business migration
is required. ADR0094 records the exact trust/protocol boundary. If actual source
shows a supported contract change or missing guard, stop that dependency and
record the concrete counterexample before widening scope.

## Proof and immutable delivery

- Actual Owl/components/templates and native asset consumer; keyboard/focus,
  awaited tab veto, draft retention, unavailable selected-tab fallback, duplicate
  keys and stale provider replies. Pinned Sass/RTL, print/default form behavior.
- Actual app methods/source boundaries: scoped contact query/defaults/capability,
  create callback, reader/Edit/CAS, provider denial/unmount/focus refresh and no
  fake fields/counts. Preserve existing regression coverage. Workboard actual
  pending secondary promise must show saving without retry-only content; partial
  and uncertain tests continue passing. Deterministic exact archives/admission.
- Normal core33 build with ALL five current archives unchanged, all-layer/source
  audit and ten-scope core_upgrade/review/exact approval/checkpoint/apply. Then
  app-enabled image with only the three successors, exact admission retaining old
  catalog blobs, six A/B upgrade targets and fresh independent review. No source
  injection/guard bypass or replay. Verify every current original record,218B
  brief/pin, completed reminder/job/notice and full business history, current
  authority, checkpoints, other targets and exact retired-view removal.
- IAB on18730: useful Northline customer reader/real linked task, actual Add
  contact and durable contact reader, native Edit/cancel/stale guard, optional Work
  section and focus, task/reminder pending/partial presentation. Compare Meridian;
  desktop/narrow/light/dark, original Arabic/RTL/keyboard/zoom/contrast/motion
  matrix, current-authority and optional app absence remain explicit exit cards.
  Existing main human form stays untouched. Show screenshots at meaningful
  outcomes; do not claim polish from backend tests.

No universal third-party rich-slot wire/ABI, financial product or arbitrary app
compatibility claim. The supported result is the exact qualified native owner /
companion combinations. Document this seam so another native app can reuse the
same core patterns and intentionally choose its own content contract.
