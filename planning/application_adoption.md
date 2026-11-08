# Application adoption program

Authorized 8 November 2026 (Asia/Riyadh). One umbrella goal runs the four phases
below sequentially without asking for approval between phases. Current state,
acceptance results, blockers and resume instructions belong only in
[implementation status](../docs/implementation-status.md). This plan defines
scope and exit checks; creating it earns no implementation progress.

Start from sealed core49/Tasks0.2.2, [final delivery](../docs/evidence/post-r1/aurora-tasks/final-delivery.json).
Preserve that kit/image and sealed47/46. Native WebClient infrastructure and
list/form screens stay the default. This is our owned fork, with no external
Odoo compatibility objective. Aurora is read-only at bedrock-2.2 commit
`e48e04ed4cf155a83e66e08dfb33a669ebb5c228`.

## Phase order and progress

| Phase | Weight | Prerequisite | Outcome | Acceptance |
| --- | --- | --- | --- | --- |
| AP-01 |20| sealed49 | A usable local Tasks pilot and evidence-based limitations | AP-A..D |
| AP-02 |30| AP-01; freeze selected app delta and downstream contract | Separately authored, populated application-only upgrade/recovery | AP-E..H |
| AP-03 |30| AP-02; freeze selected business workflow/integration | Another useful application and optional cross-app extension | AP-I..L |
| AP-04 |20| AP-03 | Short repeatable downstream developer/release workflow and handoff | AP-M..P |

Each phase's four acceptance checks have equal shares of its weight. Report
verified weighted points separately from acceptance counts. No points for plan,
generated files, a build alone, queued operations or unverified source code.
Keep one primary work item active. Small prerequisites identify their parent
check, concrete output and return condition. Finish each phase before advancing.

## AP-01 — Pilot the delivered release

- [ ] **AP-A:** Create a fresh, clearly owned local development site from exact49,
  install Tasks0.2.2 through independent approval, and start a reviewed managed
  worker profile. Record source/image/artifact pins, ownership, resource bounds,
  start/stop/resume commands and credentials location privately. Preserve this
  useful pilot across checks; distinguish it from disposable fault fixtures.
- [ ] **AP-B:** Exercise daily workflows in the in-app browser: create/configure
  a shared list, create/assign/edit tasks, due dates, completion/reopen and private
  reminders/read-state/Open task. Use several fictional users and useful records,
  including native views and search/filter/navigation behavior.
- [ ] **AP-C:** Check owner/member/external-assignee/outsider behavior through
  actual authorized and denied operations, two-session/stale edits where relevant,
  cancellation/reassignment and a bounded worker stop/start. Verify retained
  data and eventual notice behavior; never equate a queued job with delivery.
- [ ] **AP-D:** Record observed developer/user limitations with evidence and
  triage. Fix only pilot-blocking correctness/access/data-loss problems here;
  select one useful application change for AP-02. Document a reproducible pilot
  walkthrough and its boundaries. Agent walkthrough is not human usability
  acceptance; lack of optional human feedback does not block this unattended run.

## AP-02 — Independent application authoring and release

AP-01-P1 exception after the first pilot: native new-list creation is blocked by
a required/read-only owner with no client default; the task creator has the same
missing default in actual `default_get`. Record AP-B failed and keep AP-01 active.
The smallest required repair is a new Tasks artifact, not a UI bypass or edit to
sealed49. Pull forward only AP-E/F's separate-source/composition prerequisite and
the necessary approved app update, then return to AP-B. Freeze its exact default/
ownership/data contract first. Full AP-02 populated failure/recovery qualification
still follows AP-01; any valid early evidence is linked, not counted twice.

- [ ] **AP-E:** Create a separate owned application checkout/repository outside
  the foundation source roots. Pin foundation49 and package from that application
  source using an explicit recipe. Prove that downstream developers do not need
  to copy/patch foundation code. Compare exact foundation source, dependencies,
  contract and platform version. Repair a demonstrated composition/tooling gap
  with the smallest reviewed change; never smuggle source into ignored build paths.
- [ ] **AP-F:** Implement the useful Tasks change selected in AP-01 as a new
  immutable application version, with explicit source/provenance/dependencies,
  upgrade declaration and native views. Produce reproducible baseline/successor
  deployment artifacts. A native app change needs a new composed image even
  when foundation code/version stays fixed; do not claim the image is unchanged.
- [ ] **AP-G:** Independently approve/apply a real app-only upgrade on populated
  data. Preserve IDs, roles, assignments, files, original job actors, logical
  schedule/deadline and deduplication; demonstrate stale-claim refusal and actual
  effects. Reject unsupported versions/dependencies/drift before mutation.
