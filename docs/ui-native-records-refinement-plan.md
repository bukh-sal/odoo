# Native record frame and semantic refinement

Activated15November2026 from the installed core17/Partners1.3 critique, under
the original D03-D06 goal. Core17/app13 operations are complete; no replay.
Meridian `dsf_exp_01` partner-360 light/dark captures remain the reference.

## Direction and boundaries

Adopt its compact breadcrumb/context, clear end-aligned commands, legible record
sections and quieter metadata. Do not invent invoices, balances, addresses,
owners, avatars, tabs or cross-app counts that the installed app does not own.
The reference's audit also reports contrast, duplicate-create and dirty-save
failures; its claims and workflows are not platform acceptance evidence.

The current native form interrupts breadcrumbs with New, has icon-only dirty
save/discard controls, and presents a loaded-ID count as a total. Partners owns
its sparse one-column declaration; core must not rewrite an app's field layout.
Actual Notes textarea and column chooser are unnamed, and the collection title
has no level1 heading. Narrow list New wraps unnecessarily; the horizontal
scrollbar remains visually light in dark mode. These are the bounded inputs.

## Exact shared core batch (candidate0.2.18)

1. Select a record presentation through existing ControlPanel display config in
   FormController, disabled with its existing in-dialog/no-control-panel paths.
   Keep the existing breadcrumb, create, action, status, button-box and view
   switch slots. Put context first and commands at the logical end; use a
   separate compact navigation/tool row. Do not change editable/read-only mode,
   automatic save-on-leave, validation, revision CAS or create permissions.
2. Replace only the form's inherited Pager presentation with a shared
   RecordNavigation. Reuse TablePagination's pending/refused/error behavior and
   the actual existing FormController onUpdate producer. Say Record N of M
   loaded, not total matches; use bounded Previous/Next without wrapping.
   Table pagination and non-form Kanban traversal retain their own consumers.
3. Present the existing FormStatusIndicator mode with visible Saved/Unsaved/
   Invalid/Saving/Discarding state and text Save/Discard buttons. Guard duplicate
   pending commands; await the same callbacks, preserve false/refusal/errors and
   the model's own dirty state. Do not create a second save/persistence path.
4. Give the table Breadcrumbs an optional level1 title semantic, leaving form
   record headings in the actual sheet. Name and make the existing column chooser
   reachable in the normal keyboard order. Preserve native grid behavior.
5. In the existing useInputField hook, provide the current native field string
   as a browser-native title fallback when the caller supplies no title or ARIA
   name. Associated labels and ARIA retain their native precedence, including
   when an outside label changes without re-rendering the input component.
   Preserve readonly/absent controls and clean up only the owned fallback. Parsing, input preservation,
   onchange/commit/bus and data behavior remain unchanged.
6. Shared screen-only styles unify record actions/status, native outline actions
   and ordinary checkbox marks with light/dark tokens; preserve switch widgets,
   focus and indeterminate state. Keep the accepted rail/sidebar/font/row sizes.
   Remove the narrow table-action full-row width and explicitly theme actual
   scroll containers. No print, backend, schema, grant, runtime-policy or lock edit.

Use two fixed inventoried RecordNavigation exports in the existing backend
manifest; no new framework, package or registry. Source attribution remains.
Reserve unpublished platform0.2.18/core19.0.0.2.18/web19.0.2.18.0. Keep all five
current app archives unchanged for this normal full-scope core maintenance.

## Verification and useful return condition

Test the actual native record pager producer/save/load refusal and loaded-ID
scope, pending/error/refused navigation, actual status callbacks and model states,
and actual input-hook effects with labels/explicit names/dynamic labels/missing
controls. Keep table/route regressions. Compile real affected Owl templates and
locked Sass/RTL; prove the new semantic witnesses fail on the predecessor.

One clean immutable image: exact expected source/manifest delta, unchanged app/
Python identities and final-layer audit. Then normal stage/all-native-scope
core_upgrade nomination, exact independent review/approval/checkpoint/apply.
Preserve166global partners including the163owned Sample records, all other17
tables/full job/outbox history and ten other targets. Reload the fresh observer.

Verify installed list h1/chooser keyboard, labelled Notes, record navigation,
dirty status/save/discard/error retention, desktop/narrow light/dark and the
ordinary customer/task/document route. Any actual UI save needs its own exact
Sample-row/revision intent; never repeat the original task revision2 change.
Retain failed observations, restore appearance/viewport/drafts, show screenshots.

After this core batch, a separate legitimate Partners successor may use an
ordinary four-column contact group and retain revision as an invisible loaded
CAS field. Plan that app input against the installed result before editing it.
It must not require app-specific core CSS or invented business features.

The original Arabic/RTL, real200% zoom, reduced-motion, contrast, changing
authority, zero/one/many-app matrix and one final frozen canonical remain
mandatory. This batch is not a substitute for those phase acceptance cards.

The real Owl/TextField mount exposed a counterexample to the initial aria-label
fallback: adding an external label can patch the parent without re-rendering the
field, leaving that fallback inappropriately authoritative. Use the native title
fallback order from [HTML Accessibility API Mappings](https://www.w3.org/TR/html-aam-1.0/#accessible-name-and-description-computation),
not an observer per input or a second naming algorithm. This provides a fallback,
not a replacement for app-visible labels. The final installed accessibility tree
must show the actual Notes name; the test DOM alone cannot prove that mapping.
