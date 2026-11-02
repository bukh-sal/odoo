# Minimal Notes analysis action

Owns F-01c, specification sections 22.4/22.5 and the remaining UI part of SVC-02. It does not reopen the qualified SVC-05 worker transition/recovery work.

- `source-checks.json`: 17 Node checks, 97 frozen files/eight rows, four reproducible valid archives and composition. Source checks do not establish browser behavior.
- `package-curation.json`: NotesStats 0.1.1 archive, fixture trust9→10; existing data/release/worker unchanged.
- `compiler-inspection.json`, `candidate-admission.json`: only the NotesStats addon/archive changes. Compiler rebuilt psycopg2/python-ldap binaries; derived runtime retains the actual deployed OS/Python and all other plugin/core/SDK/shell bytes.
- `compiler-retirement.json`: unused compiler image and temporary aliases retired. Current/checkpoint base and admitted candidate retained.
- `staged-image.json`, `http-preview.json`, `http-request.json`, `manager-bundle.json`, `independent-review.json`: ordinary staged native upgrade, application request and separate executor review. No new grants.
- `completed.json`, `preservation.json`, `entrypoints.json` are produced only by their respective successful steps. Check the status ledger and private marker before continuing; never infer success from this list.

## Required before G6 exit

| Remaining work | Specification / acceptance | Evidence needed |
| --- | --- | --- |
| Install the exact NotesStats successor and verify preservation | §§10/12/19/22.4; retained lifecycle/release guarantees | Normal approved native upgrade; terminal old jobs/Notes/history/schema/files/worker authority retained; installed slot and compiled native bundle |
| Execute analysis and demonstrate degraded behavior in the actual UI | §§14/22.4/22.5; SVC-02, applicable UI lifecycle checks | Healthy saved-revision result; unavailable/timeout behavior keeps Notes usable; navigation/scope retirement prevents late results; native record screens remain usable. Actual browser execution is required. |
| Final current-profile G6 integration/evidence audit | §23 acceptance matrix; §25 Phase F; JOB-01..03, EVT-01..03, SVC-01..05 | Reconcile current installed hashes and retained qualified profiles, run only necessary changed-path regressions, resolve gaps, then write gate-G6 result. Do not blindly repeat completed crash/restore transitions. |

Browser work is deferred at the user's request while backend checks continue. SVC-02 stays `not_run` until its required proof is complete. G7 remains separate: ID-03 path audit, UI-09/accessibility/RTL, performance, fresh install/recovery/runbooks/provenance and the complete R1 release evidence.

## Optional improvements, outside the gate

A dedicated result page, richer charts, a new dialog, Canvas polish, extra commands, or a WebClient rewrite are unnecessary. The reference action uses the existing slot, scoped services, locale and Odoo notification adapter. Standard CRUD remains native Odoo list/form; Canvas keeps its minimal custom-page capability.
