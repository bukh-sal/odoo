# Modular Platform implementation

## Product direction (user clarification, 7 November 2026)

This is an independently owned hard fork, not an Odoo-compatible distribution.
Do not preserve compatibility with Odoo releases, third-party Odoo addons,
hosted services, marketplace or historical folder boundaries as a design goal.
Retain useful framework behavior and modify/extract the core directly when that
produces a simpler platform than another adapter. Organize by platform engine,
framework services, optional applications, examples and tests, rather than a
permanent upstream-versus-platform split. Preserve attribution/provenance and
our own supported contracts, data migrations, security and recovery guarantees.
Source removal/moves still require dependency/import/asset/data checks and
affected qualification; do not delete useful regression tests for module count.
See `docs/architecture-decisions/0071-owned-fork-and-addon-boundaries.md` and
`docs/addon-retention-review.md`. The user authorized implementing the cleanup/extraction/restructuring and
release requalification under `planning/addon_cleanup.md` on7 November2026.

The user authorized implementing `planning/modular_platform_spec.md` v1.1 through R1, with local Git commits and disposable container tests. No publication, paid services, production deployment or destruction of existing user data is authorized.

Before work, read `docs/implementation-status.md` and the active gate's linked evidence/ADRs. Read the specification in full on first implementation, and relevant sections on resumption. Follow its section 25 sequencing and loop rules. The required path is G0 baseline, G1 feasibility, G2 contract freeze, then G3-G7 R1 vertical slices and qualification. R2/R3 are excluded. Do not restart completed work or mark a gate passed without real evidence.

Keep one active work item. Update the status/checklist, acceptance results, blocker register, work log and next-action resume capsule after meaningful results and before stopping. Give rough progress using the gate weights and actual verified work, separately from acceptance counts. Do not inflate progress for documentation or generated files.

Use the explicit installed Python interpreter or isolated environments; do not change global Python. Use project-owned, clearly named disposable Docker targets. Never reset unknown databases/volumes. Preserve upstream source/license notices and record substrate edits in `docs/upstream-patches.md`.

Native Python and same-origin frontend plugins are trusted. Workspace gates, independent executor approval and scoped technical identities must follow the specification. Do not turn grant metadata into a sandbox claim. Do not spawn sub-agents unless the user or applicable higher-level instructions explicitly authorize delegation.
