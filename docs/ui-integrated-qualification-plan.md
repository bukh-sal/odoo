# UI-D06 integrated qualification implementation plan

Activated14November2026 against host839f0d2a367 and the frozen source described
below, before its execution work. This phase completes the existing
[delivery plan](ui-shell-delivery-plan.md); it introduces no new UI framework,
application feature, support promise or release publication.

The entry is deliberately limited to independent regression and native lifecycle
work while UI-BROWSER-01 remains open. D03/D05 rendered cards are not accepted.
Those cards still gate the overall exit and the visual portion of this phase.
The source/native/API evidence is sufficient to test packaging and lifecycle
without pretending that screenshots or human usability review have happened.
This refines the earlier D05 resume order: make required independent progress,
then close the same outstanding visual cards when in-app controls attach.

## Current evidence and fixed boundaries

* Core sourcea75d2d77afc is0.2.12/native19.0.0.2.12/web19.0.2.12.0. The current
  app image3b5188c6 was built at host489bffb9d1b; later host changes are evidence
  and documentation. Bind the full current source-input map before any build.
* Private app sources are Workboard1f8b536/0.2.13, Documents6aef5fe/0.1.9,
  Deliveryee96475/0.1.6, Partners244cf7d/0.1.1 and unchanged Taskfiles7bbbd84/0.1.5.
  Exact digests are in the [installed record](evidence/G7/20261114-shared-work-surface-apps-01/qualification.json).
  Preserve these independent repositories, licences and notices.
* Current review site18610/config6 has27tasks, one file/two versions and a
  useful customer/task/pinned-document path. One intentional description edit
  advanced an existing task to revision2. Both normal core and app upgrades
  preserved eighteen compared tables, authentication, current authority and
  job/outbox business data. Do not repeat that edit or either upgrade as a check.
* [Legacy maintenance/recovery](evidence/G7/20261114-legacy-web-recovery-01/qualification.json)
  proves the supported owned-web transition, controlled native-commit failure,
  fresh restore, separate resume and newer-authority preservation. Its18611
  fixture stays protected. Native executor/recovery readers were not changed by
  this UI source slice; do not replay historical operations.
* [Actual Owl compilation](evidence/G7/20261114-shared-work-surface-compiler-01/qualification.json)
  passes25templates from19inventoried image files. The private test DOM performs
  no layout or screenshot qualification and is no product dependency.
  [Delivery/A availability](evidence/G7/20261114-shared-work-surface-companion-01/qualification.json)
  passed normal suspend/enable, fresh409/PLUGIN_SUSPENDED with healthy provider
  and other-workspace controls, exact data and full feature restoration.
* The eight-addon default remains base,web,base_setup,auth_password_policy,bus,
  mp_compat,mp_identity,mp_core. Existing licences/notices and private app status
  remain unchanged. No production, publication, broad compatibility, sandbox,
  long-term-support or1.0 claim is authorized.

Before each operation inspect current state, not a historical capsule. Capture
the seven previous protected target hashes plus current18610 and legacy18611,
their immutable image/worker identities and retained resources. One active work
item, no agents. Keep every original failure and exclusive intent. Observation
timeouts never justify replaying apply, restore, publication or recovery.

## A. Freeze source and run the integrated host regression

First reconcile the two new evidence records and this plan in a local commit.
Require all tracked platform/private-app trees clean. Record the actual current
HEADs, curated inputs, frozen-contract result and the installed candidate pins.
Historical untracked build evidence remains retained; never use `git add .`.

Run the canonical entrypoint once:

```powershell
& .local/toolchain/operator-python16/Scripts/python.exe -I tests/run_host_regression.py
```

Give only this subprocess an explicit `MP_SECRET_SCAN_RG` pointing to the actual
installed `rg.exe` from `Get-Command rg`, verify its version/hash first, and
preserve its exit/log and source binding. Do not change global Python, PATH or
scanner policy. Use the canonical runner's existing trusted import roots.
Do not substitute raw unittest discovery or call a source-only subset the full
regression. Record actual totals, skips/reasons, failures and errors; do not
assume the earlier PP05 count923 still applies. Existing app68Node/62Python
checks and real-template/compiler evidence remain separately scoped.

Use exclusive private receipts under `.local/ui-d06-qualification-01/` and a
bounded process handle. Inspect the same running process until terminal. A
failure is diagnosed against its actual producer/consumer before any patch or
new run; a timeout preserves status and diagnostics. Repeat broad testing only
when a concrete fix, changed source or unresolved concern warrants it. If a
later visual fix changes the candidate, bind/revalidate the affected checks and
ensure the final integrated result corresponds to the delivered code.

## B. Build and bootstrap an independently clean eight-addon candidate

Use the existing clean build route, with a fresh owned output name:

```powershell
& .local/toolchain/operator-python16/Scripts/python.exe -I tools/build_candidate.py --output docs/evidence/G7/20261114-uid06-core012-clean-01 --gate G7 --policy deploy/distribution-r1-core.json
```

