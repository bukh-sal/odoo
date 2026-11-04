# ADR0053: package public release inputs separately from site recovery state

Date: 2026-11-04. Status: accepted for G7 artifact/rehearsal work; clean install
qualification is still required.

Create one project-owned draft kit containing a Git source snapshot, the five
selected immutable application/dependency/worker/database/proxy images, verified
curated plugin archives, retained notices and the selected Windows operator
toolchain inputs. Recreate catalogs from archives; never copy an existing
catalog SQLite database, operator journal/approval/policy, site configuration,
credentials, database/filestore, session or worker issuer authority into the kit.

Use `release/` for host packaging/bootstrap helpers. It is outside the existing
application Docker context allowlist, so documentation/operator setup work does
not silently change the already qualified application image. Reuse the SDK and
ordinary independent executor for application initialization/lifecycle work.
Historical fixture drivers depend on private author-machine state and are
evidence references, not the portable fresh-developer interface.

The local checksum inventory is packaging data, not a new application SDK
contract, artifact signature or executor approval. Curation uses the existing
frozen digest-trust configuration; execution still needs a newly scoped operator
store and explicit native/permission approvals. No frozen authority/lifecycle
contract changes or G2 invalidation are introduced.

Keep the kit draft until actual offline operator setup, clean reference
installation and final G7 checks pass. Its source snapshot can be refreshed with
verified committed operator/runbook changes before sealing; reuse unchanged
large image/toolchain inputs instead of generating disposable duplicate kits.
Do not publish it or deploy publicly. Current native/codec residual decisions
and licensing scope remain visible; packaging is not a compatibility opinion.

The clean rehearsal gets one new disposable realm. Two exact endpoint-free
networks of an already archived/retired owned fixture were removed after label,
container and endpoint checks to free default address-pool space. Active/shared
networks and existing data stay outside that cleanup scope.

The worker's independent runtime attestation requires its immutable repository
reference as well as the image bytes. On this Docker image store, both ID and
`repository@digest` exports omit the repository binding. Export the worker with
one stable local `modular-document-stats:release-<digest-prefix>` tag after checking
that it names the exact selected image. Retain the immutable runtime reference
separately; the mutable transport tag grants no authority. Actual tagged-archive
load into a previously absent probe repository restored the expected digest
reference; the probe tag/archive were retired. This proves name reconstruction
on the existing image store, not a blank second Docker daemon. Other selected
image IDs and application source remain unchanged.
