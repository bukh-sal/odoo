# Owned addon cleanup and restructuring

Authorized7 November2026. Implements the retention review and ADR0071.
The active checklist/evidence/blockers/resume capsule are in
`docs/implementation-status.md`. Core46 is a sealed historical release and must
remain unchanged. This goal has no Odoo interoperability requirement.

## Required path and exit checks

One work item is active. Gate weights total100; evidence, not generated file
counts or documentation, earns progress. Sixteen AR checks are separate from
the original99 R1 and12 CF checks.

| Gate | Weight | Required exit evidence |
| --- | --- | --- |
| AR-01 audit/freeze |10| AR-A: exact keep/move/remove inventory, namespace and Python/JS/XML/asset/data/test reference audit. AR-B: retain source/image46 inputs, dependency boundaries and supported transition decisions; freeze public contract impact before deleting source. |
| AR-02 dependency extraction |25| AR-C: editor functions without IAP/mail imports or Odoo-hosted media/AI dependencies. AR-D: platform settings/catalog omit removed-app recommendations, upsell and vendor marketplace paths. AR-E: generic messaging/chatter/activities optional, with separate Discuss/gateway entry points rather than mandatory app UI. AR-F: meaningful source/native regression coverage and minimal core cold boot for extracted dependencies. |
| AR-03 source ownership/pruning |20| AR-G: engine/framework/application/example/test roots are authoritative, with no duplicate vendor tree or old discovery roots. AR-H: unused629 inherited addon trees removed after reference audit, useful23 test fixtures retained/adapted separately. AR-I: builder, source inventory, artifact tooling, CLI, test lookup and package discovery work from new roots. |
| AR-04 populated release lifecycle |25| AR-J: independently reviewed46→new release transition validates exact policy/module changes, ownership/migrations and data preservation. AR-K: populated Aurora/Maintenance/native views/permissions/jobs and optional communication profiles pass. AR-L: injected failure, fresh independent recovery and separate resume pass while peer stays useful; unsupported changes/authority remain refused. |
| AR-05 release requalification |20| AR-M: clean core-only, Aurora-only and Maintenance boot/install profiles with exact installed sets. AR-N: final image reproduces inventory; isolated kit operator/consumer and source/build provenance pass. AR-O: current host/contracts/native/browser/job and finite privacy checks pass at declared scopes. AR-P: handoff, retention accounting and exact owned Docker/temporary asset retirement; no uncertain mutation. |

Gates run AR-01→02→03→04→05. Small fixtures needed for a gate are allowed.
After two materially distinct failed approaches, record the failure and choose
a smaller/new hypothesis; do not reset a database or replay an uncertain apply.
Reopen affected gates when changing qualified source or contracts.

## Initial inventory and intended ownership

Baseline513cf91d:665 inherited addon directories (641 community+base/23tests),
13 inherited+10 owned shipped. Keep useful engine and regression infrastructure;
remove unused629 top-level addon trees from the active source. Git history is
the retrieval source for future deliberate application adoptions.

- `engine/odoo/`, `engine/odoo-bin`: owned Python runtime and launcher; retaining
  its initial internal namespace is an implementation choice, not compatibility.
- `framework_addons/`: base/web/auth/settings/import/bus/editor and owned
  platform authority/lifecycle/UI services, plus optional generic communication.
- `applications/`: adopted Maintenance/Aurora and optional Discuss/gateway apps.
- `examples/`: reference addon sources; `plugins/` remains their package inputs
  unless a clearer single move is justified.
- `tests/addons/`: useful inherited regression/feasibility addons; separate
  discovery from shipped modules. Existing installer fixtures remain tests.

The runtime image may materialize one flat installed Python/addon layout from
these owned source roots; it must not ship a second copy of the old tree.
Do not change serialized public contracts or native ABI names for cosmetics.
If a semantic change needs a new identifier/schema, record the exact migration,
freeze revision and supported own-archive path. No arbitrary Odoo packages are
promised support by retaining an inherited spelling in old artifacts.

## Extraction and migration constraints

Manifest dependencies are not sufficient: html_editor directly imports IAP and
mail helpers, and mail includes Discuss/gateway code/assets/data. Audit actual
import/asset/XML/model relationships before choosing final extraction seams.
Keep useful framework primitives; remove unwanted vendor routes/buttons/code,
rather than leave clickable stubs or another compatibility wrapper.

Source moves alone must preserve package contents/IDs where practical. Direct
engine changes are allowed and recorded in the inherited patch/provenance
ledger. Preserve license notices. Keep stock native UI infrastructure.

Available-addon policy expansion/removal and modified inherited modules are
currently outside the core-upgrade guard. Design an exact independently reviewed
owned release transition, not a blanket guard bypass. Observe installed modules
and stored data under old46 code. Preserve retired-module data where required;
do not silently drop IAP/mail data or simply falsify module state. Pause/drain,
checkpoint, source/target validation, current authority, claim fences and separate
recovery/resume remain mandatory. An operator-reviewed retirement/migration must
record its effects and retained data. New target versions are assigned to real
source changes; do not invent schema changes solely for a test.

No apps are silently installed to make a core-only profile boot. No fake Notes
installation target substitutes for a core operation if a real plugin-free
operation is needed. Optional app profiles must declare their own dependencies
and current rights. Native trusted code remains trusted, not sandboxed.

Excluded: new business features, UI redesign, full Aurora migration/imports,
broker/autoscaling/provider delivery, R2/R3, production/publication and global
Docker/Python changes. Fix failures on this required path; record unrelated
improvements with their trigger rather than expand the goal.
