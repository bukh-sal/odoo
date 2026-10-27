# Modular Platform Implementation Specification

Specification version 1.1. Updated 28 October 2026.

Recipient: an implementation agent working on the user's machine. Deliverable: a working, tested, locally runnable modular application platform, not another architecture proposal.

The product is provisionally called **Modular Platform**. This is a working name, not a final brand. Build on Odoo Community 19 as an initial implementation substrate, retain its useful ORM and native module composition, and expose a more general plugin, service, identity, and UI developer experience. The application must run independently of Odoo-hosted services and require neither an Odoo Enterprise subscription nor proprietary Enterprise code.

This specification is normative for the proposed platform, not a description of features already implemented. Source findings are pinned in section 2. A successful minimal boot, upgrade, restore, custom UI integration, and plugin composition are release gates, not assumptions.

**Current delivery state: specification only; implementation has not started.** Editing or reviewing this document does not authorize starting implementation. When the user later authorizes implementation or sets an implementation goal, initialize the durable progress records described in section 25.2. Do not report any gate or acceptance test as passed from the existence of this specification.

## How to navigate and resume this specification

| Need | Authoritative location |
| --- | --- |
| Product scope, trust model and exclusions | Sections 1-3 |
| First work and early architectural evidence | Sections 4-5; gates G0 and G1 |
| Public contracts to freeze before substantial R1 development | Sections 6, 10, 11, 13, 14 and 16; gate G2 |
| Implementation order, current-work record and loop prevention | Section 25 |
| Acceptance requirements and evidence rules | Section 23 |
| Changes allowed without user direction | Section 26 |
| Completion and handoff | Sections 28-29 |

Read the whole specification on initial implementation. On later resumptions, follow section 25.2 instead of restarting planning or relying on chat memory. Section 25 controls sequencing; detailed subsystem sections control behavior. Only observed results can satisfy a gate. The launch prompt in section 31 is an optional future instruction, not current authorization.

# 1 Mission and delivery scope

## 1.1 Product objective

Build a Python application platform in which independently packaged plugins can introduce data models, server functionality, pages, commands, UI contributions, and integrations without modifying the platform's core source.

Developers should receive a productive default stack: ORM, identity, authorization, navigation, forms, tables, settings, jobs, events, developer CLI, tests, and packaging. They may use the standard UI system, adopt only its design tokens, or bring a custom frontend. That visual choice must not alter authentication, authorization, deployment, or compatibility requirements.

Plugins must be able to depend on and extend other plugins. Supported extension methods must be explicit and testable. Native Odoo model extension and remote service consumption are different forms of dependency, with different guarantees.

The platform should suit internal tools, planning systems, knowledge applications, administration, integration products, and the management layer of AI or collaboration products. It is not intended to become a rendering engine, a media transport, a database engine, or a hard-real-time runtime.

## 1.2 Required outcome

A developer must be able to:

1. Start a fresh local instance using documented commands.
2. Log in to a neutral application shell.
3. Create a plugin from a scaffold.
4. Add models and a standard CRUD UI without a core patch.
5. Add a custom non-Owl page using the host SDK.
6. Package the plugin and install it through a controlled operation.
7. Have required plugins resolved and displayed before installation.
8. Extend another plugin's model and contribute a UI action through declared contracts.
9. Upgrade a plugin using a tested migration and recovery procedure.
10. Suspend its exposed features without being misled into thinking native code was unloaded.
11. See logs, health, dependency information, and operation progress.
12. Run a documented external service example without giving it the main database credentials.

A system that has a polished plugin browser but cannot safely perform these workflows is not an acceptable result.

## 1.3 Releases and implementation priority

| Stage | Required scope | Completion gate |
| --- | --- | --- |
| R0 Foundation validation | Pinned upstream, clean environment, minimal verified distribution, dependency inventory, boot tests, unchanged ORM behavior | Fresh boot and disposable lifecycle experiment pass |
| R0-to-R1 feasibility and contract freeze | Minimal workspace enforcement and custom UI proofs; six concrete contract decisions | G1 feasibility evidence and G2 frozen contract inventory before substantial R1 development |
| R1 Trusted modular platform | Neutral shell, native SDK, custom UI hosting, dependency planning, curated catalog and upload, recoverable deployments, workspaces, authorization, developer tooling, example plugins | Complete R1 acceptance suite and operator walkthrough |
| R1 service boundary proof | Versioned service contract, scoped credentials, one separately running reference worker, events/jobs needed for that example | A worker can fail without bringing down the host; no shared ORM objects |
| R2 Isolated extension platform | Confined service execution, sandboxed frontend hosting, verified publisher trust, hardened quotas and revocation | Explicit security verification and threat-model review |
| R3 Ecosystem and distribution | Public publisher workflow, broader marketplace operations, billing if requested, more deployment profiles, optional desktop host | Separate product requirements and approval |

Implement R0 and R1 end to end unless blocked by a material architectural finding. Specify R2 extension contracts now, but do not delay a useful R1 to build a public marketplace or general container orchestration platform.

R1 is **trusted native software distribution**, not a hostile-code sandbox. The service example proves an architectural boundary; it does not certify arbitrary third-party execution as safe.

## 1.4 Non goals for R1

Do not attempt the following as prerequisites:

- Extracting the ORM into a standalone Python library.
- Replacing PostgreSQL with a generic interchangeable database layer.
- Rewriting Owl, the Odoo registry, or the native module loader.
- Hot unloading arbitrary Python modules.
- Running two versions of a native addon in the same Python process.
- Installing arbitrary native code independently for tenants sharing one process environment.
- Guaranteeing zero downtime for schema-changing upgrades.
- Guaranteeing automatic rollback of arbitrary migrations.
- Treating a manifest permission list as a Python sandbox.
- Implementing a complete React, Vue, and Web Component design system.
- Full offline-first synchronization, CRDT editing, native mobile apps, or desktop distribution.
- Public reviews, payments, licensing commerce, or app-store moderation.
- Recreating ERP applications merely to demonstrate the framework.
- Full compatibility with every existing Odoo app.

Compatibility with unmodified third-party Odoo addons is best effort and explicitly opt-in. The supported contract is the platform SDK and the documented native extension model.

## 1.5 Normative language and authority

MUST means a release requirement. SHOULD means the default unless an architecture decision record explains the exception. MAY means optional.

The implementing agent may choose internal libraries and implementation details within these constraints. It must not silently change the trust model, erase license notices, claim unimplemented security guarantees, switch upstream major versions, or replace the chosen architecture because another framework is more familiar.

Proceed autonomously with reversible local development and testing. Stop for decisions that materially change the product, for destructive actions affecting non-disposable data, or for permission boundaries enforced by the user's tools.

# 2 Source baseline and corrections to prior assumptions

## 2.1 Pinned starting point

Use the official Odoo Community repository:

`https://github.com/odoo/odoo.git`

The inspected 19.0 baseline is:

`5c7defb49e020fec8b6bb82403a2f54eb79e92e1`

Record it in `upstream.lock` together with branch, retrieval date, repository URL, license provenance, and build environment. Before using it, verify it exists in the official repository and inspect subsequent security fixes. Changing the baseline requires a recorded decision and rerunning R0; do not silently substitute a moving branch or Odoo 20.

The original static audit did not boot a stripped distribution or measure runtime performance. R0 must establish those facts.

## 2.2 Verified constraints

| Source fact | Relevant source | Required design consequence |
| --- | --- | --- |
| Empty native dependencies are normalized to `base`, except for `base` itself | `odoo/modules/module.py::_load_manifest` | A native plugin is not independent of the base model system |
| Native modules are imported process-wide and can have server-wide post-load hooks | `odoo/modules/module.py::load_openerp_module` | No general native hot unload or per-database Python package isolation |
| Registries are associated with database names, while imported Python modules are shared | `odoo/orm/registry.py::Registry.new/load` | Database isolation and code-version isolation are different |
| User identity delegates through a partner record; a company also requires a partner | `base/models/res_users.py`, `res_company.py` | Preserve compatibility models initially; hide ERP concepts behind new public contracts |
| Web session information includes partners, companies, currencies, settings, and views | `addons/web/models/ir_http.py::session_info` | A generic session adapter is needed |
| Native dependencies are names, not a complete plugin version-range solver | `odoo/modules/module_graph.py::ModuleGraph._update_depends` | Add planning and reproducible version solving outside the loader |
| Python external requirements already support version/marker checks | `odoo/modules/module.py::check_python_external_dependency` | Preserve the checks; do not confuse checking with installing or solving |
| Module operations contain explicit commits | `base/models/ir_module.py::_button_immediate_function`, `modules/loading.py` | A whole deployment is not a single transaction |
| Uninstall marks dependents and can delete records, tables, columns, and constraints | `ir_module.py::button_uninstall`, `ir_model.py::_module_data_uninstall` | Do not equate uninstall with harmless disablement |
| Default server-wide modules include `base,rpc,web`; required ones include `base,web` | `odoo/tools/config.py` | Make bootstrap configuration explicit |
| Core initialization adds built-in addon paths | `odoo/modules/module.py::initialize_sys_path` | `--addons-path` alone is not a package allowlist |
| The root web client and client actions provide extension seams | `web/static/src/start.js`, `webclient/actions/action_service.js` | Adapt the existing frontend rather than replacing it immediately |
| Frontend service removal is not a complete lifecycle | `web/static/src/env.js::startServices` | Reload clients after native release activation |

The exact source names and behavior must be rechecked against the pinned checkout. Do not copy obsolete paths such as assuming the primary registry still lives in `odoo/modules/registry.py`.

## 2.3 Terminology corrections

Use these precise meanings throughout the implementation:

- **Feature suspension:** disable platform-managed entry points while native code, schema, overrides, and imports can remain active.
- **Native uninstall:** a destructive Odoo module operation, potentially cascading to dependents.
- **Recoverable deployment:** a journaled operation with backups, verified restore, and reconciliation; not a promise of atomic rollback.
- **Workspace:** a logical authorization and organization scope inside one site database.
- **Tenant or site:** a deployment/data-isolation boundary; not an Odoo company.
- **Service plugin:** functionality outside the host process, accessed through a defined protocol.
- **Sandboxed plugin:** a separately justified security property; not a synonym for subprocess, container, iframe, or signed package.
- **Custom UI:** permission to use another presentation pattern, not permission to bypass host security.
- **Microkernel:** a design direction for small public contracts. R1 remains an Odoo-derived modular application server internally.

# 3 Architecture and dependency boundaries

## 3.1 System layers

| Layer | Responsibilities | Must not own |
| --- | --- | --- |
| Upstream substrate | Native registry, ORM, HTTP lifecycle, view/action infrastructure | New generic public contracts scattered across upstream files |
| Compatibility adapter | Translate identity, routing, session, native model and view interactions | New product-specific business logic |
| Platform core | Plugin catalog, installation metadata, workspaces, authorization contracts, service/extension registries | ERP workflows |
| Application shell | Routing, navigation, settings, plugin hosting, session UX, accessibility | Direct database or privileged executor access |
| SDK and tooling | Scaffolds, schemas, UI adapters, validation, build, testing, type generation | Implicit installer authority |
| Deployment control plane | Plan, stage, verify, migrate, restart, recover, journal | Normal end-user request handling |
| Application plugins | Business or application features and documented extension points | Private core monkeypatching |
| External services | Specialized compute, independent jobs/storage where appropriate | Direct access to the host ORM or unrestricted credentials |

The control plane must remain operable when a plugin prevents the main web application from starting. At minimum, a local operator CLI and journal inspection path must work without importing installed third-party plugins.

## 3.2 First implementation choices

- Retain Odoo's ORM and registry for native plugins.
- Retain PostgreSQL for relational persistence.
- Retain Owl and declarative views for the default UI SDK.
- Use a framework-neutral mount API for trusted custom pages.
- Use declarative metadata for discovery and planning.
- Use JSON-serializable public service contracts with explicit versions.
- Use one native release environment and dependency solution per deployment unit.
- Start with one site database per local deployment.
- Make workspace filtering explicit; do not map workspaces to Odoo companies.
- Use a separate maintenance executor for install/upgrade operations.
- Use a PostgreSQL-backed outbox and job implementation initially if sufficient; isolate the interfaces so a different backend can be added without changing plugin contracts.
- Keep the initial runtime synchronous where required by Odoo. Do not force ASGI or async ORM behavior into the core merely for architectural consistency.

Do not hide SQLAlchemy beneath a compatibility layer and call it the same ORM. Replacing the ORM would remove much of the reason for using this foundation.

## 3.3 Dependency direction

The generic SDK may depend on its own schemas and interfaces. It must not require a consumer to import Odoo merely to parse a plugin manifest, inspect a package, generate types, plan dependencies, or read a deployment journal.

Native adapters may depend on Odoo. Native plugins may use documented Odoo model APIs in their backend. Remote services may not.

The shell may call the host API and compatibility adapters. A custom page must not require access to the entire Odoo frontend environment.

Core functionality must use the same supported extension contracts where practical, but bootstrap, identity verification, deployment policy, and permission enforcement are not optional plugins that an ordinary plugin may replace.

## 3.4 Upstream change policy

Prefer, in order:

1. New platform addons and external tooling.
2. Supported upstream extension points.
3. A concentrated compatibility adapter.
4. Small documented upstream patches with regression tests.
5. Larger extraction only after a measured need and an explicit decision.

Every upstream patch needs a ledger entry: file, reason, alternative rejected, regression test, merge risk, and removal condition. Avoid mass renaming of the `odoo` package or all model identifiers. Neutral user-facing branding does not require renaming internal imports.

# 4 Repository and development environment

## 4.1 Repository layout

Use a local repository with the official Odoo history retained as an upstream remote if practical. Keep product additions visibly separate. The following paths describe the intended ownership boundaries; adapt minor names to existing files without creating shadow copies.

| Path | Purpose |
| --- | --- |
| Existing `odoo/`, `addons/`, `odoo-bin` | Pinned upstream substrate |
| `platform_addons/mp_core/` | Installation metadata and central registries |
| `platform_addons/mp_identity/` | Workspaces, memberships, generic session adapter |
| `platform_addons/mp_shell/` | Neutral shell and standard UI integration |
| `platform_addons/mp_services/` | Public service gateway, authorization and events |
| `platform_addons/mp_jobs/` | Initial job/outbox adapters |
| `platform_addons/mp_plugins/` | Catalog and operator UI, not privileged installation code |
| `packages/modular_platform/` | CLI, manifest schemas, solver, package validator, executor |
| `packages/host_sdk/` | TypeScript host contracts and custom-page adapters |
| `packages/ui_kit/` | Tokens and initial Owl components/patterns |
| `examples/` | Independently packaged reference plugins |
| `deploy/` | Compose, images, configuration templates, release tooling |
| `tests/` | Contract, solver, installer, integration, security and browser tests |
| `docs/` | Architecture, ADRs, SDK, operations and implementation status |
| `upstream.lock` | Source provenance |
| `platform.lock` | Exact release dependency and artifact solution |
| `LICENSE`, `COPYRIGHT`, `NOTICE` | Preserved and added attribution as appropriate |

Do not create a Python package named `platform`; it conflicts with Python's standard library. Use `modular_platform` as a provisional Python namespace and `mp_` for new native addon technical names. The CLI working name is `modular`.

A native platform plugin maps to exactly one native Odoo addon in R1. An external-service plugin maps to no native addon and uses the operator-managed endpoint contract in section 14.6. A native connector, if needed, is a separate plugin with its own identity and declared dependencies. Multi-addon bundles and automatic service runtime deployment are outside R1.

## 4.2 Local environment

The primary local path should be Linux containers on Docker Compose. Windows development should use Docker Desktop/WSL2 where available; do not require a globally modified Windows Python installation.

Initial candidate runtime: Python 3.12 and PostgreSQL 16, subject to R0 verification against upstream requirements. Select and pin exact image versions/digests after validation. Pin the frontend build toolchain too; do not rely on an unversioned global Node installation.

Services should include:

- Application server.
- PostgreSQL.
- A maintenance/executor path that runs on demand.
- A separate worker process when jobs/outbox are enabled.
- The optional reference external service.
- A reverse proxy only if needed for testing origin isolation or production-like routing.

Bind development services to loopback by default. Do not publish a development database or admin interface to all network interfaces. Use isolated named volumes for disposable test databases and filestores. Provide clear commands for start, stop, logs, reset of explicitly disposable state, backup, and restore.

Production secrets must never appear in examples, images, fixtures, git history, or browser bundles. Generate development credentials during setup or require explicit environment values. Provide `.env.example` with placeholders, not reusable shared passwords.

## 4.3 Reproducibility

From a fresh checkout and empty disposable volumes, documented commands must reproduce the same dependency solution and boot a working instance.

Lock:

- Upstream commit and patch set.
- Python interpreter/platform.
- Native Python dependencies with hashes where available.
- Node/build dependencies.
- Runtime base images.
- Plugin IDs, versions, artifact digests, and addon mappings.
- Service-provider bindings.
- Manifest and SDK contract versions.

Installation must not query a moving `latest` during an already approved operation.

# 5 Foundation validation and minimal distribution

## 5.1 R0 deliverables

Before generalization, produce:

1. `docs/baseline.md`: source commit, tool versions, startup commands, runtime configuration, and observed installed modules.
2. `docs/dependency-inventory.md`: required substrate modules, optional modules, auto-install behavior, and actual dependency closure.
3. A bootable container/venv configuration using untouched upstream behavior where possible.
4. A disposable native fixture addon with one model and a field-extension addon.
5. A scripted installation, upgrade, removal, and restore experiment.
6. Baseline startup, request, resource, and test results on the actual machine.
7. An initial upstream patch ledger, even if empty.

