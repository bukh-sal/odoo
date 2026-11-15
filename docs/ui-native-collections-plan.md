# Shared native collections: header, query tools and pagination

Activated by the owner's15November2026 screenshots and explicit layout direction.
Continue the existing UI delivery goal; no replacement goal or new UI framework.
The two already prepared app corrections finish their normal rollout first.

## Direction and reference review

Keep the accepted roomier Meridian shell,56px desktop app rail and264px context
sidebar. Replace the inherited native list composition rather than cosmetically
restyling its range-and-two-arrows pager.

| Reference inspected locally | Adopt | Leave out of this change |
| --- | --- | --- |
| Meridian `dsf_exp_01`, Partners list source and v0.5 light capture | Distinct page heading, optional description, create action at the logical end, quiet bordered collection | Redundant segment/sidebar/query mechanisms and large always-visible sort/filter controls |
| Bootstrap/Folio pagination component and gallery capture | Bounded first/current/neighbour/last page window with inert ellipses, selected page and retained query context | A long button for every result page or React/runtime dependency |
| Bootstrap Fluent reference, table source and desktop capture | Clear applied scope, accessible selection, restrained toolbar, bounded table overflow | Extra comparison/column-management ribbons on an ordinary two-column collection |
| Bootstrap Fumadocs reference, business-table query source and design/source notes | Separate query tools, explicit filter state/clear action, neutral semantic styling | Documentation layout or importing its private table renderer |
| Fuma multiapp, customer source and final light capture | Title/actions row, start-aligned query row, table and bottom results/paging row | Another app switcher, fixed outer rounded workspace or session-only demonstration services |

These are design references, not backend/security contracts or runtime packages.
Do not copy application models, mock services, audit claims or whole theme bundles.
Retain existing provenance/notices; record any actually adopted source separately.

## Required anatomy

1. Page title remains visible at the start of the content header. The reusable
   heading can show an optional plain-text description; do not invent a new
   business description or duplicate the native title/breadcrumb.
2. The primary create action sits at the logical end of that header, with a plus
   icon and meaningful accessible text. Preserve create permissions, busy/edited
   state, normal action callback and access key. Do not add an Import command
   where the application does not supply one.
3. Search and a named Filters disclosure sit at the start of a separate row
   immediately above the table. Preserve native search facets, groups, favourites,
   applied filter state, clear behavior, sort and selection actions. Avoid a
   second search/filter system or duplicate hidden focus targets.
4. Table data sits in the shared native surface, with bounded horizontal overflow
   on narrow screens and native semantic headers/cells/selection retained. Remove
   artificial empty filler rows; do not replace the table with visual-only cards.
5. Below the table, show the actual result range/count and accessible numbered
   pagination: Previous, bounded page window/ellipses, Next. No wrapping from the
   last page to the first. Current page uses aria-current; ellipses are inert.
   A single page needs a quiet count, not a redundant range editor and arrows.
6. Logical start/end and arrows work in RTL. Narrow/zoom layouts wrap without
   dropping the title, search, primary command or footer; use44px touch targets
   where controls need them. Keyboard focus remains meaningful after loading.

## Producer/consumer implementation route

The current ListController already publishes exact offset/limit/count/onUpdate
through usePager. Its callback saves or refuses an edited row before loading,
retains current model/domain/order and scroll behavior, and exposes fetchCount
when the count is limited. Keep that producer and callback contract.

Implement one reusable TablePagination in the existing shared interface assets.
Use the actual model values and existing onUpdate/fetchCount callbacks. Provide
pending/error handling; prevent duplicate requests and preserve the displayed
page after a refused save or failed load. Do not turn a cancelled save into a
successful page transition or bypass current authorization through raw RPC.

Where the native count is a lower bound, do not fabricate a last page or an exact
total. Show honest current/previous/next controls and an explicit count action
using the existing fetchCount path if useful. This retains intentional bounded
query cost; an always-exact arbitrary database count is not silently promised.

Update the owned native list/control-panel/layout templates/controllers to use
the title/actions/query composition and place the shared pagination below the
renderer. Use existing slots/display configuration; preserve form controls and
record-to-record navigation separately. Trace grouped-list and embedded x2many
table pager consumers, place their pager below the corresponding table/group,
and retain their real page/selection/edit callback scopes. Do not globally replace
the generic form record navigator with a table page number.

Expose the same component/pattern to custom applications and document its input,
failure, limited-count and focus behavior. No app-name branches, arbitrary layout
registry, storage schema, service API, grant, authority or search-model rewrite.

Batch the already observed remaining dark close-SVG/native color-scheme issues
with this next shared-core presentation successor. Inspect the current source
before selecting the exact diff/version; keep app pins unchanged during core
maintenance. No new image per individual cosmetic observation.

## Verification and rollout

Before implementation, record the final source map/callers and chosen exact
templates, current core/app pins and expected delta. Add meaningful real
controller/component tests for page boundaries/window/ellipses, query/model scope,
pending/refused-save/failure, limited count, grouped/embedded tables and keyboard
semantics. Compile actual Owl/RTL assets. Native controller/auth/data behavior
must remain intact; source tests are not rendered acceptance.

