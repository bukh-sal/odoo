# F-01d: actual different worker image and reviewed recovery

Scope: spec14.6/SVC05 and the shared maintenance/recovery boundary in ADR0038.
This record is in progress. It does not pass SVC05 or G6 yet.

Verified so far:

- Normal HTTP manager suspension, independent import/review/exact approval and
  checkpointed execution: operation `4d742d8a-56cb-42f6-a252-0b561f373b0d`,
  hash `sha256:9ac326ed3f1999bda745dbd082a2d2b19f58d5a96b37fd9107ddb0acc0dbe67f`.
  `suspend-preservation.json` verifies native20/control104, all29 terminal jobs,
  30 Notes, native schema/modules and48files. Only the provider feature/policy and
  authorized job epochs changed; the connector and other eight features remain.
- A separately built compatible release has actual image
  `sha256:5482020e027debc8a7b3d0a413e36417717b60642ea5b38e168aed328af5bbe0`.
  `worker-build.json` proves exactly the old1d RootFS/runtime configuration with
  new release labels. This intentionally isolates image identity, API compatibility
  and approval ordering; it claims no new computation or storage migration.
- Separate operator publication8 revoked endpoint6; worker05 was explicitly
  stopped and retained. New Compose worker06 uses a new public-key-only volume,
  scope/configuration7, the existing immutable public key, internal network, and
  the exact cached repository/digest reference. `runtime-switch.json` records it.
  The first raw-ID launch was correctly refused by the strict Config.Image guard;
  only that unused container was archived/removed and recreated with the verified
  RepoDigest and `--pull never`. No production guard was weakened.
- Metadata0.1.2/minimum platform17 was independently curated with the exact new
  image and unchanged service schema/permissions. The previous archive remains.
  `unapproved-image-manager-refusal.json` records a real manager400 before current
  approval. `runtime-new-publication.json` records separate publication9/endpoint7;
  `runtime-refusals.json` records actual old-image/third-image and default
  maintenance mismatch refusals. All host data remained exact.
- Normal HTTP manager upgrade, independently reconstructed/reviewed/approved:
  operation `5edcfc97-6477-48a4-ad2b-ba36252834fc`, hash
  `sha256:612c70223b6e9b11c2793d177f46ec1e1c6f2f725a917ab5727653ec0b3922ee`.
  `reviewed-transition-native.json` proves the installed native database checker
  admitted its private stored-operation transition while all scopes were
  suspended, with29jobs and all other tracked data unchanged.
- `upgrade-fault.json` records actual metadata0.1.2/new-image commit (child exit0),
  followed by an injected host-side exception before readiness. The operation
  remained recovery_required, edge closed, with old29job outcomes and other data
  exact under the explicit manifest/feature timestamp/policy footprint. The new
  worker and publication9 were unchanged. This is not another process-kill test.
- Separately reviewed fresh-target restore: `closed-preservation.json` verifies
  fresh native22/control107 paused, checkpoint metadata0.1.1 and suspended feature
  restored, all29outcomes/30Notes/native/auth/history/48files retained under explicit
  security/queue epoch changes. Actual new worker06/image548202/publicconfig7 and
  publication9 were not rolled back. Traffic remained closed for separate resume.
- `source-checks.json` records117source tests plus unchanged97file/eight-row
  contract freeze. Synthetic fixtures follow the reference artifact's new
  minimum17 and use a newer synthetic package for upgrade cases. Source-only
  active/partial-scope negatives are distinguished from actual runtime tests.

- `stale-resume-refusal.json` records separate publication10/endpoint8 revocation
  after the closed restore and an actual unexpired old resume review rejection.
  A distinct fresh review resumed native22/control108 with the current revocation
  retained. `resumed-http.json` verifies original-user native A/B/C views, saved
  Note, degraded/suspended manager state, old release20 gateway409, retired
  original upgrade exit2, and exact29outcomes/other data/current physical worker.
  This is host availability with an unavailable provider, not remote enablement.
- `retirement.json` records33exact terminal containers removed, including16
  receipt-bound observations and two superseded hosts, after private diagnostic
  archive. The earlier unused raw-ID container was also removed. The current
  application/database/edge/new worker, stopped old worker pending final image
  qualification, and real checkpoint images/volumes remain. No global prune.

Remaining: separately update worker public configuration7->9 and approve the
new current endpoint, then a NEW normal metadata0.1.2 upgrade and enable with an
ordinary original-user remote job. The original failed plan remains revoked.
Do not restore old publication9 or replay the failed upgrade. Browser rendering
remains deferred by user request.
No arbitrary external-effect rollback, generic reconciliation, new UI product,
remote process control by the installer or G6 completion is claimed.

The initial revoke preflight safely stopped on an incorrect assumption that the
publication held only one entry. Inspection found the canonical enabled entry and
one historical revoked entry. The corrected harness selects the exact canonical
scope and preserves that history; no authority mutation occurred before the fix.
