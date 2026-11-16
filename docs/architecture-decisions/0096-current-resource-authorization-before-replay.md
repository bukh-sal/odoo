# ADR0096: Resource authorization precedes saved-result replay

Date:16November2026. Status: accepted for local implementation/qualification.

The first real Pages consumer exposed an HTTP service gap: the generic gateway
rechecks workspace/model/feature/binding authority but can return a completed
service outcome before calling the app handler. A record-specific check inside
that handler cannot protect a saved response after the record grant is revoked.

Add an optional private `authorize_resource` method name to trusted native Method
registration. Only `_mp_authorize_*` names are accepted. It receives validated
input in the current provider frame, raises on denial, and returns None on
success. It runs before any service-outcome lookup/insertion and before an
uncached handler. Bound native provider calls use the same hook. No browser/DB
parameter selects the hook, no arbitrary model dispatch and no app ID in core.

Authorizers may take current authorization locks/fences; they must not perform
business/external effects or commit. Existing request rollback semantics remain.
App mutation handlers still lock/CAS and reauthorize the actual effect. A create
command must expose a stable input identity from which its app can authorize the
created resource on replay. It must not check an old expected content revision
as a condition for replaying a completed result. Prefer small mutation receipts
and fresh detail reads to cached labels or permission controls.

The default is None, preserving existing workspace-only services. Frozen request,
binding, output, approval, deadline and error contracts are unchanged. This is a
private trusted-native API and a correction to the promised current-authority
boundary, not an authorization sandbox. Do not divert app writes into an unrelated
transport or mark mutations as reads to avoid the gateway's outcome mechanism.

Pages supplies the installed duplicate/revoke/denial consumer. Source counterexamples
must first prove the actual HTTP and bound-dispatch control flow. Core57's empty
schema proof remains historical; a compatible immutable core58 candidate is needed
for the new hook. Do not replay its completed upgrade or alter protected demos.
