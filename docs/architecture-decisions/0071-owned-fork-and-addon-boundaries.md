# ADR0071. Own the fork and its module boundaries

Accepted from the user's clarification,7 November2026. This extends ADR0060
from release ownership to source architecture and addon retention.

Odoo is the origin of the engine, not an external compatibility target. Do not
promise installation of arbitrary Odoo addons, source/API compatibility with
Odoo, future Odoo major upgrades, or integration with its hosted services or
marketplace. Retained modules become code we own and maintain in this fork.
Security fixes may be adapted from upstream; attribution and provenance remain.

Choose boundaries for this platform. Keep useful ORM/registry/HTTP/security and
UI infrastructure; directly simplify or extract inherited core code where that
is clearer than maintaining another override or compatibility wrapper. Protect
our own supported plugin contracts and populated deployment upgrade/recovery
paths. An inherited dependency is a current refactoring constraint, not a reason
to keep its feature or folder forever.

Separate the engine, framework services, optional applications, reference
examples and regression fixtures. The current `odoo/`, `addons/` and
`platform_addons/` roots describe historical packaging, not permanent ownership.
Internal package/model/ABI names may change with a coherent import/schema/
contract migration. Renaming everything immediately is not a prerequisite;
remove accidental coupling and clarify ownership before cosmetic churn.
In particular, `native_compatibility="odoo-19"` currently identifies an inherited
runtime profile; it is not an Odoo interoperability promise. A future runtime
identifier/manifest revision should name our own platform ABI and migrate its
consumers deliberately.

The [retention review](../addon-retention-review.md) distinguishes source,
shipped addons and installed apps. It recommends removing unused business
addons from the active tree, keeping selected regression fixtures in test roots,
extracting generic messaging/editor services, removing Odoo IAP/cloud/marketplace
coupling, and keeping Maintenance/Aurora outside the mandatory platform kernel.
No mass deletion or runtime changes were performed by this assessment.

The sealed core46 artifact retains its exact qualified contents. A later prune
or restructuring produces a new platform release and affected evidence; it must
not mutate that artifact or relax current executor/schema/authority guards.
