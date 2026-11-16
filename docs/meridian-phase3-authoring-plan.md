# Phase3 remaining authoring and integration execution plan

Activated16November against installed015/config8 and source6636aa6e. Full goal
all5phases/1accepted remains. Current owned3pages64heads74receipts2comments,
copy4/source-template7/handbook53/current authority preserved. No operation replay.

## Findings and implementation sequence

1. JSON/Markdown transfer and editor controls. Core BinaryEndpoint already gives
   bounded authenticated/create-scoped POST,4096B metadata, CSRF/client-release
   and protected whole GET. Pages owns parse_document duplicate-key/UTF8/node/
   URL/size validation and immutable-body accounting. Add app json-transfer binary
   endpoint: POST creates ONE new independent page atomically from validated raw
   JSON; metadata pins raw SHA256/frozen key/title/icon/cover/parent. Validate the
   ORIGINAL bytes before editor coercion or DML. Deterministic actor/workspace/key
   identity, current destination checks on replay, existing quota fence/default
   reader policy and own receipt. GET uses existing current-authorized revision
   download (history still needs editor). No new core transport/global limits.
   UI file selection/metadata/preview confirmation is separate from save; unknown
   results hold the SAME raw bytes/key. Export first refreshes current get/body,
   then downloads a local JSON file; no privileged URL or cached denied body.
   Add explicit paragraph/heading/alignment controls using pinned existing editor
   commands, no second editor framework. JSON is lossless; Markdown conversion
   must have an explicit supported-node/format-loss contract. Research and pin
   the actual parser before using it; do not invent a safe regex Markdown parser
   or silently drop raw HTML/unsupported structures. No dependency approved yet.
2. Page organization and same-app links. Existing update(move) is CAS checked;
   implement explicit sibling reorder against observed complete/bounded sibling
   set, refusing unknown order/overflow. Preserve current parent checks/cycle
   refusal and sharing independence. Existing pageReference node persists ONLY
   a page UUID, currently renders a generic placeholder. Add app-owned insertion,
   current readable resolution and backlinks from CURRENT readable heads. Never
   derive a hidden ancestor/source title/count; links do not grant read. Follow
   normal links/Back/modified click and show honest unavailable state. No copied
   title snapshots or arbitrary app/model dispatch from browser IDs.
3. Real optional providers. Audit actual Partners/Documents producer schemas and
   call_bound(original actor) exactly as current Taskfiles does. Its reference
   rows store IDs, not names/bytes; resolution catches explicit current denials.
   Do not assume a services.requires alias is optional: inspect actual resolver/
   approval behavior first. Choose supported late binding/optional composition
   from actual source, with no generic framework unless a real missing primitive
   is proved. Qualify normal provider admission/image/install/grant on owned18742
   only, then current/pinned file and partner links and provider loss. Move-to-
   Storage requires an acknowledged export/upload receipt BEFORE page archiving;
   uncertainty preserves source and original submission. No fake integration UI.

## Gates and boundaries

Implement source/tests in coherent app slices, publish no half-working buttons.
Each changed shipped app gets legitimate successor identity/archive/one clean
image/current core3747file equality/normal reviewed upgrade. Current-authority
and same-key/changed-byte/partial failure/quota/foreign parent/malformed input
counterexamples plus actual useful workflow/reload are mandatory. Keep old data,
policy, images and evidence. Source mocks cannot prove installed atomicity.

Then actual system checkpoint/fault/post-checkpoint policy revoke/restore/separate
resume, preservation and independent app disable/uninstall/source subtraction.
Remaining full visual scenes/light-dark/narrow/real200/RTL/keyboard/reduced motion
remain required alongside phase2/sharedrail/header carryover, phase4 adoption and
phase5 final canonical qualification. No existing gate accepted from this plan.


### Transfer UI and timely Markdown audit

Unpublished016 now has actual Import dialog/file choice/title/confirmation,
original-byte SHA/key freezing and same-input retry on unknown results. No editor
coercion before server validation. Export saved JSON first fetches current page
and verified current head, refuses denied reads, downloads only saved content;
filename normalizes/strips controls and bounds Unicode length. Actual-controller
and Owl compiler cases now44Node pass0fail (pages016-source-01/node-transfer.txt),
28Python prior import/model evidence carried unchanged. No installed transfer
claim,016 build or source injection. Private UI sourceHEAD recorded in capsule.