Do not delete large portions of the upstream source tree as the first action. Start by controlling the distribution and installation set. Packaging fewer modules and deleting their source are separate decisions.

## 5.2 Bootstrap rules

Explicitly configure server-wide modules. If excluding `rpc`, verify that `--load=base,web` is supported and sufficient for the intended behavior. If using defaults, include `rpc` in the runtime inventory.

Inspect built-in addon search paths. The production distribution must have a verified allowlist at the artifact/release level; it cannot rely only on a custom `addons_path` setting.

Inspect and record automatically installed modules. Account for modules added because all their dependencies are satisfied, and for upstream security/authentication modules. Do not disable a security feature merely to minimize module count.

Use a fresh database without demo business data. Essential identity/configuration bootstrap records may remain.

## 5.3 Foundation acceptance

R0 passes only when:

- Database initialization succeeds from empty state.
- Login and logout work.
- Anonymous users cannot reach operator controls.
- Standard web assets load without missing resources.
- A custom addon with `base`/platform dependencies installs.
- A second addon extends its model.
- A schema-changing upgrade works in a disposable test environment.
- A deliberate failed upgrade is diagnosable and recoverable.
- Native uninstall effects are observed and documented.
- Database plus filestore restore returns the fixture to its previous release state.
- Multi-worker registry synchronization is exercised at least once.
- No CRM, sales, accounting, inventory, or manufacturing module is required to render the reference application.
- Any failing upstream test relevant to the changed path is investigated rather than silently excluded.

If R0 exposes a fundamental incompatibility, stop expansion and produce a concrete options memo. Do not spend weeks repairing an unproven fork with no working baseline.

## 5.4 Early feasibility gate G1

After baseline gate G0, build only the small executable proofs below. They may introduce the minimum adapter/mixin/schema code needed for the experiment. Do not build a polished shell, catalog, general resolver or complete SDK to run these proofs. Reuse successful proof code in the product where practical; disposable experiments must be identified and retired explicitly.

| ID | Required proof and evidence |
| --- | --- |
| FEAS-01 | One workspace-owned native model obeys the section 11.7 policy for the same human who is editor in A and viewer in B. Exercise read/create/update/delete, relation assignment, search and aggregates through the gateway and retained legacy model transports. Viewer writes and cross-workspace record IDs fail. |
| FEAS-02 | Two browser tabs use different explicit workspaces without shared-context or cached-rule leakage. Warm the caches in both directions. Commit membership/role revocation through another worker and show fresh authoritative checks plus the maximum 30-second cached/stream bound. Missing workspace and forged context fail closed. |
| FEAS-03 | A minimal neutral host root mounts a plain TypeScript/JavaScript page through the section 16.4 API without exposing the Odoo frontend environment. Prove a deep-link refresh, back/forward, one native action/view integration, workspace change and repeated dispose/remount with stale responses discarded. Record every substrate patch. |
| FEAS-04 | Demonstrate the authority distinction with a tiny gateway fixture: browser plugin attribution cannot expand a human's rights; a scoped technical identity cannot change site/workspace; a provider-to-provider call cannot acquire the provider's broader rights. This is not a full external runtime or marketplace. |

Run against real PostgreSQL and the pinned native runtime, with browser evidence for browser behaviors. The asymmetric role case and cross-worker cache case are mandatory; two users with identical roles do not substitute. Record environment, commands, expected/actual results and relevant patches under `docs/evidence/G1/`.

G1 passes only when FEAS-01 through FEAS-04 pass and any required substrate changes have a bounded patch ledger entry. If a proof fails, investigate that boundary rather than expanding other product features to conceal the failure. Apply section 25.4 and the foundation exit criteria in section 26.4. Passing ordinary Odoo boot/lifecycle tests alone does not establish platform feasibility.

## 5.5 Contract-freeze checkpoint G2

After G1, freeze a small implementable contract set before substantial R1 development. Freeze means versioned schemas, examples and executable contract checks in the repository, not a new architecture essay or a claim that R1 is complete.

| Contract | R1 choice that must be concrete at G2 |
| --- | --- |
| Workspace enforcement | Request-scoped workspace, per-workspace role checks in a shared model layer, global scope rules, cache/invalidation integration, backing-user mapping; section 11.7 and G1 evidence |
| Actor and plugin identity | Browser attribution versus authenticated technical identity, actor-preserving call chains, scope intersection and no implicit provider elevation; section 13.2 |
| Executor approval | UI plan request, independent local CLI approval of exact hash, operator-owned approval record, expiry/revocation and single-operation consumption; section 10.6 |
| Versions and migrations | Canonical numeric X.Y.Z packages mapped to 19.0.X.Y.Z native versions and migration directories; sections 6.2 and 6.5 |
| Service bindings | Named consumer-local aliases resolving a fixed contract major/version and provider; schema, lock entry, SDK call and wire example; sections 6.4 and 13.1 |
| External-service packaging | Metadata-only service artifact, operator-managed Compose runtime/endpoint, scoped credentials, health and explicit lifecycle separation; section 14.6 |
| UI host | Minimum mount/dispose, routing, context generation and service-binding types verified by FEAS-03 |

Create `docs/contracts/freeze-v1.md` with a contract inventory, each schema/type/example path and digest, applicable ADRs, G1 evidence links and contract-test commands/results. It must contain a no-open-critical-decisions checklist for the rows above. Fix the exact schema dialect, normalized manifest shape, IDs, request workspace carrier (`X-MP-Workspace` for R1 HTTP calls), typed errors/HTTP mapping, binding records, approval serialization and compatibility fixtures. Browser SDK and retained native RPC must propagate the same workspace carrier; model code receives only server-validated context. Page URLs carry workspace selection in the `workspace` query parameter, validated before mounting, to support separate tabs and deep links. Publish bootstrap/session routes that are explicitly workspace-free.

The implementing agent may complete G2 autonomously within these choices; it does not require a fresh user approval or a complete Phase E executor. Use golden serialization examples and minimal fixtures for later subsystems. Actual execution and fault-injection acceptance remains required in the owning phase. No public-contract TODO that changes authority, version meaning or lifecycle semantics may be deferred beyond G2. After freeze, version contract changes, update affected consumers/tests and invalidate affected gate evidence as specified in section 25.3.

# 6 Plugin identity and manifest

## 6.1 Identifiers

Keep the following separate:

| Identifier | Example | Meaning |
| --- | --- | --- |
| Plugin ID | `org.example.notes` | Stable globally unique identity |
| Plugin version | `0.1.0` | Package/release version |
| Native addon | `mp_example_notes` | Stable Python/Odoo technical name |
| Artifact digest | `sha256:<hex>` | Exact package bytes |
| Installation ID | UUID | Plugin installed in one site database |
| Release ID | UUID or immutable content identifier | Whole executable environment |
| Service ID | `org.example.notes.documents` | Public interface identity |
| Service API version | `1.0` | Contract compatibility, not package version |
| Contribution ID | `org.example.notes:page:home` | Namespaced UI/action/slot contribution |
| Operation ID | UUID | One plan/apply/recovery operation |

IDs must be stable across rebranding. Validate them before registering anything. The same plugin ID/version with a different artifact digest must be rejected as an immutable-version conflict unless an explicit development-only rebuild workflow identifies the replacement.

Reserve `org.modularplatform.*` and `mp_*` core names according to a documented namespace policy. Example plugin names are reserved fixtures, not marketplace ownership claims.

## 6.2 Version policy

Use the maintained `packaging` library for version comparison and PEP 440 dependency specifiers. R1 platform and plugin package versions are restricted to canonical `X.Y.Z`: exactly three nonnegative decimal integers, no leading zero except `0`, and no prefix, epoch, prerelease, development, post-release or local-version suffix. Examples: `0.1.0` and `2.10.3` are valid; `v1.0.0`, `1.0`, `01.0.0`, `1.0.0rc1`, `1.0.0.post1`, `1!1.0.0` and `1.0.0+build` are rejected. Validate the spelling before parsing; do not normalize an invalid author version into an accepted one.

Dependency ranges remain PEP 440 specifiers over that restricted candidate set, for example `>=0.1,<0.2`. Python dependency versions retain ordinary upstream PEP 440 semantics; the package restriction does not rewrite Python wheel versions. Do not accept npm-style caret ranges or silently invent prerelease support. A future expansion of package-version syntax requires a new documented mapping and compatibility tests.

Service and UI protocols have explicit major versions and published schemas. Additive compatible minor changes are permitted. Breaking public schema or semantic changes MUST introduce a new contract major. A package major version or declared breaking deployment is additional metadata, not a substitute for contract versioning. A provider MAY offer old and new contract majors concurrently through distinct registry entries and bindings.

Native runtime compatibility is a separate constraint, initially `odoo-19`, plus the platform build range. Do not imply that all Odoo 19 revisions are interchangeable; the release lock records the actual source commit and patch set.

## 6.3 Authoritative manifest

The source of truth is `plugin.toml`, parsed as data without importing code. Provide a versioned JSON Schema or equivalent strict validator for the normalized representation.

Required fields include identity, version, license, publisher, runtime kind, compatibility, dependencies, permission definitions, requested capabilities, contribution metadata, and data/upgrade declarations. Optional functionality must be explicit.

This is a proposed authoring format to implement, not an existing upstream format:

```toml
schema_version = 1

[plugin]
id = "org.example.notes"
version = "0.1.0"
name = "Notes"
description = "Workspace notes with a standard data interface."
publisher = "example"
license = "LGPL-3.0-only"

[compatibility]
platform = ">=0.1,<0.2"
host_api_major = 1
ui_api_major = 1

[runtime]
kind = "native"
addon_name = "mp_example_notes"
native_compatibility = "odoo-19"
python = ">=3.12,<3.13"
python_dependencies = []

[activation]
scopes = ["site", "workspace"]
supports_feature_suspension = true

[permissions.defines]
"notes.read" = "Read notes in the current workspace"
"notes.write" = "Create and update notes in the current workspace"
"notes.delete" = "Delete notes in the current workspace"

[data]
models = ["mp.example.note"]
extension_targets = []
export_schema = "schemas/notes-export-v1.json"

[ui]
mode = "trusted"
design = "standard"

[[ui.pages]]
id = "home"
path = "/"
title_key = "notes.title"
kind = "native_view"
action_ref = "mp_example_notes.action_notes"
permission = "notes.read"
layout = "shell"

[[ui.navigation]]
id = "main"
page = "home"
label_key = "notes.title"
icon = "file-text"
order = 200

[[services.provides]]
id = "org.example.notes.documents"
api_version = "1.0"
schema = "schemas/documents-v1.json"
handler = "mp_example_notes.services:NotesService"
methods = ["list", "get", "create", "update", "delete"]

[[services.requires]]
alias = "documents"
id = "org.example.notes.documents"
contract_major = 1
version = ">=1.0,<2.0"

[upgrade]
strategy = "native_migrations"
requires_maintenance = true
destructive = false
```

The SDK normalizes local permission definitions into full IDs such as `org.example.notes:notes.read`. The UI and service schema may use local names only within the declaring plugin. Cross-plugin references must use full IDs.

Permission definitions and requested capabilities are separate. `[permissions.defines]` describes actions owned by the plugin. `[[permissions.requests]]` entries identify a fully qualified existing capability, reason and intended scope requested from the platform or another provider. Declaring either does not grant authority. Roles and explicitly approved grants determine actor and plugin access. Validate every requested capability against its provider's public contract. Native code still remains fully trusted; these checks govern supported application paths, not Python confinement.

The handler declaration is inspected syntactically during planning and imported only after trust approval in the appropriate runtime.

Do not describe `destructive = false` as a proof that arbitrary Python migration code cannot delete data. Treat it as an author declaration checked against available evidence and operator policy.

## 6.4 Dependencies and optional integrations

A native extension example adds:

```toml
[dependencies.plugins]
"org.example.notes" = ">=0.1,<0.2"

[integrations.optional]
"org.example.analytics" = ">=1,<2"

[[services.requires]]
alias = "notifications"
id = "org.modularplatform.notifications"
contract_major = 1
version = ">=1.0,<2.0"
```

A hard plugin dependency means the compatible plugin must be installed in the same relevant site. Native model extension also requires the provider's native addon in the same runtime and registry.

An optional integration does not auto-install its provider. If absent or incompatible, only that integration is unavailable. Its code must not use unconditional imports or model inheritance that breaks startup. A separately packaged bridge addon is required when native model composition cannot be conditional safely.

A service dependency may be satisfied by a compatible local or remote provider. Provider choice is explicit when more than one exists. Service dependencies cannot substitute for native model inheritance.

Every service consumer, including a plugin calling its own public service through the SDK, declares a unique local binding alias. Use `[[services.requires]]` entries, not a service-ID-keyed map. `contract_major` is required and the version range must stay within that major; optional requirements add `optional = true`. Missing required aliases fail activation; unresolved optional aliases return `DEPENDENCY_UNAVAILABLE` without substituting another major/provider. Sections 13.1 and 16.5 define alias resolution.

## 6.5 Generated Odoo manifest

Generate or strictly verify the native `__manifest__.py` from the platform manifest and resolved mapping for `runtime.kind = "native"` only. External-service packages must not acquire a fabricated native addon or native migration execution path.

Keep one editable source of truth for dependency declarations. Generated `depends` must include required platform native addons and the mapped hard native dependencies. Validate existing native manifest fields such as data, assets, hooks, version, and license.

For R1 native plugins, map package version `X.Y.Z` to native manifest version `19.0.X.Y.Z`. Use the same full native target version as the migration directory, for example `migrations/19.0.0.2.0/pre-transform.py` for package `0.2.0`. Build copies migration files into the native addon's migration directory; a detached archive-level directory is not an executable migration location. Do not use upstream's special `0.0.0` directory in SDK-generated packages.

Numeric package ordering and native migration ordering must agree. Test `0.1.9 -> 0.1.10`, `0.1.10 -> 0.2.0` and skipped releases `0.1.0 -> 0.3.0`, including execution of every applicable intermediate pre/post/end migration in upstream order. A fresh installation at `0.3.0` initializes the current schema/data and does not pretend upgrade scripts were run. Reject non-increasing versions for ordinary upgrade; recovery is the coordinated restore protocol. External-service artifacts retain package versions but have no generated native version or native migration directories.

Do not modify native model names or field names when a plugin's display name changes.

## 6.6 Manifest validation

Reject before import:

- Unsupported schema or protocol major.
- Invalid/duplicate IDs and reserved namespace misuse.
- Incompatible platform, Python, or native runtime requirements.
- Missing hard dependencies.
- Undeclared native model-extension targets where detectable.
- Multiple providers with no binding.
- Conflicting route, action, service, field, or UI contribution IDs.
- Paths outside the package.
- Unsupported runtime kinds or permission requests.
- A frontend mode whose required isolation is not available.
- A manifest and generated Odoo manifest that disagree.
- Unknown security-sensitive keys rather than silently ignoring them.

Benign future extension fields may live only under a clearly namespaced `extensions` object. They cannot modify security or dependency semantics unless recognized.

# 7 Package format and supply chain

## 7.1 R1 artifact

Use an immutable ZIP-based `.mplug` artifact with one root package. The exact filename is not a trust signal.

Expected content:

- `plugin.toml`.
- Native addon source under `backend/odoo_addons/<addon_name>/`, if applicable.
- Prebuilt frontend assets under `frontend/dist/`.
- Contract schemas under `schemas/`.
- Locale resources.
- Migration scripts.
- Licenses and notices.
- A file inventory with per-file hashes.
- Build/provenance metadata.
- An optional supported signature envelope.

For `runtime.kind = "external_service"`, the `.mplug` payload is metadata-only: manifest, contract schemas, licenses/notices, inventory and provenance. It contains no native addon, runnable installer, service image, executable deployment template or native migration. The reference service source and reviewed Compose definition live separately under `examples/` and `deploy/`. Its pinned runtime image digest is an expected identity to verify, not authority to pull or launch the image. Section 14.6 controls registration.

The artifact's outer digest identifies the exact bytes. The per-file inventory must define which metadata files are excluded to avoid self-referential hashing. Do not invent cryptographic primitives or custom signature algorithms.

Every extracted path is validated before creation. Do not import a plugin to discover its metadata.

## 7.2 Archive limits and validation

R1 default limits are proposed operational settings, not universal limits: 100 MiB compressed, 500 MiB expanded, 10,000 entries, a bounded per-file size, and a bounded compression ratio. Make them configurable only by operators. Tests must cover each boundary.

Reject:

- Absolute paths, drive-letter paths, UNC paths, `..` traversal, mixed-separator escapes.
- Symlinks/hard links unless a future validated format explicitly supports them.
- Duplicate normalized paths, case-insensitive collisions, and Unicode normalization collisions.
- ZIP bombs and expanded-size limit violations.
- Names that overwrite manifest, inventory, or another plugin.
- Unrecognized executable installation hooks.
- Embedded secrets detected by package linting; detection is supplementary, not a guarantee.
- Unapproved remote script references or browser assets with credentials.

Extract into a fresh private staging directory. Do not overwrite an installed package or an existing release. Calculate hashes from the actual extracted files and compare with the declared inventory.

## 7.3 Trust policy

R1 accepts native code only from an operator-approved trust source.

Provide these distinct policies:

- **Development:** local unsigned artifacts allowed only by explicit development configuration, with visible warnings.
- **Curated deployment:** artifact digests approved by an operator and/or signatures verified against configured trusted publisher keys.
- **Open marketplace:** unsupported until R2 security and publisher controls pass.

A checksum proves byte identity, not publisher identity. A valid signature proves a key signed the artifact, not that the code is safe. The UI must present these separately.

