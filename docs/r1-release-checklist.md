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
- [ ] Finish UI09 observation and the required native close-button presentation
  correction. Browser work is deferred while following the user's backend-first
  direction. Standard record screens retain native Odoo views; Canvas stays minimal.
- [ ] Qualify the corrected immutable candidate through normal independent
  maintenance gates and installed UI09; no live source overlays.
- [ ] Independently reproduce that final image (BOOT-02). Do not reproduce the
  known residual core24 candidate just to regain a progress point.
- [ ] Refresh the draft kit once against the qualified image/source. Current kit
  still packages image14de; its source differs from current code in eight paths.
  Include `tools/operation_progress.py`, updated `tools/modular.py`, runbooks and
  the final shell/version sources. Retain exact unchanged large inputs.
- [ ] Qualify new source/image/archive/history/log privacy deltas and current
  provenance/network scope before OPS-03 is restored. Existing finite scans do
  not establish an unrestricted absence-of-secrets claim.
- [ ] Reconcile final fresh-developer proof and complete the §28 audit/handoff.
  The old kit's actual fresh setup is retained evidence, not proof that the
  current final kit was installed or that a new developer extended a plugin.

| §28 deliverable | Existing entry point / observation | Final closure still required |
| --- | --- | --- |
| 1 Source/branch | Local `platform/r1`; exact source commits in receipts | Identify final commit and clean working tree |
| 2 Upstream/patches | [Patch ledger](upstream-patches.md), pinned substrate | Include final source/notice inventory |
| 3 Reproducible environment/build | [Baseline](baseline.md), [toolchain](operator-toolchain.md), ADR0052 | BOOT-02 on final image and its exact dependency base |
| 4 Native/custom UI SDK | `packages/platform_sdk`, `packages/host_sdk`, native Notes and Canvas examples | Document and exercise a fresh developer extension/custom-page path |
| 5 Schema/planner | [Frozen contracts](contracts/freeze-v1.md), [planning](planning-core.md) | Bind final source to unchanged contracts or requalify affected changes |
| 6 Catalog/install | [Packaging](packaging.md), actual kit install | Reconcile final kit inputs; historical prose is not latest lifecycle state |
| 7 Lifecycle/executor | [Operations](operations.md), [runbooks](operator-runbooks.md), current core24 receipt | Package qualified CLI observation addition |
| 8 Workspace/identity | Acceptance ID/TEN/API evidence in status; ID08 current-line two-tab proof | Retain exact unchanged seams; requalify any affected final change |
| 9 Reference plugins/worker | Native Notes/Labels, minimal Canvas, separately managed Stats | Preserve examples and separate worker startup; no product expansion |
| 10 Mapped tests | Full acceptance ledger in status | Resolve BOOT-02, OPS-03, UI-09; verify all 99 required R1 checks |
| 11 Fresh install/restore | [Kit rehearsal](release-kit.md), [recovery](recovery-rehearsal.md) | Explicit final-image/source compatibility and fresh developer reconciliation |
| 12 Operator/developer docs | Twelve runbooks; setup, security and SDK sources | Add a concise executable developer entry point; check commands against final kit |
| 13 Limitations/security | [HTTP security](http-security.md), [network](network-independence.md), native trust warnings | Carry residual advisory/license/authority limits into handoff |
| 14 Release/lock inventory | Draft kit, dependency locks and hash-bound receipts | Final kit inventory/source/image/privacy binding |
| 15 Final handoff | Status, evidence and runbooks exist | Final startup/test/example/recovery commands, URL/account setup, risks and milestone |

Do not replay completed lifecycle operations, recreate the benchmark or start
another disposable realm merely to make a checklist look current. Retain prior
proof only at unchanged boundaries and record what a new observation establishes.
Delete only known completed disposable Docker assets after diagnostics are saved;
checkpoint/base images and existing databases retain their recovery roles.

Optional improvements excluded from this closure: Canvas polish or new features,
a wholesale WebClient/shell rewrite, additional design-system work, and R2/R3.
Required accessibility fixes and the fresh-developer path remain R1 requirements.
