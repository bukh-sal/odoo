# Author an owned native application

Use a reviewed source checkout and the isolated interpreter recorded by the
selected kit's `operator-setup.json`. In this development checkout the interpreter
is `.local/toolchain/operator-python16/Scripts/python.exe`. Preserve sealed kits
and installed catalog blobs; create a new version and image for changed bytes.
[Current qualification](implementation-status.md) distinguishes source-supported
authoring from a fully qualified application release.

Ordinary record screens use native models, ACLs/rules, XML views, actions and
menus. Read `applications/mp_aurora_tasks` for list/task permissions and
`examples/mp_example_notes` for explicitly workspace-scoped data. Choose the
application's real authorization boundary; workspace membership is not implied
by being a native app user. A custom page remains available for a plugin that
needs it; Canvas is the minimal example. Native and same-origin code is trusted.

## Explicit inputs

Create a normal v1 `plugin.toml` with your own reverse-DNS ID and numeric version,
native addon mapping, platform/Python constraints, permission/model/contribution
inventory and dependencies. Follow the [manifest schema](../packages/contracts/v1/manifest.schema.json)
and [catalog rules](packaging.md). Native source manifests use the owned archive
ABI's numeric prefix, for example package`1.0.0` maps to native`19.0.1.0.0`.
Historical ABI names do not promise external Odoo addon compatibility.

Add a recipe relative to that checkout:

```toml
schema_version = 1
manifest = "applications/my_tasks/plugin.toml"
addon = "applications/my_tasks/native/my_tasks"

[resources]
"notices/LICENSE" = "applications/my_tasks/LICENSE"
"notices/COPYRIGHT" = "applications/my_tasks/COPYRIGHT"
```

The selected addon directory's name must match `runtime.addon_name`. Include
required schemas and built frontend assets as explicit resource mappings when
declared by the manifest. The builder accepts portable relative paths, rejects
links/junctions and bounds files/counts. It reads native source as data, includes
notices, and creates fixed-order/time/mode ZIP bytes with inventory/provenance.
It runs no application imports, arbitrary build hooks, dependency installer or
network fetch. Prepare any frontend asset build separately as a reviewed input.

Use an existing output directory and a new `.mplug` path:

```powershell
& $mpDevPython -I tools/package_application.py --source $mpDevCheckout --recipe applications/my_tasks/application.toml --output (Join-Path $mpDevOutput 'my-tasks-1.0.0.mplug')
```

The CLI reports plugin/version/bytes and exact SHA-256. Rebuilding identical
inputs produces identical bytes. Existing outputs are refused. Structural
preflight does not grant curated trust; independently review that exact digest
with the ordinary validator/catalog workflow. Review code, required Python
dependencies and their locked runtime solution before approval.

## Compose a release

In a new operator-selected distribution policy, add the addon to `addons` and
the recipe path to `application_packages`. Existing `reference_packages` can
coexist; they retain their reference assembler. For example, the additions to
an otherwise complete selected framework policy are:

```json
{
  "addons": ["base", "web", "my_tasks"],
  "application_packages": ["applications/my_tasks/application.toml"]
}
```

The fragment is illustrative; keep the full required framework closure and
existing policy fields in a real policy. Materialization uses the archive's
verified native bytes, stores the exact `.mplug` in the distribution, and records
its digest and composition in the inventory. Build input enumeration includes
each recipe, manifest, addon and resource even outside historical plugin paths.

Native dependencies must be admitted framework addons or packaged applications.
Declare a hard package/version dependency for every native application dependency;
missing native code, missing/incompatible package edges and ownership conflicts
are refused before output. Required Python packages still need the reviewed image
lock and whole-release solver; packaging alone does not install them.

Build/stage/review the immutable image and exact artifacts through the independent
operator before lifecycle mutation. Existing sites cannot adopt a changed
available-addon policy by editing their configuration or relabeling an image.
They need a supported, explicitly reviewed transition and checkpoint/recovery.

For a site-only native application, use activation scopes`["site"]` and
`supports_feature_suspension=false`, with native XML menus/views and no workspace
permission/service/host-UI registrations. The new source CLI accepts
`plugin plan-current-install --site-native` in place of`--workspace`, with all
ordinary site/plugin/version/digest and independent operator/catalog arguments.
See [private native site scope](contracts/native-site-lifecycle-v1.md). An old
runtime bridge is refused before apply; sealed core47 is not relabeled to gain it.
The source planner/projection tests pass, while actual image/native child
consumption remains required AT-E. Do not create a dummy workspace or manually
insert metadata to bypass this boundary. AT-04 must prove real clean install and
the populated native-only Aurora adoption/upgrade path.

## Application jobs and data

Use workspace-scoped APIs for workspace-owned applications and the explicit
native job adapter for native-authorized applications. Neither converts grant
metadata into a sandbox. The selected [Aurora contract](aurora-tasks-contract.md)
defines role, completion, reminder, inbox and recovery behavior; the native
adapter remains subject to managed-worker and final-image qualification.
Own migration scripts and data changes need declared transitions, exact digest
review, populated data/permission tests and independently recoverable checkpoints.