Reserve a legitimate new unpublished core/web identity, build one immutable clean
candidate with unchanged app archives, audit exact source/layer deltas, then normal
full-scope core upgrade review/approval/checkpointed apply on the owned site. Never
replay any completed operation or inject live addon/frontend source.

In the actual in-app browser show before/after native Partners and another native
collection, title/create/search/filter alignment, one/many pages, empty/filtered
results, selection/grouping, pending edit/save refusal, Back/forward and actual
queries preserving filters/sort. Use scoped synthetic data or a separate owned
fixture intent if multi-page data is required; preserve existing records. Capture
desktop/narrow light/dark and RTL/keyboard/zoom with measured viewport and contrast.
Bring screenshot-backed visual judgments to the owner. Retain the full original
matrix and one final canonical run once executable sources are frozen; do not
claim this layout alone completes D03-D06.


## Exact implementation activation on configuration10

Source63b63297/core15, current imagef04b6f534/config10 and app upgrade391e9079
are terminal. Ten other targets/eighteen tables/full history remain exact.
Private Workboard717c788/0.2.14 and Partners6a4da83/0.1.2 are installed.
Reserve previously unassigned core0.2.16/web19.0.2.16.0/native19.0.0.2.16.

Use ControlPanel's existing display configuration for a table presentation
variant selected by native ListController; keep the non-table template intact.
Reuse its native breadcrumb/action/selection/view slots, with an end-aligned
create command and separate start-aligned query row. Factor the existing view
navigation fragment once, without a table header pager. Keep list search visible
through an optional alwaysVisible argument on the existing search-bar toggler;
other callers retain defaults. Name the existing filter disclosure visibly.

Retain usePager's current model callback producer. Pass its reactive props into
ListRenderer's optional pagination input and render TablePagination immediately
after the actual table INSIDE the existing scroll container, preserving native
scroll/history export. Group pagers move to a following group footer row.
x2many lists pass their OWN pager props; their Kanban/form-record navigation is
separate. Remove blank filler rows, retain actual create/aggregate rows. Add only
the two fixed interface JS/XML exports to the existing manifest; style them and
the table frame in shared CSS. App backend/source/artifact pins stay unchanged.

Actual browser testing now proves dirty Back keeps the Workboard editor/text,
but the router commits the destination URL before the leave refusal. Correct
this in the existing router/WebClient path, before menu/action loading: preserve
the last committed presentation route, attach positions to newly owned browser
history entries, undo a refused known Back/Forward without loading/discarding,
and cancel a rejected internal-link route. For a legacy entry lacking a position,
restore the visible committed route in place; document that exact pre-upgrade
legacy history-stack preservation is not proved. History positions are navigation
metadata, never workspace/actor/permission authority. Test refusal, acceptance,
known Back/Forward, legacy fallback and stale event handling. Never bypass the
existing action or authority guards.

Batch native light/dark color-scheme and close-SVG contrast in the existing theme
files. The Notes single-column app declaration expands width but puts heading
and field in one grid row; retain this failure and queue a normal full-span field
app successor after core16. Do not silently relabel its installed0.1.2 archive.

No new source is accepted by documentation: actual Owl compilation, meaningful
source/controller tests, exact image/layers, normal checkpointed core maintenance
and the original actual in-app interaction/visual matrix remain required.

## Installed critique and next refinement (core17)

Core16 was normally installed as operation7c6d0472, configuration11. The actual
in-app list now has the requested title/end create/query/footer anatomy. Empty
filter results and removing the filter work; dirty task Back preserves both text
and the exact task URL, followed by explicit discard. These are bounded installed
results, not completion of the original visual matrix or live many-page proof.

Keep the local Meridian light/dark Partners captures beside the installed screen.
Its quieter uniform rows and clear header hierarchy are useful; do not copy its
duplicate tabs/sidebar choices, fabricated avatars, balances or ownership fields.
Our list is still overly banded and heavy. Grouped dark headings are unreadable
because the native template applies fixed text-black/text-body utilities; search
chips retain a fixed light surface. A native task dialog also exposes a purple
primary button because the shared action mapping is scoped too narrowly. Group
pagination incorrectly calls its group count records. Preserve these screenshots.

Next reserve unpublished core0.2.17/web19.0.2.17.0/native19.0.0.2.17, leaving app
pins unchanged: map native group/facet/action presentation to shared semantic
tokens, remove fixed conflicting colour utilities in the owned templates, use
quiet uniform table rows with hover/selection retained, lighter header typography,
consistent36px desktop query controls and44px narrow primary/query targets. Keep
query input shrinkable beside Filters. Add an explicit grouped-count presentation
flag to the existing pagination producer/consumer; no query/count/model changes.
Actual narrow dimensions must be measured; viewport emulation is not real zoom.

Compile and test the affected real templates/component/producer, then one exact
immutable build and normal core maintenance, followed by paired actual light/dark
group/filter/dialog and narrow captures. Fix Partners Notes in its ordinary
full-span native declaration as the next legitimate app successor, separately
from this unchanged-app core maintenance. No live source injection or relabelling.
