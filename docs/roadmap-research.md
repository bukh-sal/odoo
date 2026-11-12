# Roadmap research and decisions

13 November 2026 (Asia/Riyadh). Read-only research for the
[product/platform roadmap](product-platform-roadmap.md), source baseline
`69a053bd64b11a30835c2f7ff7b4ed3260373847`. No new runtime, browser, build,
application or lifecycle qualification was performed for this record.

## R-01 — Start from useful behavior already demonstrated

The [customer-work pressure evidence](evidence/G7/20261111-customer-work-01/qualification.json)
and [CW-L01 lifecycle evidence](evidence/G7/20261112-customer-work-lifecycle-01/qualification.json)
establish independent task/customer integration, discussion, private reminders,
current-authority fresh recovery and exact optional-leaf removal/return in their
bounded scopes. Existing real UI review found and corrected actual navigation,
draft and status problems. Source tests alone would not have established usability.

Read-only Aurora source review found distinct Tasks, Documents and CloudStorage
models, including stages/reminders/comments, document access and file access
concerns. These are product inspiration, not a new runtime comparison or proof
that Aurora's implementation is safe/current. Its private code is not copied.
Prior actual Aurora interaction review remains the visual baseline; PP-01 must
inspect the current visible journey again when activated.

Decision: improve the coherent customer-work experience first, then use a
workspace document library to exercise a genuinely different workload. Avoid
another task demo or repeating already-accepted lifecycle tests as the product.

## R-02 Scoped binary support is a real core prerequisite

Actual source [attachments.py](../framework_addons/mp_core/attachments.py) denies
attachment create/write/access and content streaming for models marked
`_mp_scoped`. Although its profile docstring mentions Notes/Canvas, the managed
model test applies to other workspace-scoped apps too. Its ownership preflight
covers public/token and limited-field streaming routes because they can bypass
ordinary access hooks. This is an intentional security restriction, not an
already-supported file API or evidence that file apps are fundamentally impossible.

The bounded JSON service request path is not a large-file transport. A document
app therefore needs a deliberate generic core capability, with fresh authority
checks on every supported upload/read/preview/native route, resource bounds and
coordinated byte/metadata recovery. Merely lifting the existing denial or writing
directly to a filestore in the app would not satisfy it. PP-02 owns this prerequisite.

OWASP recommends required-type allowlists, content/signature and filename checks,
size limits, authorization and safe storage/retrieval; supplied MIME headers are
not sufficient. It also identifies parser, active-content and resource-exhaustion
risks. The phase plan must explicitly choose supported formats, preview isolation
and scanning disposition rather than assume every file is safe or introduce a
new scanning service without authorization.
[OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)

## R-03 — Scope sharing and recovery honestly

[AP-LIM-015](application-adoption-limitations.md) distinguishes current native
authentication/platform revocation overlays from app-owned business ACL rows,
which restore from a checkpoint. Current recovery does not universally preserve
every later per-list/folder ACL revocation. Default the first document app to
workspace-shared editor-write/viewer-read; finer sharing must first define and
qualify its current-authority recovery behavior. Do not use a narrower demo as
proof of per-document privacy or a generic permission sandbox.

Application-level version history and trash are useful separate interactions.
Nextcloud documents visible prior versions with retrieval/restoration, and a
separate deleted-files recovery workflow. Those distinctions inform the proposed
journey; its retention policies and implementation are not adopted as ours.
[Nextcloud version control](https://docs.nextcloud.com/server/stable/user_manual/en/files/version_control.html),
[deleted-file management](https://docs.nextcloud.com/server/stable/user_manual/en/files/deleted_file_management.html)

Our [capability register](application-capability-register.md) also records that
operator fresh restore currently requires an unresolved failed operation. An
already-completed uninstall cannot be undone by promising a reinstall restores
its deleted rows. PP-04 deliberately includes a bounded new coordinated named
checkpoint restore for the qualified native cohort, using fresh targets and
independent review. It is not claimed available now; its target/effect policy
and implementation require fresh research and planning at activation.

## R-04 — Usability acceptance needs actual interaction

W3C's dialog guidance calls for focus entering the dialog, keyboard containment,
Escape dismissal and appropriate focus return. This informs actual keyboard and
draft/navigation checks in PP-01, not just screenshot inspection.
[W3C modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)

WCAG2.2's AA target-size criterion specifies 24-by-24 CSS pixels with stated
exceptions/spacing alternatives. Focus-not-obscured addresses focused controls
hidden by author-created content. Use these relevant criteria in the phase's
declared desktop/narrow-screen acceptance; bounded checks are not a complete
WCAG conformance or assistive-technology claim.
[W3C target size minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html),
[focus not obscured minimum](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)

## R-05 — A fresh developer/operator should not need private harness knowledge

[Application authoring](application-authoring.md) already describes independent
repositories, recipes, owned models/views/services and deterministic packages.
The [developer guide](developer-guide.md) still begins with historical core47
kit instructions. Preserve that historical workflow while making current-candidate
navigation unambiguous. Existing private qualification wrappers are evidence,
not automatically supported public operator tooling.

Recent lifecycle runs exposed private-wrapper assumptions about observer shape,
held/pending jobs, public DTOs and binding/key incarnations. The actual core
guards correctly refused unsafe/stale assumptions. PP-04 should improve ordinary
diagnostics and reconciliation, retaining exact independent approval and no-replay
semantics, rather than auto-acknowledging or hiding those guards.

## R-06 — Define build reproducibility before claiming it

Earlier clean app-composition work rebuilt same-version native Python dependencies
with different executable bytes; exact source subtraction instead reused the
qualified dependency bytes. Same dependency names/versions do not establish
identical artifacts. Preserve the existing immutable source/inventory evidence.

Reproducible Builds defines reproducibility against specified artifacts, source,
environment and instructions, verified by identical bytes. PP-04 must distinguish
package, runtime/dependency inventory and OCI claims, investigate nondeterminism
and measure a declared scope. No full-image bit-identity promise follows merely
from the current locks.
[Reproducible Builds definitions](https://reproducible-builds.org/docs/definition/)

## Decisions deferred to the moment they matter

- PP-01: actual interaction defects and chosen screens after fresh visual review.
- PP-02: allowed file types/size/retention/preview, byte transport/storage contract,
  supported workspace role behavior and optional links before implementing them.
- PP-03: the useful app evolution requiring a real migration/event effect; any
  finer ACL recovery policy before introducing it.
- PP-04: completed-checkpoint target/effect/review model, supported operator path
  and reproducibility envelope after the earlier implementation findings.
- PP-05: workload/performance budgets before measuring; final exact version and
  support cohort before candidate acceptance, with no production/LTS inference.

These are inputs to fresh just-in-time implementation plans. This research
creates no phase plans, source changes, new support claims or gate acceptance.
