# First rendered UI corrections

Activated15November2026 after the restart exposed working `mcp__cua_repl`
in-app controls. This continues the original D03/D05/D06 cards; it does not
replace them. The earlier capability blocker is cleared by an actual rendered
page, interaction and screenshot, not by opening a preview alone.

## Current evidence and scope

Baseline host304616b60b8, executable sourcea58c4c544c0, core0.2.12, web19.0.2.12.0.
Current populated18610/config6/image3b5188c6 and all five private app revisions
are unchanged. Private receipts/screenshots are `.local/ui-rendered-20261115-01`;
eleven target hashes, five private repositories and eighteen main tables were
verified before the round. The pre-existing user tab on18556 was untouched.

The actual native customer → related work → task → new-tab pinned Documents
journey works. Pinned version1 and current version2 previews differ as intended;
UI downloads are120and186bytes with the previously qualified distinct hashes.
The original task context remains open. Narrow390px task sheets and filters fit,
and Escape closes them and returns focus. No saved business or preference change
was made. These observations are bounded first-pass evidence, not full acceptance.

| Finding | Actual reproduction | Ownership and correction |
| --- | --- | --- |
| Task draft lost on Back | Edit task, type a temporary unsaved description, browser Back. Editor closes and customer work returns without asking. No Save was called. | Workboard: reuse the existing action `beforeLeave` hook and app-owned pending-dialog tracking already used by Documents. Cover task/list/stage editors, nested editor and comment drafts, saving/uncertain state and cleanup. Existing explicit Cancel confirmation remains authoritative. No browser persistence or business draft in URLs. |
| Native narrow context does not receive focus | Open Partners context at390px; Tab moves to global search, Escape leaves the context open. | Shared Shell: focus the opened context, handle Escape within the shell, return focus to its opener, preserve normal navigation and modified clicks. Reuse AppLayout behavior; do not change app permissions. |
| Dialogs and palette input lack accessible names | Real rendered dialog elements have neither name nor labelled-by; command combobox AX has no name. | Shared Dialog: label active dialogs from visible titles, label headerless callers explicitly, hide inactive stacked dialogs semantically. Palette: label its combobox and associate its actual listbox. Keep existing overlay, keyboard and close semantics. |
| Native Notes section is unnecessarily narrow on desktop | Native Partners form renders a short paragraph in a narrow grid cell despite available width; narrow mode already wraps it normally. | Partners: use the native group/field full-width declaration. Document the ordinary native pattern, not an app-specific core CSS exception. |
| Appearance cannot be selected from current core UI | User menu, Preferences and palette expose no light/dark switch; existing core templates already select dark assets from the `color_scheme` cookie. | Shared user menu: expose light/dark through the existing cookie/assets path, run the ordinary leave guard before reloading. No new theme engine, forced CSS or second host. Verify both rendered themes after normal rollout. |

Inspect current source before edits. Keep unsupported external vendor account
links out of the owned account menu; attribution/notices remain. Do not change
backend auth, grants, dispatch, release fences, data schemas, frozen contracts,
recovery or native maintenance policy for these presentation corrections.

## Implementation and qualification sequence

1. Reconcile first-pass receipts and prove all eighteen main tables and eleven
   targets exact after the unsaved-only checks. Record before/after screenshots
   and the failures truthfully. Keep all original captures, including early
   navigation captures taken before the asynchronous destination settled.
2. Implement the bounded generic web corrections first. Extend affected tests
   against actual production hooks/functions; prove the relevant new cases fail
   before the fix. Compile selected real Owl templates. Do not call source or
   mock evidence rendered acceptance. Reserve unpublished core0.2.13/native
   core19.0.0.2.13 and owned web19.0.2.13.0 for changed shipped bytes; verify those
   identities are unassigned. Record substrate changes in upstream-patches.
3. Keep all private app bytes/pins unchanged while building one clean core
   maintenance candidate with the existing five-app composition. Inspect exact
   source/core/web deltas and unchanged Python/app pins; normal stage, complete
   native-scope core-upgrade nomination, independent exact approval/checkpointed
   apply. Reload the current observer. No source injection, old image relabel,
   maintenance guard change, blind retry or recovery replay.
4. Then implement Workboard successor0.2.14 and Partners successor0.1.2, with
   matching native versions, meaningful affected tests and deterministic new
   archives. Preserve old archives/digests and independent licences. Use existing
   core APIs; no mandatory new core compatibility requirement for these app fixes.
5. Write the exact current-input app rollout subsection at activation. Build one
   successor app image on unchanged core0.2.13, admit only new archive digests,
   stage and normally approve/apply the two app upgrades. Preserve Documents,
   Delivery and Taskfiles bytes and all business/authority/document history.
6. Once source/private trees are frozen at the final corrected identities, run
   one canonical host regression for the new core. Preserve the previous936-test
   result as historical; do not claim it proves changed code. Independent build/
   installed browser work can continue while the same retained process runs.