Verify output/private record absent first; no dependency-base image,
reproduction flag, relabel or source injection. The selected core8 policy and
shipped code are unchanged; no version bump is needed for this composition.
Compare Python,Node/RTL locks, all core files and existing app image3b5188c6.
Require exact eight native addons and zero artifacts/app sources/host operators.

Adapt the existing PP05 read-only OCI layer/merged-tree audit to exact new
inputs, without copying its historical IDs/counts or invoking old mutators.
Bind saved-image index/config/layer hashes and actual diffIDs; inspect every
final ancestor layer as well as the merged project tree. Detect app archives,
private app directories, host/reference operators, project fixtures or a hidden
old runtime behind whiteouts. Distinguish permitted vendor notices/protocol
data and harmless base-image whiteouts from project/application bytes. Preserve
the tar/evidence. A clean merged tree alone is not an all-layer result.

Use `tools/initialize_candidate.py` normal plan/prepare/initialize/publish,
each explicit phase once. Proposed fresh workdir is
`.local/development/uid06-lifecycle-01`; proposed loopback port18612 and subnets
10.206.72.16/28 and10.206.72.32/28 are **not reserved**. Revalidate actual free
port/IPAM and generated exact names before creation. Bind the successful core8
record and use the existing disposable-development and local noninteractive
operation options. Save generated state before assets; inspect any partial
phase instead of removing an intent to replay it. Do not weaken sealed Reference
or source/kit/runtime guards, patch entropy, or mount source into the app.

Verify fresh login, empty catalogue/published plugins/zero installations,
eight installed modules, current workspace/own-job/account APIs and assets.
The in-app zero-app landing and account/chooser interactions remain a browser
card until inspected. Retain main18610, comparison18608 and the legacy cohort.

## C. Normal optional-app lifecycle in that separate fixture

Use the already verified immutable app image3b5188c6 and its five exact archives,
validated against current source/records. Admit exact digests into this new
fixture's own trust/catalogue, preserving its baseline. Normal stage-image,
explicit install nomination, independent review/register/exact approval/apply
must install five native apps in both workspaces. Derive actual acknowledgement
flags from the plan/source policy; preserve all guards and mandatory checkpoint.

Seed a small useful original-human fixture: customer, linked task, file/two
versions and one pinned task reference, with current viewer/foreign refusals.
Use actual services/binary APIs and stable submission identities. Capture exact
IDs/revisions/bytes and current authority before each effect; a timeout requires
reconciliation, never another submission identity. No business SQL injection.

Prepare normal native uninstall from the real independently observed impact.
To finish at a source-free core, select the actual five-app native dependency
closure and exact workspace scopes; review owned tables/fields/views, including
Delivery's inherited Partners view, bindings and declared grant revocations.
Only synthetic data in this new fixture may be removed through the reviewed
destructive operation. Retain its verified pre-uninstall checkpoint and export
evidence. Existing populated review/control sites are not uninstall targets.

Require completed native **and** metadata removal, not merely successful native
module uninstall: native states, owned metadata, suspended feature/tombstone
state, revoked grants and removed bindings must agree. Inspect retained base
form metadata and stale routes/bindings while source still exists, using exact
frozen error mappings rather than guessed status codes. No new job/write or
unavailable companion data may appear after refusal. Browser stale-link and
widget-absence proof remains open if controls are unavailable.

Stage the clean core8 image as the subtraction target and use normal
`operation_type=remove` planning from complete retained-source inventory.
Require an actual complete checkpoint/recovery/retained-source proof and exact
app-only file removals; derive counts from these inventories, not the old PP05
76-file fixture. No native maintenance flags, runtime/script hash relaxation,
database resets or fake installed metadata. Separately review/register/approve/
apply once, then independently verify core8/no artifacts/no app directories,
empty published plugin/binding set and inert history, preserved checkpoint
hashes/catalogue/filestore/failed sources and current native scope behavior.
Keep every history record; no source uninstallation claim from hide/suspend.

The previous PP05 timing failures are immutable. Measure this cycle honestly
against its existing limits; do not rename a late completed operation a success
or rerun it to obtain a nicer time. Source-free means runtime code/artifacts,
not erasing retained synthetic history or checkpoint bytes.

## D. Close the real in-app interaction matrix

Use only the in-app browser. The preview is visible, but no interaction or
screenshot tool is currently exposed; no bundled browser skill was found.
Do not use Edge, OS browser automation, headless replacement or a guessed CDP
transport. When controls attach, use documented APIs and preserve any existing
draft in the owner's tab. Keep screenshots private and reference them by full
local paths for visual judgment. Inspect rather than merely open a preview.

