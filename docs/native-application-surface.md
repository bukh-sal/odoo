# Candidate native application surface

This is the concrete authoring subset demonstrated by the owned clean core and
independent application work, not a promise to support every inherited engine
API or arbitrary third-party addons. It complements [application authoring](application-authoring.md),
[packaging](packaging.md) and the [owned-fork decision](architecture-decisions/0071-owned-fork-and-addon-boundaries.md).
The [provisional candidate support boundary](candidate-support.md) records the
owner's addon, support and licensing choices. Broader support remains deferred.
Native and same-origin application code is trusted; none of these APIs is a
sandbox for hostile code.

## Models, records and permissions

| Surface | Application responsibility | Evidence and boundary |
| --- | --- | --- |
| `models.Model`, `fields.Char`, `Text`, `Boolean`, `Integer`, `Selection`, `Many2one` | Own model/table names, required fields, defaults, constraints, content bounds and relation semantics | Independent Partners uses these fields in its own table, without extending a core business model. Native installation left every non-app table column unchanged. Other engine field types exist but are not all qualified by this slice. |
| `models.Constraint`, `@api.constrains`, `@api.model_create_multi`, `create`/`write` overrides | Enforce business invariants in server code, including native entrypoints; XML readonly/domain attributes alone are insufficient | Unique public identity, positive revision, immutable kind/ownership, bounded content and same-workspace organization links were exercised. |
| `mp.workspace.scoped`, `_mp_plugin_id` | Declare the owning installed plugin; retain superclass guards and relation validation | [Implementation](../framework_addons/mp_identity/models/scoped.py) resolves current actor/membership/feature state for read/search/create/write/unlink, injects workspace ownership and prevents public-ID reassignment. ACLs/rules remain additional gates. |
| Native ACLs and record rules | Declare explicit model access and rules; use current human or scoped technical context | Viewer is read-only; nonmembers and foreign-workspace relations/records are refused. Trusted `sudo`/raw SQL can bypass normal gates and must not be presented as application isolation. |
| `search`, `search_count`, `read`, `web_read`, list/form reads | Bound queries, field selections and DTOs; minimize sensitive output | Actual A/B counts and foreign reads were verified. Scoped relation checks apply to supplied relations, not merely search widgets. Apps must review custom SQL, computed fields, exports and newly overridden methods separately. |
| Application revision/CAS | Define revision semantics, lock/update atomically and reject stale writes; provide a native form adapter when needed | The Partners app owns its expected-revision adapter. Native form save and service mutation share the same server revision check. Core does not automatically add optimistic concurrency to every arbitrary model. |

Workspace context is request-local, never client authority. Dataset requests
carry the selected public workspace ID and pinned client-release token; the
server resolves current membership again. Client-supplied platform authority
context is refused. A workspace picker or cached view does not keep a revoked
membership valid. App-owned expected revision values are preconditions, not
permission grants.

## Native screens and application assets

Use manifest data files for XML list/form/search views, window actions and
menus. Assets are inventoried application source and remain inside the exact
native archive/image; no live source injection or arbitrary install hook is
needed. Standard buttons, fields, Many2one lookup and list/form navigation use
the retained WebClient. Application-specific record-save behavior belongs in
the app's native controller/model adapter, not in a core branch for that app.

The candidate core0.2 workspace picker uses the existing authenticated workspace
list, opens a separate `/odoo?workspace=<public-id>` page and drops the old
action/record context. Existing tabs keep their drafts and release/workspace
pins. It requires neither the reference shell nor an application-specific link.
Menus and visible actions are navigation, not authorization. The original
backend gates remain decisive even when an action URL is known.

Custom Owl/client actions are trusted native extensions. The optional reference
shell's custom page facade and fixed reference shortcuts are not mandatory
clean-core dependencies. Availability of an inherited widget, global object or
private engine method does not make it a separately supported application API.

## Services and cross-application calls

Declare a service/API version, methods, package schemas and permissions in the
application manifest, then register its trusted native implementation with
[`registry.Method` and `register`](../framework_addons/mp_core/registry.py).
Handlers must use the explicit `_mp_service_` naming seam. Input schemas may be
app-owned literal JSON Schema with local `$defs` and local references; legacy
registered core definitions remain supported. Output validation is independent.
No client can select an arbitrary handler, schema path or model attribute
through the service gateway.

Normal bindings select provider installation/API identities. Bound provider
calls and HTTP gateway calls preserve current actor/model access, permission,
feature, grant, binding, release and transaction checks. Declare cross-app
permission requests and obtain normal approved grants; service metadata is not
proof of current access. Mutation idempotency keys identify the original
validated request and are not permission tokens. Error responses are bounded;
raw SQL, tracebacks and credentials do not belong in public errors.

## Jobs and events

