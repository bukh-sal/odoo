# ADR0084: Current-authority binary transport for workspace applications

Date:13 November2026. Status: accepted design; source and installed qualification
are separate. Owner: PP-02 / CR-0020.

The document-library phase needs useful file sizes beyond the64KiB JSON request
bound. Existing `ir.attachment` access is deliberately unavailable for managed
workspace models. Inherited binary routes can elevate through a public or
limited-field token before normal record checks, including fields stored directly
on a model. Removing that denial is not a safe file capability.

Add a bounded authenticated raw-octet HTTP gateway. Trusted native code registers
an owner plugin/resource, scoped model, private upload/download handlers, local
metadata/result schemas and a byte bound. Requests cannot select arbitrary
model fields or methods. Registration grants no authority. The current session,
release pin, workspace membership/action, feature and installation model guards
run before the handler; uploads also require CSRF. App handlers retain resource,
revision, quota, content and idempotency policy. No new artifact permission or
consumer-label shortcut replaces actor authority; this is the owner's direct
resource route, not an integration binding or technical bearer-token protocol.

The generic ceiling is8MiB, metadata4KiB and upload result64KiB. Applications may
set smaller limits. Downloads are whole resources with forced attachment,
octet-stream, no-store, nosniff and restrictive CSP. No public link, access token,
range delivery, inline renderer, MIME inference or remote parser is added.
Existing64KiB JSON service envelopes and error/release semantics remain unchanged.
See [binary-v1](../contracts/binary-v1.md).

Keep managed `ir.attachment` denial. Reject scoped models before inherited
`ir.binary` token elevation and again before low-level field streaming. Unscoped
framework assets retain their existing path. Apps must not substitute an unscoped
attachment or a raw filestore path to bypass this boundary. This deliberately
retires any accidental direct-model token streaming of scoped binary fields;
there is no supported qualified application using that path.

Storage remains app-owned. The first app uses existing
`fields.Binary(attachment=False)` bytea columns, with all versions and metadata
in the same database transaction/checkpoint. This trades bounded base64/database
overhead for simple atomicity and owned-table uninstall behavior. It is not a
large-object/object-store/sync framework. No inherited storage engine or license
is changed, and no runtime dependency is added.

File types, scanning disposition, previews, quotas and retention are application
policy. The first app's reviewed policy allows a small content-checked set,
escaped text preview and unscanned attachment downloads, not hostile-file safety.
Workspace-shared access avoids claiming finer ACL revocations survive checkpoint
restoration (AP-LIM-015). Trusted native apps remain trusted code, not sandboxed.

Contract freeze revision28 adds this new documented surface and its source
witness; existing frozen schemas/types/fixtures are unchanged. A new immutable
core successor identity/image is required before installing changed bytes;
existing core0.2.1 artifacts remain exact. Source tests do not establish installed
authorization, app usefulness, recovery or lifecycle acceptance.
