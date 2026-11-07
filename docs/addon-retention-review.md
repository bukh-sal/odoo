# Addon retention review

Assessment7 November2026 against repository checkpoint`7c27441e25f` and the
core46 distribution policy. This is an owned hard fork: useful code is retained
for our platform, not for Odoo compatibility. See ADR0071 and AGENTS.md.
[Full inventory/classification evidence](evidence/post-r1/addon-retention/source-assessment.json).

## What remains now

Counts are manifest-bearing addon directories, excluding `__pycache__`; sizes
are uncompressed file bytes, not Git history, Docker layer or installed DB size.

| Source root | Addons | Approximate size | Meaning |
| --- | --- | --- | --- |
| `addons/` |641|944.4MiB| Broad inherited application/technical addon collection; most is not shipped. |
| `odoo/addons/` |24|109.2MiB| `base` and23 test addons. This root is not24 production framework services. |
| `platform_addons/` |11|0.4MiB| Our framework, apps/examples and the old `mp_feas` feasibility fixture. |

The active source therefore still contains665 inherited addons (about1,053.6MiB).
The qualified image contains only13 inherited and10 owned addons,23total,
selected by `deploy/distribution-r1-foundation.json`. Installed sets are smaller
and differ between deployments. The full source archive still carries the wide
checkout. Excluding modules from the image has not gutted the repository.

Of the652 inherited addons not shipped,629 are in top-level`addons/`;23 are
regression fixtures under`odoo/addons/`. Their combined source size is807.1MiB.
Do not mistake useful tests for unwanted application dependencies.

## Recommended boundaries

| Module/code | Recommendation | Reason and current constraints |
| --- | --- | --- |
| `odoo/` engine and `odoo/addons/base` | Keep and own; simplify deliberately | ORM, registry/module loading, HTTP, access rules, model/view/action metadata, users, attachments and related infrastructure. `base` also bundles partner/company/currency/catalog concerns; these are candidates for extraction, not all kernel requirements. Current users/company models depend on partner records. |
| `addons/web` | Keep as framework UI | Native WebClient, Owl, action/view hosting, list/form/kanban, dialogs, notifications, assets. No replacement UI framework is proposed. |
| `auth_totp`, `auth_passkey`, `auth_password_policy` | Keep security capabilities | Valuable platform authentication. Remove Odoo-specific presentation/dependencies as appropriate; preserve protection and recovery. |
| `bus` | Keep framework capability | Realtime transport/signalling; distinct from durable background execution. |
| `base_setup` | Refactor | Auth/IAP/mail currently depend on it. Keep needed settings primitives, remove inherited app recommendations, upsell and vendor-specific setup behavior. |
| `base_import` | Keep as optional generic capability | Useful CSV/import infrastructure; not a reason to keep business applications. Scope and import authorization still apply. |
| `html_editor` | Keep editor; remove unrelated services | Valuable rich-text UI, but its controller imports IAP and mail helpers outside manifest dependencies and contains Odoo-hosted media/AI endpoints. Split these concerns. |
| `mail` | Split and make optional | Reusable chatter, activities, message history and notification primitives are mixed with Discuss/chat/mail gateway functionality. Maintenance currently depends on mail. Do not force the whole application into every foundation deployment. |
| `web_tour` | Optional onboarding/test infrastructure | Mail currently declares it as a dependency. Extract or remove that runtime dependency where practical; keep useful tour tests. |
| `iap` | Remove after decoupling | Odoo in-app purchase/account/service plumbing does not belong in this platform's foundation. It currently auto-installs when web/base_setup exist; html_editor directly imports `iap_tools`. Deleting the directory alone will break imports. |
| `maintenance` | Keep as optional adopted app/reference | Demonstrates reuse of an existing application on our framework. It is not part of the mandatory kernel or an Odoo compatibility commitment. |
| `mp_core`, `mp_identity`, `mp_shell`, `mp_compat` | Keep useful owned framework behavior; clarify boundaries/names | These supply platform authority/lifecycle/workspace/UI integration. `mp_compat` is currently a tiny owned asset adapter, not support for arbitrary Odoo addons. Consolidate code into the engine/services when that is simpler. |
| `mp_aurora_tasks` | Optional application | Preserve the useful synthetic task slice and independent app permissions. |
| `mp_example_*` and `plugins/*` | Reference examples/tests | Notes, Labels, Canvas, Stats and Background are contract/workload examples. Keep them outside the mandatory foundation. Canvas remains minimal. |
| `mp_feas` | Test fixture/archive | Early feasibility proof, not a shipped product module. |
| The other629 inherited top-level addons | Remove from the active foundation tree after reference audit | Examples include accounting, sales, inventory, manufacturing, POS, website/ecommerce, HR, marketing and their localization/connector families. Retrieve/adapt selected code from recorded Git history when a real app requires it. No need for a second full vendor tree inside the active repository. |
|23 internal test addons | Retain useful regression coverage in test roots | ORM/inheritance/access/HTTP/assets/conversion/uninstall tests remain valuable even though the original production addons are being removed. Update fixtures for fork behavior rather than preserve external compatibility. |

