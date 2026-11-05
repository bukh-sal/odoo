# R1 release closure checklist

The [status ledger](implementation-status.md) owns current progress and the active
item. This is a closure map for specification §28, not a second progress estimate.
G0–G6 passed; G7 is still in progress. Existing evidence retains its original
image, source and environment scope. A checked item below means the stated bounded
observation exists; it does not mean the entire final release passed.

- [x] Backend installation, independently reviewed upgrade and recovery exercised.
- [x] Current core24/Shell11 upgrade completed with business data, checkpoint files
  and independent worker preserved: [preservation](evidence/G7/20261104-core24-maintenance-01/preservation.json).
- [x] Current CLI operates in the kit's isolated Python environment; 19 affected
  tests pass, actual completed operation is read without replay, legacy journal
  fields agree, 174 durable control files and four runtimes remain exact:
  [operator preflight](evidence/G7/20261104-operator-release-preflight-01/qualification.json).
- [x] Install core25 through the independent maintenance gates and verify data,
  checkpoint files and worker preservation. [Upgrade evidence](evidence/G7/20261105-core25-maintenance-01/preservation.json)
- [x] Verify the installed dialog name, close glyph, keyboard focus, 200% zoom,
  RTL and 320 CSS pixel reflow. [Browser evidence](evidence/G7/20261105-core25-maintenance-01/installed-observations.json)
- [x] Qualify core26 localization, Windows accessibility announcements and
  keyboard workflows. [Installed evidence](evidence/G7/20261105-core26-maintenance-01/installed-observations.json)
- [x] Independently reproduce the selected core26 runtime inventory and
  dependency environment (BOOT-02). [Build evidence](evidence/G7/20261105-core26-repro-01/qualification.json)
- [x] Assemble the core26 draft kit from the reproduced image and current source.
  The manifest covers 52 components and binds the build and reproduction receipts.
  [Assembly evidence](evidence/G7/20261105-core26-release-kit-01/assembly.json)
- [x] Set up the clean operator offline from the core26 kit and check its
  private boundary, CLI and contract freeze. [Operator setup](evidence/G7/20261105-core26-release-kit-01/operator-setup.json)
- [x] Qualify the core26 kit's clean application install, scoped HTTP path and
  separate worker. [Backend evidence](evidence/G7/20261105-core26-release-kit-01/fresh-backend.json)
- [x] Validate and reproduce versioned Labels and Canvas examples in the clean
  operator. [Packaging evidence](evidence/G7/20261105-core26-release-kit-01/developer-packaging.json)
- [x] Build a candidate from the exact edited packages and active distribution
  policy, review and upgrade four scopes, and verify the installed variants
  over HTTP. [Review](evidence/G7/20261105-core26-developer-install-01/review.json)
  and [installed backend](evidence/G7/20261105-core26-developer-install-01/backend-verification.json)
- [ ] Exercise the fresh developer walkthrough in the browser when UI checks
  resume. The browser should open native Notes list/form, invoke the updated
  Labels action, and render the one-card Canvas with the changed subtitle.
- [x] Remove the producer's hardcoded core23 selection and bind source refresh to
  explicit matching build/reproduction/image evidence:
  [ADR0058](architecture-decisions/0058-explicit-release-application-inputs.md),
  [actual refusal proof](evidence/G7/20261104-kit-input-binding-01/qualification.json).
  Nine tests and both real old-receipt refusals pass; all50 draft components
  remain unchanged. This is a producer guard, not final kit assembly.
- [x] Qualify current image provenance and fresh internal network topology,
  expanded privacy for the initial core26 kit and fresh log privacy.
  [Provenance](evidence/G7/20261105-core26-release-kit-01/provenance.json),
  [kit privacy](evidence/G7/20261105-core26-release-kit-01/privacy-delta.json) and
  [log privacy](evidence/G7/20261105-core26-release-kit-01/fresh-log-privacy.json)
- [x] Verify expanded privacy and Git identity after the source-only refresh.
  The fresh run used the prior source snapshot. The refresh changed the source
  archive alone and the new catalog preflight passed a separate boundary test.
  [Source refresh](evidence/G7/20261105-core26-release-kit-01/source-refresh.json)
  and [final privacy](evidence/G7/20261105-core26-release-kit-01/privacy-delta-final.json)
- [x] Carry the corrected Windows test fixtures in the selected kit. Verify
  the 51 unchanged components and recheck the source privacy and backend scope.
  [Current refresh](evidence/G7/20261105-core26-release-kit-01/source-refresh-regression.json)
  and [current audit](evidence/G7/20261105-section28-audit-01/backend-audit-regression.json)
- [x] Finish the supplemental Windows suite and exercise the Linux-only skip
  in the selected core26 image. [Regression results](evidence/G7/20261105-section28-audit-01/regression-results.json)