The inventoried native job runner and registered server-side job adapters are
the supported execution route. There is no generic HTTP endpoint accepting
arbitrary handlers or SQL. Preserve original actor/resource/revision context,
bounded deadlines/retries, fenced claims and fresh checks before final effects.
Cancellation, uncertain external outcomes and coordinated dispatch recovery
require their existing lifecycle protocols. Partners deliberately has no job
handler; its qualification does not prove every job/effect profile. See
[job/event qualification](jobs-and-events.md) and
[native application authority](architecture-decisions/0074-native-application-job-authority.md)
for the separately demonstrated profiles.

Concrete trusted entrypoints are `job_dispatch.JobDefinition`/`register`,
`enqueue_bound(env, alias, ident, values, key, ...)` for an already authorized
bound workspace service, and `job_dispatch.enqueue_scheduled(..., schedule=...)`
for that same authority mode. A definition declares owned identity/version,
input/prepared/computed/output schemas, resource authorization and separate
prepare/compute/apply functions, plus bounded attempt/time and effect policy.
Site-native apps use the separate `native_jobs.enqueue_scheduled(env, ident,
values, key, schedule=...)` route with a registered `authority='native'`
definition and exact owning addon; they do not invent a workspace binding or
serialize a privileged environment. `prepare_one`/`finish_one` are runner
orchestration, not application HTTP endpoints. Status/cancellation must retain
the definition's current actor/resource checks. External non-idempotent effects
need explicit reconciliation; queue retry alone cannot make them exactly once.

Register application domain events with
[`Topic` and `register_topic`](../framework_addons/mp_core/events.py). The app owns
payload JSON Schema, aggregate identity checks and per-event read authorization.
`emit` participates in the caller's transaction and validates before durable
append. Generic transport bounds are envelope rules, not app-domain rules.
Native bus wakeups carry no business payload; authorized durable delivery uses
the registered topic/binding and current scope. Consumers use explicit owned
`Consumer` definitions, not arbitrary client callbacks with server authority.

The bounded independent-app proof exercised real subscribe/poll/ack/close,
per-aggregate sequencing, duplicate current acknowledgement and wrong-actor/
workspace denial. A viewer received an editor-produced minimized event. This is
at-least-once delivery, not exactly-once processing. The human HTTP proof is not
a browser callback or native consumer-effects qualification. App consumers need
their own idempotency/effect tests.

## Packaging, lifecycle and compatibility

An ordinary recipe is source data relative to an application checkout. An
operator may select it from a separate repository through an explicit local
path wrapper; path-prefixing must not change archive bytes. Structural assembly
does not grant trust. Admission, catalog selection, immutable image staging,
independent exact-hash approval and current database/authority checks remain
required. See [clean builds and exact removal](clean-candidate-build.md).

Keep schema changes, migration scripts, permissions and native lifecycle
declarations in the app. Uninstalling native metadata/data, removing source
from the image and deleting historical event/checkpoint evidence are distinct
actions. A source-removal plan must account for every sharing database and all
surviving dependencies. A retained failed database can legitimately block it.
Restore verifies the coordinated checkpoint and current authority into a fresh
database/filestore namespace; traffic resume is a separate reviewed decision.

Compatibility uses the image-observed platform/native versions and the exact
app-declared range, not the latest host SDK constant. Historical Notes/Canvas
archives declaring `<0.2` remain rejected on0.2; neither their bytes nor their
constraints are relabelled. The independent Partners archive explicitly admits
both tested candidates, and is byte-identical across core53 and the useful
core0.2 workspace-navigation successor. Populated upgrade preserves its records
and permissions. These bounded results do not establish a universal ABI,
long-term support policy or compatibility with external Odoo releases.

[Current evidence and remaining work](implementation-status.md) distinguish
source checks, real installed behavior, browser proof, recovery and final
release acceptance. Provisional candidate numbers are not stable-release claims.
The [capability register](application-capability-register.md) distinguishes
demonstrated behavior, intentional boundaries, repairable gaps and unproven
application paths; none of these categories substitutes for visual qualification.


## Contextual client actions

App links should use the existing native action protocol, rather than read ad hoc
query parameters after asynchronous startup. Declare the action's `path` in its
native metadata and the component's static path. Capture owned action parameters
from `props.action.params` (or the current router state) synchronously, validate
identifiers, and resolve the referenced object through current authorized services.
Use `props.updateActionState` to retain the selected app context in reloadable
navigation. Workspace is still controlled by the core workspace context; apps do
not redefine its locking or authorization.

A contextual panel can belong to a separately optional integration application.
The provider app may expose a trusted component slot; the integration owns its
links, dependencies, declared grants and original-actor bound calls. Clear stale
panel data when permission disappears and preserve the independent task workflow.
This uses existing trusted same-origin/native extension behavior, not a sandbox.

Navigation is also a data-loss boundary. Preserve or explicitly confirm discarding
unsent edits and comments. A separate contextual tab can retain the original draft;
a before-unload guard protects full-page navigation. These patterns still need
actual browser checks: a URL in source alone does not prove route selection,
reload behavior, draft retention or usability.