7. Reproduce Back/forward/app-switch with dirty native/custom drafts: keeping
   editing retains text and URL/context; explicit discard permits navigation;
   saving/uncertain submissions cannot be silently abandoned. Verify one actual
   UI save under a separate exact row/revision intent, without repeating the old
   task807c0017 revision2 API edit. Check nested dialogs, labelled palette and
   native/context keyboard focus at desktop and390px.
8. Continue every original matrix row: matched light/dark/native/custom/screens,
   actual Arabic preference and restoration, mixed/long text, keyboard, real200%
   browser zoom, reduced motion, rendered contrast, current authority and zero/
   one/many apps. Measure the actual DOM viewport, not the requested override;
   viewport capability affects the selected tab and is reset at handoff.
9. Keep the full goal unaccepted until all cards have direct evidence. Preserve
   controls/candidate/source-free sites, original snapshots/checkpoints/images,
   private app boundaries and notices. Routine reversible UI settings use their
   normal controls and are restored; risky action-time confirmations remain.

Any newly exposed defect is recorded against its actual producer/consumer before
scope changes. No blanket support, formal accessibility, publication or production
claim follows from this corrective batch.

## Installed core0.2.13 finding and exact appearance correction

Normal operation3d12d9bd completed150.672s: configuration7/imageff5ace21,
verified checkpoint, all eighteen business/authority tables and full job/outbox
rows exact, five app pins unchanged. Actual installed context focus/Escape,
dialog names/modal state and named palette/listbox now pass. Selecting dark
changes the control to Use light appearance but still loads the light bundle.
The choice was restored through the normal UI; no saved business change.

The native `web/models/ir_http.py` reader returns light unconditionally. Follow
[ADR0089](architecture-decisions/0089-reviewed-native-appearance-reader.md):
correct that exact reader and attest only its full-file before/after source pair
in the existing core-maintenance validator, while preserving rejection of other
web backend changes. Add actual-method cookie/context tests and genuine planner/
independent-reconstruction positive and forged/unknown-source negatives. Reserve
new core0.2.14/native core19.0.0.2.14/web19.0.2.14.0; keep private apps unchanged
until its normal core upgrade completes. Re-audit source/image, normal exact
review/checkpointed apply, then actual native/custom dark assets and restoration.
Do not weaken the guard, add an overriding adapter or reload the old image as a
new version. The remaining app corrections and original matrix are unchanged.


## Actual native dark surface correction, core0.2.15

Core14 normal operation200f7e19 completed148.688s with checkpoint, full eighteen
business/authority tables and job/outbox rows exact; ten other target hashes and
five private app pins preserved. Actual dark selection now loads the existing
web.assets_web_dark bundle. The wider installed audit exposes fixed light
backgrounds/text in native tables, modal containers, native labels/title/input
and shared headings. Dark preference was restored to light, no business writes.

Before the app corrections, bridge the existing native Bootstrap table, dialog,
input, secondary button and dropdown variables to the shared semantic tokens in
the existing foundation stylesheet; inherit appropriate heading/label colors.
Scope this to screen webclient presentation. Preserve print, renderer behavior,
authority, fields and business data; no app-specific selector, palette or new
theme engine. Reserve core0.2.15/native core19.0.0.2.15/web19.0.2.15.0. Keep all
five private app bytes unchanged through one clean image and ordinary complete
core-upgrade review/checkpointed apply. Validate increasing native identities
and inspect exact CSS/manifests/SDK-version delta, layers and data. Then inspect
actual list/header/hover, native form controls/labels, custom task dialogs and
queries in both themes. Measure contrast from computed foreground/effective
background and retain matched screenshots. Only actual rendered evidence can
close these findings. After this correction use core15 (not historical13) for
the separately reviewed two-app successor build. Full original matrix remains.


## Two-app correction activation on installed core15

Core15 operation3bb12743 completed158.375s/current configuration9/imagef1532becf.
Actual native list/form labels/controls and custom headings/modal bodies now use
the semantic palette; light restored. Full matrix remains open, including dark
header close-icon contrast and native color-scheme/scrollbars to batch with the
remaining contrast review, not another build per individual observation.

Implement Workboard0.2.14/native19.0.0.2.14 only in its existing action/editor
registration and regression tests: one page-owned pending set, action beforeLeave,
editor/detail/nested tracker props, dirty/comment/saving/uncertain checks, cleanup
on unmount; existing explicit Keep editing/Discard boundaries remain. Prove the
new real-controller cases fail on the original source before applying the fix.
Partners0.1.2/native19.0.0.1.2 uses ordinary single-column native Notes group.
No storage/service/security/binding/dependency/compatibility or core API change.

After focused app checks, deterministic archive validation and separate private
commits, build ONE clean existing five-app policy with core15 byte-identical,
only two new app pins and the other three unchanged. Admit only those two exact
digests retaining the entire old catalogue/trust history; normal stage plus four
existing A/B upgrade scopes; review actual acknowledgments and exact hash before
register/approve/apply. Verify checkpoint, eighteen tables, full job/outbox rows,
ten other targets and installed module/artifact identities. Then actual dirty
Back/app-switch/keep/discard/nested-comment and native width checks on the new
image, narrow and desktop. No saved workflow replay or previous native-op rerun.
