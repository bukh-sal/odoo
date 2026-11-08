# ADR0073. Review the owned foundation46→47 transition

Accepted8 November2026 for AR-04. Implements ADR0072's lifecycle boundary after
AR-03 passed. This is a closed, versioned recipe for our own releases, not a
general Odoo upgrade mechanism or an arbitrary migration-script interface.

## Scope and approval

Keep ordinary `core_upgrade` policy/native-source restrictions. A foundation
transition requires a separately selected private declaration bound into the
staged record, descriptor, operation lock, plan hash and operator display. Bind
exact before/after image, runtime inventory and policy identities, unchanged
artifact/Python inputs, reviewed native version changes and the executable
recipe's target-image source digest. The declaration is selected after building
the image, outside its build inputs; no target-digest self-reference.

Recognize only `owned-addon-extraction-46-47-v1`: core0.1.46→0.1.47, IAP source
retirement, the two extracted apps, the known framework changes and reviewed
ownership/data effects. Reject unknown recipes/modules/steps, stale inventories,
unlisted changes, altered script bytes and unsuitable installed/data states.
Packages and application requests cannot confer this authority. Current private
OS approval, policy generation, locks, drain, checkpoint, failure closure and
separately approved recovery/resume remain mandatory.

Core maintenance has real site scope. Derive and hash all affected configured
site IDs independently of plugin installations; retain the requirement to cover
every existing native installation when any exist. A plugin-free core operation
has no fabricated plugin targets/artifacts, still requires backup/restart and
destructive acknowledgement, and displays its concrete sites/native changes.
Validate this behavior and any new declaration/display fields before freezing
their contract revision or using them for mutation.

## Stored data and native ownership

For installed mail, observe and bind the50old XML IDs enumerated in the AR-02
ownership map (36gateway,14Discuss), including actual record IDs/models. Adopt
those records into their new owners before the new registry/update processes
old mail data. Preserve IDs and existing configuration, conversations, messages,
attachments, app permissions and business data. Install both extracted apps only
on an upgraded deployment that previously had mail's bundled capabilities;
fresh Maintenance retains only the generic service. Preserve aliases for our
own R1 XML-ID/deep-link references, including old Discuss URLs. This supports
our stored data, not arbitrary external Odoo packages.

Inspect the installed legacy gateway modes before approval. Qualify POP/IMAP;
the old local mail-pipe depends on an XML-RPC endpoint absent from our production
distribution. Retire that unsupported UI/script entry, retain historical script
configuration read-only, and refuse a transition with local-pipe records before
mutation until an explicit supported data disposition exists. Do not silently
erase configuration or reintroduce a production compatibility endpoint.

Capture IAP's four owned table payloads/counts/digests under old code, privately
and after the final data preflight/drain/checkpoint. Archive representation must
preserve original JSON text without numeric re-encoding loss. Retire IAP through
the old module API; do not falsify module state or simply remove installed code.
The new core owns immutable retirement receipts/payloads with system-only read
access and no ordinary write/create/delete authority. Import under the reviewed
native operator step before publication. Public evidence contains counts/digests,
never credentials or payloads. Private exports receive the same OS protection and
retention treatment as the existing local checkpoint.

The recipe contains fixed source/table/ownership operations, not caller-supplied
SQL, command paths, hooks or template code. Bind approved retirement-data digests
and recheck after drain; a changed dataset requires a fresh review. Keep standard
record screens native. No custom retirement-management product UI is required.

## Recovery and qualification

Checkpoint the original schema/data/image before the first mutation. A failure
after any possible commit is uncertain and keeps traffic closed. Recover into a
fresh database from the independent checkpoint, preserve the failed target and
reconcile current revocations/fences before startup. A reviewed schema transition
may recognize only this exact recipe's table/metadata effects; do not broaden the
existing empty-table/recovery rules to arbitrary removals or versions. Restoring
core46 restores IAP and its original data; separate review is required to resume.

AR-04 must prove a real plugin-free maintenance scope, populated Aurora and
Maintenance workflows/permissions/jobs, preserved retirement/ownership data,
closed failure, fresh independent recovery and separately approved resume while
a peer remains useful. AR-05 still qualifies the final47 image, reproduction,
portable consumer, native browser behavior, jobs, privacy and exact retirement.
Source/host tests and the layout prototype do not substitute for these checks.

## Revision20 amendment after the first prototype proof

Revision19's exactbba33da4 prototype proved migration, closed fault, independent
fresh46restore and separate resume on the populated plugin-free Maintenance
baseline, with useful native Aurora peer jobs. Those receipts retain their
original source/inventory/schema scope. Revision20 compatibly extends the
retention witness whitelist to Aurora's task/list/stage/membership tables and
requires unique ordered witnesses plus consistency of mail's installed scope.
Qualify a populated old46 Aurora deployment through the same final47 image as
Maintenance; a fresh47 peer alone does not prove its upgrade. No added app,
arbitrary table/script authority or Odoo compatibility goal follows. Freeze and
qualify revision20 before the final forward operations; preserve old goldens.