Do not advertise signature verification if only a digest was checked. If signed catalogs are not implemented in R1, state the exact digest-approval trust model.

A production install must not silently trust a key included inside the same uploaded package. Publisher keys and catalog authorities must be configured independently.

## 7.4 Builds and Python dependencies

Build packages outside the web request process. Do not run `pip install`, `npm install`, arbitrary build backends, or migration code during upload validation.

Use prebuilt frontend assets. Resolve and build Python wheels in a controlled build environment. Prefer binary wheels where practical. Source builds execute code and require the same trust treatment as the plugin.

A native release has one Python dependency solution. Two plugins requiring incompatible versions fail planning. Do not “solve” the conflict by mutating `sys.path` unpredictably.

A runtime image/release includes exact source, dependencies, assets, schemas, and generated manifest metadata. Production application workers should not have permission to mutate their executable release.

# 8 Dependency planning and release lock

## 8.1 Planning is pure

A planning operation may read metadata, catalog entries, and installed state. It must not import third-party code, modify schemas, start services, or mutate the active environment.

Pure planning uses declarative manifests and available wheel/static metadata only. Some package tools execute source build backends just to discover metadata; this is prohibited inside planning. If metadata requires execution, obtain it in a separately authorized build environment, regenerate any changed dependency solution, and approve the new plan hash.

Inputs:

- Requested install, upgrade, suspension, enablement, or removal.
- Current release/installation state and its generation.
- Allowed artifact catalog snapshot.
- Trust policy.
- Platform and Python compatibility.
- Hard dependency constraints.
- Optional integration requests.
- Service provider bindings.
- Site/workspace policy.
- All databases sharing the release, if multi-database mode is enabled.

For external-service registration/rebinding, include operator-owned endpoint configuration generation, expected runtime image identity and requested scoped credentials. A provider configuration change is a planned change, not an untracked URL edit.

Outputs:

- Exact plugin/version/digest set.
- Native addon graph and Python dependency lock.
- Provider bindings and optional integrations.
- Added/removed/changed permissions.
- Schema ownership impacts that can be determined statically.
- Affected sites and dependents.
- Required maintenance/restart/reload.
- Required approvals.
- Known unknowns, especially effects of arbitrary trusted hooks.
- Plan ID and hash.
- Base-state digest and expiry/policy conditions.

## 8.2 Solver rules

1. Resolve version constraints before topological activation order.
2. Reject hard dependency cycles and show the exact cycle.
3. Prefer already locked compatible versions unless the request explicitly updates them.
4. Never silently downgrade a dependency.
5. Never choose a service provider by filesystem order.
6. Do not auto-install optional integrations.
7. Reject incompatible installed optional integration code if it cannot actually remain inactive safely.
8. Distinguish plugin dependency conflicts from Python dependency conflicts.
9. Block removal of a provider while dependents remain installed, unless the complete removal cascade is explicitly planned.
10. Display all transitive changes, not just the requested plugin.
11. Freeze catalog selection for the operation.
12. Fail stale-plan application if the current installation/release generation has changed.
13. Treat environment markers and Python platform compatibility consistently.
14. Require a complete solution for the release; a package-by-package greedy installer is insufficient.

Use an established resolver library where suitable. Add platform-specific metadata and policy around it. Do not write a general SAT solver as an early milestone.

## 8.3 Lockfile contract

`platform.lock` must include:

- Lock schema version and generator version.
- Platform version and upstream commit.
- Native patch-set digest.
- Python/runtime architecture.
- Plugin IDs, exact versions, artifact digests, sources and trust evidence.
- Native addon names and dependency order.
- Python lockfile digest.
- Frontend asset inventory digest.
- Service provider bindings.
- Effective API contract versions.
- Release generation and creation metadata.

Every service binding lock entry records consumer plugin/installation, local alias, site/workspace scope, service ID, contract major, exact selected API version, provider plugin/installation, implementation mode and binding generation. External provider entries also reference the operator-approved endpoint configuration generation and expected runtime image digest; credentials are referenced, never embedded.

Do not include tokens, database passwords, or private keys. An operator must be able to reproduce a release without knowing which package happened to be newest at build time.

## 8.4 Plan display

The UI and CLI must show the same underlying plan. The UI should explain:

- What will be installed or changed.
- Why every dependency is included.
- Whether native trusted code is involved.
- Which new permissions are requested.
- Whether the application will restart.
- Whether data can be changed or removed.
- What backup/recovery path is required.
- Which dependent plugins are affected.

The UI's Request operation action submits a plan ID/hash and records a request, not an authoritative approval. It displays the independent local approval/apply step in section 10.6 and observes its result. It does not carry arbitrary shell commands or claim that clicking the action authorized execution.

# 9 Plugin lifecycle and activation semantics

## 9.1 Separate state dimensions

Do not model the lifecycle with one `installed` Boolean.

| Dimension | Example states | Scope |
| --- | --- | --- |
| Artifact | available, acquired, verified, staged, quarantined, removed | Package storage |
| Release | planned, built, qualified, active, failed, retired | Executable deployment |
| Database installation | not_installed, installing, installed, upgrading, uninstalling, failed, recovery_required | Site database |
| Feature availability | enabled, suspended, degraded | Site or supported workspace |
| Service runtime | stopped, starting, healthy, draining, failed | External process/runtime |

Expose the dimensions honestly in APIs and operator screens. A plugin may have a valid artifact but a failed database migration. An installed native module may have suspended UI features but still influence model behavior.

## 9.2 Native feature suspension

For SDK-compliant plugins, suspension blocks platform-managed entry points such as:

- Page navigation and direct page access.
- Registered API/service operations.
- New job dispatch.
- Event subscription delivery.
- New scheduled work.
- Registered commands and UI contributions.

It preserves data and native registration. It does not remove imported code, reverse class overrides, undo fields, stop arbitrary unmanaged hooks, or sandbox a compromised plugin.

The UI must explicitly call this **feature suspension**. Do not use wording such as “plugin stopped” for a native module.

Workspace suspension is offered only to plugins declaring and passing the workspace activation contract. Legacy addons without those gates are site/deployment scoped. A native addon that changes a global model invariant cannot promise that the invariant disappears per workspace.

Do not suspend a required provider while dependents remain enabled. Produce a cascade plan or reject. Suspension of mutation paths must also account for in-flight jobs; define drain/cancel behavior and keep it visible.

## 9.3 Native uninstall

Ordinary Odoo uninstall can remove data/schema and downstream modules. R1 must retain this reality.

Before uninstall:

1. Identify dependent closure.
2. Show known models, fields, constraints, records, assets, jobs, and foreign references.
3. Warn that arbitrary trusted hooks may have additional effects.
4. Require a valid backup and destructive-operation approval.
5. Run in controlled maintenance.
6. Validate surviving plugins afterward.
7. Record the actual schema and data effects.

Do not remove source artifacts from a shared runtime while any database still requires them. If a module is uninstalled but its package remains in a release, do not claim its Python imports were safely unloaded from already-running workers; replace/restart the workers.

## 9.4 Data retention choices

Offer documented options, not a misleading universal “uninstall and keep data” button:

- Suspend the feature while retaining its addon and data.
- Export data and attachments to a versioned archive with an import path.
- Keep an intentionally separate persistent data addon installed.
- Use external plugin-owned storage with a separately defined retention contract.

Leaving orphaned database columns after stripping their model definitions is not by itself a supported restoration mechanism.

“Delete plugin data” is a distinct high-risk action. It must name exact site/plugin/workspace targets and never be inferred from hiding navigation or removing an artifact from a catalog.

## 9.5 Upgrade permissions and compatibility

An upgrade that adds scopes, changes runtime trust, adds a new external endpoint, or expands data access requires renewed approval even when its version range is compatible.

Interface compatibility and deployment safety are separate. A compatible API change can still require a database migration and maintenance.

# 10 Recoverable deployment and operations journal

## 10.1 Control plane

The web application accepts authenticated operator requests and exposes progress. A separate maintenance executor performs privileged work.

The executor must accept a narrow structured job protocol, not arbitrary command strings. It must not expose a Docker socket or root-equivalent control API to ordinary plugins. It can be a local CLI/on-demand process initially; the operator UI may queue a validated operation for it.

Only authenticated operators can apply release plans. Workspace administrators cannot upload native Python merely because they can manage workspace features.

The application queue carries requests, not authority. The executor independently validates targets, plan digest and operator approval against operator-controlled state or explicit authenticated CLI confirmation. An `approved=true` field in the application database, a plugin-submitted body or knowledge of an operation ID is not authorization. Keep executor credentials and approval-signing material outside the application runtime. This separation limits escalation to host privileges; it does not retroactively sandbox trusted native access to application data.

## 10.2 Apply protocol

For every mutation affecting code or schema:

1. Validate operator authority and plan approval.
2. Acquire a deployment-level lock and the target database operation lock in documented order.
3. Recheck the base-state digest, artifact hashes, trust and permission approvals.
4. Build/stage an immutable release without altering the current one.
5. Run package, dependency, contribution and compatibility checks.
6. Enter maintenance and prevent new write/job operations.
7. Drain requests and workers using explicit timeouts. Do not abruptly kill a non-idempotent job without recording its uncertain result.
8. Capture a consistent database and filestore/object-store checkpoint plus previous release/lock/config references.
9. Record the backup reference and operation journal outside the application's restoration domain.
10. Run native installation/migration in one controlled maintenance process.
11. Replace/restart all affected workers on the same new release.
12. Check registry readiness, native module states, API contracts, UI assets, permissions and data invariants.
13. Publish the new release generation and trigger safe client refresh.
14. Resume traffic and jobs.
15. Mark the operation complete and retain evidence.

Never perform this as a long-running ordinary HTTP request. Polling or streaming operation progress is fine.

## 10.3 Failure and recovery

| Failure point | Required behavior |
| --- | --- |
| During metadata planning | No code imported and no active state changed |
| During acquisition/build | Retain current release; mark staging failure |
| Before database mutation after maintenance | Return to old release if verified safe |
| During migration or after an internal commit | Keep maintenance; set recovery_required; reconcile actual state |
| After migration before traffic | Repair forward or restore coordinated backup and old release |
| After new traffic has accepted writes | No automatic destructive restore; report potential lost writes and require a recovery decision |
| Executor dies with uncertain outcome | Reconcile journal, registry, schema and worker release before retry |
| Same operation submitted again | Return/reconcile the existing operation; do not duplicate migration |

A package downgrade or git revert is not database rollback. Never run old code against an incompatible new schema and call that recovery.

A full deployment is not atomic because upstream module processing may commit at multiple points. The UI must not display a blanket “all changes rolled back” unless a verified restore actually completed.

## 10.4 Journal schema

Store at least:

- Operation ID, request ID, actor and timestamp.
- Site/deployment targets.
- Plan hash and base/target release IDs.
- Current phase and phase history.
- Artifact and migration hashes.
- Backup/checkpoint reference.
- Approvals and policy version.
- Lock ownership/lease information.
- Redacted error and correlation IDs.
- Recovery actions and final reconciliation result.

The journal must survive restoring the application database. An append-oriented local durable store is acceptable for the first single-host executor if locking, crash recovery, permissions and backup are tested. A separate control database is also acceptable. An in-memory log or a table solely inside the restored target database is not sufficient.

## 10.5 Backup and restore

A backup includes the database, filestore/object-storage checkpoint, code release, dependency lock, required non-secret configuration, and separately secured secret-recovery instructions.

Quiesce writes when needed for consistency. Do not assume independent database and filesystem copies taken at unrelated times form a valid backup.

Validate hashes and rehearse restore to a disposable target. After restoration, test attachment reads, migrations/version metadata, plugin dependencies, user access and reference application data. Keep the previous release until recovery/retention policy permits cleanup.

A restored database initially starts in maintenance with scheduled jobs, outbox delivery, webhooks, SMTP and other external effects disabled. An older checkpoint can resurrect work already completed outside the database. Reconcile operation generations, job/event IDs and externally completed effects before resuming dispatch. A restore rehearsal must use isolated network access and neutralized integration credentials so it cannot contact production services. Invalidate restored session/token material and reconcile current revocations before reopening access; do not unintentionally resurrect revoked authority.

Deletion of backups or retirement of releases with real user data requires explicit retention policy; do not clean them up merely because a test or install command finishes.

## 10.6 R1 independent local approval workflow

R1 uses UI plan preparation plus explicit local operator approval. One-click privileged web approval and a remotely accessible approval authority are outside R1. This workflow satisfies the UI-to-executor requirement in section 20.3; the pending CLI step is a deliberate product behavior, not an unfinished screen.

1. The UI or CLI prepares an untrusted plan request. The UI displays the proposed diff and an operation ID, then enters `awaiting_operator_approval`. No request body, session role or database flag authorizes execution.
2. `modular operations approve <plan-id> --plan-hash <sha256:hex>` runs through the operator's local OS account. The CLI authenticates that account against an operator-owned allowlist outside the application database. The app-side operator role permits requesting/viewing operations but does not substitute for this authority.
3. The CLI independently loads and validates the plan against operator-controlled catalog/trust/configuration and actual deployment state. It recomputes the plan hash, displays exact targets, transitive changes, trust/permission expansion, backup policy and destructive effects, and obtains confirmation. A changed plan gets a new hash and requires review again. Noninteractive approval requires that exact hash and explicit destructive/trust acknowledgments under a configured operator policy.
4. The CLI writes a durable approval record in an operator-owned local store outside the app restoration domain. Filesystem ownership and a separate execution identity prevent application containers, plugins and ordinary users from reading privileged credentials or writing approval, revocation or operator-allowlist records. R1 uses this local authorization store, not a home-grown signature scheme. Test these access restrictions using the application OS/container identity.
5. `modular plugin apply <plan-id>` invokes the executor locally. It checks the approval store independently, acquires locks, revalidates the base-state digest and all plan bindings, and atomically reserves the approval for the plan's one operation ID. UI requests can nominate pending work but cannot consume an arbitrary approval for a different operation. Repeated apply resumes/reconciles that same operation.
6. The UI polls redacted status from the journal adapter, showing awaiting approval, approved, running, completed, expired, revoked or recovery-required states. A copied operation ID grants no access to status or execution.

The approved hash is SHA-256 of the normalized plan serialized with RFC 8785 JSON Canonicalization Scheme through a tested library. Freeze the schema and golden byte/hash fixtures at G2. The hashed object includes schema version, operation ID/type, deployment/site IDs, base-state and target-release digests, exact artifacts/locks, service endpoint and binding generations, permission/trust changes, destructive flags, backup requirements and policy version. Exclude the derived plan hash and approval records themselves. No floating-point values, credentials or arbitrary shell text belong in a plan. Canonical timestamps are UTC strings.

Each approval records operator identity, exact plan hash and targets, issue/expiry times, policy/operator-authorization generation, explicit acknowledgments, state and consumed operation ID. Default approval lifetime is 15 minutes for starting an operation, configurable only by operators. Expiry during an already-started migration does not kill it; journaled recovery rules govern completion. Before mutation, a changed base state, artifact, endpoint, permissions, policy or operator authorization invalidates the approval. Expired, revoked or mismatched approvals fail closed. `modular operations revoke-approval <operation-id>` writes an independent revocation record. Recheck revocation/authority before entering mutation; if revocation arrives after mutation begins, stop at a safe boundary and reconcile rather than claiming rollback or killing a migration blindly.

Default R1 execution is single-host/on demand. A process-held exclusive lock must remain held through the mutating operation; do not steal an expired lease while its old executor may still mutate. Loss of lock ownership fences further work and requires reconciliation. Lock takeover, crash recovery and repeated apply are tested in Phase E. The journal and approval store must survive application database restore; UI progress remains readable without giving the web application write authority over those stores.

# 11 Identity workspaces and authorization

## 11.1 Distinct concepts

| Concept | Meaning | R1 choice |
| --- | --- | --- |
| Deployment | One executable release and worker environment | One local deployment |
| Site or database tenant | One database registry and persistent plugin installation set | One site by default |
| Workspace | Logical membership, data ownership and feature scope | Multiple supported |
| Organization | Optional grouping of people/workspaces | Reserved; not required to use a personal workspace |
| Company | Existing Odoo business context | Retained internally; not the public workspace model |
| Principal | Human or technical authenticated actor | Generic public identifier |
| Membership | Principal's role in a workspace | Explicit model |
| Plugin availability | Feature exposed within a supported scope | Separate from native module installation |

A site may have several workspaces. A workspace is not security isolation from trusted native server code. Incompatible native package versions require separate deployments, not merely separate databases.

## 11.2 Initial data models

Implement project-owned native models, provisionally:

- `mp.principal`: UUID, kind, display name, state, backing user mapping where applicable.
- `mp.workspace`: UUID, name, slug, state, default locale/time zone, timestamps.
- `mp.membership`: principal, workspace, role, state; unique principal/workspace constraint.
- `mp.workspace.plugin`: workspace, plugin installation, availability state, configuration/policy generation.
- `mp.plugin.installation`: site-scoped plugin/version/digest and native installation state.
- `mp.plugin.grant`: approved plugin permissions, approver, scope and policy version.
- `mp.audit.event`: actor, workspace/site, plugin, action, target, decision, operation/request ID and redacted metadata.

Names are implementation defaults, not grounds to rename upstream models.

Do not create a second password database. Reuse established authentication, password hashing, session protection, MFA integrations where available, and account recovery mechanisms. Map authenticated users to generic principals.

A service principal must not inherit administrator privilege. Use dedicated restricted identities or scoped tokens; do not impersonate arbitrary humans.

Every native service call resolves an explicit effective Odoo backend user from the authenticated human or service principal. Carry that identity through ORM authorization together with independently validated workspace scope. Missing, disabled or inconsistent mappings fail closed. Acquiring an administrator or sudo environment as a generic fallback is prohibited; narrowly reviewed internal elevation follows section 11.5.

