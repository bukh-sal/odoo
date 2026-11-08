# ADR0075. Native application installation has real site scope

Accepted8 November2026 after pure planner/projection/independent reconstruction
proof. [Private scope v1](../contracts/native-site-lifecycle-v1.md) specifies the
frozen semantics; runtime qualification remains pending. This extends
ADR0074's native authority path; it does not change workspace authorization or
the qualified core47 artifact.

The general builder now composes ordinary application archives and declared native
dependencies. The current lifecycle installer still requires a nonempty observed
workspace list, and deployment projection expands installations through workspace
features. A native application declared for site scope cannot be represented
faithfully by that path. Do not manufacture a workspace/feature/grant, insert
metadata manually in the installation workflow, or reinterpret a workspace UUID.

Use the existing independently approved lifecycle with an explicit site-native
scope. In the private lock/state, `workspace_id=null` means the actual site-wide
native installation, never "all workspaces" or a wildcard. Preserve deterministic
site/plugin installation identity. Require a native manifest with activation
scopes exactly`["site"]`; reject ambiguous mixed native/workspace state. Native v1
uses native ACLs/rules and admitted native dependencies. No workspace permission
requests, service bindings, endpoints or scoped UI contributions are created by
site-native installation. Cross-app native extension uses its declared addon and
package dependencies. Public workspace request/DTO schemas remain unchanged;
the operator CLI selects site-native intent explicitly.

Independently reconstruct site-native targets from current site metadata and the
actual image/catalog. Check complete dependency closure, source/version/artifact
identities, concrete native installed state and every affected site. Bind a private
scope protocol marker and exact targets into the operation lock/hash and local
review. Display "site-native" explicitly. Existing workspace targets must still
require real active workspace observations and preserve all their old checks.
Preserve publication epochs, maintenance/drain, independent checkpoint, current
approval, failure closure and separately approved restore/resume. Reuse native
module execution and metadata publication, skipping workspace-feature/grant writes
only for validated site-native targets. Read back the actual installation even
when it has no workspace feature rows.

Initial required paths are clean site-native installation, supported staged app
update and foundation maintenance carrying native applications. Unsupported
site-native actions must fail before mutation rather than inheriting workspace
feature semantics. Broader global suspension/uninstall/removal can only be exposed
after their exact metadata, data disposition and recovery behavior is qualified;
the new app must not advertise an unimplemented feature-suspension contract.

Ordinary fresh install must refuse an already-installed unregistered native addon.
Aurora0.1.0 on sealed core47 predates package registration. Its adoption/update
to the selected app0.2.0/foundation successor is a separately reviewed closed
transition, with exact retained row/role/job witnesses and independent recovery.
Do not weaken generic install guards to admit arbitrary legacy module adoption.

Before runtime mutation, freeze the scope semantics and update the corresponding
fixtures/inventory after pure planner/projection/independent-reconstruction tests.
AT-E needs real catalog/image/inventory consumption of non-example application
artifacts through this path. AT-I/J/K/L still require final-image clean install,
populated adoption/update, native workflow/browser/jobs and independent recovery
beside useful Maintenance; unit/source tests do not satisfy those checks.
