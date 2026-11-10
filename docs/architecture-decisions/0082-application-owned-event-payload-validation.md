# ADR 0082: application-owned event payload validation

Date: 2026-11-10. Status: accepted under the owned-core extraction direction.

## Context

The generic `event-transport` major-1 contract and SDK validator previously
contained one application-specific rule: Note payload shape plus
`aggregate_id == payload.note_id` / `aggregate_sequence == payload.revision`
for topic `org.example.notes.changed`. The Notes addon already registered the
same rule through the native `Topic(payload_schema, validate_identity, ...)`
seam, and `mp_core.events.emit`/`_envelope` already validated registered topics
before persistence and delivery.

Keeping the Notes rule in the shared schema/validator gave generic clients a
defense-in-depth promise they cannot generally provide for arbitrary
applications, made the shared contract carry application bytes, and duplicated
the app-owned rule.

## Decision

- Generic `event-transport` validation owns the envelope and transport bounds:
  protocol/kind/version, identifiers/topic/owner syntax, aggregate numeric
  bounds, site/workspace/correlation/causation UUIDs, timestamps, payload object
  type/size/depth, duplicate delivery/receipt IDs, leases/retries/replay and
  request authority-field exclusion. It does not own a registered application's
  payload schema, aggregate identity or domain semantic version.
- The Notes addon owns
  `examples/mp_example_notes/schemas/notes-changed-v1.json` and its existing
  `identity()` function. Its registered `Topic` remains the enforcement seam for
  real emission and delivery.
- `mp_core.events.emit` derives the owning plugin and schema version 1 from
  the registered definition and validates payload/identity before
  `durable.append_event`; `_envelope` continues to reject
  unsupported registered schema/owner/payload/identity before returning an event.
  Current scope/authorization/release/binding checks are unchanged.
- The generic examples/fixtures/host TypeScript fixture use a neutral arbitrary
  domain payload. The fixed 12 transport golden cases and generic envelope
  negative cases remain.
- The Notes app takes the next native/plugin version (`19.0.0.2.10`/`0.2.10`)
  because its addon bytes and packaged archive change; old archives/evidence are
  not relabeled. No domain data migration is introduced because the payload
  shape and schema version are unchanged.

This intentionally retires the shared-client promise that generic
`validate('event-transport')` enforces Notes domain semantics. Generic clients
still receive events only through the current native server; any additional
Notes domain validation belongs to the app-owned contract/service. This is not
a contract-neutral change and does not add a new compatibility promise.

## Consequences and evidence

- Current Notes malformed payload, schema-version, owner-plugin and
  aggregate/sequence cases are refused by the registered Topic seam. Emission
  derives its owner/version and rejects malformed domain input before persistence;
  delivery rechecks the stored owner/version/domain before return. Generic
  envelope failures remain refused by
  the shared validator.
- Existing frozen ADR0031 remains historical; this ADR records the current
  ownership boundary. Freeze revision 27 updates the changed shared paths and
  adds the app-owned regression test. Sealed old evidence/archives remain valid
  for their original scope; no historical runtime replay or image qualification
  is claimed here.
- Legacy token audience, `remove_metadata` guard, and clean runtime COPY/all-layer
  packaging remain separate open items.

## Ordered deployment prerequisite

Notes 0.2.9 imports the shared `notes_changed_payload` definition during module
registration. It cannot be combined with the new shared schema after that
entry is removed. The existing app's broad platform range is not evidence of
compatibility with this retired internal definition. Its original image/archive
pair remains unchanged.

Preserve an app-only source bridge with Notes 0.2.10 owning its schema while the
shared definition is still present. For a populated upgrade, deploy that app
successor first through the normal reviewed app-upgrade path. Only then remove
the shared definition in a separately identified core release, retaining the
same application archives. The current core-upgrade guard must continue to
refuse combined app-archive/core-source changes; do not add an exception or
silently load an old app against the new core. Fresh candidate composition uses
Notes 0.2.10. Exact bridge/core images and installed transition qualification
are later release work, not proved by these source/package checks.
