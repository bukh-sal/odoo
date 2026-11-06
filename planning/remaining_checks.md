# Remaining checks after local R1 and the shared foundation rehearsal

Local R1 passed G0–G7 and all 99 required acceptance checks. The shared foundation rehearsal passed all four checkpoints. These results apply to their recorded release and test profiles. The rows below track deferred checks and conditions for future releases. [R1 closure](../docs/r1-release-checklist.md) · [Shared foundation evidence](../docs/evidence/post-r1/shared-foundation/lifecycle.json)

The current execution order is:

1. [x] Fix the known stale-tab failure in stock Odoo. The in-app browser verified that an old save was refused after an approved release change, the notice opened the same record and workspace in a new tab, the original input remained visible, and the new tab saved successfully.
2. [x] Qualify Notes revision checks through the stock form. Notes 0.2.9 uses the revision the editor loaded. A current save advanced revision 1 to 2, a second tab's stale save preserved revision 2, and the viewer's write was denied. The stale edit still shows Odoo's generic error.
3. [x] Qualify the supported stock release profile. The exact kit passed draft recovery, installation, security, accessibility, performance, upgrade and recovery checks. [Stock release gates](stock_webclient_release.md)

Plugin-free upgrades, shared migrations and platform major upgrades depend on a selected deployment shape or a concrete release change. Background execution is deferred at the user's direction. R2 and R3 retain their separate scope.

| Check | When it applies | Acceptance and source |
| --- | --- | --- |
| Platform major upgrade | First breaking platform release | Declare supported source releases and plugin/contract compatibility. Verify fresh install and supported upgrades on populated sites. Confirm data, permissions and plugin behavior survive. Reject unsupported paths before mutation, and demonstrate checkpoint recovery and separate resume after a fault. Spec §§6, 9–12, 19, 23 and [ADR 0060](../docs/architecture-decisions/0060-independent-fork-release-policy.md). |
| Shared foundation update with a real schema or data migration | When a core or shared module change requires one | Upgrade both representative deployments with populated data and differing app sets. Verify the migration's data invariants, then restore one from checkpoint while the peer continues. The core27 rehearsal exercised real module maintenance and recovery. R1 separately qualified plugin migration cases. Spec §§10 and 12.3 and [stress plan](shared_foundation_stress_test.md). |
| Upstream security fix intake | Periodic review and before cutting an affected release | Assess advisories against retained fork code and dependencies. For a selected fix, record provenance, run a targeted regression, and verify the candidate's affected lifecycle and release checks. No fixed review cadence has been selected. Spec §§15.4, 25.3 and 27 and [ADR 0060](../docs/architecture-decisions/0060-independent-fork-release-policy.md). |
| Notes conflict message | If the stock release requires a specific recovery message for revision conflicts | The stock form now enforces revision checks, and retains the editor's input when the server refuses a stale save. A stale edit currently shows a generic Odoo error. [Browser and dataset evidence](../docs/evidence/post-r1/shared-foundation/stock-webclient-follow-up.json). |
| Core upgrade on a site without a registered plugin | If this becomes a supported deployment shape | Qualify planning, exact site approval, checkpoint and recovery with no plugin scopes. Both stress sites used the existing Notes fixture as a real operation target. Spec §10 and [ADR 0059](../docs/architecture-decisions/0059-stock-webclient-foundation-stress.md). |
| Additional Aurora behavior or real-data import | Only if a later Aurora slice includes it | Define and test permissions and data mapping for standalone tasks, reminders, notifications, attachments, accounting references or historical data, as selected. The current proof covers synthetic, list-bound tasks. [Stress plan](shared_foundation_stress_test.md). |
| Application background execution | Before qualifying a workload that depends heavily on background jobs | Follow the sequence below. G6 already qualified the reference jobs, worker failure and recovery for its recorded profiles. |

## Background execution prerequisites

1. Choose one application workflow and define its workload and effect policy. Aurora's task reminder is a concrete candidate because it needs a future run time, current task and recipient checks, and a decision about what to do if a notification may already have been sent. Record the expected workload before setting latency and throughput targets.
2. Give trusted plugins a documented way to enqueue a registered job for immediate or future execution, track status, and cancel eligible work. Define retryable errors and the policy for jobs that can outlive a lease. Verify normal dispatch rechecks the original actor and workspace authority, including after a delay. A scheduled system job needs an explicit scoped service identity.
3. Qualify continuous operation under supervision with restart, graceful drain, queue depth and age, failure visibility and controlled retry or reconciliation. Use the existing PostgreSQL queue and guarded runner as the starting point. Prove that urgent jobs stay responsive during bulk work and use dedicated pools or limits if the workload requires them.
4. Exercise the chosen workflow end to end with concurrent workers, worker death, cancellation or revocation, and deployment recovery. Verify that a stale worker cannot write results, and that an uncertain external effect is surfaced for reconciliation. Measure queue latency and impact on web requests against the targets from step 1.

The runner can poll continuously and the queue already tracks leases, retry state and progress. The reference release exercise used a guarded one-job command. The existing registered-job interface is internal, and the general runner currently records detached computation errors as nonretryable. Per-job scheduling and named worker pools need a supported application-facing design if the chosen workload uses them. [Spec §14.2](modular_platform_spec.md) · [G6 qualification](../docs/evidence/G6/20261102-headless-ui-01/gate-G6.json)

The original specification also has five formal R2 checks excluded from R1. R2 first needs an agreed threat model, confinement design and publisher trust policy. [Spec §§14.4, 18, 23.2 and 25.5](modular_platform_spec.md)

- [ ] **ISO-01** Hostile services cannot reach host mounts, main database credentials or privileged sockets.
- [ ] **ISO-02** Resource and network controls hold under abuse.
- [ ] **ISO-03** Frontend checks reject forged origins or sources, wrong nonces, replayed requests and stale frames.
- [ ] **ISO-04** A sandboxed frontend cannot access host cookies or the host DOM.
- [ ] **ISO-05** Revocation and teardown invalidate runtime and bridge authority.

R3 has no acceptance IDs yet. The original plan defers public publisher and marketplace operations, any requested billing, additional deployment profiles and an optional desktop host to separate product decisions. Multi-tenant hosting is also a separate decision. The platform name and visual redesign are open product choices. [Spec §§1.3, 25.5, 26.3 and 27](modular_platform_spec.md)
