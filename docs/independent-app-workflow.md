# A current independent application workflow

Start with [current development](current-development.md): build the default core,
create a named disposable development site and retain its protected operator
directory. Use the public commands below separately; no private qualification
runner is required. This is local development, not production onboarding.

## Own and package the application

Keep your application in its own private repository under an operator-selected
checkout such as `applications/external/YOUR_APP`. That source is not part of the
core repository. Follow [application authoring](application-authoring.md) for its
manifest, declared dependencies, native model ownership, ACLs, scoped rules,
views and explicit resources. Native Python is trusted code. A manifest permission
description does not enforce access or make a sandbox.

Choose the user-facing policy before coding. For example, a workspace log can
have immutable saved content and a monotonic receipt, rather than ordinary edits.
Enforce that in model methods as well as the UI; readonly fields are not server
authorization. Current human, workspace role, feature and foreign-record checks
must happen before mutations or cached results. Decide separately what uninstall
and checkpoint restoration mean for that data.

Use your app's relative portable recipe to assemble a **new** archive:

```powershell
$appSource = 'applications/external/YOUR_APP'
$appArchive = '.local/YOUR-QUALIFICATION/packages/YOUR_PLUGIN-0.1.0.mplug'
# Explicitly create the owned output parent first. Existing output is refused.
& $candidatePython -I tools/package_application.py --source $appSource `
  --recipe application.toml --output $appArchive
```

Record the returned plugin/version/digest/bytes. Packaging validates declarations
and collects source without importing native code. Review the actual source,
dependencies, license/notices and archive inventory. Repeated assembly can prove
archive equality; it grants no trust and does not prove native or browser use.
Never replace an old archive under its old version after a correction.

## Compose the immutable runtime

A core image cannot install addon bytes it does not contain. Supply a separate
**operator-owned local** recipe under `deploy/application-inputs/` with manifest,
addon and each resource path relative to the platform checkout. These recipes
can contain private paths and are intentionally local-only here; do not assume
the repository includes your private application or its recipe.

For example, an operator recipe uses checkout-relative paths (replace every
`YOUR_*` value; add every resource your manifest declares):

```toml
schema_version = 1
manifest = "applications/external/YOUR_APP/plugin.toml"
addon = "applications/external/YOUR_APP/native/YOUR_ADDON"
[resources]
"notices/LICENSE" = "applications/external/YOUR_APP/LICENSE"
"notices/COPYRIGHT" = "applications/external/YOUR_APP/COPYRIGHT"
"notices/NOTICE" = "applications/external/YOUR_APP/NOTICE"
```

Make an explicit development composition from the default clean-core policy:
add your native addon to `addons` and your operator recipe to
`application_packages`. Preserve the clean runtime/default framework selection;
the resulting artifact is app-enabled, not app-free. Do not add the app to the
core's explicit bootstrap install list. The normal operator will install it.

```powershell
& $candidatePython -I tools/build_candidate.py --gate G7 `
  --policy deploy/YOUR-APP-COMPOSITION.json `
  --output docs/evidence/G7/YOUR-FRESH-BUILD
```

Inspect the build record, exact source map, inventory, core/app versions,
interpreter and dependency hashes. Distinguish project-file equality from native
dependency bytes and OCI layers. In this qualification, two native extensions
rebuilt to different bytes at the same locked versions. The exact new hashes
must be reviewed/bound by the release; locked versions are not a bit-reproducible
build claim. No digest relabelling or source/runtime guard relaxation is needed.

## Admit, stage and nominate

Use the actual protected `target.json`, trust configuration, catalog and control
store generated for your site. After independent source/digest review, explicitly
add the exact digest to curated trust and advance its generation, preserving
existing digests and policy fields. Do not enable unsigned development as an
approval shortcut. Validation and catalog admission are separate from execution:

```powershell
# $candidateWork is the workdir used by initialize_candidate.py.
$appPrivate = Join-Path $candidateWork 'private'
$appLocal = Join-Path $appPrivate 'site'
$appTrust = Join-Path $appLocal 'operator/trust.json'
$appTarget = Join-Path $appLocal 'operator/target.json'
$appStore = Join-Path $appLocal 'operator/control'
$appCatalog = Join-Path $appPrivate 'catalog'
# $appDigest is the independently reviewed exact package digest.
# $appImage is the independently reviewed immutable build image ID.
```

```powershell
& $candidatePython -I tools/modular.py --config $appTrust plugin validate `
  $appArchive --digest $appDigest
& $candidatePython -I tools/modular.py --config $appTrust catalog `
  --store $appCatalog add $appArchive --digest $appDigest
