# Private native site lifecycle v1

Contract revision22, ADR0075. Additive to the owned v1 public approval envelope;
existing workspace HTTP request schemas and canonical goldens stay unchanged.

`plugin plan-current-install --site-native` is mutually exclusive with repeated
`--workspace`. It requires the existing config/catalog/deployment/site/plugin/
version/digest arguments. `--operator-store` keeps its existing independent
observer authority; catalog storage never becomes the control store.

A native site target has the existing private target fields:
`installation_id`, `site_id`, `workspace_id`, `plugin_id`, `action`.
Only `workspace_id` is NULL, explicitly representing the one real site-native
installation. UUIDs remain canonical and installation identity is derived from
the site/plugin or retained existing identity. NULL is not a wildcard, omitted
workspace selection or authorization to operate on workspace records.

Native site manifests have runtime native, activation scopes exactly`["site"]`,
`supports_feature_suspension=false`, no workspace permission requests, no host
service provides/requires, and no host page/navigation/slot/command/contribution
registrations. Native XML menus/actions/views and optional native client actions
use the existing WebClient. Workspace/custom-page plugins retain their existing
capabilities. Site-native package dependencies must close over compatible
site-native packages; admitted framework addons remain part of the image graph.

The private operation lock includes`native_site_scope_protocol:1` (integer, never
boolean) exactly when a target has NULL workspace. The lock is bound through the
existing dependency digest and plan hash. Local display adds`native_site_targets`
with concrete site/installation/plugin/action and scope`site-native`. Independent
reconstruction must produce identical marker, targets and display. Application
requests, serialized roles or grants do not supply scope authority.

Initial supported actions are native install/upgrade and deploy targets carried
by platform maintenance. Other native-site actions and tombstone reinstall are
refused before mutation. Workspace activation still requires an active real
workspace and a workspace-capable native manifest. Preserve complete dependency
closure, current exact artifact/image/runtime checks, original approval and
site/deployment lock scope, checkpoint/drain and failure/recovery discipline.

Project actual native site installation rows from installation metadata plus
matching verified artifact and installed native version, without feature rows.
The existing private state row uses NULL workspace and derived enabled status;
this does not create a workspace feature or grant. Reject mismatched native
versions/artifacts, workspace features or grants on that installation. Native
metadata publication checks the same profile, creates/updates real site metadata,
and skips workspace-feature/grant writes only for this validated scope. The
executor checks exact target-image native metadata/reader bridge source before
mutation; an old bridge must fail before a possible native commit.

An already-installed unregistered addon is not a fresh install. Reject it on
both current-image and staged paths. Aurora's known old47/native0.1.0 adoption
must use its separate reviewed closed transition, with retained data/permission
witnesses, failure closure and independent restore/separate resume. This contract
does not authorize arbitrary legacy adoption, schema migration or source removal.

Pure scope/planner/projection/independent-reader tests establish the contract.
AT-E and AT-04 still require actual reviewed image/artifact consumption, native
metadata child execution, app/job/browser behavior and supported release recovery.
