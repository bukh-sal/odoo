# G5 pure solver and plan core

Implemented and qualified on Windows/Linux; **E-01b and G5 remain in progress**. The operations request UI, independently observed deployment adapter, approvals and executable lifecycle are not yet connected. See [status](implementation-status.md), [packaging](packaging.md) and [operation-lock decision](architecture-decisions/0008-operation-lock-preimages.md).

Install `deploy/requirements-tooling.lock` and `deploy/requirements-operator.lock` with hashes into an isolated Python environment. The latter adds resolvelib1.2.1 without changing the G2 frozen dependency lock. Planning uses this established backtracking resolver and static metadata; it never runs installers, source-build backends, plugin imports or network resolution.

```powershell
.venv/Scripts/python.exe tools/modular.py --config <operator.json> plugin plan --input <proposal.json> --store <existing-catalog>
```

Output is a JSON bundle for review, containing the frozen v1 plan and exact hash, complete operation lock and derived display. This command creates no authoritative approval and executes nothing. The catalog is opened in SQLite read-only mode and its bytes remain unchanged. The approval/apply command path will be added in E-01c/d. Redirecting output is an operator choice; no file is silently installed or published.

The proposal has exactly five sections: `state`, `environment`, `provenance`, `python_metadata`, and `request`. `tests/test_planning_cli.py` gives a runnable example using all three real reference artifacts. This is an internal preparation format rather than a new frozen public API. An app may propose it; an executor must independently observe/recompute it.

- State identifies the deployment, every sharing site, generation, current release lock/digest, exact scoped installations, current bindings/endpoints, policy and independent operator-authorization generation. Only sanitized metadata belongs here.
- Environment explicitly selects platform/native version, every target Python marker value, accepted wheel tags and reviewed core native addon names. Host marker defaults cannot leak into a Linux target plan prepared on Windows.
- Provenance pins upstream commit, native patch/core inventory digests, exact Python runtime/architecture/markers and Python dependency lock digest. Marker/version/platform disagreements fail.
- Python metadata is pre-reviewed static wheel/runtime distribution data, with exact source digest, version, Requires-Python/Requires-Dist and target wheel tags. URL requirements or metadata requiring source-build execution fail planning. Operator-controlled acquisition/build supplies this metadata separately.
- Request identifies operation type, plugin constraints, explicit exact targets and optional updates/provider choices/site constraints/binding/endpoint/grant changes. Fixed operation ID/UTC time produce repeatable bytes. `approved` and arbitrary command fields are rejected.

The solver retains every installed plugin and locked Python root, prefers compatible locked versions, never downgrades ordinarily, and backtracks across plugin/Python/service constraints. Missing constraints distinguish plugin and Python causes; hard cycles show their actual path. Optional integrations do not auto-install. Multiple eligible providers require an explicit consumer-local choice. Existing bindings preserve selection unless explicitly changed. The one selected code version must satisfy every supplied sharing-site constraint; every changed shared artifact needs targets for all current installations. Native dependencies/extension ownership and declared contribution conflicts are checked before runtime import.

Scoped bindings use stable UUIDs and increment generations on changes. The plan validates actual alias/major/API/provider ownership and exact consumer/provider workspace. Its lock also binds permissions/activation declaration changes, full targets and migration digests. Fresh native install selects no upgrade scripts; upgrades select applicable numeric target versions in pre/post/end order. This is metadata selection, not evidence that the real upstream migration ran; runtime ordering qualification remains E-01d.

Feature suspension/enablement preserves the executable release and requires declared workspace support. Native uninstall is destructive, requires a backup and all workspace installations in that site database; it retains executable artifacts until separately removed. Provider removal/suspension requires an explicit dependent closure. Artifact removal is blocked while any site still needs it. Independent executor enforcement and actual effects remain later tests, not implied by these pure guards.

Remaining E-01b integration: actual independently sourced deployment/Python metadata; operations UI and request queue; multiple workspace-specific provider selections where they differ; full enable/provider-health preconditions; complete state-dimension adapters. E-01c/d supply approval/journal locks, revalidation, maintenance/drain, coordinated backup, native execution, fencing and recovery. No G5 exit or additional release acceptance is claimed from this core alone.

Qualification: `tools/qualify_planning.py --output docs/evidence/G5/<fresh-run>` records67 host tests (including20 frozen contracts) and46 focused Linux tests. The Linux container is non-root/read-only/network-disabled, with disposable tmpfs. It receives current source and the locally hash-locked resolver package, including license and wheel RECORD verification. This is an isolated test environment, not a production operator-image build. Current source-bound evidence: [planning-core.json](evidence/G5/20261028T0523322202821Z/planning-core.json).
