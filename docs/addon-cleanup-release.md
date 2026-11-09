# Owned addon extraction release

Qualification is recorded in [the checklist](implementation-status.md),
The local-only AR plan (removed from the public tree) and the kit's
`qualification/foundation-release.json`. The final local kit is
`.local/releases/foundation-r1-core47`. Its inventory/checksums and qualification
receipt identify the sealed snapshot; source-archived progress files are dated
development records. Core46 stays sealed and unchanged. Standard record screens
remain native. No external Odoo package or major-upgrade compatibility is a goal.

Final image is
`sha256:a572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a`, inventory
`sha256:c69c1015d61b93e6ac79114915a3da82d12f6ca1813032b570c24115684135ad`;
local alias`modular-platform:foundation-r1-core47`. A separate no-cache,
network-disabled image reproduced all10runtime inventory comparisons from6,276
recorded inputs. The alias is convenience; operator actions bind immutable IDs.

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
native browser, privacy and exact owned resource retirement. The final evidence
records both final-image forward operations and exact final-image stopped-app
fresh recovery/separate resume. Prototype receipts retain their earlier scopes.

## Verified release scope and starting again

Cold installations pass with13core modules,14Aurora-only and15Maintenance.
Maintenance uses generic mail, with no forced Discuss/gateway/tours. The upgraded
old mail deployment retains those previously bundled capabilities explicitly.
The available policy has24production/example addons; source also keeps25explicit
regression/feasibility fixtures outside production discovery.22inherited regression
fixtures remain; RPC is test-only.628unused production addon trees plus IAP source
were removed. Engine/framework/app/example roots are authoritative.

The isolated kit operator was created offline with hash-locked binary wheels,
imported21reviewed own archives, initialized a fresh realm and independently
installed3reference plugins in6workspace activations. Five backend walkthrough
checks passed. In-app browser verification covered native owner/list/form and
read-only viewer behavior plus the existing one-card Canvas custom page. No UI
source/theme/product expansion was needed. Current host suite:600passes/1existing
Windows skip;9native cases passed. Exact final-image urgent/bulk lanes completed
8bulk jobs once and1reminder once, then drained. Both populated source systems'
workflows, roles, data, attachments and pending/stale jobs survived the common update.

Use [the kit instructions](release-kit.md) to verify checksums, set up a **fresh**
project-local operator, import the selected catalog and initialize a new
loopback-only reference realm. Use the kit's recorded interpreter/source paths;
do not reuse retired test databases or replay their operations. The archived
source includes native lifecycle, recovery and useful regression instructions.
Source refreshes may update evidence/bootstrap documentation only when the exact
selected application input hashes still match; they cannot replace an image.

All recorded AR test containers/volumes/networks are retired. Private logs,
checkpoints, exports and receipts remain under`.local/addon-cleanup` for diagnosis;
they are not in the kit. Retired prototype images and owned transient tags are
listed in the retirement evidence. The selected47image, sealed46image and useful
locked support/dependency images remain; unrelated Docker assets were preserved.
No production deployment or publication occurred. Checksums are corruption
checks, not publisher authentication or executor approval.
