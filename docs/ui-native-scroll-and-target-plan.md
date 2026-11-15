# Native action scrolling and shared preview targets

Activated15November2026 against core23/config21, root5752afe021a and private
Deliveryb413b58/Workboarde842edc/Documentsb057169, unchanged Partnersdcf85a6 and
Taskfiles7bbbd84. This plan precedes source changes. Continue the existing full
UI goal; no new framework, app domain, permission or compatibility policy.

## Actual finding and source cause

The normal three-app upgrade completed168.406s. Actual customer/task/pinned and
current brief, empty Sample, action titles and native/task viewer controls pass.
All18tables/full history/ten other sites remain exact with no business writes.
At390x845, the Related work card ends at942px and the native page at959px.
Wheel and PageDown cannot reach it: root scrollTop remains0, body overflow is
hidden, every native ancestor has overflow visible. This is clipped content,
not an intentional unsupported screen. New preview buttons measure27.3/23.82px.

`webclient_layout.scss` owns the useful native action layout but matches only
`.o_web_client > .o_action_manager`. The shared shell nests that manager inside
its protected `.mp-shell-action` slot; its native height/overflow/controller and
mobile delegated-scroll rules therefore never apply. Desktop form CSS partly
masks the omission; horizontal no-overflow is not vertical reachability proof.

## Coherent source change

1. Extract the existing action-manager block, including all child/mobile rules,
   into one Sass mixin in the same native layout file. Include it at the existing
   direct mount and `.mp-shell-action > .o_action_manager`, screen only. Keep the
   old declarations identical, including mobile form/container and delegated
   scroll behavior. Do not add overflow:auto to every ancestor or another scroll
   implementation. Custom AppLayout and dialog scroll owners remain theirs.
2. Increase shared related-record action targets:34px minimum on desktop and44px
   at narrow width; allow the title action to fill available row width, retain
   status space, long-name wrapping, logical properties and visible focus.
   Header actions also meet those sizes. No data/query/count/navigation change.
3. Reserve unpublished0.2.24/core19.0.0.2.24/web19.0.2.24.0. Only native layout
   Sass, shared surfaces CSS and three identity files ship. Keep all five exact
   app archives, SDK behavior, Python/locks, authority and schemas unchanged.

## Proof and normal execution

Compile actual old/current layout using installed locked Sass, actual native
media-only and Bootstrap breakpoint mixins. Compare compiled legacy declaration
maps and print output; new shell mount must receive the original layout while
old source has no matching rule. Compile RTL and shared surface CSS. Retain the
unchanged54core/80app Node proofs by source hashes, affected identity checks and
freeze. These are source/selector proofs, not browser layout evidence.

One immutable clean image with exactly five shipped deltas/no new JS exports,
unchanged five apps/Python and final-layer audit. Fresh normal10scope core plan,
independent exact review/approval, checkpointed apply and exact eighteen-table,
full-history, ten-site retention. Never replay preceding app/core operations.

Installed IAB: wheel and keyboard reach the last related-task action on native
customer/long Sample forms; native165-row directory/footer and three-page flow;
desktop/narrow/light/dark; measured target rectangles; custom Workboard task
dialog and Documents scrolling still work; named dialogs/focus remain. Zero
business edits, reset theme/viewport, close only owned transient tabs. Preserve
counterexamples. No full UI/RTL/zoom/contrast or formal accessibility claim from
this slice. Finish those original cards and final frozen canonical afterward.

The separate optional visual preference asks whether the customer reader should
become a compact relationship summary with native Edit. It is still pending;
continue this independent usability correction without inventing an answer.
