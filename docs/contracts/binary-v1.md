# Workspace binary transport v1

New optional native capability under [ADR0084](../architecture-decisions/0084-current-authority-binary-transport.md).
This contract does not make old core0.2.1 images support files. Qualification is
recorded separately for the exact immutable successor/application cohort.

Trusted native startup calls `mp_core.binary.register_binary(plugin, resource,
BinaryEndpoint(...))`. The plugin/resource key is unique; the model must be a
workspace-scoped model owned by that plugin. Upload and download names begin
`_mp_binary_`; handlers are private, not arbitrary dataset RPC dispatch.
Registration supplies local-only JSON Schemas and a positive bound at most
8,388,608 raw bytes. The model's current `_mp_guard(create/read)` remains decisive,
and handlers must check current resource-specific authority and semantics.
No installation/grant is conferred by registration.

## Upload

`POST /api/v1/binary/<plugin>/<resource>`

- Authenticated native session, `X-MP-Workspace`, current `X-MP-Client-Release`
  and valid `X-CSRFToken` (the same native current-release fence as JSON calls).
- `Content-Type: application/octet-stream`; no content encoding, query parameters
  or multipart form. Native route bounds chunked/unknown-length bodies at8MiB;
  endpoint bound is also checked against declared and actual size. Empty body
  refuses. Unsupported transport/bound/schema inputs produce the usual JSON error.
- `X-MP-Binary-Metadata` is a JSON object at most4,096UTF8 bytes, duplicate keys
  refused, validated by the registered app schema. Its filename/key/revision and
  type semantics belong to the app; no string becomes a model/field/handler path.
- Private upload handler `(metadata, bytes)` returns an app DTO, validated against
  its result schema and limited to64KiB encoded JSON. Successful response uses
  the existing major1 service-response envelope and no-store. Bytes and outcomes
  commit with the ordinary HTTP transaction; no core manual commit.

Apps must implement idempotency/uncertain-outcome reconciliation and quotas;
the raw transport does not make a mutation safe to retry. No caller attribution
header supplies integration permission. Native technical contexts still need the
supported authentication/action path; this adds no bearer credential endpoint.

## Download

`GET /api/v1/binary/<plugin>/<resource>/<canonical-public-UUID>`

Authenticated session, selected workspace and current-release header are required.
No query/token/range path. The private download handler receives only the UUID
and returns `BinaryContent(bytes, filename)`. It must resolve the resource in the
current scope, handle app trash/version policy and perform its normal access checks.
The gateway rechecks the model guard after the handler and validates type/size.

Successful bytes have `Content-Type: application/octet-stream`, forced attachment
`Content-Disposition` with UTF8 filename, exact length, `Cache-Control: no-store`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and sandboxed
`default-src 'none'` CSP. Filenames are NFC,1..180characters, no surrounding space,
path separators or Unicode control/format characters. No raw path is accepted.
No inline/public cacheable URL or server-side preview/parser is provided. An app
may fetch with the required headers then display safely escaped supported text.

Both routes use existing bounded JSON errors, rollback/audit and current-release
conflict semantics. Serialization/deadlock failures propagate to the ordinary
whole-request transaction retry. A successful request authorizes that bounded
transaction; it cannot retract bytes already sent if membership changes later.

## Alternate paths and storage

Managed `ir.attachment` create/write/access/content/stream remain denied. Inherited
`ir.binary` XML-ID/model and low-level stream paths refuse scoped models before
limited-field token/sudo or byte access. These routes do not become preview or
download alternatives. Nonworkspace framework assets are unchanged.

Storage is not prescribed by this transport. The first app uses immutable,
bounded `Binary(attachment=False)` app-table rows included in ordinary database
checkpoint/restore; it owns cleanup and byte/metadata consistency. Files are not
certified safe: content/type/filename checks, policy bounds and attachment headers
are complementary defenses, not antivirus/CDR or a hostile-native sandbox.
