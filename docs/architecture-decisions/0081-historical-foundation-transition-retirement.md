# ADR 0081: historical foundation-transition execution retirement

Date: 2026-11-10. Status: source retirement decision under the owned-core
extraction direction.

## Context

The current SDK and operator CLI contain closed implementation of two historical
transition recipes:

- `owned-addon-extraction-46-47-v1` (`foundation_transition.py`,
  `foundation_native.py`, `tools/review_foundation_transition.py`), and
- `owned-native-tasks-adoption-47-49-v1` (`tasks_adoption.py`,
  `tasks_adoption_native.py`, associated tests and cleanup helper).

These recipes target already-sealed 46/47/49 foundation images. The exact old
source and tests are preserved in the sealed `core47`, `core49-tasks` and
`foundation49` kit `source.zip` files. The kits verify checksums, extract their
exact source and provide the original review/apply tool. Their images and source
hashes are the historical qualification evidence; the current candidate does not
need a duplicate implementation to preserve that history.

Keeping current app-specific closed recipe constants, table/SQL witnesses and
transition branches in the generic SDK makes new SDK/core release surfaces carry
an unsupported historical support promise and application-specific machinery.

## Decision

Retire current SDK/CLI execution support for the closed 46→47 and 47→49
historical recipes:

- the four generic SDK recipe modules and current historical review tool are
  removed;
- closed planning/staging/approval/native-executor branches and parameters are
  removed;
- the current operator fails closed on any historical `foundation_transition`
  field with a clear instruction to use the exact sealed kit source/tooling;
- the exact old sealed kits, images, source archives, checksums and evidence are
  left unchanged and are the preservation route for historical transitions;
- generic native migrations, version/source-inventory checks, current
  approval/checkpoint/recovery/job behavior and ordinary staged core upgrades
  remain intact.

The frozen historical wire schema/examples and the frozen tasks-contract example
test remain historical evidence of the payload shape; they are not a promise that
the current executor runs those recipes. `tests/test_foundation_transition_contracts.py`
is removed from the current test suite and its exact bytes/hash remain in the
sealed legacy kits. Freeze revision 26 records that removal and the remaining
unchanged frozen bytes.

## Consequences

- Historical 46→47/47→49 execution requires the exact old sealed kit source and
  tooling, not the new candidate. No new optional historical operator framework is
  introduced.
- Old prepared/historical staged records are rejected before side effects. They
  are never normalized, rewritten or relabeled.
- Current generic core-upgrade planning, staging, approval, checkpoint, recovery
  and job guarantees remain subject to their existing guards and tests.
- This is a supported-surface retirement under the owned-core extraction
  direction, not a final platform support/ABI/licensing decision and not a new
  backward-compatibility promise.
- Sealed kits, source archives, images, frozen schemas/examples and existing
  historical evidence remain immutable. Private product sources and local
  planning records are not restored publicly.

## Affected qualification

Existing 46/47/49 transition qualification remains historical kit evidence. The
current replacement checks are negative: current CLI/planner/staging/approval/
native-executor paths reject retired declarations and forged historical locks
before side effects, while generic native core upgrade and recovery checks remain.
Current candidate release qualification must be re-run by the normal owner; this
ADR does not claim the historical recipes were freshly executed.

## Reconcile the existing freeze inventory

Revision 26 also resolves two baseline inventory inconsistencies explicitly:

- The private application document `docs/aurora-tasks-contract.md` was removed
  from the public tree in commit `30090ca3d39`. Remove its path and digest from
  the current public freeze inventory; this does not remove another source file
  or restore private product material. Its historical digest is
  `3bd49f92ad024376396a94ca4e3fb08691d69c1825c0a0be4e1f03bf5f0eab60`. The unchanged ADR0074/0076 records retain the historical
  application decisions; the frozen native-site lifecycle contract and generic
  native job authority remain supported. This does not retire the native job
  adapter or authorize weaker actor/resource/dispatch checks.
- Refresh the frozen `tests/test_native_uninstall.py` digest after the accepted
  CR0006 metadata-checkpoint fix and CR0009 reference extraction. The previous
  digest `8a4c4ea9931d456ee76095ad8161038fa46d5636a559674b829c5e403010cdf4` identifies commit `e0aaa627a843`.
  All six original test methods remain; five additional methods cover private
  checkpoint scope, producer/consumer shape, metadata payload flow, the existing
  four-argument publisher protocol and old-reader refusal. The current digest is
  `ac0618a817b67cc7e5140fc78cad435e8bd2618f1d4196a0afbc04613380f356`. Requalification includes those assertions and the actual
  metadata-entry helper ordering tests; this is not a hash-only drift approval.

The new retirement tests and retained task-contract tests qualify the current
source boundary. The canonical host suite and freeze checker must both pass
before acceptance. No changed inventory digest retroactively requalifies an old
kit or image, and no historical evidence is rewritten.
