# Current G6 backend audit

This bounded prerequisite to F-01f reconciles earlier JOB/EVT/SVC qualification with the actual native24/dispatch117 installation. It does not pass G6 or start G7.

- `native-guards.json`: all 12 native job guard cases ran on the actual current image and registry. Every test rolls back; all 17 tracked tables and the independent worker/authority match the original snapshot.
- `attempts.json`: the original fixture failed because Bob already has a revoked workspace-C membership. The corrected fixture reuses that exact row inside its rollback transaction. No production implementation changed. A separate audit-helper error correctly hit the existing reference-policy guard when a fresh adapter tried to consume another instance's snapshot; reusing the observing adapter fixed the helper.
- `source-boundaries.json`: 36 qualified/current file comparisons and exact historical source commits for the differences. This report alone does not assert changed code is covered.
- `coverage.json`: verifies current executable inventory against checkout hashes and binds the retained evidence to it. It maps all 11 JOB/EVT/SVC acceptance IDs and explicitly leaves SVC-02 UI open.
- `retirement.json`: the exact two native test containers and two receipt-bound read-only observers were archived and removed. No images or volumes were created. Active and checkpoint roles remain.

## Coverage decisions

| Difference from earlier evidence | Current coverage |
| --- | --- |
| Native core manifest12→17 | Only numeric version changed; actual installed core17 passes the 12 native cases. Native claim/runner/durable/Notes job implementation bytes remain exact. |
| External metadata projection | Later SVC-05 qualification binds the exact current projection/metadata/planning source to real upgrade, fresh restore, independent revocation, new review/resume and ordinary remote result. |
| Native external bridge snapshot/finalization | Six executable authority/connector files are byte-identical to the real installed post-computation eight-case matrix. Committed role and revision races remain separate evidence. This is not a claim that all eight controls were committed lifecycle transitions. |
| Private changed-worker-image `_reference` profile | All other JOB-03 lifecycle definitions are unchanged. The only changed definition adds the explicit reviewed transition. Later current-source SVC-05 proof covers that transition and an actual installed strict-default unknown-effect refusal. The real non-idempotent commit/SIGKILL/lease/nonretry proof remains the original JOB-03 fixture. |
| Recovery transition adapter | Exact current source is bound by later actual different-image commit fault, fresh restore, stale resume refusal and new success path. No arbitrary external rollback claim. |
| Event delivery, authority, native consumer and host integration | Fourteen relevant event/identity/consumer/producer/host files remain byte-identical to the qualified native and actual deployed-host event proof. Their existing test scope is retained. |

## Remaining required work

1. Execute the minimal analysis action in an actual browser: correct saved-revision result, timeout/unavailability while Notes stays usable, and scope/navigation retirement. This completes the remaining proof for SVC-02 and sections 22.4/22.5; source mocks and compiled-asset HTTP checks do not suffice.
2. Review that UI proof together with this backend coverage and current pins, then produce the G6 gate result.
3. After G6 passes, complete the separate G7 release requirements, including ID-03, UI-09, fresh-install/runbooks/provenance and performance.

No new record screen, Canvas feature, generic subsystem or wholesale frontend rewrite is required. Native list/form remains the CRUD default. Browser work was deferred by the user while backend work continued. An availability check found installed Edge and Node24's built-in WebSocket; an isolated, project-owned headless test profile can be investigated without controlling the personal browser session or installing global packages.
