# Modular Platform foundation

An independently owned fork of the Odoo Community engine and native UI. We retain
useful infrastructure and maintain our own releases; external Odoo addon/release
compatibility is not a product goal. Original attribution remains in LICENSE,
COPYRIGHT, source notices and upstream.lock.

Read [implementation status](docs/implementation-status.md) first: it identifies
the active gate, verified checks, evidence, blockers and the next executable step.
The current addon cleanup follows [AR-01 through AR-05](planning/addon_cleanup.md).
The sealed core46 release is historical and remains immutable; source cleanup
alone does not qualify a replacement release.

| Directory | Responsibility |
| --- | --- |
| engine/ | Owned registry, ORM, HTTP/security runtime and CLI |
| framework_addons/ | Native UI/auth/settings/import/realtime/editor and optional communication services |
| applications/ | Aurora Tasks, Maintenance, optional Discuss and incoming mail gateway |
| examples/ and plugins/ | Minimal reference addon code and package manifests, including Canvas |
| tests/addons/ | Explicit native regression fixtures, outside production discovery |
| packages/ | Public SDK/contracts and independent operator implementation |
| deploy/, tools/, release/ | Pinned builds, scoped operations and portable release kits |

The source CLI is `engine/odoo-bin`. Source discovery uses the owned framework,
application and example roots; test roots are explicit. The builder materializes
one installed namespace (`odoo/`, `addons/`) inside the image. Its inherited Python
spelling identifies an internal ABI retained for our archives, not compatibility
with external Odoo packages.

Use the pinned isolated Python/operator environment and project-owned Docker
resources described in [PLATFORM.md](PLATFORM.md). The active candidate policy is
`deploy/distribution-r1-foundation.json`; older policy files/evidence retain their
historical scope and require the corresponding historical source. Runtime and
operator deployment use the Docker/release-kit tooling. Obsolete vendor pip and
OS installer recipes have been retired; the SDK retains its own package metadata.

Standard record screens use the native WebClient and list/form views. Optional
custom plugin pages remain available. Canvas stays a small reference/test plugin.
No publication or production deployment is implied by local qualification.
