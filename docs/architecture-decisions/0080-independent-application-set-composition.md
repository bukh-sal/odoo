# ADR0080. Add independently authored native application slots

Accepted9November2026 for AP-I/M. [Projects contract](../aurora-projects-contract.md)
selects a second native app and separate optional Tasks integration. Existing
ADR0078 v1 composer only replaces an already admitted application slot. The
ordinary staged native installer already allows packaged application additions
while `validate_plugin_core_stability` protects unrelated native/core source.
Do not weaken core maintenance,trust or independent approval guards.

## Frozen build contract v2

Extend the build-only composer with a bounded application-set path,retaining v1
replacement behavior/CLI. Host recipe2 pins exact sealed49 kit manifest,image and
inventory and selects1..16 reviewed artifacts by portable relative path and exact
digest. Paths stay within the explicit release recipe root;reject source links/
junctions,unknown keys,duplicate paths/identities/addons and mutable outputs.
No author-machine path,application code execution,build hook or implicit download.

The image-side request has exactly`schema_version=2`,foundation_image_id,
foundation_inventory_digest and applications(array). Each row has exactly file
and digest;file is a generated portable`application-NN.mplug`leaf. Hashes are
canonical sha256 strings. Derive plugin/addon/version/dependencies from validated
archive bytes,never caller-provided model/SQL/command data.

Build FROM exact sealed49. Verify every inventoried source file before writes.
Selected existing package:allow newer version or exact unchanged bytes;reject
same-version/different bytes,downgrade or addon identity swap. New package:addon
must be new and cannot shadow any foundation addon or existing recipe identity.
All incoming packages must be native/site-only and admit platform0.1.49.

Validate combined archive/model/field ownership,package/native version dependency
closure and cycles before writing. Stage all native directories as data. Preserve
every unselected archive/addon and every foundation/SDK/engine/tool/Python file.
Only selected app directories/archives and generated inventory may differ.

The policy delta is derived,not arbitrary input:append new application addon
names and logical recipe slots`applications/<plugin-id>/application.toml` in
deterministic order. Preserve all existing policy values and slots. New slots
identify external application source recipes,not copies of foundation code.
Explicit installation/server-wide modules/reference packages remain unchanged.
Recompute ordinary native/package inventories from actual validated bytes.

Host receipt binds recipe/artifact/helper hashes,all exact base/target pins,the
precise derived policy/file delta and retained foundation/environment comparison.
An assembled image grants no curated trust,installation,role or executor approval.
Removal,arbitrary foundation overrides,unregistered legacy adoption and external
worker images remain outside this build path. Compile an older application set
for recovery if desired;ordinary lifecycle guards decide whether a running site
can install/upgrade to it. Do not imply build success authorizes a downgrade.

## Feasibility and return condition

Before substantial app code,prove multi-archive/addon assembly and negative
core-shadow/drift,identity/version,dependency/cycle,duplicate/unknown/path cases.
An actual isolated sealed-image composition/planner proof must show ordinary
site-native install with no public contract/core changes or fabricated workspace.
Use a clearly marked temporary probe;never install an import-trap probe or count
it as a useful application. Retire its exact image/alias after proof.

Then implement the frozen Projects workflow/extension in separate source repos,
qualify actual native access/new forms/app sets/populated upgrade/recovery,and
reproduce useful final compositions. Retain original v1 tests and historical
evidence. Unchanged public contracts must pass their existing freeze;new build
protocol2 has its own strict producer/consumer fixtures. No new platform service,
orchestrator,marketplace,theme or Canvas expansion is needed.
