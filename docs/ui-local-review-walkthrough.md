# Local shared-UI review

This is the retained disposable review combination, not a production deployment.
Current executable source is `748c5e32b3b4480ac7471b7b7a8a06301a26544b` /
core0.2.40. The [support record](ui-qualified-combinations.md) and
[acceptance matrix](ui-delivery-acceptance.md) state actual evidence and limits.
The final canonical regression is still pending at this record's creation.

## Open the retained sites

Use the **in-app browser**, as requested by the owner. Preserve the human main
site on18610 and any unsaved form there. Do not restart/bootstrap a site simply
because a stale tab needs a fresh authorized navigation.

* [Populated review18730](http://release-cd4dd6d48e72.localhost:18730/odoo?workspace=943892c1-f556-4771-aa8d-51410c1124a7): configuration16,
  immutable image `sha256:9335a01e023b1de8de0652732a946b1e77f2a492064a4cc38e79cc7756329854`.
  Partners0.1.10, Workboard0.2.19, Delivery0.1.10, Documents0.1.12,
  Taskfiles0.1.6. The existing owned review tab retains the native reader at
  the owner's200% page zoom; do not confuse it with a viewport override.
* [Empty source-free review18731](http://release-50bcf6e7bffa.localhost:18731/odoo?workspace=f5916da5-de2a-4064-8530-26f2e4963c37): configuration7,
  immutable image `sha256:d30bb72ef80ec59d3389eb85c6ffc7fd560f77890666121f2ffa2cf9f1a297a5`.
  Eight native addons, no executable optional app/archive/current binding.
  Removed-installation history and recovery material remain retained.

Existing credentials and synthetic fixtures are private; do not copy passwords
or session tokens into this guide, screenshots, a URL or a public evidence file.
Private durable state roots are `.local/development/ui-shell-cohesion029-01/`
and `.local/development/ui-final-core036-site-01/`. Use the current protected
target and fixtures there; no installer or credential reset is part of review.

## Useful walkthrough without new business writes

1. In18730, use the rail or All apps to open **Partners**. The list has a title/
   description, start-side search and Filters, end-side New, and below-table
   paging. The small current cohort has four records; the quiet single-page
   count is deliberate, not a fake page selector. Earlier large/grouped
   pagination evidence is linked from the acceptance matrix.
2. Open the existing organization with linked onboarding work. Its default is
   an informational reader; **Edit** exposes actual native fields. Use Overview
   and the optional Work section. Follow the existing onboarding task into
   Workboard, rather than creating another fixture. Native New/dialog creation
   and task-plus-reminder submission were already exercised; do not repeat them
   merely to inspect layout.
3. On Workboard, try search, Filters, Display and list/board. Clear the query
   after review. Open the task sheet and its existing document reference. The
   pinned brief opens in a separate scoped Documents tab; the task stays intact.
4. Compare pinned version1 and current version2. They are deliberately distinct;
   a newer current revision does not rewrite the pin. The qualified downloads
   were218B and302B with independently checked hashes. Close only your newly
   created review tab when returning, not a pre-existing user tab.
5. Collapse/reopen the contextual sidebar. Expanded width is264px; the app rail
   is56px. Preference is device-local per authenticated user/application; it
   does not store business state or change permissions. On narrow layouts the
   context becomes a transient drawer with a labelled opener.
6. Open the command palette with the normal search trigger; Escape returns
   focus. Test actual200% with ordinary browser controls, separately from390px
   responsive emulation. At200%, vertically scroll a row into view before
   clicking it; the native sticky header can cover previously scrolled rows.
   Wide table columns have a local horizontal scroller. Record readers/tabs and
   Workboard reflow without document-wide horizontal overflow.
7. In18731, verify truthful empty-workspace guidance. Account and own background
   jobs remain available. An old removed-app record link gives one friendly
   unavailable-page message; Close and choose a current page. No automatic
   retry or private server exception text belongs in that expected state.

Do not treat an informational reader as a write permission. Viewer/foreign/
revoked-member and stale-save checks were journaled and restored; review does
not require another authority mutation. A native Discard returns its loaded
snapshot; reopening reads a newer saved revision. Already downloaded/rendered
bytes cannot be erased by a later access change.

## What remains and what was retained

The exact final canonical process is bound in
`.local/ui-final-canonical040-01/{intent,source-freeze,process}.json`.
Observe that process to terminal; do not launch a second run on a timeout.
No source/test/app change is permitted while it runs. Documentation-only
commits are recorded separately from the frozen executable source.

Private current screenshots and measured receipts are under
`.local/ui-focus040-01/browser/`; the installed proof binds their observations.
Earlier design studies and matched Meridian/native/custom captures
remain in their original private audit directories. They are comparisons, not
production mock data or a new runtime dependency.

Both sites, old workers/helpers/images, checkpoints, failed diagnostics and
private application repositories remain retained. The current read-only resource
inventory is `.local/ui-focus040-01/retained-resources.json`; it is not a cleanup
authorization. No prune, prefix sweep, image force-removal or user-data deletion
belongs to this walkthrough. Exact cleanup requires reconciling current durable
ownership and sharing before a separately recorded operation.
