# Consolidated foundation handoff

This local release combines the stock Odoo WebClient, platform/SDK0.1.46
(native core19.0.0.1.46), reference plugins and reviewed background execution in
one available-addon policy. [Current checklist](implementation-status.md#consolidated-foundation-release-current-goal)
and [qualification plan](../planning/foundation_release_consolidation.md) record
the exact outcomes. The kit is `.local/releases/foundation-r1-core46`.
Its `qualification/foundation-release.json`, `images.json`, inventory and
checksums identify the sealed release; source-archived progress records are
dated development evidence.

## Available versus installed

`deploy/distribution-r1-foundation.json` declares23 available addons, including
Aurora Tasks, Maintenance, the platform and five reference packages. Availability
does not install or activate every application. Native list/form/kanban actions,
navigation, dialogs and notifications remain Odoo infrastructure. Canvas remains
an optional minimal custom-page reference. No theme or shell redesign belongs
to this release.

Aurora is the existing synthetic, list-bound task slice based on the reviewed
bedrock-2.2 source, not a complete port or real-data import. Maintenance uses
the retained community addon and its import/runtime dependencies. Native Odoo
app groups and record rules remain separate from platform workspace membership;
installing an app does not grant its administrative groups to all users.

## Qualified paths and recovery

Both independent populated deployments adopt the same final image:
`sha256:72d51d3282c93df591e01cf63c2d0fe66c06633f5d4b569d557da5f3c47d0e82`.

| Deployment | Actual qualification path | Result required by CF |
| --- | --- | --- |
| Aurora Tasks | Recomputed common-policy core30 baseline →46; controlled publication fault →fresh30 restore →separate resume →successful46 retry | Task/list/stage data, app permissions, scoped Notes, queue timing/authority and retained files survive. |
| Maintenance | Same core30 baseline →45 →46, with background work between updates | Equipment/request/workspace data and roles survive the real shared schema introduction and adjacent patch; remains useful during peer recovery. |

The core30 input is a transparently recomposed compatibility baseline using the
recorded old platform sources, current fixed app packages and common policy.
It is not a claim that historical stock-r1 contained this addon set. Exact-policy
and package guards remain in force; adopting a different available-addon policy
on an existing site requires a separately qualified transition. Do not rewrite
module versions or bypass those guards. Future breaking upgrades are platform
major releases, independent of Odoo's major numbering.

The run found and fixed the skipped history/recurrence introduction recovery
gap. [ADR0070](architecture-decisions/0070-empty-shared-schema-recovery.md) allows
only the explicit30-to45/46 pairs with four exact known, empty added tables.
Populated additions, unknown effects/schema changes and unsupported paths still
require reconciliation. The actual final46 fault was recovered while its app
was stopped; the peer served native workflows and completed16 reports once.
Restore verified a new database/filestore while traffic stayed closed, then a
separate reviewed resume opened it. Both the original failed45 operation and
the final46 repetition are retained as evidence.

## Start a new disposable system

Follow [the kit procedure](release-kit.md), using the kit-created interpreter
and source from `operator-setup.json`. Verification and operator setup use
retained Python/binary wheels offline; they do not change global Python.
Reconstruct the private catalog from the kit archives. Never copy another
system's catalog SQLite, approval store, credentials, database, filestore or keys.

For fresh native app bootstrap, append `--native-app maintenance` or
`--native-app mp_aurora_tasks` to the initializer's `initialize` phase. That
explicit choice is checked against the selected image before database creation.
Omit it for the standard platform reference recipe. Use a new workdir, unused
loopback port and private subnets; each phase is once-only. Inspect its phase,
logs and operation journal after any failure before retrying. Existing systems
use independently reviewed lifecycle operations and checkpoints.

The clean consumer rehearsal used Maintenance plus the ordinary reference
install/walkthrough from an isolated kit operator, with no author catalog or
application/control state copied. All test application data is synthetic.

## Background deployment

Web, urgent and bulk lanes are separate pinned processes/containers, sharing the
deployment's database and application release. Workers require the same reviewed
code and current site/release/database/inventory pins. Scope, current actor and
plugin authority remain checked at execution/apply. Long compute does not hold
the originating request transaction. Application code uses the documented job
adapters, rather than treating arbitrary cron code as scoped job authority.

Use [reviewed profiles and capacity advice](background-capacity.md),
[job operations](jobs-and-events.md), and [continuation contracts](background-continuations.md).
Drain before lifecycle maintenance and independently review a current profile
after release/recovery. Old profiles/claims are not a resume permission.
The CF smoke used one urgent and one bulk lane per app deployment; detailed
BG/BX throughput/recurrence limits retain their separate measured profiles.
No autoscaling controller, broker, provider delivery or general workflow engine
was selected by this release.

## Evidence and boundaries

The final image independently reproduces its declared inventory with cache and
RUN network disabled. Its change from core45 is exactly the recovery guard and
two version fields; packages, policy and dependencies are unchanged. The full
host suite reports585 passes/one existing Windows skip across586 tests, and
the106-file major1 public contract freeze passes. Native HTTP, background,
in-app Odoo screens, clean consumer setup, bounded privacy/provenance and owned
Docker retirement have separate receipts in `docs/evidence/post-r1/foundation-release`.

Native Python/same-origin plugins remain trusted; grants are not a hostile-code
sandbox. Checksums are not publisher authentication or executor approval. This
is a local representative-app release qualification, not a production rollout
or a claim that every R1 test was rerun on every app combination. Original R1,
stock and BG/BX evidence retains its recorded source/environment scope.
R2/R3, full Aurora/imports, policy expansion and breaking platform releases remain
separate work. Test sites are disposable and retired after qualification; the
sealed kit and its useful pinned foundation image remain for the next system.
