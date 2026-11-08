# Local application pilot

AP-01 pilot `ap01-pilot-01` uses unchanged foundation49 and independently upgraded Tasks0.2.3 with fictional
users/data. It is an intentionally retained development site, distinct from the
retired AT qualification fixtures. [Current checklist](implementation-status.md)
and [limitations](application-adoption-limitations.md) track what has been tested.
Agent walkthroughs do not imply human usability acceptance.

## Access and ownership

- URL: `http://release-261d5d0954ee.localhost:18172/odoo` (loopback only).
- Docker project: `mp-r0-r1release261d5d0954ee` (historical bootstrap prefix).
- Private root: `.local/application-adoption/ap01-pilot-01`.
- Fictional logins/IDs: `fixtures.json`; generated passwords:
  `account-passwords.json` in that private root. Never commit or publish them.
- Current image/database/worker ID: `operator/target.json`; use this current
  configuration after an upgrade, not a remembered bootstrap container name.
- Six named volumes and two networks are listed in `pilot-intent.json` and
  `state.json`. They belong to this pilot only. Its database is synthetic.
- Reviewed workers: one urgent lane and one bulk lane, each bounded to one CPU/
  768MiB; producer disabled. Web and worker roles use the exact selected image.

Keep the pilot for development/review until it is explicitly superseded or
retired. One-shot bootstrap/read helpers remove themselves after private logs
are saved. Fault/recovery siblings must use different owned resources and are
retired after proof. Do not delete unrelated stopped Docker assets by prefix.

## Inspect without changing state

From the project checkout, use the isolated interpreter and independent control:

```powershell
$apPython = '.local/toolchain/operator-python16/Scripts/python.exe'
$apPilotRoot = '.local/application-adoption/ap01-pilot-01'
& $apPython -I tools/modular.py --config "$apPilotRoot/operator/trust.json" jobs --store "$apPilotRoot/operator/control" --deployment-config "$apPilotRoot/operator/target.json" status
& $apPython -I tools/modular.py --config "$apPilotRoot/operator/trust.json" jobs --store "$apPilotRoot/operator/control" --deployment-config "$apPilotRoot/operator/target.json" metrics
```

`pilot-ready.json` records initial installation and pins. The current independent
journal/target remains authoritative after later lifecycle operations. A prepared
plan or running service is not itself evidence of completed business effects.

## Stop and start the same release

For a planned stop, use `jobs ... drain` with the same store/config arguments.
Wait for the stopped/paused result and all lanes to stop. Drain pauses dispatch;
it is a maintenance action, not an ordinary empty queue. Business changes that
need to enqueue work may be refused while dispatch is paused.

Read `operator/target.json` and verify its project/deployment against
`pilot-intent.json`. Stop that project's edge, the exact current `worker_id`,
then its database container. Keep named volumes. Do not run `compose down -v`,
reset a database or restart an uncertain failed lifecycle operation.

To restart an unchanged release, start the same database and wait for
`pg_isready`, start the exact current worker and wait for readiness, then start
the project's edge. Use `jobs ... profile-review --urgent-lanes 1 --bulk-lanes 1
--producer-lanes 0 --shutdown-seconds 5`; review the returned exact pins/resource
approval, then `jobs ... profile-apply <approval-id>`. New pins or a different
resource request require a fresh independent review. Do not reuse consumed
approvals or silently substitute a deployment image.

An unexpected worker outage differs from maintenance drain: dispatch can remain
enabled and valid work may queue until the pinned lane returns. AP-C separately
exercises that path and records actual delivery; no latency guarantee is implied
while workers are stopped.

## Daily walkthrough (AP-B/C)

Use native menus/list/forms. As Alice, create a shared list, configure membership,
create/assign a task and set a due time/reminder. As member and external assignee,
exercise allowed work without acquiring extra list rights; check an outsider's
direct access denial. Complete/reopen, change assignee or reminder and inspect
the current recipient's inbox. Save read state and reload; opening a historical
notice must recheck task access. Keep real record IDs and evidence in private
walkthrough receipts, not a fabricated success checkbox.

Record date/time and permissions as observed. Test concurrent edits and actual
worker interruption rather than assuming the framework protects every workflow.
The limitations register distinguishes defects, supported boundaries, future
features and unmeasured human experience. Required corrections feed AP-02's
separately versioned application release; there is no UI/theme redesign here.

## Verified current pilot

The immutable app-only operation `50f3bf2f-0629-4d26-8c48-22e68b60711e`
updated0.2.2→0.2.3. Current imagebf39b8d8/inventoryd84289ff differs from sealed49
because the application changed;6087foundation files, policy, environment and
platform0.1.49 stayed unchanged. Read exact pins from current target.json.
Original records/file/future reminder survived. The new version repairs missing
readonly ownership defaults that blocked native new-record forms in0.2.2.

AP-B/C agent walkthrough passed: Alice created Workshop readiness/member Bob and
Confirm workshop access/assignee Operator; edited/searched/completed/reopened.
Operator saw assigned tasks, no lists, changed due time and received a private
notice; read flag persisted and Open task showed Sent. Direct owner/creator,
outsider/list/inbox denials and member reassignment passed. An unexpected urgent
lane stop accepted a queued reminder; restarting the exact lane delivered once.

Two independent sessions can overwrite the same text field without a conflict
warning; the later save wins. Disjoint dirty-field edits are retained. Avoid
simultaneous edits to the same task description when preserving both drafts is
important. This measured boundary is AP-LIM-014, not an optimistic-lock claim.
