# Actual installed native feature lifecycle

F-01d prerequisite G6-QUEUED-NATIVE-FEATURE-01; spec §§9.1, 10.2-10.5, 13, 25;
ADR0034. Uses installed core/SDK.13. No source or handler substitution.

Two exact independently reconstructed/reviewed/approved operations completed:

| Action | Operation | Dispatch |
| --- | --- | --- |
| Suspend Notes-C | f2311728-b243-4547-be0a-50c5e9a6197e | 46→47→48→49 |
| Enable Notes-C | 68e5366a-74e9-4258-a0ef-1cdb4ad11dbe | 49→50→51→52 |

Each uses the new full NativeFeatureExecutor lifecycle with real ingress/dispatch
fences, stopped worker, PostgreSQL+filestore checkpoint, fixed atomic feature
child, replacement/readiness/profile publication, job reconciliation and durable
traffic fence before queue enable. The release and configuration generation11
remain unchanged; core/plugin code remains installed. No native install/unload/
migration command runs. Exact operation receipts and audits are verified.

Actual installed native probes show Notes-C record access denied while suspended
and restored after enable; A/B remain available throughout with native list/form
view compilation. Probes use original human UID6 with freshly resolved workspace
scope and call installed native methods, then roll back. This is not a new browser
rendering/accessibility audit. Standard record screens continue using native views.

For each operation17table comparison proves all business data, plugin installation,
bindings/grants/service credentials, human authority and event history exact.
Only the target feature availability/write timestamp and C workspace policy+1
change, plus exact job claim/dispatch epoch updates from current reauthorization
(2terminal rows during suspension,17during enable). No input/actor/outcome/attempt/
deadline or other job field changes. All18original jobs remain terminal. All46
checkpoint files remain byte-identical. Target feature/audit and policy changes
are individually checked; no blanket timestamp exclusions.

After re-enable, a new owned `inspect_revision` job ran once through the normal
WorkerOperator CLI as its original actor. It completed at attempt1 with no business
change. All old job/event/authority/business rows remain exact; only this new job
was added (19total:7completed/10dead_letter/2cancelled). The authority volume remains
the current revokedgen2 projection, mounted only into the normal job process.
That process automatically removed itself. The installed operator/runner bridge
source guards pass without substitution. This is a current normal caller-path
check, not a repetition of unchanged death/reclaim experiments.

20completed owned helpers and the two replaced app containers were archived
privately and removed after qualification. Current app/database/edge, volumes and
current/recovery images remain. No new image or volume, no global prune. Frozen
94files/eight rows remain unchanged and passing.

Limits: these two feature operations carry terminal queue history. Fresh pending/
in-flight feature races are not directly exercised here; unchanged native dispatch/
job authority guards retain their linked earlier evidence. Actual remote/provider
revocation and uncertain-effect cases still belong to required F-01c/d/e2/f and G7.
No external metadata/provider/connector is installed and no SVC acceptance is
awarded by this native checkpoint.

Next return to F-01d: curate the metadata-only artifact, provision/attest/approve
the actual canonical provider scope and separately operated worker, then register
through the normal exact reviewed lifecycle. Installer/runtime actions must stay
separate. Connector, remote/degraded behavior, changed-image transition and external
recovery remain required; Canvas remains minimal.