- [ ] **AP-H:** Cause a bounded post-commit/publication failure on a disposable
  sibling deployment, stop its app, independently restore the original app release
  into a fresh database and separately resume. Preserve current revocation and
  keep the pilot useful. Qualify a fresh forward operation and record the actual
  developer steps/remaining coupling. Do not replay an uncertain apply.

If an actual required defect forces a foundation successor, preserve49 and record
the deviation, impact, freeze and qualification. Finish by proving at least one
genuine application-only update with unchanged selected foundation code/version.
Do not invent a core/schema change to manufacture an upgrade exercise.

## AP-03 — Another useful business application

- [ ] **AP-I:** Compare bounded source candidates and select/freeze one workflow,
  native model/data/role contract, dependencies and integration boundary before
  substantial implementation. Initial candidate: Aurora Projects (name,
  description, manager, lifecycle states); inspect actual API/permissions/tests.
  Optional customer/logo/full Partners import are not assumed requirements.
  Reuse retained framework features wherever they satisfy the selected need.
- [ ] **AP-J:** Implement that bounded application in its own downstream source
  with native list/form/search/actions, real roles and server-enforced denials.
  Demonstrate an everyday workflow beyond Tasks. No theme/shell rewrite, full
  Aurora port, accounting or unrelated product expansion.
- [ ] **AP-K:** Implement a separately declared optional extension connecting
  the new app to Tasks or Maintenance. Require exact compatible package/native
  dependencies and both records' current access rights. Demonstrate useful linked
  work, outsider denial/no metadata leak and independent operation without the
  extension. Do not hide a mandatory dependency inside application code.
- [ ] **AP-L:** Qualify clean installation, populated app evolution and compatible
  app sets on the common foundation. Include an integration-absent profile,
  dependency/version refusal, native browser workflow and independent recovery
  for actual new persistent effects. Reuse earlier evidence only where code,
  contract and deployment bounds are demonstrably unchanged.

## AP-04 — Reusable local workflow and delivery

- [ ] **AP-M:** Consolidate the commands actually exercised in AP-01..03 into a
  small documented developer path: author, validate, package, compose, test and
  inspect artifacts. Explicit foundation pin, arbitrary supported application
  source and per-system release recipe. Avoid a parallel generic framework or
  a new orchestration service.
- [ ] **AP-N:** Provide a short operator path for plan/review/approve/install/
  upgrade/status/restore/separate resume and local pilot start/stop. Keep executor
  authority independent; no automatic grant, hidden Docker control in app APIs,
  or wrapper that silently approves a new hash. Record state before mutation
  and make uncertain operations inspectable rather than blindly retryable.
- [ ] **AP-O:** Run the documented path from a clean downstream checkout and
  isolated operator with no author-machine path assumptions. Automate meaningful
  artifact/dependency/role/upgrade/recovery checks and verify source/dependency
  drift refusals. Record affected tests, reproducibility and finite credential/
  source hygiene. Cleanup must be ownership-bound and preserve unrelated assets.
- [ ] **AP-P:** Deliver checksummed application/release artifacts, developer and
  operator instructions, useful retained pilot access instructions and final
  phase/acceptance decision. Reconcile roadmap/status/evidence/limitations.
  Retire all obsolete disposable containers/volumes/networks/images/aliases;
  list intentional pilot resources with bounded retention and stop/cleanup steps.

## Limitations and control points

Use [the limitations register](../docs/application-adoption-limitations.md).
Each item records: stable ID, developer/usage/both perspective, observed evidence,
severity/impact, current boundary, fix now or deferred trigger, owning check,
verification and current state. Separate observed defects from deliberate scope
and unproven concerns. A resolved item retains its original counterexample.

Before new code at each phase, record its selected contract/dependency boundary;
change frozen contracts only with ADR, schema/golden/consumer checks and freeze
requalification. Historical AT/AR/CF/BG/R1 passes retain their recorded scope.
Follow spec§25 attempt and loop rules: inspect journals before retrying, review
source/logs/minimal reproduction after two failed approaches, and change the
experiment after three repeats without new evidence. Review direction after
each work item or45minutes on one unresolved problem. Optional polish goes into
the register, not the active path. Continue between phases automatically.

## Scope and unattended operation

Local Git, isolated Python and owned Docker development/disposable targets only.
Synthetic users/business data. Preserve source/license notices and record actual
engine edits in the upstream-patches ledger. Aurora's checkout stays read-only;
read committed files, not its `.env`, media or database. No sub-agents are
authorized. Native/same-origin code remains trusted, not sandboxed.

Excluded: full Aurora/history import, real-data migration, accounting, branding,
Canvas expansion, production/hosted deployment, publication/paid services,
R2/R3/hostile code, marketplace and speculative broker/autoscaling work. No human
sign-off is inferred from agent testing. Ask only for genuinely required input;
an optional preference or absence of human feedback is not such a dependency.
