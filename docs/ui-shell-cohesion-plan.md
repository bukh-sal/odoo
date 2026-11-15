# Shared shell cohesion implementation plan

Activated15November2026 after the owner's record/shell clarification and current
source audit. Existing delivery goal remains active. Source core28/d1c041526cf,
docs2e0739e1b9a; current config28/image5bf1d698 and five app successors remain the
qualified control. All old failed candidates/checkpoints/11targets are retained.

The user is currently using the main site's creation route. Do not navigate,
reload, close or deploy over that tab or assume its draft is empty. Do not take
native Codex window input during human activity. Source and offline work can
continue. First visual iteration uses a separately owned preview; any rollout
must use a safe disposable target and fresh actual-data baselines, not overwrite
the user's working state or replay old mutation intents.

## Scope and implementation

1. Inventory visible icon uses in shared/native chrome and the real cohort. Add
   one `@web/interface/icon` Owl primitive with a reviewed pinned Lucide SVG data
   subset, exact licence/provenance/hashes, semantic names, consistent size/stroke,
   decorative default and labelled wrappers. Keep rendering declarative: no
   post-render DOM scanning, arbitrary HTML, network lookup or React runtime.
   Migrate shared rail/app chooser/palette/context, query controls, record/table
   paging, common New/Edit/Actions/breadcrumb/column controls and representative
   native/custom views coherently. Preserve old declared icon names through
   explicit neutral aliases where needed; unknown names get a named fallback.
   Inventory remaining legacy glyph users before retiring any font/assets.
2. Reconcile semantic light/dark tokens and the remaining visible legacy brand
   colours, including code/checksum text. Preserve semantic danger/warning/success
   distinctions and meaningful focus. Gather actual rendered contrast failures
   rather than blanket-replacing every pink hexadecimal (some are error colours).
3. Reuse the native `browser` storage wrapper and authenticated user identity for
   a small device-local boolean preference, scoped by site/user/stable application
   key. Native menu `pluginID` already exists; custom AppLayout gains an explicit
   stable key. No new server model/wire schema just for this preference. Storage
   unavailability/malformed/foreign values fall back safely. Never persist data,
   permissions, drafts or translated labels. Sync in-memory presentation across
   current native/custom context owners without changing app/record selection.
4. Keep264px expanded and remove the context column when collapsed; retain the
   permanent56px app rail and a clear labelled reopen button. Desktop preference
   persists across reload and app changes only for its own key. Narrow context
   remains a transient focus-managed drawer; desktop collapse must not strand
   navigation on a phone. Escape/selection/outside close and resize restore sane
   focus. No hidden mounted controls reachable by Tab; do not unmount business
   content or bypass pending-action/dirty-leave guards to change chrome.

   Source trace before integration: ActionContainer mounts exactly its current
   keyed component. Reuse Owl's existing portal into a shell-owned context-control
   slot so native and custom pages put their single toggle in the same topbar.
   AppLayout falls back to a local toolbar outside Shell/in dialogs; nested layouts
   do not inherit the global portal target. Actual mounted tests must prove portal
   removal on action teardown, no duplicate toggles and preserved work-area state.
5. Style native breadcrumbs and provide a reusable shared component for app
   PageHeader: quiet path, logical separators, current item, truncation/overflow,
   narrow Back and long/mixed-script names. Preserve native callbacks/real links,
   modified click/new tab, independent action history and dirty refusal. Don't
   reimplement routing or put business state into stored breadcrumb preferences.
6. Update actual custom AppLayout callers with explicit keys and shared icons as
   legitimate private successors. Bind source/architecture-only differences;
   models/services/CAS/grants/storage stay unchanged in this slice. Final record
   creation/composition API design belongs to its later fresh plan.

## Qualification and delivery

Use actual Owl components/native hooks plus fake storage/action boundaries to
exercise user/app isolation, reload, corrupt/unavailable storage, two context
owners, hidden focus, narrow/desktop transitions, dirty navigation refusal and
icon escaping/fallback. Preserve useful tests; add counterexamples before fixes.
Compile actual Sass/RTL and templates, compare unchanged print/unrelated behavior.
Do not repeatedly run a broad suite for cosmetic diffs; final canonical follows
the final integrated source freeze.

Prepare a real-code local visual comparison first: current versus improved shell,
expanded/collapsed native and custom contexts, breadcrumbs/long names, desktop/
narrow/lightdark/RTL. Show screenshots for consequential visual choices. Avoid
another wholesale speculative redesign; start from the actual Meridian visual
language and the owner's accepted roomier baseline.

Reserve next legitimate core/web/native identities only after checking; expect
core0.2.29 for changed shipped UI. Commit source before immutable build. Deliver
core-only with exactly the installed app archive bytes, then app successors via
normal separate admission/stage/review/exact approval/checkpoint/apply. The earlier
28 build-scope/Windows CRLF findings require archive digest preflight BEFORE a
core-only build; never silently accept/relabel same-version byte drift. Use raw
pinned Git/archive source bytes where source checkout conversion would change
identity, and keep all failed evidence. No runtime source mounts/injection.

Exit only after installed native/custom sidebar persistence, real breadcrumb and
icon routes/focus/dirty guards, colours/contrast,18table/history/current-authority
preservation and protected-site checks. No full UI acceptance from source tests,
mockups or this plan. Current true200%zoom/motion/current authority/optional absence/
current appfree/final canonical cards remain open.
