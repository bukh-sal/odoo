# ADR0078. Compose independently authored apps on a pinned foundation

Accepted8November2026 for AP-01-P1/AP-02. The native pilot cannot create a list:
required/read-only owner has no default. Actual default_get also omits task
creator. Backend create assigns both correctly, so earlier seeded-record browser
checks did not exercise this entry path. [Counterexample](../evidence/post-r1/application-adoption/ap01-create-counterexample.json).

## Selected application repair

Publish a new local Tasks artifact0.2.3, native19.0.0.2.3, authored in a separate
Git checkout. Give owner/creator fields current-user defaults so native new forms
validate. Preserve server create's authoritative current-user overwrite, immutable
ownership and all existing role/reminder behavior. Defaults are presentation/data
entry support, never permission grants. No schema/data migration is required.
Declare only supported registered0.2.2→0.2.3, maintenance/checkpoint, no migration
scripts and independently reviewed restore/separate resume. Legacy47 still uses
its existing closed path to0.2.2; it cannot jump through this app repair.

The independent checkout must reproduce admitted0.2.2 archive bytes before changes.
Never overwrite the old artifact, edit sealed49, patch a running container or
manually install metadata to make the pilot pass. After the app update return to
native creation immediately. Full AP-02 recovery evidence remains required.

## Why a build-only composition path

The general archive builder accepts an independent source checkout; the existing
distribution builder reads app recipes within its foundation checkout. Requiring
app developers to fork that checkout contradicts the intended workflow. For the
bounded prerequisite, compose a reviewed application archive as a layer on exact
sealed49, retaining the engine/framework/SDK/OS/Python code and platform version.
A new application version necessarily produces a different immutable image.

Use operator-selected kit/image/inventory pins and explicit artifact digest. This
first path replaces one already available native application slot: same package
identity/addon, newer version, structurally validated archive and native dependency
closure. Preserve policy and every other archive/addon/core file. Recompute the
ordinary distribution inventory/composition from verified bytes, not invented
installed metadata. The policy's existing application recipe remains the logical
source slot; the composition receipt separately identifies external source and
archive provenance. No application source is executed during build.

The build input v1 is an exact data-only object: schema_version1,
foundation_image_id, foundation_inventory_digest, application_digest,
application_file (one portable filename). Reject unknown keys, invalid pins,
wrong base inventory, undeclared application/addon swaps, non-native scope,
unchanged/downgrade versions, missing/incompatible dependencies and source drift
before output. This is a local build contract, not a new public API or runtime
grant; existing R1 frozen wire/approval contracts remain unchanged.

The image-side helper uses the pinned foundation's existing archive validator,
materializer and declarative composition/dependency checks. Before writes verify
all inventoried source files. Only the selected native application directory,
old/new archive and generated distribution inventory may change. Validate all
other identities/hashes and compare Python environment/core markers after build.
Keep the new builder outside runtime SDK/engine sources. Do not relax staged
planner, native version, curated trust or independent approval checks.

## Qualification and ownership

Prove negative input/dependency/core-drift cases before building. Prove two
independent compositions have equal declared inventories. Stage the resulting
immutable image using ordinary registered site-native app upgrade with a fresh
checkpoint/approval. Prove actual default_get/UI create and forged-owner rejection,
then retained rows/jobs, post-publication failure, fresh original-app restore and
separate resume. An absent app remains absent until independently installed.

This decision does not add arbitrary engine overrides, new addon-policy slots,
hosted deployment, public artifact trust or a sandbox. New application addition
in AP-03 needs its own explicit policy/dependency contract and qualification.
The archive-layer path is the required prerequisite for AP-B; after it works,
resume the pilot rather than expanding a general build platform here.
