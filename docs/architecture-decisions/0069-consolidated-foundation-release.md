# ADR0069. One available-addon release, distinct installed application sets

Accepted for CF-01 feasibility, 7 November 2026.

The qualified stock kit, app rehearsal and background profiles currently contain
different available addons. Consolidate their union in a named release policy;
keep explicit bootstrap installation limited to the stock platform. Each target
selects its business addon independently. Reuse stock WebClient, native app
models/actions and the existing separately approved lifecycle/recovery executor.

Core maintenance continues to require identical available addon policy and
packaged artifacts across the transition. Do not weaken this guard to cross
historical profiles. Recompose a transparent core30 compatibility baseline with
the common policy and fixed application packages, and prove boot/observation
before claiming a supported upgrade to the current foundation. Only platform
source and versioned core addons may change in that transition. The baseline
is a qualification input, not a retroactive release claim.

Use existing history/recurrence schema changes to qualify a real shared
migration on populated Aurora Tasks and Maintenance. Restore one deployment
from its independently reviewed checkpoint into a new database/filestore and
require a separate resume decision. Exercise the peer during the outage, not
merely compare an image tag afterwards. Current worker claims/profile generations
must honor the changed release and recovered authority. Keep the manual reviewed
fleet/capacity policy selected by BX-04; no new scaling controller is implied.

Public contracts remain frozen. The public release kit contains reproducible
inputs, never a copied operator control store or application state. Its support
claim is limited to the concrete source/upgrade paths and workloads qualified
by the [CF plan](../../planning/foundation_release_consolidation.md).
