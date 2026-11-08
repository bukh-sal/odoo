# Owned addon extraction release

Current qualification is in [the checklist](implementation-status.md) and
[AR plan](../planning/addon_cleanup.md). Core46 stays sealed. Core47 prototypes
are evidence at their exact source/image scopes; this document is not a final
release approval. Standard record screens remain native. No external Odoo
package or major-upgrade compatibility is a goal.

The source roots are `engine/`, `framework_addons/`, `applications/`, `examples/`
and explicit `tests/addons/`. Runtime images materialize one installed layout.
The available foundation contains optional mail service, Discuss and incoming
gateway. Clean core/Aurora do not install communication; fresh Maintenance uses
generic mail without full Discuss, gateway or tours. The owned46 transition
preserves already installed capabilities: old mail adopts the two extracted
apps/50actual record identities and retains aliases for our own R1 references.

## Review and apply

Use the qualified isolated operator/environment and its protected private
directory. The supported source is the exact sealed46 image/inventory in
ADR0073, with installed versions matching its independently inspected manifests.
The only recipe is `owned-addon-extraction-46-47-v1`; it cannot run arbitrary SQL,
commands, tables, module removals or package migration hooks. Normal core-upgrade
policy restrictions are unchanged.

1. Select/build the exact47 image. Run `tools/review_foundation_transition.py`
   with `--deployment-config`, `--image-id` and a fresh private `--output`.
   This reads current data and writes a declaration; it approves nothing.
2. Review exact source changes, policy/image/recipe identities, actual installed
   module scope, IAP counts/digests, application table witnesses and ownership
   records. Configured local mail-pipe records refuse this recipe. POP/IMAP are
   supported; historical script settings remain readonly.
3. Privately select the declaration with `plugin stage-image
   --foundation-transition <file>` plus the normal exact image/store/config/
   catalog arguments. The existing stage digest covers the declaration too.
4. `plugin plan-staged` takes a data-only `core_upgrade` nomination. Include all
   actual native plugin scopes as `deploy` targets when present. A genuinely
   plugin-free deployment uses empty plugin targets and binds real site IDs.
5. Register, review and independently approve the exact plan/hash, including
   trust/destructive acknowledgments. Pause/drain existing job lanes. The normal
   executor reobserves data/authority, fences ingress/dispatch and checkpoints
   before any possible mutation. Changed data requires a new review.
6. Apply through the staged native executor. It privately exports raw IAP JSON,
   uses old code's supported IAP module uninstall, adopts identities, updates
   native modules/explicit extracted apps, imports and verifies the immutable
   archive, preserves business rows, then reconciles release/job authority.

The archive is `mp.retirement.archive`: system-only read, no ordinary create,
write or delete. Raw JSON text preserves decimal precision. Payloads/checkpoints
are OS-protected private files; public receipts expose counts/digests only.
Retain them according to the deployment's local checkpoint policy.

## Recovery and evidence

A possible commit or publication failure keeps traffic closed. Never replay the
uncertain apply or reset its database. Use `plugin recover prepare-restore`,
review/approve the exact restore decision, and `restore` to a fresh database from
the independent checkpoint. Preserve the failed database/image for diagnosis.
Current revocations/fences are reconciled before startup. `prepare-resume` and
`resume` require a separate exact review; restoring data alone opens no traffic.
Core46 restoration returns IAP and its original data/owners. A forward attempt
requires a fresh declaration/approval against that actual restored target.

Revision19 prototypebba33da4 proved populated plugin-free migration, closed
publication failure, stopped-app fresh recovery, separate resume, and16useful
Aurora peer jobs. The final forward qualification uses revision20 with Aurora
task/list/stage/membership witnesses and real Maintenance pending/stale job and
filestore witnesses. AR-05 still requires final reproduction, portable consumer,
native browser, privacy and exact owned resource retirement before a release
can be called qualified.
