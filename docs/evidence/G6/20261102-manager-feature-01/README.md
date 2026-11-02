# Actual core14 manager preview counterexample

The actual IAB browser loaded deployed core14/shell10. Alice was denied manager
access; native Odoo logout/login with the existing fixture operator opened the
actual manager. The rendered external0.1.1 row showed healthy independently of C
availability; native rows retained unknown liveness. No proxy, source substitution
or credential/role change was used.

After capturing17table/19job/schema/fullmodule/worker preimages and existing app
request IDs, the browser selected Document Stats0.1.1 / Feature suspension /
Owned lifecycle C and clicked Prepare plan once. The manager displayed Validation
failed. It did not display a preview, and Request operation was never clicked.

`prepare-diagnostic.json` reproduces the exact real-profile/current-metadata path
read-only: prepared_view reached the frozen validator, which raised Prepared
restart description mismatch. The planner already described host restart correctly;
the checker still duplicated the older native-only rule.

`failed-request-audit.json` proves existing HTTP rollback left no new app request,
and all17 tables and independent worker identity/publication remained exact. The
audit's first hypothesis of a persisted unrequested draft was contradicted by the
actual zero-row result; corrected audit reads that retained observation and confirms
the unchanged data/worker. No independent import/approval/apply or suspension took
place. No failed test data needs deletion.

`browser/preview-failure-core14.png` and its DOM snapshot preserve the actual UI
counterexample. `prepare-source-fix.json` proves that the corrected host source now
round-trips the same real profile through the real public preview without creating
an operation. It is source proof, not an installed runtime fix.

ADR0036 and G2revision15 introduce one shared host_restart_required rule for planner
and checker, retaining native/short legacy distinctions. Tests now cover the actual
prepared_view boundary instead of replacing it. Source qualification is in
`../20261102-manager-preview15-01/`; coherent core15 activation is required.

Do not invoke the unexecuted capture_request/approve/apply paths of this failed
core14 baseline. The private marker records runtime_preview_fix_required; the
next successful browser lifecycle must capture a fresh baseline after core15
deployment. No wholesale frontend rewrite, Canvas expansion or hot patch is needed.