One internal Odoo company per site is acceptable initially. Public plugin APIs must not require `partner_id`, `company_id`, `allowed_company_ids` or Odoo group IDs to perform ordinary workspace operations. The compatibility adapter may retain those concepts internally.

## 11.3 Roles

Provide a minimal documented role model:

- Workspace viewer: permitted read operations.
- Workspace editor: permitted read/create/update operations and explicitly mapped delete permission (included for R1 Notes).
- Workspace administrator: membership, workspace configuration and approved feature availability.
- Site operator: installation/deployment, trust policy, backups and recovery.
- Service identity: only explicitly granted contracts/actions.

These are independent from being a database superuser or Odoo superuser. A workspace administrator must not automatically install native code or acquire site-operator powers.

R1 account provisioning may be operator-managed. Public signup, email invitations and external identity providers are optional integrations, not prerequisites. Do not send real invitation emails during tests.

## 11.4 Effective authorization

Every public operation must evaluate:

- Authenticated actor.
- Server-selected site.
- Validated current workspace membership.
- Actor action permission.
- Plugin installation and availability.
- Approved plugin capability/grant where relevant.
- Resource ownership and record-level rules.
- Additional service-token scope if applicable.

Client-supplied actor IDs, site names, company IDs, arbitrary ORM domains or `sudo` flags cannot grant authority.

Do not rely on hiding navigation. Direct API calls, old bookmarks and saved object IDs must pass the same checks.

Retained native views use legacy transports such as `/web/dataset/call_kw`, `/web/dataset/call_button`, and public model methods. The new gateway cannot be the only authorization enforcement point. Platform-managed operations enforce workspace scope, actor permissions and documented feature-availability gates in a shared server/model layer used by every enabled transport. Inventory retained legacy routes and test direct calls. Disable unused external RPC transports instead of assuming they are absent.

For new workspace-scoped native models, provide an SDK mixin with an indexed, required workspace owner unless the model explicitly declares global/shared ownership. Ensure create, update, deletion, relation assignment and search/read are covered. Prevent moving a record to another workspace simply by writing the ownership field.

Odoo ACLs and record rules remain part of the enforcement. Test their real composition: group rules can broaden access, global rules combine differently, and absence of a rule is not default deny for an otherwise granted model. Do not assume adding one group rule fixes all scope leakage.

Authorize imports, exports, attachments, autocomplete, search, aggregates, batch operations, server actions, scheduled jobs and notifications—not only form pages.

## 11.5 Privilege elevation

Supported public service methods must not expose a generic elevation mechanism.

Use `sudo()` only in narrowly reviewed internal operations with an explicit preceding authorization decision, constrained records, and audit when sensitive. Annotate each platform-owned use with its purpose.

Native plugin Python remains trusted and can technically bypass SDK checks. State this in developer and operator documentation. Grants are still useful for supported application paths, but they do not confine arbitrary in-process code.

## 11.6 Revocation and session changes

R1 requires fresh authorization decisions to observe committed revocations. Cached authorization and active streams may delay enforcement by at most 30 seconds; document and test the actual bound. Sensitive operations such as native installation, grant changes, destructive data operations and privilege changes must perform an authoritative check at execution time without relying on cached positive authorization. Use immediate invalidation when available rather than deliberately waiting for expiry.

Active streams/subscriptions must be reauthorized or closed. A queued job must revalidate relevant authorization before execution; recording permission at enqueue time alone is insufficient for future-sensitive operations.

Workspace switching must cancel stale page requests and replace the effective context. The client must not briefly show the previous workspace's data as the new workspace loads.

Current workspace is request/mount context, not mutable process-global state or one session variable that makes browser tabs race. Each request identifies its intended workspace through a documented route/header/token mechanism; the server validates membership and fixes scope for that request. Propagate it explicitly to jobs and events. Cache keys/invalidation must account for principal, site, workspace and relevant policy/release generation. This applies to server query caches, frontend caches, menus, search, commands and persisted UI state. Logout or context changes must not reuse another principal/workspace's private cached values.

## 11.7 R1 workspace enforcement design

Use one backing Odoo user per human/service principal as applicable; do not create a different human identity or mutate site-wide Odoo group membership on every workspace switch. Workspace roles are membership data evaluated for the current operation. A role in A does not imply that role in B. Site operators have deployment powers, not an implicit data-access bypass for every workspace.

R1 applies these layers together:

1. HTTP adapters require `X-MP-Workspace` for workspace-scoped operations and validate it against the authenticated actor and server-selected site. Native view/RPC adapters send it too. Remove or reject reserved platform authority keys in client-supplied Odoo context before creating the server context. Missing/invalid workspace fails closed; bootstrap/session and declared global operations use an explicit separate path. Jobs/internal calls receive the equivalent validated context from their dispatcher.
2. A shared SDK model layer checks actor state, current membership role/action permission and feature availability on public methods and CRUD paths, including legacy RPC. Batch operations validate every target. Keep necessary native ACLs, but do not use additive Odoo group membership to represent workspace editor/admin roles. Freeze each reference plugin's explicit role-to-permission mapping at G2; Notes viewer gets read, editor gets read/write/delete, and workspace administrator additionally manages membership/configuration without acquiring installation powers.
3. Every workspace-owned model has a required indexed workspace field and a global record-rule scope restriction for supported operations. Restrict to the validated active workspace and live permitted membership; model checks provide action-level denial. Package/registry qualification verifies both the mixin and scope rules. A missing rule or a broadened group rule must not allow another workspace. Global/shared models require explicit declaration and separate authorization; the mixin does not retrofit all upstream identity/configuration models indiscriminately.
4. Create/write validates ownership and cross-workspace relations, including batch relational commands. A client cannot move ownership by writing the workspace field. Supported internal transfer is a separately authorized operation, outside the initial Notes/Canvas contract. Read/search/aggregate, attachment and export adapters share the same checks.
5. Extend the native rule evaluation context and cache-key mechanism for the validated workspace and relevant policy generation. The pinned upstream default only keys contextual rule evaluation on `allowed_company_ids`; a workspace context value by itself does not alter that cache. Re-read authoritative actor/membership/policy state at request/dispatch entry, use explicit per-site policy generations for cached derived decisions, and propagate cross-worker invalidation. Do not reuse one Odoo environment or prefetch/result cache across workspace/principal contexts. Prove this in FEAS-02 and the R1 revocation tests.

G1 must implement enough of this design to demonstrate the asymmetric-role and cache cases. G2 freezes the supported public-method checks, rule composition, context carrier, cache keys, invalidation and role mappings. A failure requiring a materially different identity/ORM model triggers the section 26.4 assessment before substantial feature development.

# 12 Data ownership and migrations

## 12.1 Relational ownership

One plugin owns each baseline model. A different native plugin may extend it only through a declared hard dependency and native extension contract.

Require a contribution inventory covering:

- New models/tables.
- Added fields, indexes and constraints on existing models.
- Relationships and delete policies.
- Owned XML/data IDs.
- Views, actions and menus.
- Scheduled jobs.
- Attachment/object storage namespaces.
- Export/import formats.
- External storage ownership.

Compare declarations with registry/schema introspection where possible. A manifest is not a proof of what arbitrary trusted Python does.

Use collision-resistant field names for cross-plugin extensions. Do not silently replace another plugin's field type, delete policy, authorization scope or model method semantics.

Native model composition shares tables and a transaction environment. Do not promise separate per-plugin schemas while also relying on ordinary `_inherit` to modify shared models.

## 12.2 Public model extension contracts

A provider may publish native extension points such as:

- Supported model names.
- Fields whose semantics are stable.
- Methods that may be overridden.
- Required `super()` behavior.
- Return types and domain exceptions.
- Named validation hooks.
- Supported UI slots.
- Allowed relationship/delete policies.

Other native access may remain technically possible, but it is outside the compatibility guarantee. Private methods and SQL table shapes are not automatically public APIs.

Do not let registration order decide conflicting definitions. Detect duplicate contributions and reject them, or require an explicitly documented override mechanism with ordering and tests.

A plugin can expose a service contract without exposing its storage. Prefer services for broad cross-plugin interactions; use native model inheritance where the deeper coupling is intentional and valuable.

## 12.3 Migration contract

Use upstream native migration phases and conventions through the packaging adapter.

For each version transition, declare:

- From/to version compatibility.
- Script and schema hashes.
- Data transformations.
- Irreversible or destructive changes.
- Expected duration/volume assumptions.
- Preconditions and postconditions.
- Whether a step is safe to retry.
- Progress/checkpoint behavior for long operations.
- Recovery procedure.
- Any external side effect, normally prohibited.

Do not claim all migration scripts are idempotent. If a step is not safely repeatable, the journal must prevent blind replay and require reconciliation after failure.

Prefer expand/backfill/validate/contract patterns for substantial schema changes. R1 may require maintenance rather than implementing full online migration.

Do not send email, charge money, trigger external jobs or emit irreversible webhooks directly from schema migrations. If unavoidable, obtain explicit approval and a separately designed reconciliation process.

## 12.4 Exports and retention

Reference plugins must support a versioned export/import format for their user data and attachments. Include schema version, stable object IDs, workspace scope, checksums and relationship information.

Import must validate permissions and references. It cannot blindly restore original owner/admin IDs into a different site.

Data export is not a full site backup. Clearly distinguish portable application data from database/filestore recovery.

Retention and erasure policies must name who owns data and what dependent plugins can retain. Feature suspension preserves data. Native uninstall may delete it. External service storage needs explicit retention and deletion behavior.

## 12.5 Concurrency and transactions

For state-changing public operations, use validated versions or equivalent optimistic concurrency checks where lost updates are plausible. Return a typed conflict rather than silently overwriting a newer edit.

A native internal transaction may involve multiple models. A public cross-process service call may not assume it shares the caller's SQL transaction. Never expose ORM recordsets, cursors, sessions, lazy objects or Python exceptions as a remote protocol.

# 13 Services commands and extension contracts

## 13.1 Service registry

A service declaration contains:

- Stable service ID and API version.
- Provider plugin and implementation mode.
- Method allowlist.
- Request and response schemas.
- Required permissions and scope.
- Timeout and payload limits.
- Read-only or mutation classification.
- Idempotency semantics.
- Health/degradation behavior.

Provider registration identity is `(service_id, contract_major, provider_plugin_id, installation_id)`. Duplicate registration of that identity is an error; distinct providers may implement the same contract. Consumer binding identity is `(site_id, workspace_scope, consumer_installation_id, alias)`. Its immutable release/configuration record selects service ID, contract major, exact compatible API version and provider installation. A required binding resolves to one provider unless the contract explicitly defines multi-provider aggregation. Ambiguous binding is an error, not the mere existence of several compatible providers.

The SDK calls aliases, never an unqualified service ID with an implicit latest major. For example, a legacy consumer declares alias `documents`, service `org.example.notes.documents`, major 1 and range `>=1.0,<2.0`; a new consumer declares its own `documents` alias for major 2 and range `>=2.0,<3.0`. Both run concurrently against a provider publishing both contracts. One consumer needing both declares `documents_v1` and `documents_v2`. Planning freezes each to an exact API version/provider in `platform.lock`; startup verifies the binding. No name collision exists across consumers. Rebinding requires a validated configuration plan, authority checks, generation change and context/cache refresh; it is never inferred from provider discovery order.

Startup must validate declared providers and dependencies. A required service failure prevents dependent feature activation; an optional integration failure produces a visible degraded state.

## 13.2 Request context

The host constructs a context equivalent to:

```python
@dataclass(frozen=True)
class CallContext:
    principal_id: str
    site_id: str
    workspace_id: str | None
    authenticated_installation_id: str | None
    attributed_plugin_id: str | None
    provider_installation_id: str
    binding_id: str
    contract_major: int
    api_version: str
    request_id: str
    trace_id: str
    deadline_utc: str
    granted_scopes: frozenset[str]
```

This is an illustrative interface to implement with validation. It is not an instruction to trust serialized client claims.

The transport authenticates the caller and constructs authoritative context. Untrusted fields in the request body never override identity, tenant, grants or deadlines.

For R1, identity and attribution have the following distinct meanings:

| Call source | Authenticated authority | Plugin attribution |
| --- | --- | --- |
| Human browser session, including native views and trusted custom pages | Current human principal, backing user, validated workspace and live actor permissions | Page/plugin/binding labels support routing, diagnostics and SDK conventions. Same-origin JavaScript can forge these labels; they do not authenticate a plugin or grant additional authority. |
| External technical identity | Validated audience-bound credential mapped to one active service installation, site/workspace and approved method/scopes | `authenticated_installation_id` comes from the credential, never the request body. |
| Supported native provider-to-provider dispatch | Original actor/backing user and validated scope, with permissions narrowed by applicable supported-path grants | Host-created call-chain attribution is diagnostic; fully trusted Python can still bypass it. |

Use `authenticated_installation_id = None` for ordinary human sessions. Resolve browser binding aliases using a consumer/plugin label and registered metadata, but enforce the resulting target method's actor/resource permissions regardless of that label. Browser-selected attribution cannot supply plugin-only authority or unlock methods reserved to technical identities. Plugin grants constrain supported integrations and authenticated installations; they do not confine same-origin browser code or arbitrary native Python. Do not put supposedly secret per-plugin credentials in the browser to simulate that boundary.

Supported synchronous call chains preserve the original principal/backing user, site and workspace. A provider calling another provider must not switch to its own broader user or expand scopes. When technical credentials or supported-path capability grants apply, effective permissions are the intersection of current actor/resource authority, token scopes and approved grants, never their union. Audit original actor, authenticated installation where present, attributed chain and target provider separately. Any reviewed internal elevation follows section 11.5 and is not a service-dispatch default.

R1 does not provide general cross-service human impersonation or delegation tokens. The host authorizes and minimizes each outbound reference-worker request. Its result is applied by the host only after rechecking the originating actor/job authority. A technical callback, if used, acts as its restricted service principal and cannot name a human to inherit that human's rights. Freeze outbound authentication/audience and request schemas at G2; an endpoint URL, actor ID in a payload or a returned result cannot establish authority.

A local native provider may use an internal adapter to acquire an Odoo environment. The generic DTO does not contain that environment.

## 13.3 Public transport

Provide a documented HTTP/JSON gateway, provisionally:

`POST /api/v1/services/{service_id}/{method}`

The endpoint dispatches only registered service methods. It must not become an unrestricted proxy to any Odoo model or Python attribute.

The SDK resolves its local alias to a registered binding ID, service ID, exact API version and provider before using this transport. Requests carry the binding ID (for example in `X-MP-Binding`), exact `api_version` and `X-MP-Workspace` when scoped. The server checks that the binding, scope, version and target agree; supplied binding IDs are routing references, not bearer authority. Missing/ambiguous version or provider selection fails rather than choosing latest. Direct registered-service calls remain subject to the same actor/technical-identity and target checks.

Request:

```json
{
  "api_version": "1.0",
  "request_id": "client-correlation-id",
  "idempotency_key": "optional-mutation-key",
  "input": {
    "note_id": "public-object-id",
    "expected_revision": 4,
    "title": "Updated title"
  }
}
```

The gateway derives the authenticated site/workspace context from the session/token and verifies any requested workspace selection. Correlation IDs are not authority.

Successful response contains `data`, contract version, server request ID and optional revision/cursor. Error response contains a stable code, safe message, correlation ID, retryable flag and bounded structured details.

Initial error taxonomy:

- `UNAUTHENTICATED`
- `FORBIDDEN`
- `NOT_FOUND`
- `VALIDATION_FAILED`
- `CONFLICT`
- `DEPENDENCY_UNAVAILABLE`
- `PLUGIN_SUSPENDED`
- `RATE_LIMITED`
- `DEADLINE_EXCEEDED`
- `CANCELLED`
- `INTERNAL_ERROR`

Do not return stack traces, secrets, SQL text or sensitive object existence information to unauthorized users. Define when a forbidden object is deliberately reported as not found.

## 13.4 Idempotency and cancellation

A mutation with an idempotency key must have a documented deduplication scope: actor/site/workspace/service/contract major/provider installation/method/key, plus request-body digest. Record the resolved binding/API version and refuse incompatible replay after rebinding or an incompatible contract change; never replay a v1 result into a v2 call. Do not use a caller-controlled attribution label to evade deduplication.

Repeating a key with different input is a conflict. Enforce a unique constraint on the full deduplication scope/key and store the input digest plus in_progress, completed or outcome_unknown state. Concurrent duplicates join/poll the same operation or receive a typed in-progress response; they must not both execute. For same-database mutations, the business effect and successful outcome record commit in the same transaction. External effects require provider-side idempotency, an outbox or durable reconciliation; a local result table alone does not provide exactly-once execution.

Persist results or outcome references for a bounded configured period. Returning a saved result still requires current authorization. Document behavior after retention expiry. A timeout does not prove an operation failed; callers reconcile or retry only according to the method's idempotency contract.

Cancellation is best effort after execution starts. It must not falsely report a committed mutation as rolled back.

No distributed ACID transaction is promised. Cross-service workflows use explicit state machines, retries and compensating actions where appropriate.

## 13.5 Native hooks versus public services

Keep two categories:

- Native hooks: fast in-process extension points, potentially transaction-aware, trusted and coupled to the native runtime.
- Public services: validated DTO contracts suitable for local or remote providers.

Do not disguise network calls as ordinary Python methods with identical failure/transaction semantics.

A validation hook that can veto a transaction needs a specified order, timeout/failure policy, error aggregation behavior and reentrancy rules. Do not use asynchronous post-commit events as if they could veto a completed write.

