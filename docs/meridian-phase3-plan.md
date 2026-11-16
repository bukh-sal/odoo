# Phase3: real Pages authoring, sharing and recovery

Activated16November2026 against source1b3dfcd951f/core56 and the installed
phase2 review. One active implementation item is now this phase's prerequisite
and Pages vertical slice. Phase2's manual visual gates stay open in
`meridian-phase2-review.md`; milestones remain1/5. This development overlap
does not waive those gates or change the five-phase objective.

## Result to deliver

Build a private installable `dev.local.pages` application, native addon
`mp_pages`. Someone must prepare an onboarding handbook, organize child pages,
write formatted content, share with a coworker, receive a durable comment,
review/restore a prior revision and open a real related record. Reload and a
new session must retain the work. Review usefulness and interaction, not merely
API success. Keep the existing Documents file library independently useful.

Use Meridian's actual Docs composition and controls as the reference: Home
cards/recent writing/templates, filtered page tree, page cover/icon/title,
centered prose, compact toolbar, slash insert, block actions and a right
Outline/Comments/Info rail. Preserve its fitting details. Use our approved
roomier shell/sidebar, stronger targets, below-table pagination and quieter
shortcut treatment. Never display simulated saved state or dead app actions.

Reference revisioncecb81593036 is unchanged. Acme39 stays open and reference48
now shows `#/docs/doc-handbook`. Source audit covers `features/docs/DocEditor`,
`DocsIndex`, `DocsSidebar`, `DocPanels`, `PageRail`, `insert-commands`,
`docs-workspace.css`, `doc-access`, plus the installed component seams.
The handbook screenshot/AX tree are in `.local/meridian-pages-reference-01/`.
They are prototype evidence, not installed Pages evidence.

## Findings that determine the architecture

1. ContextNav already supports recursive children, disclosure, loading and real
   links. Reuse it; do not create another generic tree framework. Existing
   AppLayout, PageHeader, BreadcrumbTrail, RecordLayout, Dialog, Icon, Badge,
   StatusMessage, TablePagination and scoped action/leave hooks supply the frame.
