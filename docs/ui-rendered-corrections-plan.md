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