## 13.6 Commands and contribution registries

Commands are named user/system actions with input schemas and permissions. They may be exposed through menus, buttons or command palettes, but server-side authorization is mandatory.

A plugin may publish an extension slot for other plugins. Slot metadata includes owner, version, accepted contribution type, context schema, cardinality, ordering and failure behavior.

If ordering ties, use a deterministic documented tie-breaker. Registration conflicts are errors, not silent replacement. Cycles in ordered contributions must be rejected.

# 14 Events jobs and external services

## 14.1 Domain events

Committed domain changes must be emitted through a transactional outbox or equivalent commit-safe mechanism.

An event includes:

- Unique event ID.
- Event type and schema version.
- Owning plugin and aggregate identity.
- Site/workspace scope.
- Occurrence timestamp.
- Correlation/causation IDs.
- Optional aggregate sequence.
- Validated, minimized payload.

Delivery is at least once. Consumers must deduplicate. Do not promise exactly-once effects or global ordering.

Specify ordering only for a meaningful scope, such as one aggregate, if implemented. Define retry backoff, maximum attempts, dead-letter visibility, retention and replay behavior.

A rolled-back database transaction must not deliver a success event externally. Consumer failure must not undo an already committed producer operation.

Subscription authorization must restrict topics and payload scope. Installing a plugin must not automatically grant access to every event in the site.

## 14.2 Jobs

The first job backend may use PostgreSQL, provided it supports:

- Durable job records.
- Atomic claim/lease behavior across workers.
- Heartbeats or lease expiry.
- Attempt count, retry policy and dead-letter state.
- Idempotency keys where applicable.
- Time limits and cancellation signaling.
- Principal, workspace, plugin and trace context.
- Progress and safe error reporting.
- Drain behavior during deployment.
- Recovery after worker death.

A worker must revalidate job authorization and plugin availability. Do not run every job as the superuser by default.

Each job claim has a monotonically increasing generation/fencing token. For the supported database-backed job contract, business mutation/finalization must verify the current claim in the same transaction so an obsolete worker cannot commit after its lease was reclaimed. Retryable handlers remain idempotent under redelivery. External effects need their own idempotency or uncertain-outcome reconciliation; a lease alone cannot prevent them from executing twice.

Retries are not appropriate for every job. Non-idempotent actions require explicit deduplication or reconciliation. Jobs must not run on a release whose contract/schema assumptions conflict with the job payload.

Existing native cron can be an implementation adapter for scheduling. Do not represent it as a complete durable distributed workflow engine.

## 14.3 Reference external service

R1 must include one separately running service, such as a deterministic document-analysis worker that receives text and returns word statistics or a checksum. Do not require paid model access.

It must:

- Use the public JSON service/event boundary.
- Have its own process and dependencies.
- Receive no main database password or unrestricted filestore access.
- Use a scoped service identity.
- Expose health and structured logs.
- Handle timeout, restart and duplicate requests.
- Demonstrate a failed/slow worker without host failure.
- Be optionally launched through local Compose.
- Clearly state that this reference is trusted development code, not certified hostile-code containment.

A future AI worker may replace the computation without changing the host contract. Live provider keys, paid API calls and external spending require separate user authorization.

## 14.4 Later isolated runtime

R2 requires a concrete execution threat model and confinement backend. A container name alone is not adequate.

Required controls include:

- Non-root dedicated identity.
- Restricted filesystem and mounts.
- No host socket or privileged container access.
- No shared host credentials or main DB credentials.
- Network egress policy.
- CPU, memory, disk and process limits.
- Runtime image provenance.
- Per-installation secrets and revocation.
- Health/restart policy.
- Separate storage with declared retention.
- Audited host API surface.
- Tested escape/abuse scenarios appropriate to the chosen boundary.

Document which threats remain outside the design. Do not claim protection from a malicious kernel exploit simply because ordinary filesystem isolation works.

## 14.5 Service identity tokens

Prefer short-lived, audience-bound tokens or an equivalent authenticated local channel. Bind identity to installation, deployment/site and approved scopes. Validate audience and expiry.

An endpoint URL alone is not authentication. A plugin-provided arbitrary URL must not cause unrestricted server-side requests; defend against SSRF with configured destinations, network policy, redirect restrictions and resolved-address checks appropriate to the implementation.

Revocation must stop new authorized requests within the documented bound. Never hand a service plugin a reusable administrator session cookie.

## 14.6 R1 external-service registration and lifecycle

The supported R1 service deployment model is an operator-managed local Compose service with an explicitly configured endpoint. The plugin installer registers metadata and provider bindings; it does not pull images, start/stop containers, run deployment templates, install the service's Python dependencies into the host, or gain Docker-socket authority. This is the selected R1 behavior, not a placeholder for an orchestrator.

An external-service artifact uses this runtime declaration instead of a native addon declaration:

```toml
[runtime]
kind = "external_service"

[external_service]
endpoint_config = "document_stats_local"
expected_image = "registry.example.invalid/document-stats@sha256:<64-hex-digest>"
```

The example image value is schematic and must fail validation until replaced by a real immutable build digest. `endpoint_config` references an independently operator-owned configuration entry; the artifact cannot define or override a URL, network allowlist, credential, mount, launch command or trust authority. Native `addon_name`, host Python dependencies and native migrations are invalid for this runtime kind. Service provides/requires declarations, schemas, package version, permission requests, provenance and archive validation remain mandatory as applicable. Backend image identity and contract version are separate from `.mplug` artifact identity.

The reviewed reference source builds a local image pinned by digest, with its own dependency lock and inventory. The operator starts it using the documented Compose profile through a separate explicit command. Native connector/UI code, if required, is packaged as a separate native plugin; the external metadata artifact contains no same-origin frontend code. R1 does not support arbitrary external-service deployment descriptors.

An operator-owned endpoint entry records installation/site/workspace binding, configured destination, expected image digest, health path, allowed contract/methods, credential references, timeouts/payload limits and configuration generation. The local development profile uses an explicit internal Compose destination allowlist; it does not weaken SSRF controls by accepting arbitrary private URLs. The operator verifies actual Compose image identity; health reports alone are not image attestation. The app sees only the endpoint information and narrowly scoped invocation material it needs, never deployment-control credentials.

Credentials are generated/provisioned outside packages and browser bundles. Host-to-worker calls use a worker-audience, short-lived scoped credential (at most five minutes), bound to installation/site/workspace and allowed methods; a host-owned issuer validates current approval and issues them through a reviewed standard token library. The worker verifies audience/issuer, expiry, scope and the frozen request schema. For R1, remove the endpoint from dispatch immediately on revocation and ensure new host authorization checks obey section 11.6. Already-sent worker computations may finish; results cannot mutate host data without a fresh host-side authorization decision. If worker-to-host access is needed, provision a separate host-audience service credential with only the explicit callback methods; never reuse a host administrator cookie, signing key or main DB password. G2 fixes the exact token format/key provisioning and test vectors without designing a new cryptographic protocol.

| Operation | Metadata/host behavior | Operator-managed runtime behavior |
| --- | --- | --- |
| Install/register | Validate trusted artifact, approved endpoint identity, scopes and binding plan; record installation. Native schema is not fabricated. | Already launched or remains stopped; a required unhealthy provider cannot activate dependent features. |
| Enable | Revalidate endpoint/configuration, credentials and health; activate allowed provider bindings. | No automatic launch. |
| Suspend/revoke | Block new dispatch, drain/cancel as documented, stop accepting unauthorized results/callbacks; show in-flight uncertainty. | Process may remain running; UI must say so. |
| Upgrade | Validate new artifact/image expectations, schemas and binding compatibility; approve changed endpoint or permissions; coordinate host maintenance if needed. | Operator separately deploys the pinned image; no schema migration of remote storage is inferred. |
| Unregister | Reject or explicitly rebind/cascade required consumers; remove provider/bindings and revoke credentials. | No automatic process stop or remote data deletion. |

The reference worker is stateless apart from bounded deduplication/diagnostic state. User data remains host-owned; request text is not retained after computation and is not logged. A future stateful service requires a separate versioned storage migration/retention contract. A metadata unregister is not native uninstall, remote storage erasure or proof that the process stopped. Demonstrate process outage and registration/suspension independently in Phase F.

# 15 Platform security and operational defaults

## 15.1 Trust boundaries

Document at least these boundaries:

1. Browser/end user to application.
2. Workspace to other workspaces.
3. Application HTTP process to privileged executor.
4. Native trusted plugins to host process.
5. External service to public service gateway.
6. Custom trusted frontend to host page.
7. Future sandboxed frontend to host bridge.
8. Artifact/catalog publisher to installer.
9. Site database/filestore to backup and restore system.

The native plugin boundary is explicitly not a confinement boundary. Review protects quality and provenance; it cannot make arbitrary in-process code harmless.

## 15.2 Required controls

- Parameterized queries and reviewed ORM bypasses.
- CSRF protection for browser session mutations.
- Correct cookie flags and no broad parent-domain host cookies.
- CORS allowlists; no blanket wildcard with credentials.
- Input, output, upload and message-size validation.
- Rate limits on login, public endpoints and plugin operations.
- Sanitized rich text/Markdown and escaped manifest metadata.
- Safe attachment download authorization and content-type handling.
- No arbitrary remote code or template evaluation from catalog text.
- No dangerous public database manager/listing endpoints in production.
- Explicit allowed-host and trusted-proxy configuration.
- Protected admin/operator interfaces.
- Sensitive configuration redaction.
- Dependency/license inventory and vulnerability scan reports.
- Security logging without credentials or private document contents.

Do not declare the platform “secure” solely because these items appear in a checklist. Map them to tests and observed behavior.

## 15.3 Production separation

Application containers should be non-root where supported and have read-only code releases. Separate data volumes, temporary uploads and logs. The maintenance executor has narrower, explicit privileges rather than lending root-equivalent access to all application processes.

Production initialization, migrations and account creation must be explicit operator operations. Starting a web worker must not silently upgrade a production database.

Disable development routes and sample users. Rotate generated bootstrap credentials. Do not leave a documented default administrator password active.

## 15.4 Dependency and release response

Produce an SBOM or equivalent complete dependency inventory for the release. Record excluded/accepted vulnerability findings with rationale and review date.

A quarantined artifact cannot activate. If compromised native code already ran, hiding its menus is not sufficient: stop/replace the affected runtime, assess credentials/data exposure, and follow a recovery procedure.

Preserve upstream security-relevant behavior unless a test-backed replacement exists. Reduce source coupling gradually; do not delete auth, session or rule machinery just to make the directory tree smaller.

# 16 Application shell and UI hosting

## 16.1 Shell responsibilities

Build a neutral web-first shell that owns:

- Authentication/session expiry handling.
- Workspace selection.
- Application navigation.
- URL routing, browser history and deep links.
- Command palette.
- Notifications and host dialogs.
- User/settings entry points.
- Plugin page mounting and error recovery.
- Theme, density, language, direction and locale.
- Plugin management for authorized operators.
- Global accessibility landmarks and focus transitions.

It must not require every page to be an ORM list or form.

Use the existing replaceable WebClient root and client-action seams where practical. Keep menu/action/session translation in a compatibility adapter. Do not expose Odoo's entire frontend environment as the generic host SDK.

The first shell should be clean and restrained: clear hierarchy, readable typography, minimal chrome, good spacing, reliable keyboard behavior, light/dark themes. Avoid filling the interface with dashboard cards that are not relevant to the current application.

## 16.2 Hosting modes

| Mode | Required release | Behavior | Trust |
| --- | --- | --- | --- |
| Native view | R1 | Declarative list/form and existing action/view tooling | Trusted native addon |
| Trusted custom page | R1 | Prebuilt JS bundle mounts into a plugin-owned subtree | Fully trusted host-origin browser code |
| Sandboxed embedded page | R2 | Dedicated origin plus restricted host bridge | Separately verified frontend confinement |
| External application link | Optional | Explicit navigation to an approved external application | Not equivalent to shell-hosted integration |

Backend and frontend trust are separate declarations. A service plugin with an external backend can still have an unsafe same-origin frontend.

Visual modes are independent:

- `standard`: shared components and page patterns.
- `tokens_only`: shared tokens with custom components.
- `custom`: plugin-owned visual design.

Choosing `custom` must be supported without forking the shell. It does not waive accessibility or security requirements.

## 16.3 Page and routing contract

Normalize routes under a host-owned namespace such as:

`/app/{plugin_id}/{page_path}`

The shell owns login, settings, workspace, plugin manager and error routes. Plugins cannot claim them or another plugin's namespace.

Each page declares:

- Local page ID.
- Relative path.
- Localized title.
- Renderer kind.
- Entry asset or native action reference.
- Required permission.
- Shell or immersive layout.
- Optional unsaved-work policy.
- Compatible UI API major.

Direct navigation, browser refresh, back/forward and deep links must work. Missing/suspended/unauthorized plugin pages must produce appropriate errors without leaking private metadata.

A workspace change invalidates page context. Pending requests from the old mount generation must not update the new page.

## 16.4 Custom page lifecycle

Implement a framework-neutral interface similar to:

```typescript
interface PluginPageModule {
  mount(input: {
    element: HTMLElement;
    host: PluginHost;
    route: RouteSnapshot;
    signal: AbortSignal;
  }): MountedPage | Promise<MountedPage>;
}

interface MountedPage {
  updateRoute?(route: RouteSnapshot): void | Promise<void>;
  canLeave?(): "allow" | "confirm" | Promise<"allow" | "confirm">;
  dispose(): void | Promise<void>;
}
```

Contract rules:

- The page owns its mount subtree, not the document root or shell chrome.
- `dispose` removes subscriptions, observers, timers, sockets and handlers.
- The host aborts outstanding SDK calls and stops delivering events for the old mount generation.
- Async responses are discarded if their mount/context generation is obsolete.
- The host distinguishes a route update from a remount.
- An immersive page retains an accessible exit path.
- Mount failures display recovery actions and a correlation ID.
- Repeated failures must not create an automatic reload loop.
- A dirty page receives an unsaved-work confirmation before navigation where feasible.
- Session expiry must not silently discard an unsaved draft; provide safe local recovery where appropriate without persisting sensitive data indiscriminately.

Trusted JS can still damage the host page. Lifecycle cleanup and error boundaries are quality mechanisms, not a security sandbox.

## 16.5 Host SDK

Publish versioned TypeScript types and runtime schema validation. A minimal surface:

```typescript
interface PluginHost {
  context(): Readonly<HostContext>;

  navigate(target: {
    pluginId: string;
    pageId: string;
    params?: Record<string, string>;
    query?: Record<string, string>;
  }): Promise<void>;

  services: {
    call<T>(
      bindingAlias: string,
      method: string,
      input: unknown,
      options?: {
        signal?: AbortSignal;
        idempotencyKey?: string;
      }
    ): Promise<T>;
  };

  commands: {
    execute(commandId: string, input?: unknown): Promise<unknown>;
  };

  events: {
    subscribe(topic: string, callback: (event: HostEvent) => void): () => void;
  };

  notifications: {
    show(input: {
      severity: "info" | "success" | "warning" | "error";
      message: string;
    }): void;
  };

  dialogs: {
    confirm(input: {
      title: string;
      message: string;
      destructive?: boolean;
    }): Promise<boolean>;
  };

  theme: {
    current(): ThemeSnapshot;
    subscribe(callback: (theme: ThemeSnapshot) => void): () => void;
  };

  locale: {
    current(): LocaleSnapshot;
    translate(key: string, values?: Record<string, unknown>): string;
  };
}
```

`host.services.call("documents", "get", input)` uses the current consumer installation's declared `documents` alias. The host supplies the locked binding ID, exact API version, selected provider and workspace context; page code cannot override them in call options. Use a second declared alias to access another contract major. Publish binding descriptors/types and typed unavailable errors from the frozen schemas. This wrapper prevents accidental version drift; it does not authenticate same-origin plugin code or replace server authorization.

`HostContext` contains only necessary generic identity/context fields: principal ID, display name, site/workspace IDs, plugin/installation ID, locale, direction, time zone, effective UI generation and advertised capabilities.

Advertised capabilities are convenience information for presentation, not authorization proof. The server checks every call.

The new generic SDK must not expose host credentials, arbitrary ORM method dispatch, `sudo`, the whole Odoo environment, generic JavaScript evaluation, unrestricted filesystem access, or an unrestricted open-URL action. Existing native views may retain their Odoo ORM transport behind the compatibility layer; it is not a generic public SDK contract and remains subject to the server/model-layer enforcement and direct-transport tests in section 11.4.

## 16.6 UI contributions

Support a deliberately small initial set:

- Application navigation item.
- Page.
- Command-palette item.
- Settings section.
- Toolbar action.
- Contextual record action.
- A provider-owned named slot.

Each has a namespaced ID, owner, permission, order, context schema and renderer/handler reference.

A slot provider declares whether it accepts actions, text, components or other structured content. The host must not evaluate arbitrary template strings from catalog metadata.

A plugin extending another plugin's UI must declare a dependency on the slot contract. Unknown or incompatible slot versions fail activation or disable only a declared optional integration.

Visibility predicates must use a safe declarative representation or compiled trusted plugin code. Do not introduce an ad hoc eval language into manifests.

# 17 Optional design system and UI primitives

## 17.1 Principles

Consistency should be the easiest path, not a mandatory visual style.

Keep the default component stack based on the existing Owl ecosystem and selectively wrap useful upstream primitives. Do not build an entirely new component library before the reference applications work.

Publish framework-neutral CSS tokens. Add Web Components only when a concrete integration benefits; do not promise first-class wrappers for every frontend framework.

## 17.2 Initial tokens