2. Meridian uses Tiptap; React is its wrapper, not an editor requirement.
   Use the headless editor inside Owl. The initial production pin is the
   currently documented3.31.3 family, with exact locked dependencies, licenses,
   integrity and counterexample tests before vendoring. Do not copy the reference's
   dependency tree blindly or ship React/Tailwind. Current docs show the plain-JS
   entry point and JSON persistence ([installation](https://tiptap.dev/docs/editor/getting-started/install/vanilla-javascript),
   [persistence](https://tiptap.dev/docs/editor/core-concepts/persistence)).
   The reference cache has2.27.3. Its advisory metadata/backport discrepancy is
   recorded in [issue8339](https://github.com/ueberdosis/tiptap/issues/8339);
   the [attribute advisory](https://github.com/ueberdosis/tiptap/security/advisories/GHSA-cp6q-959q-f8rh)
   and [Markdown advisory](https://github.com/ueberdosis/tiptap/security/advisories/GHSA-j95f-988m-3j2f)
   must be checked against the exact chosen lock. No general security-clean claim.
3. The ordinary JSON gateway is64KiB (`mp_core/controllers.py:bounded_body`).
   Do not arbitrarily shrink useful pages or increase that global contract.
   The existing registered binary gateway supports application-owned bounded
   bodies up to8MiB,4096-byte metadata and current actor/workspace/installation
   guards. Use that seam for content save/read; keep metadata operations small.
4. Per-page access can be app-owned today, but supported restore only overlays
   current principals/memberships/operators/integration grants/native auth.
   It does not preserve arbitrary app ACL revocations. Native-auth recovery
   preserves user/group membership, not arbitrary new group/policy definitions.
   Sharing cannot be accepted with that gap hidden. Add the generic resource
   authority capability below; do not put Pages tables/names in recovery.

## P3.0: generic resource authority prerequisite

Write the ownership/security ADR before code. Add two domain-neutral framework
models in mp_core: a resource policy and its principal capability grants. Bind
each policy to installation, workspace, declared owning model/resource UUID,
owner principal, state and monotonic revision. Grants use declared app capability
IDs, not Pages-specific roles in core. Page roles are app-provided label/group
mappings. The default eight-addon core contains zero resource policies and no
Pages permission definitions, content, editor, model or application navigation.

Provide private trusted-native helpers for registration, current capability
checks, readable-record filtering and CAS policy changes. Derive actor and scope
from the authoritative native context. Validate owning model/plugin metadata,
current installation/feature, active membership, subject eligibility and exact
resource/workspace binding. A grant never widens the workspace/app/technical
action ceiling. No arbitrary model dispatch or browser-writable policy model.
Keep ordinary direct/native CRUD on policy models unavailable. Native app authors
must apply the helper to searches and direct reads, not only a UI DTO endpoint.

Before committing to the exact query seam, prove it against actual WorkspaceScoped
`_search`, `_check_access` and read-window behavior: no foreign results/counts,
relation/title leaks, cached read bypass, ordinary-RPC writes or forged context
markers. Use parameterized owned predicates, not client SQL. Pages uses private
mutation markers and CAS for its own writes, as the existing independent apps do.

Policy changes and authorized content mutations lock the same policy row.
A committed revocation before a stale writer acquires it must cause normal
transaction retry/fresh denial, not a stale permitted write. Test policy updates,
feature/membership loss and content writes in both orderings. This is trusted
native enforcement, not a plugin sandbox claim.

Extend existing current-authority read/canonicalization/overlay/continuation/
resume checks with the fixed generic tables and public identities. Missing
current grants fail closed; preserve tombstones. Never restore old grants over
new revocations. Reconcile by stable keys, verify the resulting digest and keep
traffic closed on mismatch. No dynamic app SQL, host app imports or per-app
recovery adapter. Legacy schemas are explicit: both tables absent on a verified
pre-feature core is distinct from partial/missing tables on a current core.
Do not weaken old frozen decisions or silently invent legacy evidence.

First proof matrix: empty old schema, complete new empty/populated schema,
partial schema refusal, foreign model/workspace/installation/principal,
unknown capability, stale generation, current revoke after checkpoint,
post-overlay mismatch and fresh continuation/resume binding. Prove the source/
SQL/model closure and a real native core transition/app-free zero-policy state
before installing Pages. The first thin real Pages model/service supplies the
populated-policy installed consumer; do not invent a second disposable framework
just to test this API. Its revoke/write/restore/current-authority proofs must
pass before sharing/recovery is accepted or the cohort is presented as qualified.
Use a compatible immutable successor (next available core57 identity after
rechecking allocation). Preserve all56 images, decisions, data and demos.

## P3.1: private model, content and command contract

Create a private application repo only after its destination is verified absent.
Follow the existing private app license/notice conventions, retaining third-party
notices; no publication or paid service. Register typed `dev.local.pages` services
and normal navigation/client actions. All schemas stay app-owned.

Use app-owned models for Page, immutable Revision, Comment/Thread, per-actor
preferences/recents, templates and submission receipts. Public UUIDs identify
records. Page has title, parent, cover preset, icon, draft/final status, trash
state, revision/head revision and a generic policy binding. Immutable revisions
retain canonical structured content, digest, author and server timestamp.
Never normalize or overwrite old revisions. All reads/search/counts/exports,
native RPC and related records enforce current page access and workspace scope.

Page access is independent of parent access, as in the reference. Explain that
moving a page does not change sharing. A readable child must not reveal an
unreadable parent's title/path. Creation/move requires edit authority for the
target structural parent; prevent cycles, self-parent and cross-workspace moves.
Trash does not silently delete or repermission descendants. Hidden/trashed
ancestors do not make otherwise readable descendants disappear forever.

Start with workspace-readable/owner-and-explicit-contributor-editable pages.
Restricted pages require owner/admin or explicit grants. Workspace administrators
retain the documented management override; do not promise privacy from them.
Viewer/commenter/editor are Pages capability sets under the base workspace
ceiling. A workspace viewer remains read-only; a workspace editor can be a
page-only commenter. A page grant cannot override workspace/feature loss.

Save structured JSON, not arbitrary stored HTML. Positive node/mark/attribute
schemas cover paragraphs, three headings, lists/tasks, quote, code, divider,
tables, links and declared record references. Reject unknown attributes,
prototype keys, executable URLs/HTML and excessive depth/node/byte counts.
Initial content bound:1MiB canonical UTF-8 JSON per revision; measure the actual
editor/transport behavior before finalizing node/table/workspace-history quotas.
Every bound needs a stated resource reason and a useful UI error, not a quiet
64KiB page limitation. No silent history pruning.

Content body save/read uses the existing BinaryEndpoint. Metadata includes page
UUID, expected revision, stable submission key and digest; upload output is a
small typed receipt. Read a revision body by opaque revision UUID after fresh
page access. Metadata list/detail/history operations omit full bodies and remain
bounded/paged. Keep attachment/no-store semantics; the app fetches and parses
authorized JSON rather than asking the browser to render active HTML.

Freeze each mutation payload/key until its outcome is known. Same key+same hash
replays only after fresh authority; changed payload refuses. Serialize autosaves,
coalesce subsequent typing and use a CAS revision. A timeout holds the draft and
offers receipt reconciliation; do not create a fresh identity or claim Saved.
Conflict retains local content with explicit latest/copy/reapply choices. Do not
silently overwrite a coworker's winning revision or call local undo recovery.

## P3.2: real Home, tree and editor

Implement one coherent first authoring package, not many cosmetic successors.
Reuse core tokens/primitives; keep editor engine, domain code and schema in the
app. Add only genuinely generic reading/prose tokens/styles to the shared
foundation, with no Pages/editor-engine selectors in core. ContextNav already
provides the nested tree. Prefer existing composition slots to a new framework.

| Reference region | Real implementation |
| --- | --- |
| Library/navigation | Home, All pages, Recent, Favorites, Shared with me, Templates and Trash; scoped counts, tree/filter, child creation, stable deep links/Back/modified-click and remembered disclosure. No global unread/title leak. |
| Home | Pinned cover cards, useful recent rows, template previews and an actual searchable/paged archive. Honest empty/search/error/denied states. Server counts and per-actor preferences survive reload. |
| Page identity | Cover presets/icon, accessible editable title, author/time, draft/final, real saved/saving/conflict status. Avoid a duplicate title and technical In-memory badges. |
| Writing canvas | Reference760px measure/15px prose/1.75 line rhythm, adapted to shared approved density, light/dark and logical direction. Toolbar/selection/focus remain usable without pointer hover. |
| Editing | Bold/italic/strike/code, heading1-3, bullets/numbers/tasks, quote/code block/divider/table/link; real undo/redo, slash menu/toolbar insert, block move/duplicate/delete with keyboard alternatives. Local editor instance is destroyed cleanly. |
| Inspector | Outline anchored to real headings, durable comments and Page info/history/links. Wide right rail; narrow dialog/sheet with focus return. No permanently visible keycap strip. |
| Saving/leaving | True serialized autosave, explicit Save shortcut in help, pending/unknown/error feedback, same-submission reconciliation, guarded navigation and preserved drafts on refusal. |

Use headless Tiptap with a local locked build; no CDN/runtime network, React,
Tailwind, paid extensions or hosted collaboration. Retain dependency/license
inventory and bundle hashes. Test the actual editor with its real extensions,
selection and commands in addition to Owl composition. An isolated DOM witness
does not replace installed selection, clipboard, caret and narrow checks.

## P3.3: collaboration and durable revision recovery

Successor0.1.1 execution slice (16November, after the first installed handbook):
keep0.1.0/archive68dd/imagee0a immutable. Reuse the existing shell_context seam;
copy preference DTOs through canonical JSON rather than cloning Owl Proxies.
Keep unsaved local drafts separately when current server access is lost, disable
the editor on a known write denial, and offer explicit recovery without silently
resubmitting or displaying denied server content. Own minimal receipt status may
be reconciled under current page-read authority; it cannot authorize another
write or return another actor's receipt. Full read loss still refuses.

In that same successor, expose current eligible-member sharing with policy CAS,
durable escaped page comments/replies/resolve and paginated revision history.
History preview is read-only; restore uses the existing binary save with current
page revision, producing a new immutable head. Comment anchors name an existing
saved revision/block; detached anchors are labeled. Comments have a fixed text/
count/retained-byte budget and ordinary native CRUD remains closed. Sharing and
comments stay entirely in the private app. Test actual Owl reactivity and real
method control flow before normal package/build/admission/upgrade. Installed
two-session revocation, draft retention, comment/history and visual comparison
remain required; source tests cannot accept this slice.

Manage access with current eligible workspace members and explicit roles. Show
effective access and base-ceiling explanations, not optimistic switches. Share
updates use policy revision/CAS and an audit trail. A second authorized coworker
must read, comment and edit through real sessions; a downgrade/revoke must stop
new operations and clear known-denied content without stale title/count leakage.

Comments persist as plain escaped text with author/time, replies and resolve/
reopen state. Current page access applies to every thread. Bind anchors to a
saved revision/block identity and show detached anchors honestly after edits.
History is paged and editor/owner-authorized. Previewing does not mutate content;
restoring an old revision creates a new head under current CAS/access, preserving
the originals. User copy/undo is distinct from durable revision recovery.

Use a dedicated synthetic human editor coworker in the fresh owned Pages
cohort: the standard fixture cannot prove every page-specific restriction
because Alice/A is an administrator. Test that coworker as denied, page viewer,
commenter and editor under the same base workspace-editor role. Keep Alice's
admin override as a positive control and an existing workspace viewer as a
ceiling control. Do not downgrade existing principals or broaden membership in
protected demos; generate fixture credentials privately without printing them.

## P3.4: fitting reference features and explicit dependencies

Installed-pressure successor0.1.3 (activated after012 current revoke checks):
preserve the strong server refusal and add tab-local, explicit recovery of an
unsent comment after its composer becomes unavailable. Keep only the actor's own
text/submission metadata, separate from denied page/comment server content; no
automatic re-send, localStorage cache or authority inference. Clear list/pager/
panel totals and labels on known read denial. One confirmed leave must suffice;
discarded comment text cannot invisibly block subsequent navigation. Qualify
unknown submissions separately from known refusal and preserve receipt identity.

In the same app slice, give writer and inspector independent desktop scrolling,
keep the comment composer reachable, use reference comment cards and the shared
initials/avatar recipe, and restore inline scrolling on narrow layouts. Add the
reference's useful sidebar filter using the existing authorized paginated list
service: matching pages are a flat accessible result set, not fabricated ancestry;
late responses after a known denial/unmount must be discarded. These features
reuse AppLayout/ContextNav/shared tokens with no Pages-specific core code. Actual
revoke/draft recovery, keyboard/focus and matched original captures gate acceptance.

Before further features, successor0.1.2 closes the installed0.1.1 editor event
loop: Tiptap setEditable emits update by default, which must not be treated as
document authoring. Suppress that event and filter actual non-document update
transactions; detach old flows before destroying editors and guard late save
callbacks. Prove this with the pinned real editor, then installed idle revision
stability across sharing/access refresh and navigation. Retain all redundant
historical revisions from the discovered loop. In the same app release, use the
reference's continuous cover/icon/identity and one Outline/Comments/Info inspector
navigation; remove the cramped header controls and unconditional tree-limit
prose. No application-specific core CSS. Require corrected core59 for sharing.

Carry cover/icon choice, favorites/recent, template creation/copy-on-use, page
duplication, hierarchy/reorder, Trash/Restore, JSON/Markdown import/export,
links/backlinks and linked-from metadata. Each has real persistence, permission,
failure and keyboard behavior. Import passes the same server JSON validation;
export never bypasses current access. No raw-HTML import or automatic remote
fetch. Verify Markdown/editor conversion on the pinned library, including the
published parser counterexample; do not hide unsupported blocks.

Link to Pages and to real installed Partners/Documents through supported scoped
interfaces. Store typed identities, not privileged snapshots or bearer URLs.
Resolve current readable labels; missing/suspended/denied providers show honest
unavailability without deriving a title/count. Preserve current versus pinned
file revision semantics. Move-to-Storage needs an acknowledged export/upload
receipt before archiving a page; uncertainty never duplicates work or removes
the source. Offer that action only with an installed capable provider.

Simultaneous live co-editing, public/anonymous sharing, paid AI/cloud services and
arbitrary executable embeds are outside this program's stated scope. Explain
the concurrency/workspace/privacy reasons and record reconsideration conditions.
This does not remove ordinary two-tab concurrency, private sharing or rich
authoring. No prototype-only command is carried as a fake working button.

## Delivery sequence and evidence gates

1. Prove resource authority/recovery and editor packaging closure first; write
   ADR/author contract, affected tests and one normal core successor. Confirm
   eight-addon source/all-layer/app-free behavior and preserve current demos.
2. Deliver the first real authoring/ACL/tree/Home/editor package0.1.0, immutable
   archive/image and normal install on a fresh owned disposable cohort. Proposed
   port18742 is only a proposal until actual absent/free checks. Reuse the
   qualified `.local/core-reset/meridian-phase1-site.py` bootstrap composition;
   inspect it afresh and generate exact names/receipts, never reuse an old site.
3. Produce useful content before further features: an onboarding handbook with
   child checklist, headings, tasks, table and a real partner link. Reload/new
   session, search/tree/favorite/rename/move and conflict prove it is a real app.
4. Add collaboration/history/integration as a coherent actual feature upgrade
   (not a no-op version), retaining existing authored content. Normal admission,
   stage, review, exact approval/apply/checkpoint once; no live source injection.
5. Installed pressure: two actual writers, read-only/foreign/feature/member loss,
   current per-page revoke/downgrade, malformed/oversized/import payloads, stale
   saves and uncertain receipts. Restore only journaled fixtures exactly.
6. Controlled supported fault/checkpoint/restore/separate resume on the Pages
   cohort; a post-checkpoint policy revoke must survive. Preserve content,
   revision/comment identities and scoped authority. Never replay an uncertain
   mutation. User-level revision restore is tested separately.
7. Qualify disable/re-enable, normal uninstall and separate source subtraction,
   preserving independent apps and their data. Keep backup/export/evidence;
   protect unrelated targets, images and user data. Exact cleanup is a separate
   reviewed owned-resource action, no prefix sweep/prune.
8. Compare Home/editor/share/comments/history/insert/menu/error originals against
   Meridian while completing the handbook task. Same CSS viewport/theme/zoom/
   locale/fonts/scroll, with raw metrics. Include dark, narrow, true200%, realRTL,
   keyboard/caret/clipboard and reduced motion. Source tests are not visual proof.

Exit requires all of the useful handbook workflow, current sharing/recovery,
independent app packaging/lifecycle and installed visual review. Update the
carryover register, author guide, acceptance/blocker ledger and screenshot index.
Phase2's pending visual work still must close; phase4 adoption and phase5 final
canonical qualification remain required. Nothing here claims Pages exists yet.

Implementation checkpoint16November: P3.0 generic source/models/helpers and
recovery proof integration are implemented in the local core57 candidate.
See meridian-phase3-progress.md for affected tests, actual readonly core56 schema
compatibility and the installed proofs still required. No P3.0/phase3 acceptance
or Pages existence is inferred from these source checks.