## Concrete coupling found

`addons/html_editor/controllers/main.py` imports
`odoo.addons.iap.tools.iap_tools` and `odoo.addons.mail.tools.link_preview`.
It includes defaults for `media-api.odoo.com` and `olg.api.odoo.com` and an IAP
JSON-RPC call for the latter. Source presence does not prove these endpoints
were contacted in qualification, but the code is an unwanted platform dependency.

`addons/iap/__manifest__.py` has `auto_install=True` and depends on web/base_setup.
`maintenance` depends on `mail`; `mail` depends on base_setup, bus, web_tour and
html_editor. A manifest-only dependency audit is therefore insufficient: include
Python imports, JavaScript imports, asset bundles, XML IDs, model relations,
bootstrap data and auto-install rules.

`tools/build_distribution.py` also retains category metadata to satisfy the
inherited `base/data/ir_module_module.xml` catalog. Rather than preserve a catalog
of removed vendor applications indefinitely, replace that seed with the platform's
actual module/app metadata and qualify fresh bootstrap. Historical pins/notices
remain provenance records, not architectural constraints.

## Proposed logical layout

```text
engine/                  # owned registry/ORM/HTTP/module/security runtime
framework_addons/        # UI/auth/settings/import/realtime/editor; optional services
applications/            # Aurora Tasks, Maintenance and future selected apps
examples/                # Notes/Labels/Canvas/Stats/background reference workloads
tests/addons/            # regression/feasibility fixtures; separate discovery root
packages/                # public SDK/contracts and independent operator tooling
```

This is an ownership proposal, not a command to add another wrapper tree around
the current one. Move code once, update discovery/build/package paths and retire
the old roots. The internal Python package name can initially remain`odoo` to
avoid an unrelated giant rename; that is an implementation choice, not a
compatibility requirement. Change inherited ABI/version/catalog names where our
platform semantics require it, with explicit contract/data migration.

## Smallest useful execution sequence (not started)

1. Freeze a keep/move/remove inventory and audit references from retained code
   and tests. Treat629 business/technical addon exclusions separately from23
   regression fixtures; name any additional module adopted for a concrete app.
2. Decouple rich-text editing, generic messaging and auth/settings from IAP,
   Odoo-hosted routes, Discuss/onboarding and vendor catalog assumptions. Patch
   the owned core directly where that reduces complexity. Keep the stock UI.
3. Remove the unused addon source and obsolete catalog data; move retained
   services/apps/examples/tests into their owned roots. Update Docker allowlists,
   source discovery, artifact materialization, test lookup and provenance.
4. Qualify a new release: clean bootstrap with no optional apps, Aurora-only and
   Maintenance profiles, useful native views, current permissions, jobs, populated
   upgrades, fresh independent recovery and reproducible/portable packaging.

If a removal touches stored models/data, use a supported migration and explicit
data-retention decision rather than deleting addon files under an existing DB.
The sealed core46 kit remains unchanged. Its checks do not automatically qualify
this planned extraction. No pruning, file moves or runtime changes were performed
by this assessment.