Use semantic CSS variables, provisionally `--mp-*`:

- Background/surface/foreground/muted text.
- Border/separator.
- Primary/secondary action.
- Success/warning/danger/info.
- Focus ring.
- Font families and text scale.
- Spacing scale.
- Border radius.
- Elevation.
- Control height/density.
- Motion duration/easing.
- Layout widths.

Support light/dark and reduced motion. Tokens must be semantic, not tied to one fixed palette.

Plugin custom styles should be scoped to their root. Shadow DOM may help CSS separation but is not a security boundary. Linting and conventions cannot confine malicious trusted CSS/JS; document the distinction.

## 17.3 Required component inventory

| Category | Minimum R1 functionality |
| --- | --- |
| Controls | Button, input, textarea, select, checkbox, switch, validation message |
| Overlays | Dialog, confirmation, dropdown/menu, tooltip, toast |
| Navigation | Tabs, breadcrumbs, sidebar/app entry, command palette |
| Layout | Page header, section, panel, split view, responsive content region |
| Data | Table/list, sorting, paging, filtering, record picker, empty/loading/error states |
| Forms | Labels, help text, required state, field errors, dirty state, save/cancel |
| Status | Progress, task state, retryable error, permission denied |
| Settings | Consistent settings page and configuration form pattern |

Data components must support server-side paging/filtering. Do not fetch an entire unbounded table to paginate locally.

A generic data source is a registered service/query contract, not an arbitrary SQL string supplied by a plugin's browser code.

Existing upstream components may satisfy these requirements through documented adapters. Distinguish new public APIs from private imported upstream widgets.

## 17.4 Accessibility and localization

Target WCAG 2.2 AA for the shell and standard SDK, with automated and manual verification rather than an untested compliance claim.

Required checks:

- Keyboard access to navigation, menus, forms, dialogs and plugin controls.
- Visible focus and correct focus restoration.
- Semantic labels, landmarks, headings and error associations.
- Screen-reader loading/error announcements.
- Sufficient contrast in light and dark themes.
- Reduced motion.
- English LTR and Arabic RTL.
- Logical CSS properties and mixed-direction text handling.
- Localized dates, numbers, time zones and pluralization.
- Long labels and translations.
- 200 percent zoom and a narrow viewport.
- Keyboard alternatives to drag-and-drop.
- Accessible escape from immersive pages.

Custom UI authors own their component accessibility, but the host still enforces baseline package quality and provides test helpers. “Custom design” must not mean inaccessible navigation or unreadable permission dialogs.

# 18 Sandboxed frontend contract for R2

R1 must reserve a transport-neutral host API. It need not ship an untrusted iframe runtime. If arbitrary untrusted frontend packages are enabled, this section becomes mandatory before release.

## 18.1 Origin and storage isolation

Use a dedicated origin with no host cookies or reusable host bearer tokens. Unrelated untrusted publishers must not share mutable browser storage through one permissive origin.

Host cookies must be host-only where appropriate. Do not place a supposedly isolated page on the host origin with unrestricted script access.

Configure iframe sandbox and Permissions Policy deliberately. Deny top navigation, popups, camera, microphone, clipboard, downloads and other privileged capabilities unless explicitly granted for a reviewed use case.

The initial R2 design uses an origin-preserving iframe on a genuinely different, plugin-specific origin. `allow-scripts allow-same-origin` may be used only for that foreign origin, never as a substitute for isolating same-origin code. Other sandbox permissions remain absent unless explicitly approved. If an opaque-origin sandbox is chosen instead, specify a different nonce/source/MessagePort bootstrap and threat analysis: `null` is not a trustworthy origin identity and cannot serve as an exact-origin allowlist match.

## 18.2 Bridge protocol

A handshake must:

1. Validate exact expected origin and frame source.
2. Negotiate supported protocol major/minor.
3. Bind a fresh nonce and mount generation.
4. Establish a dedicated MessagePort or equivalent channel.
5. Expose only approved methods.

Messages include protocol version, request ID, method, validated payload and context generation. Reject unknown methods, invalid schemas, excessive sizes, duplicates/replays where relevant, and stale generations.

The host derives actor and workspace authority. Frame-supplied claims do not override it.

Apply rate limits, deadlines and cancellation. On frame teardown or token revocation, stop delivery and invalidate outstanding bridge authority.

## 18.3 Security tests

Test forged origins, wrong frame sources, stale frames, replayed requests, oversized payloads, arbitrary URL schemes, attempts to access host DOM/cookies, unauthorized service calls, cross-workspace calls and popup/top-navigation abuse.

Themes and locales cross the bridge as data. Do not serialize arbitrary host functions or expose the full host JS environment.

A sandboxed frontend does not make a native Python backend safe. Track both trust declarations independently.

# 19 Assets caching and runtime compatibility

Frontend builds are ahead of installation. Serve assets by immutable content-addressed release paths and correct content types.

A release binds backend code, schemas, UI catalog and assets. The effective UI catalog includes a generation identifier. Old clients must detect an incompatible release and reload safely; do not let them continue submitting incompatible mutations indefinitely.

Do not attempt native Odoo service unload in a live browser. Full client reload after native release activation is the default.

Cache code-only public assets independently from tenant-private data. Never embed secrets or user documents in JS bundles. Private responses and downloads require appropriate authorization/cache headers.

Define Content Security Policy per hosting mode. Record upstream constraints and exceptions. Do not weaken the entire host CSP automatically to satisfy one plugin.

Use safe URL handling; reject `javascript:`, dangerous `data:` use and unapproved external schemes. Sanitize plugin-provided rich text. Treat manifest descriptions as untrusted text.

# 20 Plugin manager and curated catalog

## 20.1 Required screens

Provide:

- Installed plugins with version, trust, health, availability and dependency status.
- Plugin details with publisher/license/provenance, declared permissions, provided services, native extension targets and data impact.
- Curated available catalog.
- Upload validation result.
- Dependency/upgrade plan preview.
- Apply progress and operation journal.
- Feature suspension and dependent impact.
- Destructive uninstall confirmation.
- Recovery-required state with operator instructions.

Use accurate terminology from section 9. Do not display a green success state before health and migration verification finish.

## 20.2 R1 catalog

The first catalog may be a local JSON index or configured authenticated endpoint containing:

- Plugin ID and available versions.
- Artifact URL/location and digest.
- Compatibility and dependencies.
- Publisher/trust reference.
- License and summary.
- Optional screenshots/help links.

It must use the same artifact validation and planning path as uploads. Do not create a separate unsafe fast path for trusted-looking catalog entries.

Catalog origins are configured by operators. Fetching an arbitrary user-supplied catalog URL is not allowed. Enforce SSRF and redirect policy.

No ratings, billing, public publisher onboarding or automatic public publication is required.

## 20.3 Upload and installation UX

Uploading an artifact only acquires and validates it. It does not execute it.

The UI must clearly separate:

1. Upload/validate.
2. Review trust and dependency plan.
3. Approve defined changes.
4. Queue/apply through the maintenance executor.
5. Observe verification and final state.

For native code, present an explicit full-trust warning. A permissions checklist must not imply the installer can restrict arbitrary Python to those boxes.

R1 completion uses the section 10.6 workflow: the UI prepares/previews the plan, displays the exact local approval/apply commands and explains why local operator authority is required, then observes the same operation's progress and result. Independent CLI approval remains required at R1 completion; a one-click privileged web Apply button is not required. Never expose shell execution through the UI or mistake an app-side approval click for executor authority.

# 21 Developer tooling and SDK experience

## 21.1 CLI surface

Implement a consistent CLI; names below are normative intent and may receive minor ergonomic refinements:

| Command | Expected behavior |
| --- | --- |
| `modular doctor` | Inspect tooling/configuration and report blockers without mutation |
| `modular dev up` | Start the isolated local development profile |
| `modular dev down` | Stop it without deleting persistent data |
| `modular plugin create <id>` | Scaffold a new plugin without overwriting existing files |
| `modular plugin validate <path>` | Validate manifest/package/contributions without code import |
| `modular plugin build <path>` | Produce immutable artifact and metadata |
| `modular plugin test <path>` | Run applicable unit/contract/integration tests |
| `modular plugin plan <operation>` | Produce a reviewable plan and dependency explanation |
| `modular operations approve <plan-id> --plan-hash <digest>` | Independently review and authorize an exact plan through the local operator account |
| `modular operations revoke-approval <operation-id>` | Revoke local execution authority; reconcile safely if mutation already started |
| `modular plugin apply <plan-id>` | Apply an approved plan through the control plane |
| `modular plugin suspend <id>` | Plan/apply honest feature suspension |
| `modular plugin uninstall <id>` | Plan destructive native removal; never implicit; external services use unregister |
| `modular operations inspect <id>` | Show phase, journal, errors and recovery state |
| `modular backup create` | Create a consistent named checkpoint |
| `modular backup verify <id>` | Verify metadata/checksums and restore evidence |
| `modular restore plan <id>` | Preview exact targets and data-loss implications |
| `modular restore apply <plan-id>` | Apply explicitly approved recovery |
| `modular services list` | Show effective providers/contracts/health |
| `modular services register <artifact>` | Plan registration of an external-service artifact against a preconfigured operator endpoint; no runtime launch |
| `modular services unregister <id>` | Plan provider/binding removal and credential revocation; no process stop or remote data erasure |
| `modular sdk generate-types` | Generate reproducible API/manifest types |
| `modular release verify` | Check release inventory and readiness |

Provide human-readable output and `--json` for automation. Structured success must distinguish “accepted/queued” from “completed.”

Define stable exit codes for success, validation, authorization, conflict, infrastructure failure and recovery-required outcomes. Do not use exit 0 for a failed migration merely because the error was handled.

Noninteractive automation must approve an exact plan hash/policy. A universal `--yes` must not bypass destructive-action or publisher-trust checks. Tests may use an explicitly labeled disposable-fixture profile.

## 21.2 Scaffold contents

A scaffold includes:

- Declarative manifest.
- Native addon files where appropriate.
- Basic model/service/page.
- Security declarations.
- Migration directory convention.
- Locale files.
- UI entry and build configuration for custom mode.
- Contract schemas.
- Unit and integration tests.
- README with supported extension points.
- License/notice placeholders.
- Export/import example where data is owned.

Offer templates for native CRUD, native extension, trusted custom page, and external service. Do not generate a large unmaintainable boilerplate project for a simple plugin.

## 21.3 Development behavior

- Support targeted frontend reload in development.
- Native backend/model changes may require controlled restart; make that explicit.
- Use watched source only in development.
- Keep production immutable.
- Provide fixtures for current principal/workspace/service context.
- Generate types from schemas to avoid drift.
- Validate declared permissions and contribution references.
- Test packaged artifacts, not only editable source trees.
- Provide warnings for private upstream imports and unsupported monkeypatching.

## 21.4 Documentation

Required documentation includes:

- Ten-minute quickstart with actual verified commands.
- Plugin author tutorial.
- Native extension tutorial.
- Custom UI tutorial.
- Service provider tutorial.
- Manifest and API reference.
- Dependency/version policy.
- Authorization/workspace guide.
- Migration and data-retention guide.
- Deployment/backup/recovery runbooks.
- Trust model and limitations.
- Upstream patch ledger.
- Supported runtime matrix.
- Troubleshooting by error code.
- Release/migration compatibility policy.

Documentation must accurately distinguish implemented, experimental and planned features. Generated placeholders or TODOs are not release evidence.

# 22 Reference plugins and product demonstrations

Build examples as independently packaged plugins using only supported public contracts plus documented native extension APIs. No example may require a new core patch solely for its feature.

## 22.1 Notes

Plugin `org.example.notes`, addon `mp_example_notes`.

Features:

- Workspace-owned notes with title, body, tags or category owned by the base example only if declared, timestamps, author and revision.
- Standard list/detail/form interface.
- Search, filter, paging, create, edit, delete and export.
- Viewer/editor permissions.
- Versioned documents service.
- Committed note-change event.
- Import/export with attachments if attachments are included.

Use meaningful loading, empty, validation and error states. Reject stale revisions and cross-workspace IDs. Do not make the example dependent on CRM/contact functionality through its public API.

## 22.2 Notes extension

Plugin `org.example.notes_labels`, addon `mp_example_notes_labels`.

It must:

- Declare a compatible hard dependency on Notes.
- Extend the Notes model with a clearly owned namespaced field.
- Add a documented UI field/action through an inherited view or provider-owned slot.
- Expose one command using the base service.
- Demonstrate a version upgrade that transforms existing extension data.
- Show dependency impact when Notes or the extension is suspended/uninstalled.
- Preserve base records across a non-destructive extension upgrade.
- Make native shared-table coupling explicit.

The extension's field definition remains in the registry while its workspace features are suspended. Do not test or claim that the field physically disappears per workspace.

## 22.3 Canvas or visual board

Plugin `org.example.canvas`, addon `mp_example_canvas` if using native persistence.

It must:

- Host a custom page built with plain JavaScript/TypeScript or another selected frontend, not dependent on Owl APIs in its page code.
- Use its own visual layout with optional design tokens.
- Persist board state through a versioned service.
- Support deep links and browser navigation.
- React to theme/locale/workspace changes.
- Clean up repeated mounts.
- Handle unsaved work and conflicts.
- Remain usable without the standard data-view patterns.
- Provide a keyboard-accessible interaction path for core operations.

The host wrapper may use Owl. The plugin's page implementation should prove that the public mount contract is framework-neutral.

This is a basic board demonstration, not a complete collaborative whiteboard or CRDT editor.

## 22.4 External document analysis service

Plugin/service `org.example.document_stats`.

Use deterministic local text statistics rather than a paid AI provider. Trigger it from Notes through a command or a job. Return structured results. Demonstrate scoped credentials, timeout, restart, duplicate-event handling and degraded UI.

Package its metadata as `runtime.kind = "external_service"` under section 14.6. Provide separately reviewed source, image lock and Compose startup instructions. The Notes integration uses a declared local service alias; it must not launch containers or import worker dependencies into the host.

The service must not import Odoo, use an ORM recordset, or receive database credentials. An integration test must inspect its configuration and verify the absence of such authority.

## 22.5 Demonstration walkthrough

The final walkthrough must show, with screenshots/log evidence and reproducible commands:

1. Fresh platform startup.
2. Two workspaces with different members.
3. Notes installed from a built package.
4. Dependency preview when installing Notes Labels.
5. Custom Canvas page with a visibly different UI.
6. A permission-denied direct request.
7. An external service task and a simulated service outage.
8. A native upgrade and controlled client reload.
9. Feature suspension with data retained and accurate warning.
10. Destructive uninstall preview without silently applying it to user data.
11. A failed fixture migration and successful coordinated restore.
12. A clean reinstallation from documented release artifacts.

# 23 Testing and verification requirements

## 23.1 Test levels

Use the appropriate tool for each boundary:

- Pure unit tests for schemas, resolver behavior, IDs, package validation and SDK utilities.
- Native Odoo test mechanisms for ORM behavior, ACLs, record rules and HTTP integration.
- Separate lifecycle integration scripts/processes against disposable databases for install/upgrade/uninstall.
- Browser tests for shell, standard and custom UIs.
- Contract tests for service providers/consumers.
- Fault-injection tests for executor, worker and migration recovery.
- Security tests for uploads, scope checks and trust boundaries.
- Packaged-artifact tests from a clean environment.

Do not run native module lifecycle acceptance solely inside an Odoo transactional unit-test wrapper; upstream explicitly warns these operations are not transactional.

Mocks are useful for unit tests, but database migration, record-rule and restore acceptance must use real PostgreSQL and actual native registry operations.

## 23.2 Acceptance matrix

Every ID below must be mapped to an automated test, a documented manual verification, or an explicit release-stage exclusion. R1-required items cannot be marked passed by future design documentation.

