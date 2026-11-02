# G6 actual browser qualification and gate exit

G6 passed at native configuration24 / dispatch117. The final audit is `gate-G6.json`; SVC-02 UI evidence is `qualification.json`. Backend source/acceptance bindings remain in `../20261102-current-backend-audit-01/coverage.json`.

These tests used the installed Windows Edge in headless mode, a separate protected project-owned profile for each run, and Node24's built-in WebSocket/CDP client. They controlled no personal browser window/profile, installed no global packages and created no Docker images or volumes. Each owned browser exited0; OS inspection found none of its five recorded PIDs running.

The test scripts authenticate the fixture Alice, navigate the real installed application, click native Odoo list rows and the real detail-action button, observe DOM/notifications, and capture screenshots. They replace no application function and fabricate no service result. Separate operator commands execute the ordinary guarded native runner and pause/kill/resume only the exact approved disposable worker06 container.

| Required behavior | Evidence |
| --- | --- |
| Actual native Notes list/form and saved revision result | `initial-native-list.png`, `healthy-native-form.png`, `healthy-result.json`: revision2,50characters/7words/1line through the existing Odoo notification service |
| Navigation retires callbacks | `navigation-job.json`, `navigation-clean.png`: real job completes after navigation to Settings; no late result, queued or error notice appears there |
| Timeout degrades analysis while native Notes stays usable | `outage-job.json`, `timeout-UI.json`, `outage-degraded.png`, `outage-native-list.png`: actual paused worker, one terminal DEADLINE_EXCEEDED attempt, real warning and usable native list |
| Recovery requires explicit new action and returns correct result | `recovery-job.json`, `recovered-result.png`: same worker unpaused/current authority retained; explicit new job completes once and renders revision1,0/0/0 statistics for the empty Note |
| Crash also degrades safely | `crash-05-job.json`, `crash-UI.json`, `crash-degraded.png`: actual SIGKILL137, one terminal DEPENDENCY_UNAVAILABLE attempt, real warning and usable native Notes |
| Same-image restart and new result | `recovery-05-job.json`, `crash-recovered-result.png`: same container/image/public config9/key19/publication11, healthy after explicit restart; new job renders revision2,36characters/5words/1line |
| Preservation | `qualification.json`: original30job outcomes and every row of the other16 tracked tables exact; all30Notes unchanged. Six explicit new terminal UI-test jobs, including the diagnosed wrong-fixture request; final36jobs (15completed/19dead-letter/2cancelled) |
| Cleanup | `cleanup.json`: exact terminal observer removed; no live owned browser PIDs; current host/worker/DB/checkpoint roles preserved. Five protected browser profiles retained after automatic deletion-policy rejection. |

The original `healthy.mjs` intentionally remains the failed-attempt source: it selected the wrong title, queued a genuine job and timed out waiting for a cached result. The baseline established the correct immutable ID/title. `healthy_corrected.mjs` passed; the original extra pending request expired and was terminalized once with zero attempts/no remote effect. The timeout recovery also demonstrated the existing readiness guard: immediate post-unpause observation refused a not-yet-healthy heartbeat; a fresh healthy attestation succeeded without another unpause. `attempts.json` records both facts.

The recorded commands were `node probe.mjs`, `node healthy.mjs`, the ordinary guarded `run-job-once`, `node healthy_corrected.mjs`, then `lifecycle.py prepare`, `node lifecycle.mjs`, and its `navigation/outage/unpause/attest/recovery` steps. Crash proof used `crash_driver.py prepare`, `node crash.mjs`, and its `crash/start/recovery` steps. `qualify.py` and `gate.py` closed preservation/current-source/evidence/cleanup checks. Each script is under this directory. These are completed, phase-guarded fixture operations: do not replay them on the finished fixture or infer that an earlier timeout makes a new mutation safe.

## Gate decision and remaining scope

All11 G6-owned JOB/EVT/SVC acceptance checks pass for their stated trusted R1 profiles. Native CRUD remains native Odoo; only the minimal existing-slot NotesStats action was added. Canvas and the custom-page capability remain unchanged.

G7 is still required: ID-03 native path audit, UI-09 keyboard/contrast/zoom/RTL, performance targets, current full acceptance review, fresh install/recovery/runbooks, security/dependency/license/network/provenance and final release inventory/handoff. The UI screenshots here do not pass accessibility or the complete R1 definition of done. Additional Canvas features, UI polish, dialogs, record screens or a WebClient rewrite are optional and unnecessary for this gate.