Primary research16November:
[Tiptap installation](https://tiptap.dev/docs/editor/markdown/getting-started/installation)
and [MarkdownManager](https://tiptap.dev/docs/editor/markdown/api/markdown-manager)
show the Markdown bridge/standalone parse+serialize seam, currently labeled Beta.
Registry metadata saved pages016-source-01/markdown-3.31.3-registry.json verifies
candidate @tiptap/markdown3.31.3 MIT peers EXACT core/pm3.31.3, dependency marked
range^17.0.1. No install/lock change yet. Pin actual resolved parser before use.
The [attribute-parser advisory](https://github.com/ueberdosis/tiptap/security/advisories/GHSA-j95f-988m-3j2f)
still has broad affected metadata plus patched3.30.5; do not infer safety from
version ordering alone. Actual existing core3.31.3 source has parseShortcodeAttributes
using tokenizeAttributes and no old attributeUtils.ts at the cited path. This
identifies the exact next audit/test target, not a safety waiver. Require actual
complete-tokenizer scaling and unsupported-node/HTML/escaping tests on the lock.
NEXT pin/inspect package source, bounded loss-aware Markdown conversion with
worker timeout where appropriate; remaining controls/reorder/typed links/providers
and all installed/recovery/lifecycle gates retained. Full goal ACTIVE1/5.


### Exact Markdown pin and complete-tokenizer source proof

Private0bf64603bcd510c6e588fd5ab869a6b1c711bad6/unpublished016 now pins @tiptap/markdown3.31.3 and
marked17.0.6 locally, MIT. Only2new dependency entries; all previous lock entries
exact. Install ignored scripts/no global install/npm upgrade. Registry/lock/license
hash proof pages016-source-01/markdown-lock-check.json. Existing shipped editor
bundle/notices remain unchanged until worker integration/build refreshes closure.

Actual MarkdownManager with existing extensions handles headings1–3/tasklists/
rectangular tables/safe links and normal roundtrip. Pure helper rejects raw HTML,
images/unsafeURLs/undeclared token types/invalid Unicode/oversize; export rejects
unsupported record nodes, underline, alignment and merged/width-specific tables
with explicit JSON fallback. Loss metadata explains IDs/history/sharing are not
Markdown. Initial positive test exposed actual marked checkbox token, added only
that known supported token after inspecting lexer output; no broad HTML allowance.

Actual core default COMPLETE block/inline tokenizer advisory families now assert
probe token returned (not a no-op call),3-run median/8x input/isolated5s worker.
Final source run48Node pass, including these cases. Bound evidence reports block
~0.65ms->3.03ms, inline~0.09ms->0.80ms in dedicated run; no general complexity or
security-clean claim. Results in markdown-attribute-scaling.json; full run receipt
node-markdown.txt may carry later measured values. No browser conversion worker/UI
MD controls or installed qualification yet. NEXT integrate dedicated browser worker
with hard timeout/termination, actual loss-aware import/export confirmation, exact
licensed vendored worker closure, then remaining editor/reorder/links/providers.
All phase3 lifecycle/visual and fullphase2/4/5 remain. Live015 data unchanged.


## Pages016 coherent transfer/controls source checkpoint -16November

Private4561be47202207f9ab243576c684dbade9f138f2/unpublished016 now implements
JSON and supported Markdown import/export plus paragraph/heading/alignment
controls. Dedicated2s worker terminates on timeout/cancel/error, no main-thread
fallback. Export re-parses and compares semantic content, refusing unsupported
or silently lossy structures with JSON fallback; Markdown identity/history/sharing
loss requires acknowledgement. Actual parser link-title output differed from
the app schema: unsupported titles now refuse, ordinary links normalize to the
existing app attributes. New-import missing block IDs are deterministic per
page/path, supplied IDs/old bodies unchanged. Same-input unknown import retry
freezes bytes/key/title; export confirmation rechecks current head and authority.

57Node pass (actual worker bundle/real editor commands/controllers/Owl plus
counterexamples),30Python pass (actual import handler with bounded persistence).
Evidence .local/meridian-phase3-pages016-source-01/node-release-source.txt and
python-worker-final.txt. Shipped editor remains byte-exact440010B/608d5cf8;
new worker482495B/5e7347a7,43licensed package closure/notices. Actual bundled
worker parses useful heading/task/link without DOM. Source proof only; no016
archive/image/installed acceptance yet. Live015/config8/3pages64heads74receipts/
2comments remains unchanged. Next deterministic package/ONE clean image/normal
reviewed upgrade and real transfer/controls visual workflow, then remaining
reorder/current-readable links/providers/system recovery/lifecycle. Full goal
all5phases ACTIVE1/5; phase3 zero exit acceptance; phase2native200/4/5 retained.


## Installed016 transfer refusal and017 editor-schema correction

ONE016 build57.578s/image23b5b871/14layers3771files/core3747exact; archive
d7125ecc/373608B/29files. Normal6e464591/plan7bb8625d completed/config9/target
bb5dfd83. Original3pages64heads74receipts/comments/policies exact across upgrade.
Actual installed Markdown worker imported useful heading/tasks/table/link once
as fd77c30c/First-week check-in revision1. Explicit loss acknowledgement required.
Its first task edit was refused VALIDATION_FAILED; one local heading edit followed
before the badge was inspected. Both local changes preserved as rendered text and
rich clipboardHTML in pages016-transfer-01; copied draft then explicitly left.
Readonly proof4pages65heads75receipts/newpage1, original rows/authority exact;
no refused-save receipt/head. No positive editable-transfer claim.

Actual pinned Link always emits title:null, absent from the app-owned server
schema. Source real imported editor/task-click producer reproduces the refusal.
Unpublished017 a436f4a047ec9571d0c31eef1d0ff548be7ea82d owns an extended Link schema without that unsupported
attribute. Server validation is UNCHANGED, including refusal of title:null. Actual
producer/consumer fixture succeeds; forged old null-title witness still refuses.
Link is now direct exact3.31.3 already in old lock, every transitive entry exact.
Import copy distinguishes original validation from normalization; known400 save
leave warning no longer calls it unresolved.59Node/31Python pass. New editor
440114B/91e0cd00; worker482599B; same43licensed packages. No017 image/install yet.
Full goal all5 ACTIVE1/5; phase3 no exit acceptance. NEXT normal017 package/ONE
clean same-core build/independent upgrade, then continue the retained useful
transfer/edit/export workflow. Organization/links/providers/recovery/lifecycle,
phase2native200/4/5 remain. No retry of old operations/source injection/cleanup.