| ID | Required observation | Stage |
| --- | --- | --- |
| FEAS-01 | Asymmetric workspace roles and record ownership are enforced through gateway and legacy model paths | G1 early gate |
| FEAS-02 | Two tabs, warmed caches and cross-worker revocation preserve workspace/role boundaries | G1 early gate |
| FEAS-03 | Minimal custom non-Owl page and native action coexist through the host adapter with correct routing/disposal | G1 early gate |
| FEAS-04 | Browser attribution and supported call chains cannot expand authenticated authority | G1 early gate |
| FREEZE-01 | All seven section 5.5 contract rows have versioned schema/type/example paths and digests, with no critical authority/lifecycle TODO | G2 checkpoint |
| FREEZE-02 | Manifest, restricted version mapping, alias bindings and approval canonicalization fixtures pass | G2 checkpoint |
| FREEZE-03 | Frozen workspace/identity/UI contracts agree with passing G1 behavior and documented patch surface | G2 checkpoint |
| FREEZE-04 | Contract inventory maps owning phases, acceptance IDs, compatibility fixtures and change/invalidation rules | G2 checkpoint |
| BOOT-01 | Empty volumes initialize and an administrator can log in | R0 |
| BOOT-02 | A second fresh build reproduces the declared inventory | R0 |
| BOOT-03 | Explicit server-wide module choice works, including RPC omission if selected | R0 |
| BOOT-04 | No excluded ERP application is unexpectedly installed | R0 |
| BOOT-05 | Unexpected addon search-path content cannot bypass release inventory policy | R1 |
| BOOT-06 | Worker startup does not silently migrate production state | R1 |
| PKG-01 | Manifest validation does not import plugin code | R1 |
| PKG-02 | Traversal, symlinks, duplicate normalized paths and ZIP bombs are rejected | R1 |
| PKG-03 | Digest mismatch and same-version/different-artifact conflict are rejected | R1 |
| PKG-04 | Unsigned artifacts follow the actual configured trust policy | R1 |
| PKG-05 | Unknown sensitive schema fields and contract majors fail safely | R1 |
| DEP-01 | Missing transitive dependency fails before any runtime mutation | R1 |
| DEP-02 | Version conflict explains the incompatible constraints | R1 |
| DEP-03 | Hard dependency cycle reports the cycle | R1 |
| DEP-04 | Python dependency conflict fails the native release plan | R1 |
| DEP-05 | Multiple service providers require an explicit binding | R1 |
| DEP-06 | Optional absent/incompatible integration does not break the base plugin | R1 |
| DEP-07 | Stale plan is rejected | R1 |
| DEP-08 | Existing compatible locked versions are preserved unless update requested | R1 |
| VER-01 | Invalid package version forms are rejected and numeric package/native order agrees | R1 |
| VER-02 | Adjacent and skipped-release migrations run applicable scripts; fresh install does not simulate an upgrade | R1 |
| ORM-01 | One packaged addon creates a model and another extends it | R0/R1 |
| ORM-02 | Extension upgrade preserves original and extension-owned values as specified | R1 |
| ORM-03 | Duplicate field/contribution conflict is caught or deterministically rejected | R1 |
| ORM-04 | Export/import preserves supported data and rejects unsafe scope reassignment | R1 |
| ID-01 | Two workspaces cannot read/write/create/delete each other's private records | R1 |
| ID-02 | Forged actor, database, company and workspace inputs do not grant access | R1 |
| ID-03 | Export/search/attachments/autocomplete/batch/job paths enforce scope | R1 |
| ID-04 | Service principal has no implicit administrator authority | R1 |
| ID-05 | Revocation affects new and cached requests within the declared bound | R1 |
| ID-06 | Workspace admin cannot install native code or run deployment operations | R1 |
| ID-07 | Direct legacy RPC/model calls cannot bypass scope, authorization or supported suspension gates | R1 |
| ID-08 | Two tabs on different workspaces and their caches/replies remain isolated | R1 |
| ID-09 | One user is editor in A and viewer in B without global-group privilege leakage, including direct RPC | R1 |
| ID-10 | Cross-worker membership/policy changes invalidate scoped rules and cached authorization within the declared bounds | R1 |
| TEN-01 | Two test databases do not leak data or registry context | R1 regression |
| TEN-02 | Incompatible native versions sharing one runtime are rejected | R1 |
| LIFE-01 | Feature suspension retains native schema/data and blocks documented entry points | R1 |
| LIFE-02 | UI/docs do not claim native overrides/imports are unloaded | R1 review |
| LIFE-03 | Required-provider suspension/removal shows the dependent closure | R1 |
| LIFE-04 | Native uninstall requires explicit destructive approval and backup | R1 |
| LIFE-05 | Upgrade permission expansion requires reapproval | R1 |
| LIFE-06 | Artifact removal is blocked while a site still needs it | R1 |
| MIG-01 | Failure before mutation preserves the previous working release | R1 |
| MIG-02 | Failure after an internal commit enters recovery_required, not false rollback success | R1 |
| MIG-03 | Executor crash is reconciled before a retry | R1 |
| MIG-04 | Concurrent operations serialize or reject safely | R1 |
| MIG-05 | Reusing operation ID does not repeat migrations | R1 |
| MIG-06 | Restore recreates DB, filestore and previous release consistently | R1 |
| MIG-07 | Destructive fixture uninstall proves the real deletion semantics | R0/R1 |
| MIG-08 | Old workers/jobs do not serve incompatible new schema | R1 |
| MIG-09 | Restored queues remain fenced until externally completed effects are reconciled | R1 |
| API-01 | Gateway exposes only declared methods and validates schemas | R1 |
| API-02 | Idempotency repeats return the same outcome; changed input conflicts | R1 |
| API-03 | Deadline/cancellation errors do not falsely imply rollback | R1 |
| API-04 | Private ORM objects and stack traces do not cross public boundary | R1 |
| API-05 | Concurrent same-key mutations and a crash before response do not duplicate the reference database effect | R1 |
| API-06 | Consumers use named bindings to call v1 and v2 concurrently; missing/mismatched bindings never select latest | R1 |
| API-07 | Forged browser plugin attribution and supported provider call chains cannot acquire broader actor/token/grant authority | R1 |
| EVT-01 | Rolled-back writes produce no externally delivered success event | R1 |
| EVT-02 | Duplicate delivery does not duplicate a deduplicated consumer effect | R1 |
| EVT-03 | Unauthorized subscription or cross-workspace payload access fails | R1 |
| JOB-01 | Reference idempotent DB job survives lease reclaim without duplicate effect; obsolete claims cannot commit | R1 |
| JOB-02 | Revoked/suspended actor/plugin is checked before dispatch | R1 |
| JOB-03 | Non-idempotent uncertain outcomes are reported for reconciliation | R1 |
| UI-01 | Standard CRUD plugin uses the shared shell and components | R1 |
| UI-02 | Custom non-Owl page works without a new core patch | R1 |
| UI-03 | Direct links, refresh and back/forward work | R1 |
| UI-04 | Unauthorized/disabled pages and service calls fail even if URL is known | R1 |
| UI-05 | Repeated mount/dispose does not accumulate listeners or stale updates | R1 |
| UI-06 | Failed plugin page offers recovery and does not trap the user | R1 |
| UI-07 | Native release mismatch triggers controlled reload | R1 |
| UI-08 | Generic SDK does not require company/partner/session internals | R1 |
| UI-09 | Standard shell passes keyboard, contrast, zoom and RTL checks | R1 |
| UI-10 | Unsaved-work and expired-session flows preserve a safe recovery path | R1 |
| SVC-01 | Reference worker runs without Odoo import or database credentials | R1 |
| SVC-02 | Worker timeout/crash leaves host healthy and feature degraded | R1 |
| SVC-03 | Scoped token cannot change workspace/site by altering payload | R1 |
| SVC-04 | Metadata register/suspend/unregister does not create a native addon, launch/stop a runtime or erase remote data | R1 |
| SVC-05 | Operator-approved endpoint/image generation and audience/scoped credentials are verified; artifact metadata cannot override them | R1 |
| SEC-01 | Plugin metadata cannot execute script in manager UI | R1 |
| SEC-02 | CSRF/CORS/session/proxy/host defaults match the threat model | R1 |
| SEC-03 | No secrets in artifacts, logs, lockfiles or browser bundles | R1 |
| SEC-04 | Production profile disables database manager/listing and dev endpoints | R1 |
| SEC-05 | Native trust warning accurately describes full process authority | R1 review |
| SEC-06 | A fabricated app-queue approval cannot authorize privileged executor actions | R1 |
| SEC-07 | Exact-hash approvals expire/revoke correctly; stale targets/policy/authority and cross-operation replay are rejected | R1 |
| SEC-08 | Application OS/container identity cannot write/read privileged approval/operator/secret stores beyond the redacted status channel | R1 |
| OPS-01 | Operator can inspect journal when main app cannot boot | R1 |
| OPS-02 | Documented restore works in a clean disposable environment | R1 |
| OPS-03 | Build/source/license provenance is preserved | R1 |
| ISO-01 | Hostile service cannot access host mounts, DB credentials or privileged sockets | R2 |
| ISO-02 | Resource and network controls behave under abuse | R2 |
| ISO-03 | Frontend origin/source/nonce/replay/stale-frame tests pass | R2 |
| ISO-04 | Host cookies and DOM are unavailable to sandboxed frontend | R2 |
| ISO-05 | Revocation and teardown invalidate runtime/bridge authority | R2 |

For tests involving crashes or destructive data operations, use targets created by the test harness with a recognizable disposable identifier. Never run them against an existing developer or user database by inference.

## 23.3 Test evidence

For every release gate, record:

- Source/release commit.
- Environment/tool versions.
- Commands run.
- Test IDs and pass/fail/skip status.
- Test data sizes.
- Logs and diagnostic artifacts.
- Screenshots for significant UI states.
- Known limitations and unresolved failures.

A skipped test is not a pass. If a tool is unavailable, implement unaffected work and report the blocked evidence. Do not claim end-to-end completion from unit tests alone.

# 24 Performance reliability and operability

## 24.1 Baseline and targets

Measure before optimizing. Use a recorded reference environment, provisionally 4 CPU cores and 8 GiB available to the app/database stack, with exact CPU/storage/container limits reported. If the machine cannot match it, record the actual environment rather than inventing comparability.

Proposed R1 quality targets, to validate and adjust only with evidence:

- Standard note list/detail operations: p95 under 500 ms after warmup with 10,000 notes and 20 concurrent requests on the recorded reference setup.
- Shell usable after login: under 3 seconds on local/LAN test conditions with production assets and warm server.
- Pagination/filtering must remain server-side and avoid unbounded object/record loading.
- No unbounded memory growth during 100 repeated custom page mount/dispose cycles.
- No material regression in relevant upstream paths without an explained tradeoff; compare against R0 baseline.
- Deployment and job operations provide visible progress/heartbeat and a bounded failure-detection time.
- Authorization revocation meets the declared bound.

These are proposed engineering targets, not observed benchmark results or promises for arbitrary hardware, datasets or plugins. R0 may refine them in an ADR with actual measurements.

## 24.2 Metrics and logs

Provide structured logs with request, operation, plugin, site/workspace and trace identifiers where appropriate. Redact sensitive fields.

Expose metrics or structured diagnostic equivalents for:

- Request latency/error rate.
- Registry readiness and release ID.
- Plugin health.
- Job queue depth, attempts and age.
- Outbox delivery failures and lag.
- Deployment phase/duration.
- Database connection saturation.
- Worker CPU/memory.
- UI mount failures and client generation mismatch.

Do not log entire user document bodies merely to simplify debugging.

## 24.3 Health and readiness

Liveness means the process is alive. Readiness means the expected release, database and registry are ready to serve traffic. A process responding to a basic ping must not be marked ready while migrations failed.

Plugin health may be degraded without making the whole platform unready when the plugin is optional. Required services must affect dependent features predictably.

Maintenance, recovery-required and incompatible-release states must reject normal mutations with useful errors.

## 24.4 Operational documentation

Provide runbooks for:

- Fresh deployment.
- Plugin install and permission approval.
- Schema upgrade.
- Failed startup.
- Failed migration.
- Worker outage.
- Expired/revoked credentials.
- Backup and restoration.
- Compromised native plugin.
- Artifact/catalog trust failure.
- Upstream patch/security update.
- Data export and destructive removal.

# 25 Implementation work plan and phase gates

Do not build all subsystems in isolation and integrate at the end. Each phase must leave a working vertical slice.

## 25.1 Execution order and gate map

The single critical path is `A/G0 -> A1/G1 -> B/G2 -> C/G3 -> D/G4 -> E/G5 -> F/G6 -> G/G7`. Phase H is R2 and excluded from the R0/R1 goal. Passing a gate permits the next phase; it does not imply later release acceptance. Do not reorder substantial feature work ahead of G1/G2. Small prerequisite fixtures needed by a gate are allowed and must have bounded scope and an owning work item.

| Phase / gate | Reviewable output | Required exit evidence | Initial state |
| --- | --- | --- | --- |
| A / G0 | Pinned, bootable baseline and disposable lifecycle fixture | Section 5.3, BOOT-01..04 and baseline ORM/install/upgrade/uninstall/restore evidence | not_started |
| A1 / G1 | Workspace/auth and custom UI feasibility proofs | FEAS-01..04; section 5.4 | not_started |
| B / G2 | Minimal contract skeleton and frozen contract inventory | FREEZE-01..04; section 5.5 | not_started |
| C / G3 | Useful Notes application in neutral shell | Working standard CRUD and asymmetric workspace roles; relevant ID/API/UI/SEC cases | not_started |
| D / G4 | Native extension and custom Canvas using frozen contracts | ORM-01..04, API-06, UI-02..06/08/10 and composition walkthrough | not_started |
| E / G5 | Packaged distribution and recoverable lifecycle through independently approved executor | PKG, DEP, VER, LIFE, MIG, applicable BOOT/TEN/SEC/OPS cases and failed-upgrade/restore evidence | not_started |
| F / G6 | Durable jobs/events and operator-managed external worker | EVT, JOB, SVC, applicable API/ID cases; scoped tokens, outage, duplicate and revocation evidence | not_started |
| G / G7 | Qualified R1 release, documentation and handoff | Every R0/R1 requirement in section 23 plus sections 24, 27 and 28; clean reinstall and operator walkthrough | not_started |
| H / later R2 gate | Isolated execution only under a later authorized scope | ISO requirements and separate threat-model review | excluded_R2 |

These are initial planning states, not a live progress dashboard. Once implementation is authorized, `docs/implementation-status.md` is the sole current-state record. Do not edit this specification to portray progress. An acceptance requirement exercised early must still be current and passing at G7. Every acceptance ID receives one primary owning phase in that record at initialization; shared/regression coverage may link to several phases. Phase categories above guide ownership, not exclusions. Unmapped requirements block G7.

## 25.2 Durable state and resumption protocol

Create progress files only when implementation is authorized. Keep one concise authoritative status file rather than competing chat/task checklists. It links to detailed evidence, decisions and history; it does not copy full logs. Preserve the exact active gate and next executable action before any handoff, interruption, context compaction or end of a work session, and update it after each meaningful work item or test result.

`docs/implementation-status.md` must contain:

- Goal scope and spec version/digest; initial state `not_started`; R2/R3 explicitly excluded.
- Repository path, branch/HEAD, working-tree changes, upstream/runtime lock digests and last-updated UTC time.
- Current phase/gate; latest passed gate and evidence link; active work item; next executable action, command/check and expected observable outcome.
- Gate ledger with state, prerequisites, artifact/evidence links, source/contract digests, blocker and revalidation conditions. Gate states: `not_started`, `in_progress`, `blocked`, `failed`, `passed`, `invalidated`; R2 is `excluded_R2`.
- Work-item table with stable ID (for example `C-03`), concrete deliverable, dependencies, owner, phase, acceptance IDs, status, changed paths and next verification. Status distinguishes `not_started`, `in_progress`, `implemented_unverified`, `passed`, `failed`, `blocked` and `deferred`. Code existing is not a passed work item.
- Acceptance ledger with every section 23 ID, primary phase, exact test/manual procedure, latest result (`not_run`, `passed`, `failed`, `blocked`, `invalidated` or permitted stage exclusion), evidence link and source/environment/contract identity. R1 requirements cannot be deferred to R2 by relabeling.
- Blocker register: ID, affected requirements, failure signature, attempts/evidence, smallest missing input or environment change, safe independent next work and explicit unblock condition.
- Last three material outcomes and links to the append-only attempt history; scope deviations and approved ADR references.
- Resume capsule: what is working, what failed, current process/container/test target IDs, any uncertain mutation/recovery state, next action and exact condition for advancing the gate. Never include secrets.

Use `docs/verification.md` as an evidence index and `docs/evidence/<gate>/<run-id>/` for immutable command outputs, browser captures and reports. Use `docs/work-log.md` for short append-only attempt records: work-item ID, hypothesis, action/command, environment and source identity, observed result, new information and next decision. ADRs describe durable design decisions, not every debugging attempt. Future goal/task tooling may link to this record, but cannot replace it or mark release gates passed without evidence.

On each resumption:

1. Read this navigation section, section 25, the status file and the active work item's linked ADR/evidence. Read the complete spec on first implementation and relevant changed sections after spec updates; do not repeatedly reread unrelated sections as a substitute for work.
2. Inspect repository instructions, branch/HEAD, working tree and relevant lock/contract digests. Reconcile differences with the saved record before acting. Do not assume a previous chat's process is still alive, its files unchanged or its tests still current.
3. If a deployment/test mutation was interrupted or its outcome is uncertain, inspect/reconcile its operation journal before retrying. Do not recreate the project, reset data or rerun migration blindly.
4. Select the first unpassed gate on the critical path. Continue the saved active work item if still valid; otherwise record why it changed and select a ready prerequisite. Do not restart completed phases.
5. Execute the recorded next action, or document the specific new evidence that requires changing it. Update the status/attempt records before moving on. Continue authorized unblocked work without asking the user to approve each checkpoint.

## 25.3 Evidence, contract change and completion discipline

A gate passes only after its concrete artifacts exist and required checks produce passing observations. At each gate, record source commit plus dirty-tree digest if applicable, locks, contract versions/digests, test environment, acceptance results and known limitations. A documentation placeholder, green mock, successful build command, queued operation or implementation claim is not gate evidence.

At G2, freeze contract inventory v1; do not freeze application implementation. Later internal refactoring that preserves the contract may continue normally. A contract change requires an ADR stating trigger, changed semantics, affected consumers and compatibility/migration effects; update the appropriate schema/protocol version and golden fixtures, then update the freeze inventory. No silent drift between manifest, SDK, gateway and executor.

Mark affected acceptance results/gates `invalidated` when their source boundary, contract, dependency lock or environment assumptions change. Record the dependency impact and rerun the smallest sufficient affected checks; do not erase useful historical evidence or rerun the entire suite after every unrelated edit. An invalidated earlier gate blocks dependent qualification until revalidated. New public majors or trust/tenancy changes still obey sections 6 and 26.

Evidence source digests cover the runtime code, schemas, build/deployment configuration and locks relevant to the check. Exclude status/work-log updates and generated evidence outputs from that code identity so recording progress does not invalidate itself. A documentation edit invalidates a check only when it changes the requirement or procedure that check establishes; unrelated prose edits do not force a full rerun.

