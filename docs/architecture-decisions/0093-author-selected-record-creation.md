# ADR0093: Author-selected creation with retained native records

Date:15November2026. Status: accepted for local implementation.

The owner wants simple directories, optional small creation surfaces and
informational durable details. A native list's New currently forces a form route;
existing dialog expansion can save. Neither behavior should dictate an app's
workflow.

An action can explicitly choose page/dialog/sheet and a creation-only native form
reference. Default behavior remains available. Native View/FormController/model
and server validation/authority remain the owners. A creation-specific wrapper
adds dirty/uncertain/busy decisions and fullscreen expansion of the same mounted
form. It does not transfer unsaved records through URLs, storage or a purported
model export; the current export lacks unsaved data. Existing detail/Edit routing
and unrelated dialogs are unchanged.

This is an additive native UI author API requiring the successor core, documented
in ui-creation-surfaces-plan.md. It changes no plugin manifest/service DTO, grant,
approval or frozen wire. No generic business orchestration or data migration.
Related multi-step creation is app-owned and declares real partial outcomes;
native ORM create does not acquire idempotency from its presentation. Uncertain
native create is held for inspection rather than blindly repeated. This boundary
is intentional; existing idempotent application services support stronger retry
semantics where the business workflow needs them.

Implementation and installed qualification remain separate evidence. Historical
images, app archives, source attribution and current user data remain intact.
