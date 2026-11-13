# ADR 0086: Independent completed-checkpoint recovery

Status: implementation under qualification, 13 November 2026. Host source and
simulated-boundary ordering tests do not establish installed recovery support.

The PP04 operator workflow must recover useful application data after a normal
completed destructive uninstall. Reinstalling code cannot recreate deleted
rows. Existing failed-operation recovery must retain its failure/status fences;
a completed operation must never be relabelled failed or have its apply replayed.

Use a new OS recovery UUID and protected append-oriented journal, bound to the
immutable original completed bundle/history, checkpoint, exact current recorded
replacement, retained image/inventory, current authority, semantic effects and
reviewed host source. Original operation records remain completed and unchanged.
The initial profile is the exact current completed native destructive uninstall,
one site, known native dispatch, no external installations, active technical
credentials, API keys, recurrence, running claims or leased deliveries. These
bounds prevent unreviewed effect reconciliation; they are not a native-code
sandbox or proof that arbitrary application code performed no outside effects.

Independently review before closing ingress, fencing dispatch and draining the
exact current worker. Bind the fence's before/after snapshots. Retain the current
database and filestore. Restore the coordinated checkpoint into a new database
and filestore namespace. Reconcile current platform membership, native login and
integration-grant authority using existing policies, then compare core semantic
effect rows before starting any restored registry. Only the fixed normal job and
outbox deployment/claim epochs are excluded from that semantic comparison;
results, attempts, payloads, receipts, consumption, subscriptions and history are
not discarded. Application business data and app-owned ACLs retain explicit
point-in-time checkpoint semantics.

Reuse shared verified restore completion and resume through private host hooks;
defaults preserve failed-operation behavior. The new workflow has separate
review actions and command intents before effects. A lost command response leaves
an uncertain pending activity, never permission to repeat it. Fresh reviewed
continuation is initially supported only after fully verified quiesce and before
any database-creation intent. It rechecks actual closed resources, current
authority/effects, absent destination, original receipts and current source, and
does not repeat fencing, dump restoration or authority overlay. Other partial
states require inspection and a separately designed reconciliation.

Restoration ends closed. A distinct current-target/authority/effects/source-bound
resume review is required. Record the conservative resume fence before enabling
dispatch or ingress. Forward operations on overlapping deployment/sites remain
blocked by the separate recovery journal until a verified resume completes;
ordinary apply cannot substitute for it. Missing/uncertain journal evidence
fails closed. Historical operation/status reads remain available for diagnosis.

No public wire schema, browser approval authority, app-selected SQL/code callback,
historical kit rewrite or arbitrary older-checkpoint promise is introduced.
Runtime and host source identities remain separate; packaging changed SDK bytes
requires a legitimate new candidate identity and immutable build. Actual completed
uninstall, meaningful bytes/data/current revocation, controlled precreation stop,
fresh continuation, closed restore, separate resume and usable recovered UI must
pass before this capability is accepted for the declared cohort.