After a work item passes, choose the next ready item at the active gate. Do not keep polishing already-passing behavior unless new evidence reveals a defect or an unmet requirement. Record optional improvements in a deferred list tied to a requirement or explicit future scope; do not implement them just because they are interesting. G7 requires the full required acceptance ledger, fresh-install/restore evidence and final deliverables, not merely an empty task list or elapsed effort. Goal completion is justified only by G7 and section 28; reports must distinguish progress from completion.

## 25.4 Loop prevention, blockers and scope control

Keep one primary work item in progress. Small prerequisite tasks are allowed, but each must identify the parent requirement, why it blocks the gate, a concrete output and return condition. Before adding a new library, subsystem, generic abstraction or substantial refactor, state which active requirement needs it and why the existing path is insufficient. If there is no required acceptance/gate connection, defer it. R2 containment, marketplace commerce, additional frontend frameworks and cosmetic redesign are not escape routes from a failing R1 gate.

Every failed attempt must record a hypothesis and what the result taught. An attempt with the same command/code/environment and no new information is a retry, not progress. After two unsuccessful attempts at the same failure, review the relevant source, logs and minimal reproduction before another edit; write the next distinct hypothesis. After three consecutive attempts with the same failure signature and no new evidence, stop that approach, record the blocker and choose a discriminating experiment, a documented alternative within scope, or a concrete options memo. Do not repeat install/rebuild/reset cycles merely hoping for a different result. An explicitly bounded retry for a diagnosed transient failure is allowed and records the reason.

Review direction after each completed work item or 45 minutes of sustained work on one unresolved issue, whichever comes first. This is a checkpoint to update the status, compare actual progress to the gate and select a next experiment; it is not permission to abandon a difficult requirement or stop a healthy long-running test/migration. Use elapsed-time evidence where available. Give concise user updates about findings, blockers and next verification; do not fill the chat with unchanged status or claims of progress based solely on repeated planning.

When blocked, stop dependent mutation work, preserve evidence and identify the smallest decision/tool/environment change that would unblock it. Continue only bounded independent work already permitted by passed gates; do not mark the blocked gate passed or drift into later features whose contracts depend on it. If no meaningful authorized work remains, report the blocker and options candidly instead of looping. Keep any goal-tool status consistent with its actual host rules; the local blocker register does not override tool permissions or authorize new scope.

## 25.5 Detailed phase work

### Phase A Baseline (G0)

Tasks:

- Inspect local repository instructions and preserve unrelated changes.
- Create an isolated branch/repository if needed.
- Pin upstream and runtime.
- Build the minimal verified distribution.
- Run R0 lifecycle fixtures.
- Record actual dependencies and baseline metrics.

Exit: R0 evidence exists and the untouched/curated substrate works.

If blocked: diagnose the specific dependency/tooling issue. Do not replace the architecture silently.

### Phase A1 Early feasibility (G1)

Tasks:

- Run FEAS-01..04 using the minimal model, server adapters and browser host fixtures in section 5.4.
- Verify asymmetric roles, cross-worker cache/revocation, direct native transports, plain-JS mounting and actor-preserving dispatch before expanding the product.
- Inventory required substrate patches and retain/reuse only justified proof code.

Exit: G1 evidence passes. A fundamental incompatibility produces a concrete foundation assessment, not a workaround hidden by UI or test changes.

### Phase B Platform contract skeleton and freeze (G2)

Tasks:

- Implement manifest/schema validation without plugin import.
- Introduce generic principal/workspace/membership adapters.
- Add platform registry and installation metadata.
- Publish service/permission/contribution schemas.
- Establish native packaging-to-addon mapping.
- Create the first CLI doctor/validate commands.
- Complete the seven-row contract inventory and compatibility fixtures in section 5.5, including approval serialization and external-service registration examples without building the full later executor/runtime.
- Reconcile schema/types/examples with G1 behavior and record `docs/contracts/freeze-v1.md`.

Exit: FREEZE-01..04 pass, G1 evidence remains current, schemas and authorization boundaries are tested, and generic contracts do not require ERP identifiers. Substantial R1 feature development starts only after this checkpoint.

### Phase C First usable application (G3)

Tasks:

- Build neutral shell through existing frontend seams.
- Implement standard Notes plugin and its service.
- Add workspace switching and role tests.
- Add core UI primitives and locale/theme support.
- Add relevant contract/browser tests.

Exit: one useful data-driven application works without core-specific hacks.

### Phase D Composition and custom UI (G4)

Tasks:

- Add Notes Labels native extension.
- Add provider-owned UI slot/action contract.
- Add Canvas through the framework-neutral mount API.
- Validate deep links, disposal, version conflicts and optional integrations.

Exit: native composition and arbitrary custom UI are demonstrated with no new core patch per example.

### Phase E Distribution and recoverable lifecycle (G5)

Tasks:

- Build immutable artifacts and curated catalog.
- Add dependency solver, lockfile and plan UI/CLI.
- Add executor, locks, journal, maintenance and backup flow.
- Implement UI preparation, independent local exact-hash approval and observable CLI apply; test store permissions, expiry/revocation and operation binding.
- Implement feature suspension and destructive uninstall safeguards.
- Run crash/failure/restore scenarios.
- Bind backend and frontend release generations.

Exit: artifacts install/upgrade/recover through one consistent control path.

### Phase F Jobs events and service boundary (G6)

Tasks:

- Implement minimal durable job and outbox adapters.
- Add scoped service identities and gateway.
- Build deterministic external worker example.
- Build its metadata-only artifact and independently reviewed pinned Compose runtime; verify endpoint registration never launches code or fabricates a native addon.
- Exercise timeouts, duplicate delivery, revocation and degraded UI.

Exit: external execution is proven without pretending it shares native transactions or permissions.

### Phase G Qualification (G7)

Tasks:

- Fresh-install rehearsal.
- Full required acceptance matrix.
- Accessibility and RTL walkthrough.
- Security/dependency/license checks.
- Performance comparison.
- Runbook verification and final documentation.
- Produce release artifact, lockfile and evidence bundle.

Exit: R1 definition of done is satisfied. Future isolation work is clearly separate.

### Phase H Later isolation (outside R1)

Only after R1 or a changed user priority:

- Select a concrete containment model.
- Implement R2 frontend and backend isolation.
- Perform threat-model and abuse testing.
- Upgrade marketplace trust/publisher workflows.
- Reassess multi-tenant hosting and desktop needs independently.

Do not enable untrusted packages merely because the contracts for this phase exist.

# 26 Architecture decisions and change control

## 26.1 Required ADRs

Create concise architecture decision records for:

1. Upstream baseline and patch policy.
2. Minimal runtime/distribution inventory.
3. Native versus external plugin boundary.
4. Plugin/package/version schema.
5. Dependency resolver and lock strategy.
6. Site/workspace/company distinction.
7. Authorization implementation and rule composition.
8. Frontend shell adaptation and custom-page host.
9. Data ownership and native extension compatibility.
10. Deployment executor/journal/recovery model.
11. Job/outbox implementation.
12. Trust/signature or digest-approval policy.
13. Public API compatibility policy.
14. Any deviation from this specification.

Each ADR states context, choice, alternatives, consequences, test evidence and revisit conditions. Avoid long retrospective essays that do not guide implementation.

## 26.2 Allowed local decisions

The agent may choose:

- Test libraries compatible with the retained stack.
- Minor directory names.
- A suitable resolver library.
- Details of the initial local journal store.
- Build tools and component wrappers.
- Internal helper abstractions.

It must document choices that affect public contracts or operator behavior.

## 26.3 Decisions requiring user direction

Stop and request direction before:

- Replacing Odoo with another framework.
- Switching to another major Odoo version.
- Rewriting ORM/auth/frontend wholesale.
- Promising or enabling untrusted third-party execution.
- Changing the agreed license/distribution posture.
- Making desktop/offline-first/multi-tenant SaaS the primary target.
- Publishing a hosted repository, catalog or package.
- Deploying to production.
- Using paid external services.
- Running destructive operations on non-disposable data.
- Taking new account/credential authority outside configured task-relevant access.

Ordinary reversible implementation choices should not trigger a question every few minutes.

## 26.4 Fork exit criteria

Reconsider the foundation if tests show that:

- Every new plugin type needs invasive registry/loader patches.
- Generic public identity cannot be separated without continuous unrelated core changes.
- Custom UI hosting cannot be implemented through contained adapters.
- The intended trust/tenancy model fundamentally conflicts with native runtime assumptions.
- Upstream patch maintenance outweighs retained value.
- Core framework removals are required before any useful vertical slice can work.

A failure must be concrete: source references, prototype behavior, alternative design and estimated migration surface. Do not abandon the fork on stylistic dislike alone, and do not keep it solely because earlier work was invested.

# 27 Licensing branding and upstream independence

Use Odoo Community source and permitted dependencies only. Preserve applicable copyright, license and third-party notices. Odoo's root license identifies LGPLv3 and notes bundled components may have other licenses.

The user-facing platform can have neutral branding, its own documentation and governance, and independent hosting. Do not remove required attribution or imply that inherited code was independently authored.

Do not import Enterprise-only code, proprietary marketplace modules, commercial assets or trademarks under an assumption that all Odoo-related material shares the Community license.

Record licenses per plugin/dependency. Code modification, distribution, linking and service operation can have different obligations; obtain qualified legal review before commercial distribution decisions that depend on those distinctions. This spec does not choose a proprietary relicensing strategy.

Identify Odoo-hosted URLs/integrations encountered in the retained runtime:

- Support/buy links.
- App-store/catalog endpoints.
- Optional IAP or external-service integrations.
- Branding assets and product names.
- Update/telemetry behavior if present.

Classify each as technical requirement, optional integration, user-facing link or attribution. Replace/disable optional product ties deliberately without breaking unrelated functionality. Do not assume complete network independence until tested with outbound access restricted.

The target runtime must boot and run reference applications without contacting Odoo-hosted services. Build-time downloads and optional integrations are separate, explicitly documented network uses.

# 28 Final deliverables and definition of done

Deliver:

1. Working source on a clearly identified local branch.
2. Pinned upstream source and patch ledger.
3. Reproducible local environment and release build.
4. Native plugin and custom UI SDK.
5. Manifest/package schema and dependency planner.
6. Curated catalog/upload/install workflow.
7. Safe lifecycle terminology and recoverable executor.
8. Generic workspace/identity authorization.
9. Reference Notes, Notes Labels, Canvas and external service.
10. Test suite mapped to acceptance IDs.
11. Fresh-install and restore evidence.
12. Operator and developer documentation.
13. Known limitations and security boundary statement.
14. Release/lock/artifact inventory.
15. A concise final handoff listing commands, URLs, credentials setup, branch, test results and remaining risks.

R1 is done only when a new developer can use the documented path to start the platform, install the packaged examples, extend a plugin, host custom UI, validate permissions, and recover a failed fixture upgrade. The independently managed reference worker is started and registered through its documented separate workflow. G7 must pass with all earlier gates current, the complete acceptance ledger and reproducible evidence linked from the status record.

The handoff includes `docs/implementation-status.md`, the work/evidence indexes, G1 feasibility evidence and `docs/contracts/freeze-v1.md`. These must make current phase, passed/failed/unexecuted requirements, remaining blockers and next executable action discoverable without reading the chat history.

A scaffold, mock UI, large untested code generation, or a source tree that only boots on the author's already configured machine is not completion.

# 29 Instructions for the implementing agent

Read this specification in full before changing the project. Treat it as the implementation contract and preserve its trust boundaries.

These implementation instructions activate only when the user authorizes implementation. A request to review or edit this specification does not activate them. At the first authorized start, initialize section 25.2 with all work/gates unstarted; on later continuations resume from that durable record. Do not recreate progress files or restart planning on every chat/goal continuation.

Start by inspecting the local environment and repository instructions. Do not assume the audit checkout from the earlier conversation exists on this machine. Verify tools and configured credentials without printing secrets.

If an existing repository is provided, preserve unrelated changes and create an appropriate branch. If not, create a clearly named local project directory without overwriting existing files. Do not create a hosted fork, push changes, publish packages or deploy services publicly without explicit authorization.

Implement R0 and R1 through the section 25 critical path, including A1/G1 feasibility and B/G2 contract freeze before substantial R1 features. Maintain:

- `docs/implementation-status.md`: the authoritative gate/work/acceptance/blocker ledgers and resume capsule defined in section 25.2.
- `docs/work-log.md`: bounded attempt history, hypotheses, observed results and next decisions.
- `docs/contracts/freeze-v1.md`: versioned public-contract inventory and compatibility fixtures.
- `docs/architecture-decisions/`: meaningful choices.
- `docs/upstream-patches.md`: every substrate modification.
- `docs/verification.md` and `docs/evidence/`: evidence index plus actual commands/results, source/environment identity and significant browser states.

Keep the task checklist in the status file; external task/goal lists link to it rather than inventing competing completion states. Initialize new repository paths as unavailable until created instead of guessing a branch/commit. Do not create these implementation artifacts during specification-only editing.

Use local containers/virtual environments and disposable test data. Do not modify unrelated global installations or existing databases. Installation and sandbox permission requests must still use the host's approval mechanisms; this document does not override them.

Use parallel workers only when authorized by the user or applicable host instructions. If used, give them bounded, non-overlapping ownership and integrate against the frozen public contracts and one status ledger. The main agent remains responsible for end-to-end verification.

After each meaningful work item, record observed results and the next action. At each phase/gate:

1. Run relevant tests.
2. Inspect the real UI where applicable.
3. Update evidence/status, reconcile contract digests and mark affected prior evidence invalidated when needed.
4. Commit a coherent local checkpoint if the user has authorized repository work.
5. Advance only when the gate's required observations pass; otherwise follow section 25.4 and continue bounded independent work.

Do not stop after producing another plan unless a real blocker or a required user decision exists. G2's contract freeze is a checkpoint, not the endpoint of the implementation goal. Do not conceal a failing gate by changing tests to assert current broken behavior. Do not repeatedly revisit passing work, retry an unchanged failure without a new hypothesis, or broaden scope without an active requirement; apply section 25.4.

Never equate tool exit success with product correctness. Verify the observable result. Report unexecuted tests as unexecuted.

When blocked, state the exact blocker, affected scope, safe work completed, options and the smallest user decision needed. Continue unaffected work where possible.

At final handoff, include:

- What is implemented and what is not.
- Exact branch/commit and project path.
- Reproducible startup and test commands.
- How to build/install a sample plugin.
- How to view the standard and custom UIs.
- How to simulate and recover a failed fixture upgrade.
- Required acceptance results and honest gaps.
- Gate ledger, frozen contract version/digests, evidence index and the next-action resume capsule.
- Security/licensing caveats relevant to use.
- The next recommended milestone.

# 30 Source reference index

The following links identify the audited upstream baseline. They are implementation evidence and investigation starting points, not proof that the proposed platform is already built.

- [Official source repository](https://github.com/odoo/odoo).
- [Pinned source tree](https://github.com/odoo/odoo/tree/5c7defb49e020fec8b6bb82403a2f54eb79e92e1).
- [Root license](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/LICENSE).
- [Runtime version declarations](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/release.py).
- [Dependency requirements](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/requirements.txt).
- [Bootstrap configuration](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/tools/config.py).
- [Module discovery and import](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/modules/module.py).
- [Dependency graph](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/modules/module_graph.py).
- [Module loading and updates](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/modules/loading.py).
- [Model registry](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/orm/registry.py).
- [Base manifest](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/__manifest__.py).
- [Base model imports](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/models/__init__.py).
- [User identity](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/models/res_users.py).
- [Company identity](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/models/res_company.py).
- [Native lifecycle operations](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/models/ir_module.py).
- [Model metadata and destructive removal](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/models/ir_model.py).
- [Record rule composition](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/addons/base/models/ir_rule.py).
- [Native migration machinery](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/modules/migration.py).
- [Database and filestore backup](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/odoo/service/db.py).
- [Web manifest](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/addons/web/__manifest__.py).
- [Web session initialization](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/addons/web/models/ir_http.py).
- [Replaceable frontend root](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/addons/web/static/src/start.js).
- [Client action host](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/addons/web/static/src/webclient/actions/action_service.js).
- [Frontend service lifecycle](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/addons/web/static/src/env.js).
- [Legacy user context](https://github.com/odoo/odoo/blob/5c7defb49e020fec8b6bb82403a2f54eb79e92e1/addons/web/static/src/core/user.js).

The first implementation should verify these source facts locally and add test evidence. Keep the original audit's limitations visible in baseline documentation: static inspection established coupling, not a measured extraction cost or successful minimal boot.

# 31 Short launch prompt

The user can give the local agent the following instruction together with this file:

> Read modular_platform_spec.md in full and implement R0/R1 under specification v1.1. Initialize the section 25.2 status/work/acceptance ledgers once, then resume from them on every continuation. Follow A/G0 baseline -> A1/G1 feasibility -> B/G2 contract freeze -> C/G3 -> D/G4 -> E/G5 -> F/G6 -> G/G7 qualification. Prove workspace authorization and custom UI hosting early; freeze the specified contracts before substantial feature development. Preserve Odoo Community 19's working ORM/registry and use the selected R1 choices for actor identity, numeric versions, named service bindings, independent local executor approval and operator-managed external services. Build in an isolated local repository/branch with disposable test data. Record each meaningful result, failed hypothesis, blocker and next executable action; apply the loop/scope rules in section 25.4. Do not restart completed phases, drift into R2, claim unexecuted checks passed or stop at another plan. Do not publish, deploy to production, use paid services or destroy non-disposable data without my approval. Treat native plugins as fully trusted code, suspension as distinct from unloading, and schema upgrades as recoverable rather than atomic. Continue authorized unblocked work until G7 and the complete R1 definition of done are satisfied; if blocked, report the concrete evidence and smallest needed decision instead of retrying blindly.