& $candidatePython -I tools/modular.py --config $appTrust plugin stage-image `
  --store $appStore --deployment-config $appTarget --catalog $appCatalog `
  --image-id $appImage
```

`plan-staged` accepts a nomination containing `operation_type` and exact `targets`.
Each target specifies `installation_id`, `site_id`, `workspace_id`, `plugin_id`
and `action`. For an initial installation the existing planner derives the site
installation UUID as `uuid5(UUID(site_id), 'plugin:' + plugin_id)`; a caller may
use Python's standard `uuid` module to nominate that value. Independent planning
checks it, so a nomination grants no identity or authority. Subsequent operations
use the actual observed installation ID. Workspace-enabled apps nominate their
intended workspace scopes; site-native apps use their declared site-only path.

The nomination shape is:

```json
{
  "operation_type": "install",
  "targets": [
    {"installation_id":"DERIVED-INITIAL-ID","site_id":"ACTUAL-SITE-ID","workspace_id":"ACTUAL-WORKSPACE-ID","plugin_id":"YOUR-PLUGIN-ID","action":"install"}
  ]
}
```

Read the current site ID from `target.json`. The development fixture's workspace
public IDs are in `site/fixtures.json`; the normal workspace picker lists the
same authorized workspaces. Use public UUIDs, not raw database row IDs. Include
another target for a second intended workspace. An upgrade nominates `upgrade`
in both the operation and target action against the existing installation ID.

```powershell
& $candidatePython -I tools/modular.py --config $appTrust plugin plan-staged `
  --store $appStore --deployment-config $appTarget --catalog $appCatalog `
  --input .local/YOUR-QUALIFICATION/nomination.json
```

Save the returned bundle as UTF-8 JSON without a BOM. Review the **whole** plan
and lock: package/native/Python identities, exact scopes, declaration changes,
permissions, dependency resolution, migrations, checkpoint and restart effects.
Stage and planning do not change the live target.

## Independently approve, apply and verify

Follow [normal operator commands](application-operations.md) to register the
saved bundle, review its current state, approve its exact hash and apply once.
New trusted native code requires the trust acknowledgement. Expanded activation
or permission declarations can require the permission acknowledgement even when
`permission_changes` is empty. Destructive acknowledgement follows actual effects;
do not pass all flags indiscriminately or infer them only from the author's
`destructive=false`. Interactive approval is the default. Noninteractive testing
also requires the explicitly selected disposable operator policy.

Reload the durable target after worker replacement, then use a fresh observer
and current client-release token. Verify raw installation/native version plus
projected workspace features and actual useful UI behavior. One raw installation
can yield multiple workspace feature rows; do not mistake them for duplicates.
The stock workspace selector opens a **new tab**, preserving existing drafts;
use that workspace tab rather than an unscoped `/odoo` tab.

Required fields assigned by server code still need a usable native form. The
actual stock client checks active required fields even when readonly, and parent
group invisibility alone is insufficient for a server-assigned author field.
An app view may suppress that field's client-only required check while the model
keeps the required identity and server injection. Verify the real initial save;
schema/HTTP tests alone would miss this usability defect.

For evolution, create a successor package/version, new immutable image, admit
and stage it, then nominate `upgrade` against the observed existing installation.
Qualify populated preservation and a genuinely changed user-facing behavior;
an empty-site repair is not populated-upgrade evidence. Keep old archives,
images, checkpoints, source and failure receipts.

After any error, inspect the same operation/target/receipts and actual effects.
Client validation may have made no request; a timeout may have committed. Neither
justifies blindly repeating a create/apply, deleting an intent or forcing a hash.
Expired or changed reviews require fresh independent reconstruction, not a
retimestamped bundle. Completed-checkpoint recovery remains separate required
PP04 work; reinstall is not a promise to restore deleted business data.
