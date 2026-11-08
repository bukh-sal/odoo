# Tasks release qualification after AT-03

Prerequisite: [AT-03 actual-image decision](../docs/evidence/post-r1/aurora-tasks/at03-decision.json),
core48/App0.2.2. All adoption/qualification work below is complete on final core49;
the [authoritative checklist](../docs/implementation-status.md) records14/14checks
and100verifiedpoints. [Final delivery](../docs/evidence/post-r1/aurora-tasks/final-delivery.json).
[ADR0077](../docs/architecture-decisions/0077-native-tasks-adoption-47-49.md)
defines the qualified closed transition. No active work item.

- [x] AT-04a: schema/fixtures/negative tests for the specific47→49 recipe; preserve
  ordinary core/install guards and46→47. Freeze and independently reconstruct before
  any mutation. No acceptance credit for source-only work.
- [x] AT-04b / AT-J: build exact49; fresh populated47 Tasks and Maintenance sites;
  independent approvals, preserved old rows/roles/files, reminders initially off.
- [x] AT-04c / AT-K: closed failure, fresh47 checkpoint restore, independent reviewed
  resume; useful Maintenance work during outage and recovered Tasks workflow.
- [x] AT-04d / AT-I,AT-L: clean final install, real native job carry-forward across
  publication, workload and native in-app browser on final artifact. Preliminary
  core48 browser already proves assignee completion/reopen and saved reminder read
  state; it does not close these final-artifact checks.
- [x] AT-05 / AT-M: affected host/native regressions, exact reproduction and privacy.
- [x] AT-05 / AT-N: checksummed developer/operator release instructions, final audit,
  selected obsolete containers/volumes/networks/images retired. Preserve sealed kits.

Data witnesses use original columns for task tables because the update adds reminder
fields. Old stage rows remain exact; only declared missing stage choices may be new.
No full Aurora import/port, standalone tasks, custom UI, Canvas product expansion,
broker/autoscaling, public release or production deployment is included.