- [x] Bind retained core23 fault/restore/resume evidence to the current recovery
  implementation. The observed failure and recovery remain scoped to core23.
  [Recovery binding](evidence/G7/20261105-core26-release-kit-01/retained-recovery-binding.json)
- [ ] Reconcile final browser proof with the backend developer walkthrough and
  complete the §28 audit. [Local handoff](r1-handoff.md)
- [x] Add a source developer entry point and exercise its reference packaging
  commands: [guide](developer-guide.md), [packaging proof](evidence/G7/20261104-developer-packaging-01/qualification.json).
  Two isolated versioned examples validate/reproduce; mismatch and overwrite
  refusals preserve output. This does not check off the full fresh-developer path.

| §28 deliverable | Audited evidence | Remaining |
| --- | --- | --- |
| 1 Source/branch | Local `platform/r1`, exact Git source snapshot and unchanged executable inputs | Record closure commit and verify clean worktree |
| 2 Upstream/patches | [Patch ledger](upstream-patches.md) and [actual source/notice inventory](evidence/G7/20261105-core26-release-kit-01/provenance.json) | — |
| 3 Reproducible environment/build | [Offline operator](evidence/G7/20261105-core26-release-kit-01/operator-setup.json) and [BOOT-02](evidence/G7/20261105-core26-repro-01/qualification.json) bound to the kit image and exact base | — |
| 4 Native/custom UI SDK | `packages/platform_sdk`, `packages/host_sdk`, [developer guide](developer-guide.md) and two installed developer examples verified over HTTP | Verify the modified examples in the browser |
| 5 Schema/planner | [Frozen contracts](contracts/freeze-v1.md) and [planning](planning-core.md). Current and archived freeze inventory matches G2 revision 18, 106 files and eight rows | — |
| 6 Catalog/install | [Packaging](packaging.md), [fresh install](evidence/G7/20261105-core26-release-kit-01/fresh-backend.json) and [exact catalog reconciliation](evidence/G7/20261105-core26-release-kit-01/catalog-and-publication-reconciliation.json). Refreshed initializer guard tested separately | — |
| 7 Lifecycle/executor | [Operations](operations.md), [runbooks](operator-runbooks.md), current reviewed upgrade, retained recovery and actual observation through the extracted CLI | — |
| 8 Workspace/identity | ID/TEN/API ledger, retained [ID08 two-tab evidence](evidence/G7/20261104-ui-qualification-01/identity-qualification.json) and fresh current backend denials | — |
| 9 Reference plugins/worker | [Fresh install](evidence/G7/20261105-core26-release-kit-01/fresh-backend.json) and [installed developer variants](evidence/G7/20261105-core26-developer-install-01/backend-verification.json). Standard Notes CRUD uses Odoo. Canvas and the separate worker remain minimal references | Browser proof in item 4 |
| 10 Mapped tests | All 104 specification IDs matched the ledger, with 99 passes and five R2 exclusions. Windows suite and Linux startup checks passed. [Backend audit](evidence/G7/20261105-section28-audit-01/backend-audit-regression.json) and [regression results](evidence/G7/20261105-section28-audit-01/regression-results.json) | — |
| 11 Fresh install/restore | [Kit rehearsal](release-kit.md), [actual failed-upgrade restore](evidence/G7/20261103-fresh-release-01/dependency-recovery/qualification-corrected.json) and [later executor binding](evidence/G7/20261105-core26-release-kit-01/retained-recovery-binding.json). Fault evidence retains original image and scope | — |
| 12 Operator/developer docs | Twelve runbooks and fifteen real CLI help checks. [Runbooks](operator-runbooks.md) and [developer guide](developer-guide.md) | Browser portion of developer walkthrough |
| 13 Limitations/security | Trust, runtime, network and residual advisory limits linked in the [local handoff](r1-handoff.md) | — |
| 14 Release/lock inventory | Verified 52-component draft kit and source/image/privacy binding. Exact location and manifest in the [handoff](r1-handoff.md) | — |
| 15 Final handoff | [Local handoff](r1-handoff.md) links commands, URLs, credential setup, status, evidence index, tests and risks | Add final gate result after browser verification |

Do not replay completed lifecycle operations, recreate the benchmark or start
another disposable realm merely to make a checklist look current. Retain prior
proof only at unchanged boundaries and record what a new observation establishes.
Delete only known completed disposable Docker assets after diagnostics are saved;
checkpoint/base images and existing databases retain their recovery roles.

Optional improvements excluded from this closure: Canvas polish or new features,
a wholesale WebClient/shell rewrite, additional design-system work, and R2/R3.
Required accessibility fixes and the fresh-developer path remain R1 requirements.