| Required combination | Actual evidence to capture |
| --- | --- |
| Matched English light/dark at1280px desktop and390px narrow | Partners list/form, Workboard list/board/detail, Documents library/pinned/current, Customer work and reminders. Same data, zoom, viewport and theme for comparisons. Measure56rail/264context,26/34title, row/control sizes, wrapping, one context pane, primary-action hierarchy and no page overflow. |
| Real Arabic locale/RTL, with long and mixed-direction names/IDs | Use normal native language/preferences on an owned actor and restore the preference. Do not force CSS `direction` and call it localization. Measure logical ordering, icons/popup position, table/form/pane overflow, filename/UUID isolation and source/rendered error behavior. Keep any untranslated app labels an explicit support limit. |
| Keyboard-only plus200%browser zoom and reduced-motion preference | Actual focus-visible open/close/return, dropdown/dialog/sheet order and scroll, Escape ownership, one overlay, dirty native/custom draft cancellation and uncertain submission protection. Viewport emulation alone is not browser zoom. |
| Rendered contrast | Measure computed foreground/background/compositing on representative native/custom text, controls, focus and semantic feedback in both themes. Target4.5:1 normal text,3:1 large text and applicable UI boundaries; distinguish disabled/decorative cases. Source token arithmetic alone is not rendered qualification or formal accessibility certification. |
| Current authority and absence | Fresh viewer/foreign denial, membership or feature loss, no stale names/canvas after fresh denial, restored healthy control, optional widget availability and stale-link refusal after removal. Use normal scoped operations and restore every temporary fixture. |

Complete the D03 history/direct-load/palette/overflow/modified-click checks and
the D05 native customer-widget → linked task → pinned/current document → original
task-tab path. Verify one actual save and cancelled edit, stale conflict and
viewer refusal with exact expected data differences. The existing API-only
revision2 edit is historical evidence, not a UI click to replay. If another
intentional UI edit is required, record its new baseline/expected revision first.
Use matched18608 before views and actual Meridian as the starting reference,
not the rejected independent mockup. Ask for consequential visual judgment with
paired screenshots; routine spacing fixes stay within the approved baseline.

Use current useful18610 for the core comparison and owned auxiliary fixtures
for destructive lifecycle/long-name/authority cases. Journal temporary language,
membership and feature changes and restore their exact intended access state
through normal APIs; revisions/policy epochs may advance legitimately. No user
account, unknown data or protected site's business content is a test fixture.

## E. Final audit, support record and retained-resource handoff

Deliver the actual pattern catalogue, bounded support/limitations record,
installed walkthrough, matched screenshots and exact source/image/app pins.
For each D03-D06 card link current direct evidence and classify unproven items
as open. Carry earlier maintenance/recovery proof only where its unchanged
boundary applies; explain limits rather than rerunning history or implying
complex-migration/general-compatibility support. Resolve newly found defects
with appropriate changed-byte identities and normal reviewed rollout.

Refresh exact protected/current resources, operations and fixture closure.
Retain main populated and source-free review environments, old images, failed
sources, worktrees, checkpoints, archives and notices unless exact cleanup is
separately needed and reviewed. No prune, wildcard deletion, force removal,
publication or production deployment. Final code trees must be coherent and
locally committed; evidence-only generated directories remain explicitly listed.

The full goal completes only after **all** original cards and deliverables have
current evidence, including the in-app visual/interaction matrix. A passing host
suite, native lifecycle or template compiler alone cannot close this plan.

## Execution findings and remaining case

The [native/regression record](evidence/G7/20261114-ui-integrated-native-01/qualification.json)
now proves936canonical tests (934passed/two existing skips), clean core8 and
five-app layer audits, fresh core bootstrap, normal install/use/native uninstall
and separate exact77-file source subtraction. The same canonical process was
observed through the initial supervisor timeout; no broad test rerun occurred.
Source-frozen build/lifecycle work overlapped that independent host run without
changing its tested code, prior targets or main business data.

The default core image was a valid bootstrap candidate but not an exact removal
target: its profile description and omitted empty package list differed from
the app policy. The planner correctly rejected it before registration/apply.
A separate clean candidate used the exact app policy minus the five apps; the
same unchanged guard and normal approval/apply then succeeded. The added data-only
policy binds a new full source map, with every original curated input unchanged.
Do not reuse the default image as a subtraction target merely because core bytes
are equal. The existing `tools/build_clean_removal.py` is the normal exact-byte
subtraction builder; this execution also qualifies the exact source-policy route.

The explicit one-app/absent-companion current-native case now passes under its
[just-in-time execution plan](ui-single-provider-qualification-plan.md).
[Direct evidence](evidence/G7/20261114-ui-single-provider-native-01/qualification.json)
binds the unchanged code, nine-addon/one-archive image, normal two-scope install,
one synthetic customer, native navigation/form metadata and no-effect denials.
It does not prove actual rendering or focus. Preserve the one-app18613, empty18612
and populated18610 sites. All actual in-app D03/D05 and D06 matrix cards remain
open, with support/evidence boundaries in the [qualification record](ui-qualified-combinations.md).
